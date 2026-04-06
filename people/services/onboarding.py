from dataclasses import dataclass, field

from django.contrib.auth.models import User
from django.utils import timezone

from people.models import Employee, Invitation
from people.services.invitations import create_invitation, send_invitation_email


@dataclass
class ImportUsersResult:
    created_count: int = 0
    warnings: list[str] = field(default_factory=list)


def create_internal_employee(*, first_name, last_name, department, role, manager=None):
    """Create an internal employee profile without login credentials."""
    base = f"{first_name}_{last_name}".replace(" ", "_").lower()[:30]
    username = base
    suffix = 0

    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f"{base}_{suffix}"[:150]

    user = User.objects.create(
        username=username,
        email="",
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    user.set_unusable_password()
    user.save()

    return Employee.objects.create(user=user, department=department, role=role, manager=manager)


def has_pending_or_existing_user(email: str) -> bool:
    return User.objects.filter(email__iexact=email).exists() or Invitation.objects.filter(
        email__iexact=email,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists()


def import_users_as_invitations(*, rows, created_by) -> ImportUsersResult:
    """Create invitation rows imported from Excel preserving current flow semantics."""
    result = ImportUsersResult()
    batch_managers_by_email = {}

    def resolve_manager(row):
        if row.get("manager"):
            return row["manager"]

        manager_email_pending = (row.get("manager_email_pending") or "").strip().lower()
        if manager_email_pending:
            return batch_managers_by_email.get(manager_email_pending)

        first_name = row.get("manager_nombre", "").strip()
        last_name = row.get("manager_apellido", "").strip()
        if first_name and last_name:
            matches = [
                manager
                for manager in batch_managers_by_email.values()
                if manager.user.first_name == first_name and manager.user.last_name == last_name
            ]
            if len(matches) == 1:
                return matches[0]
        return None

    for row in rows:
        email = row["email"]
        manager = resolve_manager(row) or row.get("manager")

        if has_pending_or_existing_user(email):
            result.warnings.append(f"Fila {row['row']}: {email} ya existe o tiene invitación pendiente.")
            continue

        if row.get("manager_email_pending") and not manager:
            result.warnings.append(
                f"Fila {row['row']}: el manager '{row['manager_email_pending']}' también viene en el Excel y todavía no existe como empleado activo."
                " Se envía la invitación sin manager; podrás asignarlo luego en el perfil del colaborador."
            )

        invitation = create_invitation(
            email=email,
            department=row["department"],
            role=row["role"],
            manager=manager,
            created_by=created_by,
        )
        send_invitation_email(invitation=invitation)
        result.created_count += 1

    return result
