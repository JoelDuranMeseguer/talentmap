from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from evaluations.models import EvaluationCycle, QualitativeIndicatorAssessment
from evaluations.services.scoring import compute_qualitative_score
from people.models import Department, Employee, Role


class SelfAssessmentTests(TestCase):
    def setUp(self):
        dept = Department.objects.create(name="IT")
        role = Role.objects.create(name="Dev", department=dept)

        manager_user = User.objects.create_user(username="mgr", password="x")
        self.manager_emp = Employee.objects.create(user=manager_user, department=dept, role=role, active=True)

        employee_user = User.objects.create_user(username="emp", password="x")
        self.employee_emp = Employee.objects.create(
            user=employee_user,
            department=dept,
            role=role,
            manager=self.manager_emp,
            active=True,
        )

        self.cycle = EvaluationCycle.objects.create(name="2026", start_date="2026-01-01", end_date="2026-12-31")
        self.comp = Competency.objects.create(name="Comunicación", description="")
        level = CompetencyLevel.objects.create(competency=self.comp, level=1, title="L1")
        self.ind = LevelIndicator.objects.create(level=level, text="Escucha activa")
        RoleCompetencyRequirement.objects.create(role=role, competency=self.comp, required_level=1, weight=1)

    def test_self_assessment_not_used_for_qualitative_score(self):
        QualitativeIndicatorAssessment.objects.create(
            employee=self.employee_emp,
            cycle=self.cycle,
            indicator=self.ind,
            rating=4,
            assessment_type=QualitativeIndicatorAssessment.AssessmentType.SELF,
            assessed_by=self.employee_emp.user,
        )

        score = compute_qualitative_score(self.employee_emp, self.cycle)
        self.assertEqual(score, Decimal("0"))

    def test_employee_can_submit_self_assessment(self):
        self.client.login(username="emp", password="x")
        url = reverse("self_edit_qualitative", args=[self.comp.id])

        resp = self.client.post(url, data={f"ind_{self.ind.id}": "4"}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            QualitativeIndicatorAssessment.objects.filter(
                employee=self.employee_emp,
                cycle=self.cycle,
                indicator=self.ind,
                assessment_type=QualitativeIndicatorAssessment.AssessmentType.SELF,
            ).exists()
        )
