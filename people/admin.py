from django.contrib import admin

from .models import Department, Employee, Invitation, Role


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "department")
    list_filter = ("department",)
    search_fields = ("name",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "department", "role", "manager", "active")
    list_filter = ("department", "role", "active")
    search_fields = ("user__username", "user__first_name", "user__last_name", "user__email")


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "department", "role", "created_by", "created_at", "expires_at", "used_at")
    list_filter = ("department", "role")
    search_fields = ("email",)
