from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from people.models import Department, Role, Employee
from evaluations.models import (
    EvaluationCycle,
    QuantitativeGoal,
    QualitativeIndicatorAssessment,
    BehaviorRating,
    EmployeeCycleScore,
    TalentMapSettings,
    QualitativeAxisMethod,
)
from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from evaluations.services.scoring import (
    competency_qualitative_label,
    compute_quantitative_score,
    compute_qualitative_score,
    recompute_cycle_scores,
)


class ScoringTests(TestCase):
    def setUp(self):
        self.dep = Department.objects.create(name="Tech")
        self.role = Role.objects.create(name="Dev Jr", department=self.dep)

        self.mgr_user = User.objects.create_user(username="mgr", password="pass")
        self.emp_user = User.objects.create_user(username="emp", password="pass")

        self.mgr = Employee.objects.create(user=self.mgr_user, department=self.dep, role=self.role)
        self.emp = Employee.objects.create(user=self.emp_user, department=self.dep, role=self.role, manager=self.mgr)

        self.cycle = EvaluationCycle.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))

    def test_quantitative_goals_score(self):
        QuantitativeGoal.objects.create(
            employee=self.emp, cycle=self.cycle, title="A", description="",
            weight_percent=Decimal("50"), completion_percent=Decimal("100"),
            created_by=self.mgr_user
        )
        QuantitativeGoal.objects.create(
            employee=self.emp, cycle=self.cycle, title="B", description="",
            weight_percent=Decimal("50"), completion_percent=Decimal("0"),
            created_by=self.mgr_user
        )
        score = compute_quantitative_score(self.emp, self.cycle)
        self.assertEqual(score, Decimal("50"))

    def test_qualitative_competency_levels_score(self):
        comp = Competency.objects.create(name="Comunicación", description="")
        l1 = CompetencyLevel.objects.create(competency=comp, level=1, title="Base")
        l2 = CompetencyLevel.objects.create(competency=comp, level=2, title="Avanzado")

        i1 = LevelIndicator.objects.create(level=l1, text="Escucha")
        i2 = LevelIndicator.objects.create(level=l1, text="Claridad")
        i3 = LevelIndicator.objects.create(level=l2, text="Feedback")

        RoleCompetencyRequirement.objects.create(role=self.role, competency=comp, required_level=2, weight=Decimal("1"))

        # Nivel 1 completado (>=3), nivel 2 no
        for ind in [i1, i2]:
            QualitativeIndicatorAssessment.objects.create(
                employee=self.emp, cycle=self.cycle, indicator=ind,
                rating=BehaviorRating.OFTEN, assessed_by=self.mgr_user
            )
        QualitativeIndicatorAssessment.objects.create(
            employee=self.emp, cycle=self.cycle, indicator=i3,
            rating=BehaviorRating.RARELY, assessed_by=self.mgr_user
        )

        score = compute_qualitative_score(self.emp, self.cycle)
        self.assertEqual(score.quantize(Decimal("0.01")), Decimal("50.00"))  # achieved 1 / required 2

        # Completa nivel 2
        a = QualitativeIndicatorAssessment.objects.get(employee=self.emp, cycle=self.cycle, indicator=i3)
        a.rating = BehaviorRating.ALWAYS
        a.save()

        score2 = compute_qualitative_score(self.emp, self.cycle)
        self.assertEqual(score2.quantize(Decimal("0.01")), Decimal("100.00"))

    def test_qualitative_tercile_by_profile_rules(self):
        # 4 competencias requeridas en nivel 1
        reqs = []
        indicators = []
        for i in range(1, 5):
            comp = Competency.objects.create(name=f"C{i}", description="")
            l1 = CompetencyLevel.objects.create(competency=comp, level=1, title="L1")
            l2 = CompetencyLevel.objects.create(competency=comp, level=2, title="L2")
            indicators.append((LevelIndicator.objects.create(level=l1, text=f"c{i}-l1"), LevelIndicator.objects.create(level=l2, text=f"c{i}-l2")))
            reqs.append(RoleCompetencyRequirement.objects.create(role=self.role, competency=comp, required_level=1, weight=Decimal("1")))

        # Empleado top: 0 por debajo y >=1 por encima
        top_user = User.objects.create_user(username="top", password="pass")
        top_emp = Employee.objects.create(user=top_user, department=self.dep, role=self.role, manager=self.mgr)
        for l1_ind, l2_ind in indicators:
            QualitativeIndicatorAssessment.objects.create(employee=top_emp, cycle=self.cycle, indicator=l1_ind, rating=4, assessed_by=self.mgr_user)
        QualitativeIndicatorAssessment.objects.create(employee=top_emp, cycle=self.cycle, indicator=indicators[0][1], rating=4, assessed_by=self.mgr_user)

        # Empleado medio: 1 arriba y 1 abajo => delta 0
        mid_user = User.objects.create_user(username="mid", password="pass")
        mid_emp = Employee.objects.create(user=mid_user, department=self.dep, role=self.role, manager=self.mgr)
        # cumple 3 l1, falla 1 l1 -> 1 por debajo
        for idx, (l1_ind, l2_ind) in enumerate(indicators):
            rating = 4 if idx < 3 else 2
            QualitativeIndicatorAssessment.objects.create(employee=mid_emp, cycle=self.cycle, indicator=l1_ind, rating=rating, assessed_by=self.mgr_user)
        # una por encima
        QualitativeIndicatorAssessment.objects.create(employee=mid_emp, cycle=self.cycle, indicator=indicators[0][1], rating=4, assessed_by=self.mgr_user)

        # Empleado bajo: delta negativo
        low_user = User.objects.create_user(username="low", password="pass")
        low_emp = Employee.objects.create(user=low_user, department=self.dep, role=self.role, manager=self.mgr)
        for idx, (l1_ind, _) in enumerate(indicators):
            rating = 4 if idx == 0 else 1
            QualitativeIndicatorAssessment.objects.create(employee=low_emp, cycle=self.cycle, indicator=l1_ind, rating=rating, assessed_by=self.mgr_user)

        cfg = TalentMapSettings.get_solo()
        cfg.qualitative_axis_method = QualitativeAxisMethod.THIRDS
        cfg.top_min_above = 1
        cfg.middle_max_below = 3
        cfg.save()

        recompute_cycle_scores(self.cycle, Employee.objects.filter(id__in=[top_emp.id, mid_emp.id, low_emp.id]))

        self.assertEqual(EmployeeCycleScore.objects.get(employee=top_emp, cycle=self.cycle).qual_tercile, 3)
        self.assertEqual(EmployeeCycleScore.objects.get(employee=mid_emp, cycle=self.cycle).qual_tercile, 2)
        self.assertEqual(EmployeeCycleScore.objects.get(employee=low_emp, cycle=self.cycle).qual_tercile, 1)

    def test_qualitative_tercile_by_gaussian(self):
        e1 = self.emp
        e2_user = User.objects.create_user(username="e2", password="pass")
        e3_user = User.objects.create_user(username="e3", password="pass")
        e2 = Employee.objects.create(user=e2_user, department=self.dep, role=self.role, manager=self.mgr)
        e3 = Employee.objects.create(user=e3_user, department=self.dep, role=self.role, manager=self.mgr)

        cfg = TalentMapSettings.get_solo()
        cfg.qualitative_axis_method = QualitativeAxisMethod.GAUSSIAN
        cfg.save()

        EmployeeCycleScore.objects.update_or_create(employee=e1, cycle=self.cycle, defaults={"qualitative_score": Decimal("10"), "quantitative_score": Decimal("10")})
        EmployeeCycleScore.objects.update_or_create(employee=e2, cycle=self.cycle, defaults={"qualitative_score": Decimal("50"), "quantitative_score": Decimal("50")})
        EmployeeCycleScore.objects.update_or_create(employee=e3, cycle=self.cycle, defaults={"qualitative_score": Decimal("90"), "quantitative_score": Decimal("90")})

        # recompute usa scores reales, montamos una comp simple para mantener consistencia y actualizar terciles
        comp = Competency.objects.create(name="GaussComp", description="")
        lvl = CompetencyLevel.objects.create(competency=comp, level=1, title="L1")
        ind = LevelIndicator.objects.create(level=lvl, text="i")
        RoleCompetencyRequirement.objects.create(role=self.role, competency=comp, required_level=1, weight=Decimal("1"))
        QualitativeIndicatorAssessment.objects.create(employee=e1, cycle=self.cycle, indicator=ind, rating=1, assessed_by=self.mgr_user)
        QualitativeIndicatorAssessment.objects.create(employee=e2, cycle=self.cycle, indicator=ind, rating=3, assessed_by=self.mgr_user)
        QualitativeIndicatorAssessment.objects.create(employee=e3, cycle=self.cycle, indicator=ind, rating=4, assessed_by=self.mgr_user)

        recompute_cycle_scores(self.cycle, Employee.objects.filter(id__in=[e1.id, e2.id, e3.id]))
        self.assertEqual(EmployeeCycleScore.objects.get(employee=e1, cycle=self.cycle).qual_tercile, 1)
        self.assertEqual(EmployeeCycleScore.objects.get(employee=e2, cycle=self.cycle).qual_tercile, 3)
        self.assertEqual(EmployeeCycleScore.objects.get(employee=e3, cycle=self.cycle).qual_tercile, 3)

    def test_level_3_requires_siempre(self):
        comp = Competency.objects.create(name="Pensamiento", description="")
        l1 = CompetencyLevel.objects.create(competency=comp, level=1, title="L1")
        l2 = CompetencyLevel.objects.create(competency=comp, level=2, title="L2")
        l3 = CompetencyLevel.objects.create(competency=comp, level=3, title="L3")
        i1 = LevelIndicator.objects.create(level=l1, text="i1")
        i2 = LevelIndicator.objects.create(level=l2, text="i2")
        i3 = LevelIndicator.objects.create(level=l3, text="i3")
        RoleCompetencyRequirement.objects.create(role=self.role, competency=comp, required_level=3, weight=Decimal("1"))

        QualitativeIndicatorAssessment.objects.create(employee=self.emp, cycle=self.cycle, indicator=i1, rating=4, assessed_by=self.mgr_user)
        QualitativeIndicatorAssessment.objects.create(employee=self.emp, cycle=self.cycle, indicator=i2, rating=4, assessed_by=self.mgr_user)
        QualitativeIndicatorAssessment.objects.create(employee=self.emp, cycle=self.cycle, indicator=i3, rating=3, assessed_by=self.mgr_user)
        score = compute_qualitative_score(self.emp, self.cycle)
        self.assertEqual(score.quantize(Decimal("0.01")), Decimal("66.67"))

        a = QualitativeIndicatorAssessment.objects.get(employee=self.emp, cycle=self.cycle, indicator=i3)
        a.rating = 4
        a.save()
        score2 = compute_qualitative_score(self.emp, self.cycle)
        self.assertEqual(score2.quantize(Decimal("0.01")), Decimal("100.00"))

    def test_competency_labels(self):
        self.assertEqual(competency_qualitative_label(0, 0, False), "Elemental")
        self.assertEqual(competency_qualitative_label(1, 0, False), "Básico")
        self.assertEqual(competency_qualitative_label(2, 0, False), "Avanzado")
        self.assertEqual(competency_qualitative_label(2, 1, False), "Avanzado experto")
        self.assertEqual(competency_qualitative_label(3, 2, True), "Experto")
