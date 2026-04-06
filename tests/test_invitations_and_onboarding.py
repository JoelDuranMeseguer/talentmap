from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from people.models import Employee, Invitation
from people.services.invitations import create_invitation


@pytest.mark.django_db
class TestInvitationLifecycle:
    def test_create_invitation_service_sets_expiration(self, hr_user, department, role):
        before = timezone.now()
        invitation = create_invitation(
            email="newhire@example.com",
            department=department,
            role=role,
            manager=None,
            created_by=hr_user,
            expiry_days=7,
        )
        assert invitation.expires_at >= before + timedelta(days=6, hours=23)

    def test_register_with_token_creates_user_and_employee(self, invitation):
        client = Client()
        response = client.post(
            f"{reverse('register')}?token={invitation.token}",
            {
                "username": "invitee",
                "first_name": "Inv",
                "last_name": "Itee",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            follow=True,
        )
        assert response.status_code == 200
        invitation.refresh_from_db()
        assert invitation.used_at is not None
        assert Employee.objects.filter(user__username="invitee").exists()

    def test_resend_invitation_extends_expiry(self, hr_user, invitation):
        client = Client()
        old_expiry = invitation.expires_at
        client.force_login(hr_user)

        response = client.post(reverse("resend_invite", args=[invitation.token]), follow=True)

        invitation.refresh_from_db()
        assert response.status_code == 200
        assert invitation.expires_at > old_expiry

    def test_cancel_invitation_marks_as_expired(self, hr_user, invitation):
        client = Client()
        client.force_login(hr_user)

        response = client.post(reverse("cancel_invite", args=[invitation.token]), follow=True)

        invitation.refresh_from_db()
        assert response.status_code == 200
        assert invitation.expires_at <= timezone.now()

    def test_internal_employee_creation_skips_invitation(self, hr_user, department, role):
        client = Client()
        client.force_login(hr_user)

        response = client.post(
            reverse("invite_user"),
            {
                "first_name": "No",
                "last_name": "Login",
                "email": "ignored@example.com",
                "department": department.id,
                "role": role.id,
                "create_internal": "on",
            },
            follow=True,
        )

        assert response.status_code == 200
        assert Invitation.objects.count() == 0
        user = User.objects.get(first_name="No", last_name="Login")
        assert not user.has_usable_password()
