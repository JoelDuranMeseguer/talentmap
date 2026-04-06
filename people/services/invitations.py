from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from people.models import Invitation


def build_registration_url(token) -> str:
    site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000")
    return f"{site_url}/accounts/register/?token={token}"


def create_invitation(*, email, department, role, manager, created_by, expiry_days=7):
    return Invitation.objects.create(
        email=email,
        department=department,
        role=role,
        manager=manager,
        created_by=created_by,
        expires_at=timezone.now() + timedelta(days=expiry_days),
    )


def send_invitation_email(*, invitation, first_name=""):
    register_url = build_registration_url(invitation.token)
    send_mail(
        subject="Invitación a TalentMap",
        message=(
            f"Hola {first_name},\n\n" if first_name else "Hola,\n\n"
        )
        + (
            f"Has sido invitado a unirte a TalentMap como {invitation.role.name} en "
            f"{invitation.department.name}.\n\n"
            f"Crea tu cuenta aquí: {register_url}\n\n"
            "Este enlace expira en 7 días."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )


def resend_invitation_email(invitation):
    invitation.expires_at = timezone.now() + timedelta(days=7)
    invitation.save(update_fields=["expires_at"])

    register_url = build_registration_url(invitation.token)
    send_mail(
        subject="Invitación a TalentMap (reenviada)",
        message=(
            "Hola,\n\n"
            "Te reenviamos tu invitación a TalentMap.\n\n"
            f"Crea tu cuenta aquí: {register_url}\n\n"
            "Este enlace expira en 7 días."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )
