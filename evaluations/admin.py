from django.contrib import admin

from .models import EmployeeCycleScore, EvaluationCycle, QualitativeIndicatorAssessment, QuantitativeGoal


@admin.register(EvaluationCycle)
class EvaluationCycleAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date")
    ordering = ("-start_date",)


@admin.register(QuantitativeGoal)
class QuantitativeGoalAdmin(admin.ModelAdmin):
    list_display = ("employee", "cycle", "title", "weight_percent", "completion_percent", "created_by")
    list_filter = ("cycle",)
    search_fields = ("employee__user__username", "title")


@admin.register(QualitativeIndicatorAssessment)
class QualitativeIndicatorAssessmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "cycle", "indicator", "rating", "assessed_by", "assessed_at")
    list_filter = ("cycle", "rating")


@admin.register(EmployeeCycleScore)
class EmployeeCycleScoreAdmin(admin.ModelAdmin):
    list_display = ("employee", "cycle", "qualitative_score", "quantitative_score", "box_label", "updated_at")
    list_filter = ("cycle", "box_code")
