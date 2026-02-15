from django.contrib import admin
from django.urls import path, include
from evaluations.views import home  # nueva

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),  # login/logout
    path("", home, name="home"),
    path("evaluations/", include("evaluations.urls")),
]
