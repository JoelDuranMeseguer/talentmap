import io
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from people.excel_import import parse_excel_import
from people.forms import InviteForm
from people.models import Department, Invitation, Role, Employee


def build_excel(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["nombre", "apellido", "email", "departamento", "rol", "manager_email"])
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


class InviteAndExcelImportTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT")
        self.role = Role.objects.create(name="Developer", department=self.dept)
        self.hr = User.objects.create_user(
            username="hr",
            email="hr@example.com",
            password="password123",
            is_superuser=True,
            is_staff=True,
        )

    def test_invite_form_requires_email(self):
        form = InviteForm(data={
            "first_name": "Ana",
            "last_name": "López",
            "department": self.dept.id,
            "role": self.role.id,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_invite_form_allows_internal_without_email(self):
        form = InviteForm(data={
            "first_name": "Interno",
            "last_name": "Usuario",
            "email": "",
            "department": self.dept.id,
            "role": self.role.id,
            "create_internal": True,
        })
        self.assertTrue(form.is_valid())

    def test_parse_excel_allows_manager_email_from_same_file(self):
        excel = build_excel([
            ["Líder", "Equipo", "lider@example.com", "IT", "Developer", ""],
            ["Dev", "Junior", "dev@example.com", "IT", "Developer", "lider@example.com"],
        ])

        rows, errors = parse_excel_import(excel)

        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["manager_email_pending"], "lider@example.com")

    def test_import_excel_creates_invitations_when_manager_is_in_same_file(self):
        self.client.force_login(self.hr)
        excel = build_excel([
            ["Líder", "Equipo", "lider@example.com", "IT", "Developer", ""],
            ["Dev", "Junior", "dev@example.com", "IT", "Developer", "lider@example.com"],
        ])

        response = self.client.post(
            reverse("import_users_excel"),
            {"excel_file": SimpleUploadedFile("users.xlsx", excel.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invitation.objects.count(), 2)
        subordinate_inv = Invitation.objects.get(email="dev@example.com")
        self.assertIsNone(subordinate_inv.manager)

    def test_register_with_token_consumes_invitation(self):
        invitation = Invitation.objects.create(
            email="new.user@example.com",
            department=self.dept,
            role=self.role,
            created_by=self.hr,
            expires_at=timezone.now() + timedelta(days=7),
        )
        response = self.client.post(
            f"{reverse('register')}?token={invitation.token}",
            {
                "username": "new.user",
                "first_name": "New",
                "last_name": "User",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.used_at)
        self.assertTrue(Employee.objects.filter(user__username="new.user").exists())

    def test_internal_employee_creation_without_invitation(self):
        self.client.force_login(self.hr)
        response = self.client.post(
            reverse("invite_user"),
            {
                "first_name": "Interno",
                "last_name": "SinLogin",
                "email": "internal@example.com",
                "department": self.dept.id,
                "role": self.role.id,
                "create_internal": "on",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Invitation.objects.count(), 0)
        emp = Employee.objects.get(user__first_name="Interno")
        self.assertFalse(emp.user.has_usable_password())
