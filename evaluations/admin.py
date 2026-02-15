from django.contrib import admin
from .models import EvaluationCycle, QualitativeGoal, QuantitativeIndicatorAssessment, EmployeeCycleScore

admin.site.register(EvaluationCycle)
admin.site.register(QualitativeGoal)
admin.site.register(QuantitativeIndicatorAssessment)
admin.site.register(EmployeeCycleScore)
