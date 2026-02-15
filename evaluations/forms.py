from decimal import Decimal
from django import forms
from django.forms import modelformset_factory, BaseModelFormSet
from .models import QualitativeGoal

class BaseGoalFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()
        total = Decimal("0")
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                w = form.cleaned_data.get("weight_percent") or Decimal("0")
                total += Decimal(w)
        # tolerancia por decimales
        if total.quantize(Decimal("0.01")) != Decimal("100.00"):
            raise forms.ValidationError("Los pesos (weight_percent) deben sumar 100.00%.")

GoalFormSet = modelformset_factory(
    QualitativeGoal,
    fields=("title", "description", "weight_percent", "completion_percent"),
    extra=3,
    can_delete=True,
    formset=BaseGoalFormSet,
)
