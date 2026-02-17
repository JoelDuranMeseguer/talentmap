from django.urls import path

from .views import (
    cycle_home,
    set_cycle,
    nine_box_dashboard,
    team_overview,
    edit_quantitative,
    competency_picker,
    edit_qualitative,
)

urlpatterns = [
    path("", cycle_home, name="eval_home"),
    path("set-cycle/", set_cycle, name="set_cycle"),

    path("team/", team_overview, name="team_overview"),
    path("nine-box/", nine_box_dashboard, name="nine_box"),  # admin only

    # CUANTITATIVO (metas)
    path("employee/<int:employee_id>/quantitative/", edit_quantitative, name="edit_quantitative"),

    # CUALITATIVO (competencias)
    path("employee/<int:employee_id>/competencies/", competency_picker, name="competency_picker"),
    path(
        "employee/<int:employee_id>/competency/<int:competency_id>/qualitative/",
        edit_qualitative,
        name="edit_qualitative",
    ),
]
