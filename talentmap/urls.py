from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from evaluations.views import home
from people.views import (
    logout_confirm, invite_user, register_with_token, config,
    resend_invitation, cancel_invitation,
    download_sample_excel, import_users_excel,
    api_roles_by_department, delete_employee, api_add_role,
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", logout_confirm, name="logout"),
    path("accounts/invite/", invite_user, name="invite_user"),
    path("accounts/invite/sample-excel/", download_sample_excel, name="download_sample_excel"),
    path("accounts/invite/import-excel/", import_users_excel, name="import_users_excel"),
    path("config/", config, name="config"),
    path("accounts/register/", register_with_token, name="register"),
    path("", home, name="home"),
    path("evaluations/", include("evaluations.urls")),
    path("accounts/invite/<uuid:token>/resend/", resend_invitation, name="resend_invite"),
    path("accounts/invite/<uuid:token>/cancel/", cancel_invitation, name="cancel_invite"),
    path("api/roles/<int:department_id>/", api_roles_by_department, name="api_roles_by_department"),
    path("accounts/employee/<int:employee_id>/delete/", delete_employee, name="delete_employee"),
    path("api/add-role/", api_add_role, name="api_add_role"),
]
