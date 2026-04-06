from django.contrib import admin

from .models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement


@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(CompetencyLevel)
class CompetencyLevelAdmin(admin.ModelAdmin):
    list_display = ("competency", "level", "title")
    list_filter = ("competency",)


@admin.register(LevelIndicator)
class LevelIndicatorAdmin(admin.ModelAdmin):
    list_display = ("level", "text")
    search_fields = ("text",)


@admin.register(RoleCompetencyRequirement)
class RoleCompetencyRequirementAdmin(admin.ModelAdmin):
    list_display = ("role", "competency", "required_level", "weight")
    list_filter = ("role", "competency")
