from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Invitation, Department, Role


class InviteForm(forms.Form):
    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all().order_by("name"),
        label="Departamento",
        empty_label="Selecciona departamento",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.none(),
        label="Rol",
        empty_label="Selecciona departamento primero",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "department" in self.data:
            try:
                dept_id = int(self.data.get("department"))
                self.fields["role"].queryset = Role.objects.filter(department_id=dept_id).order_by("name")
            except (ValueError, TypeError):
                pass
        elif self.initial.get("department"):
            self.fields["role"].queryset = Role.objects.filter(
                department=self.initial["department"]
            ).order_by("name")


class RegisterForm(UserCreationForm):
    email = forms.EmailField(disabled=True, required=False)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ("email",):
                widget = self.fields[field].widget
                if "class" not in widget.attrs:
                    widget.attrs["class"] = "form-control"
