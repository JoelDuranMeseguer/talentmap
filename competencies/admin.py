from django.contrib import admin
from .models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement

admin.site.register(Competency)
admin.site.register(CompetencyLevel)
admin.site.register(LevelIndicator)
admin.site.register(RoleCompetencyRequirement)
