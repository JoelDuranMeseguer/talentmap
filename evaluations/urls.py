from django.urls import path

from . import views

urlpatterns = [
    path("", views.cycle_home, name="eval_home"),
    path("set-cycle/", views.set_cycle, name="set_cycle"),
    path("nine-box/", views.nine_box_dashboard, name="nine_box"),
    path("team/", views.team_overview, name="team_overview"),

    # Entry-point cualitativo (1 arg) -> selector de competencias.
    # Mantiene compatibilidad con templates que hacen:
    #   {% url 'edit_qualitative' employee_id %}
    path(
        "employee/<int:employee_id>/qualitative/",
        views.competency_picker,
        name="edit_qualitative",
    ),
    path(
        "employee/<int:employee_id>/competency/<int:competency_id>/qualitative/",
        views.edit_qualitative,
        name="edit_qualitative",
    ),
    path(
        "employee/<int:employee_id>/competencies/",
        views.competency_picker,
        name="competency_picker",
    ),
    path(
        "employee/<int:employee_id>/quantitative/",
        views.edit_quantitative,
        name="edit_quantitative",
    ),
]