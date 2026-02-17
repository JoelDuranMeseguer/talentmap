from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from people.models import Department, Role, Employee
from evaluations.models import EvaluationCycle, QuantitativeGoal, QualitativeIndicatorAssessment, BehaviorRating
from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from evaluations.services.scoring import compute_quantitative_score, compute_qualitative_score


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
