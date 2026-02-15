from django.db import models
from django.core.exceptions import ValidationError
from people.models import Employee
from django.db import models
from django.core.exceptions import ValidationError
from people.models import Employee
from competencies.models import Competency, CompetencyLevel, LevelIndicator

class EvaluationCycle(models.Model):
    name = models.CharField(max_length=120)  # "2026 Q1", "2026"
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        unique_together = [("start_date", "end_date")]

    def __str__(self):
        return self.name


class QualitativeGoal(models.Model):
    """
    Un 'reto/cualidad' asignado a un empleado en un ciclo.
    Todos los goals de un empleado+cycle deben sumar 100 en weight_percent.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="qual_goals")
    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="qual_goals")

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    weight_percent = models.DecimalField(max_digits=5, decimal_places=2)  # 0..100
    completion_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0..100

    created_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="created_qual_goals")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "cycle"]),
        ]

    def clean(self):
        for f in ["weight_percent", "completion_percent"]:
            val = getattr(self, f)
            if val < 0 or val > 100:
                raise ValidationError({f: "Debe estar entre 0 y 100."})

    def __str__(self):
        return f"{self.employee} - {self.cycle}: {self.title}"


class QuantitativeIndicatorAssessment(models.Model):
    """
    Un jefe marca si el empleado cumple un indicador concreto en un ciclo.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="quant_assessments")
    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="quant_assessments")

    indicator = models.ForeignKey(LevelIndicator, on_delete=models.CASCADE, related_name="assessments")
    met = models.BooleanField(default=False)

    assessed_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="assessed_indicators")
    assessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("employee", "cycle", "indicator")]
        indexes = [
            models.Index(fields=["employee", "cycle"]),
        ]


class EmployeeCycleScore(models.Model):
    """
    Cache de scores (para dashboard rápido).
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="cycle_scores")
    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="employee_scores")

    qualitative_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # 0..100
    quantitative_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # 0..100

    # terciles:
    qual_tercile = models.PositiveSmallIntegerField(default=1)  # 1 low, 2 mid, 3 high
    quant_tercile = models.PositiveSmallIntegerField(default=1)

    box_code = models.CharField(max_length=32, default="")  # e.g. "STAR"
    box_label = models.CharField(max_length=64, default="") # e.g. "Estrellas"

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("employee", "cycle")]
        indexes = [
            models.Index(fields=["cycle", "box_code"]),
            models.Index(fields=["cycle", "qualitative_score"]),
            models.Index(fields=["cycle", "quantitative_score"]),
        ]

    def clean(self):
        for f in ["qualitative_score", "quantitative_score"]:
            val = getattr(self, f)
            if val < 0 or val > 100:
                raise ValidationError({f: "Debe estar entre 0 y 100."})
