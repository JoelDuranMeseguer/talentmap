from django.contrib import admin

from .models import (
    EmployeeCycleScore,
    EvaluationCycle,
    TalentMapSettings,
    QualitativeIndicatorAssessment,
    QualitativeAxisMethod,
    QualitativeIndicatorAssessment,
    QualitativeIndicatorSelfAssessment,
    QuantitativeGoal,
)


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


@admin.register(QualitativeIndicatorSelfAssessment)
class QualitativeIndicatorSelfAssessmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "cycle", "indicator", "rating", "updated_at")
    list_filter = ("cycle", "rating")


@admin.register(TalentMapSettings)
class TalentMapSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "qualitative_axis_method", "top_min_above", "middle_max_below", "updated_at")

    def has_add_permission(self, request):
        # Singleton (id=1)
        if TalentMapSettings.objects.exists():
            return False
        return super().has_add_permission(request)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "qualitative_axis_method":
            kwargs["choices"] = QualitativeAxisMethod.choices
        return super().formfield_for_choice_field(db_field, request, **kwargs)
