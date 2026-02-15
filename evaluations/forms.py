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
            if form.cleaned_data.get("DELETE"):
                continue
            title = form.cleaned_data.get("title", "") or ""
            title = str(title).strip() if title else ""
            weight = form.cleaned_data.get("weight_percent")
            if not title and (weight is None or weight == 0):
                continue
            w = weight if weight is not None else Decimal("0")
            total += Decimal(str(w))
        if total > 0 and total.quantize(Decimal("0.01")) != Decimal("100.00"):
            raise forms.ValidationError("Los pesos deben sumar exactamente 100%.")

GoalFormSet = modelformset_factory(
    QualitativeGoal,
    form=GoalForm,
    extra=1,
    can_delete=True,
    formset=BaseGoalFormSet,
)
