from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from evaluations.models import EvaluationCycle, QualitativeIndicatorAssessment
from people.models import Department, Role, Employee


class TestQualitativeLocking(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(username="hr", password="x")
        self.hr.is_superuser = True
        self.hr.save()

        dept = Department.objects.create(name="D1")
        role = Role.objects.create(name="R1", department=dept)

        u = User.objects.create_user(username="e1", password="x")
        self.emp = Employee.objects.create(user=u, department=dept, role=role, active=True)

        self.cycle = EvaluationCycle.objects.create(name="C1", start_date="2026-01-01", end_date="2026-12-31")

        self.comp = Competency.objects.create(name="C", description="")
        l1 = CompetencyLevel.objects.create(competency=self.comp, level=1, title="")
        l2 = CompetencyLevel.objects.create(competency=self.comp, level=2, title="")

        self.i1 = LevelIndicator.objects.create(level=l1, text="b1")
        self.i2 = LevelIndicator.objects.create(level=l2, text="b2")

        RoleCompetencyRequirement.objects.create(role=role, competency=self.comp, required_level=2, weight=1)

    def test_locked_level_is_not_saved(self):
        self.client.login(username="hr", password="x")
        url = reverse("edit_qualitative", args=[self.emp.id, self.comp.id])

        # Nivel 1 aún no completado -> nivel 2 bloqueado.
        resp = self.client.post(url, data={f"ind_{self.i1.id}": "3", f"ind_{self.i2.id}": "4"})
        self.assertEqual(resp.status_code, 302)

        # Debe haberse guardado solo nivel 1
        self.assertTrue(
            QualitativeIndicatorAssessment.objects.filter(employee=self.emp, cycle=self.cycle, indicator=self.i1).exists()
        )
        self.assertFalse(
            QualitativeIndicatorAssessment.objects.filter(employee=self.emp, cycle=self.cycle, indicator=self.i2).exists()
        )

    def test_after_unlock_level_2_can_be_saved(self):
        self.client.login(username="hr", password="x")
        url = reverse("edit_qualitative", args=[self.emp.id, self.comp.id])

        # 1) Completa nivel 1
        self.client.post(url, data={f"ind_{self.i1.id}": "3"})

        # 2) Ahora nivel 2 debería poder guardarse
        self.client.post(url, data={f"ind_{self.i1.id}": "3", f"ind_{self.i2.id}": "4"})
        self.assertTrue(
            QualitativeIndicatorAssessment.objects.filter(employee=self.emp, cycle=self.cycle, indicator=self.i2).exists()
        )
