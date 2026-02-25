from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from people.models import Employee
from competencies.models import LevelIndicator


class EvaluationCycle(models.Model):
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        unique_together = [("start_date", "end_date")]

    def __str__(self) -> str:
        return self.name


class QuantitativeGoal(models.Model):
    """
    CUANTITATIVO = metas/retos con peso (suma 100%) y % completado.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="quant_goals")
    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="quant_goals")

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    weight_percent = models.DecimalField(max_digits=5, decimal_places=2)          # 0..100
    completion_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # 0..100

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_quant_goals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["employee", "cycle"])]

    def clean(self):
        if self.weight_percent < 0 or self.weight_percent > 100:
            raise ValidationError({"weight_percent": "Debe estar entre 0 y 100."})
        if self.completion_percent < 0 or self.completion_percent > 100:
            raise ValidationError({"completion_percent": "Debe estar entre 0 y 100."})

    def __str__(self) -> str:
        return f"{self.employee} · {self.title}"


class BehaviorRating(models.IntegerChoices):
    NEVER = 1, "Nunca"
    RARELY = 2, "Casi nunca"
    OFTEN = 3, "Casi siempre"
    ALWAYS = 4, "Siempre"


class QualitativeIndicatorAssessment(models.Model):
    """
    CUALITATIVO = competencias→niveles→comportamientos (indicadores) con escala 1..4.
    """
    class AssessmentType(models.TextChoices):
        MANAGER = "manager", "Manager"
        SELF = "self", "Autoevaluación"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="qual_assessments")
    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="qual_assessments")
    indicator = models.ForeignKey(LevelIndicator, on_delete=models.CASCADE, related_name="assessments")

    rating = models.PositiveSmallIntegerField(choices=BehaviorRating.choices, default=BehaviorRating.NEVER)
    assessment_type = models.CharField(max_length=16, choices=AssessmentType.choices, default=AssessmentType.MANAGER)

    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assessed_behaviors",
    )
    assessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("employee", "cycle", "indicator", "assessment_type")]
        indexes = [models.Index(fields=["employee", "cycle"])]

    def clean(self):
        if self.rating < 1 or self.rating > 4:
            raise ValidationError({"rating": "Rating inválido."})

    def __str__(self) -> str:
        return f"{self.employee} · {self.indicator} = {self.get_rating_display()}"


class EmployeeCycleScore(models.Model):
    """
    qualitative_score  = CUALITATIVO (competencias)
    quantitative_score = CUANTITATIVO (metas)
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="cycle_scores")
    cycle = models.ForeignKey(EvaluationCycle, on_delete=models.CASCADE, related_name="employee_scores")

    qualitative_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    quantitative_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    qual_tercile = models.PositiveSmallIntegerField(default=1)
    quant_tercile = models.PositiveSmallIntegerField(default=1)

    box_code = models.CharField(max_length=32, default="")
    box_label = models.CharField(max_length=64, default="")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("employee", "cycle")]
        indexes = [
            models.Index(fields=["cycle", "box_code"]),
            models.Index(fields=["cycle", "qualitative_score"]),
            models.Index(fields=["cycle", "quantitative_score"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {remember_cycle(self.cycle)}"


def remember_cycle(cycle: EvaluationCycle) -> str:
    # helper pequeño para evitar __str__ muy largo si lo editas a menudo
    return cycle.name
