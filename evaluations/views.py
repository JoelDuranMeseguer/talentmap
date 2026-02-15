from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from evaluations.models import EvaluationCycle, EmployeeCycleScore
from people.models import Department, Role, Employee
from people.services.access import managed_employees_qs
from evaluations.services.scoring import BOXES 
from people.services.access import is_hr
from evaluations.services.scoring import recompute_cycle_scores
from evaluations.forms import GoalFormSet
from evaluations.models import QualitativeGoal
from django.db import transaction
from competencies.models import Competency, RoleCompetencyRequirement, CompetencyLevel
from evaluations.models import QuantitativeIndicatorAssessment
from datetime import date

@login_required
def competency_picker(request, cycle_id, employee_id):
    cycle = get_object_or_404(EvaluationCycle, id=cycle_id)
    emp = get_object_or_404(Employee, id=employee_id)

    allowed = is_hr(request.user) or managed_employees_qs(request.user).filter(id=emp.id).exists()
    if not allowed:
        return render(request, "evaluations/forbidden.html", status=403)

    reqs = (RoleCompetencyRequirement.objects
            .filter(role=emp.role)
            .select_related("competency")
            .order_by("competency__name"))

    return render(request, "evaluations/competency_picker.html", {
        "cycle": cycle,
        "employee": emp,
        "reqs": reqs,
    })


@login_required
def team_overview(request, cycle_id):
    cycle = get_object_or_404(EvaluationCycle, id=cycle_id)
    emps = managed_employees_qs(request.user).select_related("user", "role", "department").order_by("user__last_name")

    # HR: opcionalmente ver toda la empresa (si quieres)
    if is_hr(request.user):
        emps = Employee.objects.filter(active=True).select_related("user", "role", "department").order_by("user__last_name")

    scores = {
        s.employee_id: s
        for s in EmployeeCycleScore.objects.filter(cycle=cycle, employee__in=emps)
    }

    return render(request, "evaluations/team_overview.html", {
        "cycle": cycle,
        "employees": emps,
        "scores": scores,
    })


@login_required
def cycle_home(request, cycle_id):
    cycle = get_object_or_404(EvaluationCycle, id=cycle_id)

    # Si el usuario no está vinculado a Employee, lo mandamos a admin o error amable
    try:
        me = request.user.employee
    except Exception:
        return render(request, "evaluations/no_employee.html", {"cycle": cycle})

    my_score = EmployeeCycleScore.objects.filter(employee=me, cycle=cycle).first()

    is_manager = managed_employees_qs(request.user).exists()
    hr = is_hr(request.user)

    return render(request, "evaluations/cycle_home.html", {
        "cycle": cycle,
        "me": me,
        "my_score": my_score,
        "is_manager": is_manager,
        "is_hr": hr,
    })


def _default_cycle():
    today = date.today()
    # ciclo actual
    cycle = EvaluationCycle.objects.filter(start_date__lte=today, end_date__gte=today).order_by("-start_date").first()
    if cycle:
        return cycle
    # si no hay ciclo “activo”, el último por fecha fin
    return EvaluationCycle.objects.order_by("-end_date").first()

@login_required
def home(request):
    cycle = _default_cycle()
    if not cycle:
        # primera ejecución: no hay ciclos
        return redirect("/admin/")  # o una pantalla “crea un ciclo”
    return redirect("eval_home", cycle_id=cycle.id)

@login_required
def edit_qualitative(request, employee_id, cycle_id):
    cycle = get_object_or_404(EvaluationCycle, id=cycle_id)
    emp = get_object_or_404(Employee, id=employee_id)

    # permiso: HR o manager del empleado (en managed_employees_qs)
    allowed = is_hr(request.user) or managed_employees_qs(request.user).filter(id=emp.id).exists()
    if not allowed:
        return render(request, "evaluations/forbidden.html", status=403)

    qs = QualitativeGoal.objects.filter(employee=emp, cycle=cycle).order_by("id")

    if request.method == "POST":
        formset = GoalFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            instances = formset.save(commit=False)

            # guardamos nuevos/actualizados
            for obj in instances:
                obj.employee = emp
                obj.cycle = cycle
                if not obj.created_by_id:
                    obj.created_by = request.user
                obj.save()

            # borrados
            for obj in formset.deleted_objects:
                obj.delete()

            # opcional: recalcular inmediatamente solo este empleado (rápido)
            recompute_cycle_scores(cycle, Employee.objects.filter(id=emp.id))

            return redirect("nine_box", cycle_id=cycle.id)
    else:
        formset = GoalFormSet(queryset=qs)

    return render(request, "evaluations/edit_qualitative.html", {
        "cycle": cycle,
        "employee": emp,
        "formset": formset,
    })

@login_required
def edit_quantitative(request, employee_id, cycle_id, competency_id):
    cycle = get_object_or_404(EvaluationCycle, id=cycle_id)
    emp = get_object_or_404(Employee, id=employee_id)
    comp = get_object_or_404(Competency, id=competency_id)

    allowed = is_hr(request.user) or managed_employees_qs(request.user).filter(id=emp.id).exists()
    if not allowed:
        return render(request, "evaluations/forbidden.html", status=403)

    req = RoleCompetencyRequirement.objects.filter(role=emp.role, competency=comp).first()
    required_level = req.required_level if req else 1

    levels = (
        CompetencyLevel.objects
        .filter(competency=comp, level__lte=required_level)
        .prefetch_related("indicators")
        .order_by("level")
    )

    indicator_ids = []
    for lvl in levels:
        indicator_ids.extend([i.id for i in lvl.indicators.all()])

    existing = QuantitativeIndicatorAssessment.objects.filter(
        employee=emp, cycle=cycle, indicator_id__in=indicator_ids
    )
    met_set = set(existing.filter(met=True).values_list("indicator_id", flat=True))

    if request.method == "POST":
        with transaction.atomic():
            # Actualizar uno a uno (rápido y claro; luego se optimiza si hace falta)
            for lvl in levels:
                for ind in lvl.indicators.all():
                    met = bool(request.POST.get(f"ind_{ind.id}"))
                    QuantitativeIndicatorAssessment.objects.update_or_create(
                        employee=emp, cycle=cycle, indicator=ind,
                        defaults={"met": met, "assessed_by": request.user},
                    )

        recompute_cycle_scores(cycle, Employee.objects.filter(id=emp.id))
        return redirect("nine_box", cycle_id=cycle.id)

    return render(request, "evaluations/edit_quantitative.html", {
        "cycle": cycle,
        "employee": emp,
        "competency": comp,
        "required_level": required_level,
        "levels": levels,
        "met_set": met_set,
    })

@login_required
def nine_box_dashboard(request, cycle_id):
    cycle = get_object_or_404(EvaluationCycle, id=cycle_id)

    dept_id = request.GET.get("department")
    role_id = request.GET.get("role")

    base_emps = managed_employees_qs(request.user)
    if dept_id:
        base_emps = base_emps.filter(department_id=dept_id)
    if role_id:
        base_emps = base_emps.filter(role_id=role_id)

    scores = (
        EmployeeCycleScore.objects
        .filter(cycle=cycle, employee__in=base_emps)
        .select_related("employee", "employee__user", "employee__department", "employee__role")
        .order_by("-qualitative_score", "-quantitative_score")
    )

    grid = {}
    for s in scores:
        grid.setdefault((s.qual_tercile, s.quant_tercile), []).append(s)

    # Orden: Y (cualitativo) 3->1, X (cuantitativo) 1->3
    order = [
        (3, 1), (3, 2), (3, 3),
        (2, 1), (2, 2), (2, 3),
        (1, 1), (1, 2), (1, 3),
    ]

    # labels del 9-box
    box_label = {k: v[1] for k, v in BOXES.items()}

    cells = []
    for qual, quant in order:
        cells.append({
            "qual": qual,
            "quant": quant,
            "label": box_label[(qual, quant)],
            "items": grid.get((qual, quant), []),
        })

    return render(request, "evaluations/nine_box.html", {
        "cycle": cycle,
        "cells": cells,
        "departments": Department.objects.all(),
        "roles": Role.objects.all(),
        "dept_id": dept_id or "",
        "role_id": role_id or "",
    })
