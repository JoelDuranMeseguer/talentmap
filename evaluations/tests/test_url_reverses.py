from django.test import SimpleTestCase
from django.urls import reverse


class TestUrlReverses(SimpleTestCase):
    def test_edit_qualitative_reverse_employee_only(self):
        assert reverse("edit_qualitative", args=[1]) == "/evaluations/employee/1/qualitative/"

    def test_edit_qualitative_reverse_employee_and_competency(self):
        assert (
            reverse("edit_qualitative", args=[1, 2])
            == "/evaluations/employee/1/competency/2/qualitative/"
        )

    def test_edit_quantitative_reverse(self):
        assert reverse("edit_quantitative", args=[1]) == "/evaluations/employee/1/quantitative/"
