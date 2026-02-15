from django.urls import path
from .views import (
    cycle_home,
    nine_box_dashboard,
    team_overview,
    edit_qualitative,
    competency_picker,
    edit_quantitative,
)

urlpatterns = [
    # Hub por ciclo (página principal de HR/Managers/Empleados)
    path("<int:cycle_id>/", cycle_home, name="eval_home"),

    # Mapa 9-box
    path("<int:cycle_id>/nine-box/", nine_box_dashboard, name="nine_box"),

    # Manager/HR: ver equipo
    path("<int:cycle_id>/team/", team_overview, name="team_overview"),

    # Cualitativo
    path("<int:cycle_id>/employee/<int:employee_id>/qualitative/", edit_qualitative, name="edit_qualitative"),

    # Cuantitativo: primero elegir competencia, luego checklist
    path("<int:cycle_id>/employee/<int:employee_id>/competencies/", competency_picker, name="competency_picker"),
    path("<int:cycle_id>/employee/<int:employee_id>/competency/<int:competency_id>/quantitative/",
         edit_quantitative, name="edit_quantitative"),
]
