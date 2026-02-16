from django.urls import path
from .views import (
    cycle_home,
    nine_box_dashboard,
    team_overview,
    edit_qualitative,
    competency_picker,
    edit_quantitative,
    set_cycle,
)

urlpatterns = [
    path("", cycle_home, name="eval_home"),
    path("set-cycle/", set_cycle, name="set_cycle"),

    path("nine-box/", nine_box_dashboard, name="nine_box"),
    path("team/", team_overview, name="team_overview"),

    path("employee/<int:employee_id>/qualitative/", edit_qualitative, name="edit_qualitative"),
    path("employee/<int:employee_id>/competencies/", competency_picker, name="competency_picker"),
    path("employee/<int:employee_id>/competency/<int:competency_id>/quantitative/",
         edit_quantitative, name="edit_quantitative"),
]
