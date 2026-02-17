from datetime import date
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from evaluations.models import EvaluationCycle


class NineBoxPermissionTests(TestCase):
    def setUp(self):
        self.cycle = EvaluationCycle.objects.create(
            name="2026", start_date=date(2026,1,1), end_date=date(2026,12,31)
        )

    def test_nine_box_forbidden_for_non_admin(self):
        u = User.objects.create_user(username="u", password="pass")
        self.client.login(username="u", password="pass")
        resp = self.client.get(reverse("nine_box"))
        self.assertIn(resp.status_code, (302, 403))  # según tu routing/forbidden template

    def test_nine_box_allowed_for_superuser(self):
        su = User.objects.create_superuser(username="admin", password="pass", email="a@a.com")
        self.client.login(username="admin", password="pass")
        resp = self.client.get(reverse("nine_box"))
        self.assertNotEqual(resp.status_code, 403)
