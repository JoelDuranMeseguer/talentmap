from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from evaluations.forms import GoalFormSet
from evaluations.models import EmployeeCycleScore, EvaluationCycle, QualitativeIndicatorAssessment
from evaluations.services.scoring import BOXES, recompute_cycle_scores
from people.models import Department, Employee, Role


class CoreWorkflowTests(TestCase):
    def setUp(self):
        self.dep = Department.objects.create(name="Tech")
        self.role = Role.objects.create(name="Developer", department=self.dep)

        self.hr = User.objects.create_superuser("hr", "hr@example.com", "pass")
        self.manager_user = User.objects.create_user("manager", password="pass")
        self.report_user = User.objects.create_user("report", password="pass")
        self.other_user = User.objects.create_user("other", password="pass")

        self.manager = Employee.objects.create(user=self.manager_user, department=self.dep, role=self.role)
        self.report = Employee.objects.create(user=self.report_user, department=self.dep, role=self.role, manager=self.manager)
        self.other = Employee.objects.create(user=self.other_user, department=self.dep, role=self.role)

        self.cycle = EvaluationCycle.objects.create(name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))

    def test_goal_weights_must_sum_100(self):
        formset = GoalFormSet(
            data={
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "0",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-title": "G1",
                "form-0-description": "",
                "form-0-weight_percent": "60",
                "form-0-completion_percent": "50",
                "form-1-title": "G2",
                "form-1-description": "",
                "form-1-weight_percent": "30",
                "form-1-completion_percent": "90",
            },
            queryset=self.report.quant_goals.none(),
        )
        self.assertFalse(formset.is_valid())
        self.assertIn("100%", str(formset.non_form_errors()))

    def test_manager_can_edit_only_direct_report(self):
        self.client.login(username="manager", password="pass")

        allowed = self.client.get(reverse("edit_quantitative", args=[self.report.id]))
        denied = self.client.get(reverse("edit_quantitative", args=[self.other.id]))

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied.status_code, 403)

    def test_nine_box_recompute_assigns_box(self):
        comp = Competency.objects.create(name="Communication")
        lvl = CompetencyLevel.objects.create(competency=comp, level=1, title="L1")
        ind = LevelIndicator.objects.create(level=lvl, text="Listens")
        RoleCompetencyRequirement.objects.create(role=self.role, competency=comp, required_level=1, weight=Decimal("1"))

        QualitativeIndicatorAssessment.objects.create(
            employee=self.report,
            cycle=self.cycle,
            indicator=ind,
            rating=4,
            assessed_by=self.manager_user,
        )

        recompute_cycle_scores(self.cycle, Employee.objects.filter(id=self.report.id))
        score = EmployeeCycleScore.objects.get(employee=self.report, cycle=self.cycle)

        self.assertIn((score.qual_tercile, score.quant_tercile), BOXES)
        self.assertTrue(score.box_code)
