from django.conf import settings
from django.db import models

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
