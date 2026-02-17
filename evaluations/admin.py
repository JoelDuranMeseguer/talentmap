from django.contrib import admin

from .models import EvaluationCycle, QuantitativeGoal, QualitativeIndicatorAssessment, EmployeeCycleScore

admin.site.register(EvaluationCycle)
admin.site.register(QuantitativeGoal)
admin.site.register(QualitativeIndicatorAssessment)
admin.site.register(EmployeeCycleScore)
