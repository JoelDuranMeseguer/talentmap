import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestPermissions:
    def test_hr_can_access_nine_box(self, hr_user, cycle):
        client = Client()
        client.force_login(hr_user)
        response = client.get(reverse("nine_box"))
        assert response.status_code == 200

    def test_manager_can_edit_direct_report_quantitative(
        self,
        manager_user,
        manager_employee,
        report_employee,
        other_employee,
        cycle,
    ):
        client = Client()
        client.force_login(manager_user)

        allowed = client.get(reverse("edit_quantitative", args=[report_employee.id]))
        denied = client.get(reverse("edit_quantitative", args=[other_employee.id]))

        assert allowed.status_code == 200
        assert denied.status_code == 403
