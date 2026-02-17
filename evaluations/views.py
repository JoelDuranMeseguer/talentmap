from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from competencies.models import Competency, CompetencyLevel, RoleCompetencyRequirement
from evaluations.forms import GoalFormSet
from evaluations.models import (
    EmployeeCycleScore,
    EvaluationCycle,
    QualitativeIndicatorAssessment,
    QuantitativeGoal,
)
from evaluations.services.scoring import BOXES, PASS_RATING, recompute_cycle_scores, terciles_for_scores
from people.models import Department, Employee, Role
from people.services.access import is_hr, managed_employees_qs

SESSION_CYCLE_KEY = "eval_current_cycle_id"
from django.shortcuts import redirect

@login_required
def home(request):
    return redirect("eval_home")



def _default_cycle():
    today = date.today()
    cycle = (
        EvaluationCycle.objects.filter(start_date__lte=today, end_date__gte=today)
        .order_by("-start_date")
        .first()
    )
    if cycle:
        return cycle
    return EvaluationCycle.objects.order_by("-end_date").first()


def get_current_cycle(request):
    cycle_id = request.session.get(SESSION_CYCLE_KEY)
    if cycle_id:
        cycle = EvaluationCycle.objects.filter(id=cycle_id).first()
        if cycle:
            return cycle

    cycle = _default_cycle()
    if cycle:
        request.session[SESSION_CYCLE_KEY] = cycle.id
    return cycle


@login_required
def set_cycle(request):
    if request.method != "POST":
        return redirect("eval_home")

    cycle_id = request.POST.get("cycle_id")
    if cycle_id:
        cycle = EvaluationCycle.objects.filter(id=cycle_id).first()
        if cycle:
            request.session[SESSION_CYCLE_KEY] = cycle.id

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/evaluations/"
    return redirect(next_url or "eval_home")


def _recompute_company(cycle: EvaluationCycle):
    # Para que el 9-box (admin) esté siempre consistente,
    # recalculamos para todos los empleados activos.
    recompute_cycle_scores(cycle, Employee.objects.filter(active=True))


@login_required
def cycle_home(request):
    cycle = get_current_cycle(request)
    if not cycle:
        return redirect("/admin/")

    try:
        me = request.user.employee
    except Exception:
        return render(request, "evaluations/no_employee.html", {"cycle": cycle})

    my_score = EmployeeCycleScore.objects.filter(employee=me, cycle=cycle).first()
    is_manager = managed_employees_qs(request.user).exists()
    hr = is_hr(request.user)

    can_edit_me = hr or (me.manager_id and me.manager.user_id == request.user.id)

    return render(
        request,
        "evaluations/cycle_home.html",
        {
            "cycle": cycle,
            "me": me,
            "my_score": my_score,
            "is_manager": is_manager,
            "is_hr": hr,
            "can_edit_me": can_edit_me,
        },
    )


@login_required
def team_overview(request):
    cycle = get_current_cycle(request)
    if not cycle:
        return redirect("/admin/")

    # Managers: solo reportes directos, HR: toda la empresa
    emps = managed_employees_qs(request.user).select_related("user", "role", "department").order_by("user__last_name")
    if is_hr(request.user):
        emps = Employee.objects.filter(active=True).select_related("user", "role", "department").order_by("user__last_name")

    scores = {s.employee_id: s for s in EmployeeCycleScore.objects.filter(cycle=cycle, employee__in=emps)}
    return render(request, "evaluations/team_overview.html", {"cycle": cycle, "employees": emps, "scores": scores})


@login_required
def edit_quantitative(request, employee_id):
    """
    CUANTITATIVO = metas (pesos 100% + % completado)
    """
    cycle = get_current_cycle(request)
    if not cycle:
        return redirect("/admin/")

    emp = get_object_or_404(Employee, id=employee_id)

    allowed = is_hr(request.user) or managed_employees_qs(request.user).filter(id=emp.id).exists()
    if not allowed:
        return render(request, "evaluations/forbidden.html", status=403)

    qs = QuantitativeGoal.objects.filter(employee=emp, cycle=cycle).order_by("id")

    if request.method == "POST":
        formset = GoalFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            instances = formset.save(commit=False)

            for obj in instances:
                obj.employee = emp
                obj.cycle = cycle
                if not obj.created_by_id:
                    obj.created_by = request.user
                obj.save()

            for obj in formset.deleted_objects:
                obj.delete()

            _recompute_company(cycle)

            return redirect("team_overview" if managed_employees_qs(request.user).exists() or is_hr(request.user) else "eval_home")
    else:
        formset = GoalFormSet(queryset=qs)

    return render(request, "evaluations/edit_quantitative.html", {"cycle": cycle, "employee": emp, "formset": formset})


@login_required
def competency_picker(request, employee_id):
    """
    Selector de competencias (para editar CUALITATIVO).
    """
    cycle = get_current_cycle(request)
    if not cycle:
        return redirect("/admin/")

    emp = get_object_or_404(Employee, id=employee_id)
    allowed = is_hr(request.user) or managed_employees_qs(request.user).filter(id=emp.id).exists()
    if not allowed:
        return render(request, "evaluations/forbidden.html", status=403)

    reqs = (
        RoleCompetencyRequirement.objects.filter(role=emp.role)
        .select_related("competency")
        .order_by("competency__name")
    )

    return render(request, "evaluations/competency_picker.html", {"cycle": cycle, "employee": emp, "reqs": reqs})


@login_required
def edit_qualitative(request, employee_id, competency_id):
    """
    CUALITATIVO = competencias→niveles→comportamientos con escala Nunca/Casi nunca/Casi siempre/Siempre.
    """
    cycle = get_current_cycle(request)
    if not cycle:
        return redirect("/admin/")

    emp = get_object_or_404(Employee, id=employee_id)
    comp = get_object_or_404(Competency, id=competency_id)

    allowed = is_hr(request.user) or managed_employees_qs(request.user).filter(id=emp.id).exists()
    if not allowed:
        return render(request, "evaluations/forbidden.html", status=403)

    req = RoleCompetencyRequirement.objects.filter(role=emp.role, competency=comp).first()
    required_level = int(req.required_level) if req else 1

    levels = (
        CompetencyLevel.objects.filter(competency=comp, level__lte=required_level)
        .prefetch_related("indicators")
        .order_by("level")
    )

    indicator_ids = []
    for lvl in levels:
        indicator_ids.extend([i.id for i in lvl.indicators.all()])

    existing = QualitativeIndicatorAssessment.objects.filter(
        employee=emp, cycle=cycle, indicator_id__in=indicator_ids
    )
    rating_map = {a.indicator_id: int(a.rating) for a in existing}

    if request.method == "POST":
        with transaction.atomic():
            for lvl in levels:
                for ind in lvl.indicators.all():
                    raw = request.POST.get(f"ind_{ind.id}")
                    try:
                        rating = int(raw) if raw else 1
                    except ValueError:
                        rating = 1

                    rating = max(1, min(4, rating))
                    QualitativeIndicatorAssessment.objects.update_or_create(
                        employee=emp,
                        cycle=cycle,
                        indicator=ind,
                        defaults={"rating": rating, "assessed_by": request.user},
                    )

        _recompute_company(cycle)
        return redirect("competency_picker", employee_id=emp.id)

    # Construimos estructura para template (visual + stats)
    levels_ctx = []
    achieved_level = 0
    for lvl in levels:
        inds = list(lvl.indicators.all())
        passed = sum(1 for ind in inds if rating_map.get(ind.id, 1) >= PASS_RATING)
        total = len(inds)

        # regla secuencial: si falla un nivel, no subes más
        if total == 0 or passed == total:
            achieved_level = max(achieved_level, lvl.level)
        else:
            # cortamos aquí (los siguientes niveles quedan "bloqueados" a efectos de nivel)
            # pero igualmente los mostramos para que puedan evaluarse.
            pass

        levels_ctx.append(
            {
                "level": lvl,
                "indicators": inds,
                "passed": passed,
                "total": total,
            }
        )

    # unlocked_max_level: el primer nivel NO completado (ese nivel sí se puede editar),
    # y todo lo que esté por encima queda bloqueado.
    unlocked_max_level = 1
    achieved_level = 0

    for item in levels_ctx:
        lvl_num = item["level"].level
        total = item["total"]
        passed = item["passed"]

        is_completed = (total == 0) or (passed == total)
        if is_completed:
            achieved_level = lvl_num
            unlocked_max_level = min(lvl_num + 1, required_level)
        else:
            unlocked_max_level = lvl_num
            break

    # si no hay niveles, por seguridad
    unlocked_max_level = max(1, min(unlocked_max_level, required_level))

    current_level = unlocked_max_level 

    # Marca qué niveles están bloqueados inicialmente (sin lógica en template)
    for item in levels_ctx:
        item["locked_initial"] = item["level"].level > unlocked_max_level


    return render(
        request,
        "evaluations/edit_qualitative.html",
        {
            "cycle": cycle,
            "employee": emp,
            "competency": comp,
            "required_level": required_level,
            "levels_ctx": levels_ctx,
            "rating_map": rating_map,
            "achieved_level": achieved_level,
            "current_level": current_level,
            "unlocked_max_level": unlocked_max_level,
            "PASS_RATING": PASS_RATING,
        },
    )


@login_required
def nine_box_dashboard(request):
    """
    9-Box: SOLO ADMINS (HR_ADMIN/superuser).
    """
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    cycle = get_current_cycle(request)
    if not cycle:
        return redirect("/admin/")

    dept_id = request.GET.get("department")
    role_id = request.GET.get("role")

    base_emps = Employee.objects.filter(active=True)
    if dept_id:
        base_emps = base_emps.filter(department_id=dept_id)
    if role_id:
        base_emps = base_emps.filter(role_id=role_id)

    scores = list(
        EmployeeCycleScore.objects.filter(cycle=cycle, employee__in=base_emps)
        .select_related("employee", "employee__user", "employee__department", "employee__role")
        .order_by("-qualitative_score", "-quantitative_score")
    )

    grid = terciles_for_scores(scores)

    order = [
        (3, 1), (3, 2), (3, 3),
        (2, 1), (2, 2), (2, 3),
        (1, 1), (1, 2), (1, 3),
    ]
    box_label = {k: v[1] for k, v in BOXES.items()}

    cells = []
    for qual, quant in order:
        cells.append(
            {
                "qual": qual,
                "quant": quant,
                "label": box_label[(qual, quant)],
                "items": grid.get((qual, quant), []),
            }
        )

    roles_qs = Role.objects.filter(department_id=dept_id).order_by("name") if dept_id else Role.objects.none()

    return render(
        request,
        "evaluations/nine_box.html",
        {
            "cycle": cycle,
            "cells": cells,
            "departments": Department.objects.all(),
            "roles": roles_qs,
            "dept_id": dept_id or "",
            "role_id": role_id or "",
        },
    )
