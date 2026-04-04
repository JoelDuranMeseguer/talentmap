from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from evaluations.models import (
    EmployeeCycleScore,
    EvaluationCycle,
    QualitativeIndicatorAssessment,
    QualitativeIndicatorSelfAssessment,
    QuantitativeGoal,
    QuantitativeGoalSelfAssessment,
)
from evaluations.services.scoring import recompute_cycle_scores
from people.models import Department, Employee, Role


class SelfAssessmentTests(TestCase):
    def setUp(self):
        self.dep = Department.objects.create(name="Ops")
        self.role = Role.objects.create(name="Ops Analyst", department=self.dep)

        self.manager_user = User.objects.create_user(username="manager", password="pass")
        self.report_user = User.objects.create_user(username="report", password="pass")

        self.manager = Employee.objects.create(user=self.manager_user, department=self.dep, role=self.role)
        self.report = Employee.objects.create(user=self.report_user, department=self.dep, role=self.role, manager=self.manager)

        self.cycle = EvaluationCycle.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))

        self.goal = QuantitativeGoal.objects.create(
            employee=self.report,
            cycle=self.cycle,
            title="Goal",
            description="",
            weight_percent=Decimal("100"),
            completion_percent=Decimal("40"),
            created_by=self.manager_user,
        )

        self.comp = Competency.objects.create(name="Colaboración")
        self.level = CompetencyLevel.objects.create(competency=self.comp, level=1, title="Básico")
        self.indicator = LevelIndicator.objects.create(level=self.level, text="Comparte información")
        RoleCompetencyRequirement.objects.create(role=self.role, competency=self.comp, required_level=1, weight=1)

    def test_self_assessment_does_not_change_official_scores(self):
        self.client.login(username="manager", password="pass")
        QualitativeIndicatorAssessment.objects.create(
            employee=self.report,
            cycle=self.cycle,
            indicator=self.indicator,
            rating=1,
            assessed_by=self.manager_user,
        )
        recompute_cycle_scores(self.cycle, Employee.objects.filter(id=self.report.id))
        before = EmployeeCycleScore.objects.get(employee=self.report, cycle=self.cycle)

        self.client.logout()
        self.client.login(username="report", password="pass")
        self.client.post(
            reverse("edit_quantitative", args=[self.report.id]),
            {f"self_goal_{self.goal.id}": "95"},
            follow=True,
        )
        self.client.post(
            reverse("edit_qualitative_competency", args=[self.report.id, self.comp.id]),
            {f"ind_{self.indicator.id}": "4"},
            follow=True,
        )

        recompute_cycle_scores(self.cycle, Employee.objects.filter(id=self.report.id))
        after = EmployeeCycleScore.objects.get(employee=self.report, cycle=self.cycle)

        self.assertEqual(before.quantitative_score, after.quantitative_score)
        self.assertEqual(before.qualitative_score, after.qualitative_score)
        self.assertTrue(QuantitativeGoalSelfAssessment.objects.filter(goal=self.goal, employee=self.report).exists())
        self.assertTrue(QualitativeIndicatorSelfAssessment.objects.filter(indicator=self.indicator, employee=self.report).exists())

    def test_manager_can_view_employee_self_assessment(self):
        QuantitativeGoalSelfAssessment.objects.create(
            employee=self.report,
            cycle=self.cycle,
            goal=self.goal,
            completion_percent=Decimal("88"),
        )
        QualitativeIndicatorSelfAssessment.objects.create(
            employee=self.report,
            cycle=self.cycle,
            indicator=self.indicator,
            rating=4,
        )

        self.client.login(username="manager", password="pass")
        quant_resp = self.client.get(reverse("edit_quantitative", args=[self.report.id]))
        qual_resp = self.client.get(reverse("edit_qualitative_competency", args=[self.report.id, self.comp.id]))

        self.assertContains(quant_resp, "88")
        self.assertContains(qual_resp, "Auto:")
        self.assertContains(qual_resp, "Siempre")
