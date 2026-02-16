from django.db import models
from django.core.exceptions import ValidationError
from people.models import Role

class Competency(models.Model):
    name = models.CharField(max_length=160, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CompetencyLevel(models.Model):
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name="levels")
    level = models.PositiveIntegerField()  # 1..N
    title = models.CharField(max_length=160, blank=True)

    class Meta:
        unique_together = [("competency", "level")]
        ordering = ["competency__name", "level"]

    def __str__(self):
        return f"{self.competency} L{self.level}"


class LevelIndicator(models.Model):
    """
    'Cualidades/behaviors' dentro de un nivel (los que se deben cumplir para subir).
    """
    level = models.ForeignKey(CompetencyLevel, on_delete=models.CASCADE, related_name="indicators")
    text = models.CharField(max_length=240)

    class Meta:
        ordering = ["level__competency__name", "level__level", "id"]

    def __str__(self):
        return f"{self.level}: {self.text}"


class RoleCompetencyRequirement(models.Model):
    """
    Perfil ideal por rol: hasta qué nivel se exige en cada competencia.
    weight opcional para ponderar competencias en el cualitativo.
    """
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="competency_requirements")
    competency = models.ForeignKey(Competency, on_delete=models.PROTECT, related_name="role_requirements")

    required_level = models.PositiveIntegerField(default=1)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=1)  # ponderación relativa

    class Meta:
        unique_together = [("role", "competency")]

    def clean(self):
        if self.required_level < 1:
            raise ValidationError({"required_level": "Debe ser >= 1."})
        if self.weight <= 0:
            raise ValidationError({"weight": "Debe ser > 0."})

    def __str__(self):
        return f"{self.role} - {self.competency}: L{self.required_level}"
