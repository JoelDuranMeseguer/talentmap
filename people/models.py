import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self):
        return self.name


class Role(models.Model):
    name = models.CharField(max_length=160, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="roles")

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="employees")

    # Jerarquía simple (para permisos):
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")

    active = models.BooleanField(default=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()


class Invitation(models.Model):
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True, editable=False)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="invitations")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="invitations")
    manager = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invited_reports",
    )
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pending_invitations",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_invitations"
    )
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    accepted_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_invitations",
    )

    def __str__(self):
        return f"Invitation to {self.email} ({self.role.name})"

    @property
    def is_valid(self):
        if self.used_at:
            return False
        return timezone.now() < self.expires_at
