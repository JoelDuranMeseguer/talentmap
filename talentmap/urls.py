from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from evaluations.views import home
from people.views import logout_confirm, invite_user, register_with_token, config
from people.views import resend_invitation, cancel_invitation


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", logout_confirm, name="logout"),
    path("accounts/invite/", invite_user, name="invite_user"),
    path("config/", config, name="config"),
    path("accounts/register/", register_with_token, name="register"),
    path("", home, name="home"),
    path("evaluations/", include("evaluations.urls")),
    path("accounts/invite/<uuid:token>/resend/", resend_invitation, name="resend_invite"),
    path("accounts/invite/<uuid:token>/cancel/", cancel_invitation, name="cancel_invite"),
]
