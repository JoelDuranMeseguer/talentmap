from decimal import Decimal
from django import forms
from django.forms import modelformset_factory, BaseModelFormSet
from .models import QualitativeGoal

class GoalForm(forms.ModelForm):
    class Meta:
        model = QualitativeGoal
        fields = ("title", "description", "weight_percent", "completion_percent")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Título"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Descripción"}),
            "weight_percent": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 100, "step": "0.01"}),
            "completion_percent": forms.NumberInput(attrs={"class": "form-control", "min": 0, "max": 100, "step": "0.01"}),
        }


class BaseGoalFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()
        total = Decimal("0")
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data is None:
                continue
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                total += Decimal(form.cleaned_data.get("weight_percent") or 0)
        if total.quantize(Decimal("0.01")) != Decimal("100.00"):
            raise forms.ValidationError("Los pesos deben sumar 100.00%.")

GoalFormSet = modelformset_factory(
    QualitativeGoal,
    form=GoalForm,
    formset=BaseGoalFormSet,
    extra=0,
    can_delete=True,
)
