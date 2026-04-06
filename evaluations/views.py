from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from competencies.models import Competency, CompetencyLevel, RoleCompetencyRequirement
from evaluations.forms import GoalFormSet
from evaluations.models import (
    EmployeeCycleScore,
    EvaluationCycle,
    TalentMapSettings,
    QualitativeAxisMethod,
    QualitativeIndicatorAssessment,
    QualitativeIndicatorSelfAssessment,
    QuantitativeGoal,
)
from evaluations.services.scoring import BOXES, PASS_RATING, recompute_cycle_scores, terciles_for_scores
from people.models import Department, Employee, Role
from people.services.access import is_hr, managed_employees_qs
from django.contrib import messages


SESSION_CYCLE_KEY = "eval_current_cycle_id"

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


def _cycle_or_admin_redirect(request):
    cycle = get_current_cycle(request)
    if cycle:
        return cycle, None
    return None, redirect("/admin/")


def _can_manage_employee(user, employee: Employee) -> bool:
    return is_hr(user) or managed_employees_qs(user).filter(id=employee.id).exists()


@login_required
def cycle_home(request):
    cycle, fallback = _cycle_or_admin_redirect(request)
    if fallback:
        return fallback

    try:
        me = request.user.employee
    except Exception:
        return render(request, "evaluations/no_employee.html", {"cycle": cycle})

    my_score = EmployeeCycleScore.objects.filter(employee=me, cycle=cycle).first()
    is_manager = managed_employees_qs(request.user).exists()
    hr = is_hr(request.user)

    can_edit_me = hr or (me.manager_id and me.manager.user_id == request.user.id)
    can_self_evaluate = hasattr(request.user, "employee")

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
            "can_self_evaluate": can_self_evaluate,
        },
    )


@login_required
def team_overview(request):
    cycle, fallback = _cycle_or_admin_redirect(request)
    if fallback:
        return fallback

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
    cycle, fallback = _cycle_or_admin_redirect(request)
    if fallback:
        return fallback

    emp = get_object_or_404(Employee, id=employee_id)

    allowed = _can_manage_employee(request.user, emp)
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

    return render(
        request,
        "evaluations/edit_quantitative.html",
        {"cycle": cycle, "employee": emp, "formset": formset},
    )


@login_required
def competency_picker(request, employee_id):
    """
    Selector de competencias (para editar CUALITATIVO).
    """
    cycle, fallback = _cycle_or_admin_redirect(request)
    if fallback:
        return fallback

    emp = get_object_or_404(Employee, id=employee_id)
    is_self_eval = hasattr(request.user, "employee") and request.user.employee.id == emp.id
    allowed = _can_manage_employee(request.user, emp) or is_self_eval
    if not allowed:
        return render(request, "evaluations/forbidden.html", status=403)

    reqs = list(
        RoleCompetencyRequirement.objects.filter(role=emp.role)
        .select_related("competency")
        .order_by("competency__name")
    )

    model_cls = QualitativeIndicatorSelfAssessment if is_self_eval else QualitativeIndicatorAssessment
    req_rows = []
    for req in reqs:
        levels = (
            CompetencyLevel.objects.filter(competency=req.competency, level__lte=req.required_level)
            .prefetch_related("indicators")
            .order_by("level")
        )
        indicator_ids = [ind.id for lvl in levels for ind in lvl.indicators.all()]
        ratings = model_cls.objects.filter(employee=emp, cycle=cycle, indicator_id__in=indicator_ids)
        rating_map = {a.indicator_id: int(a.rating) for a in ratings}
        achieved_level, _, _ = _qual_progress(levels, rating_map, int(req.required_level))
        req_rows.append({"req": req, "achieved_level": achieved_level})

    return render(
        request,
        "evaluations/competency_picker.html",
        {"cycle": cycle, "employee": emp, "req_rows": req_rows, "is_self_eval": is_self_eval},
    )


def _qual_progress(levels, rating_map, required_level):
    """
    Devuelve (achieved_level, unlocked_max_level, missing_level)
    - achieved_level: último nivel completado (con indicadores).
    - unlocked_max_level: primer nivel NO completado (editable) o nivel con config incompleta.
    - missing_level: número de nivel sin indicadores (si existe).
    """
    achieved = 0
    unlocked = 1
    missing_level = None

    for lvl in levels:
        inds = list(lvl.indicators.all())
        if not inds:
            missing_level = lvl.level
            unlocked = lvl.level
            break

        passed = sum(1 for ind in inds if rating_map.get(ind.id, 1) >= PASS_RATING)
        if passed == len(inds):
            achieved = lvl.level
            unlocked = min(lvl.level + 1, required_level)
        else:
            unlocked = lvl.level
            break

    unlocked = max(1, min(unlocked, required_level))
    return achieved, unlocked, missing_level


@login_required
def edit_qualitative(request, employee_id, competency_id):
    """ CUALITATIVO = competencias→niveles→comportamientos con escala Nunca/Casi nunca/Casi siempre/Siempre. """
    cycle, fallback = _cycle_or_admin_redirect(request)
    if fallback:
        return fallback

    emp = get_object_or_404(Employee, id=employee_id)
    comp = get_object_or_404(Competency, id=competency_id)

    is_self_eval = hasattr(request.user, "employee") and request.user.employee.id == emp.id
    allowed = _can_manage_employee(request.user, emp) or is_self_eval
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

    model_cls = QualitativeIndicatorSelfAssessment if is_self_eval else QualitativeIndicatorAssessment

    existing = model_cls.objects.filter(employee=emp, cycle=cycle, indicator_id__in=indicator_ids)
    rating_map = {a.indicator_id: int(a.rating) for a in existing}

    self_rating_map = {}
    if not is_self_eval:
        official_ids = set(
            QualitativeIndicatorAssessment.objects.filter(
                employee=emp, cycle=cycle, indicator_id__in=indicator_ids
            ).values_list("indicator_id", flat=True)
        )
        self_existing = QualitativeIndicatorSelfAssessment.objects.filter(
            employee=emp, cycle=cycle, indicator_id__in=indicator_ids
        )
        self_rating_map = {a.indicator_id: int(a.rating) for a in self_existing if a.indicator_id in official_ids}

    achieved_level, unlocked_max_level, missing_level = _qual_progress(levels, rating_map, required_level)
    current_level = unlocked_max_level

    if request.method == "POST":
        with transaction.atomic():
            post_rating_map = dict(rating_map)
            dynamic_unlocked_max = unlocked_max_level
            for lvl in levels:
                # Enforce server-side locking: no aceptar niveles bloqueados.
                if lvl.level > dynamic_unlocked_max:
                    continue

                inds = list(lvl.indicators.all())
                for ind in lvl.indicators.all():
                    raw = request.POST.get(f"ind_{ind.id}")
                    try:
                        rating = int(raw) if raw else 1
                    except ValueError:
                        rating = 1
                    rating = max(1, min(4, rating))

                    model_cls.objects.update_or_create(
                        employee=emp,
                        cycle=cycle,
                        indicator=ind,
                        defaults={"rating": rating, **({} if is_self_eval else {"assessed_by": request.user})},
                    )
                    post_rating_map[ind.id] = rating

                # Recalcula desbloqueo dentro del mismo submit para no obligar a guardar entre niveles.
                if inds:
                    passed = sum(1 for ind in inds if post_rating_map.get(ind.id, 1) >= PASS_RATING)
                    if passed == len(inds):
                        dynamic_unlocked_max = min(lvl.level + 1, required_level)
                    else:
                        dynamic_unlocked_max = lvl.level
                        break

        if is_self_eval:
            messages.success(request, "Autoevaluación cualitativa guardada.")
        else:
            _recompute_company(cycle)
            messages.success(request, "Cualitativo guardado.")
        return redirect("edit_qualitative_competency", employee_id=emp.id, competency_id=comp.id)

    # GET render
    levels_ctx = []
    for lvl in levels:
        inds = list(lvl.indicators.all())
        total = len(inds)
        passed = sum(1 for ind in inds if rating_map.get(ind.id, 1) >= PASS_RATING)

        levels_ctx.append(
            {
                "level": lvl,
                "indicators": inds,
                "passed": passed,
                "total": total,
                "missing_config": (total == 0),
                "locked_initial": (lvl.level > unlocked_max_level),
            }
        )

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
            "missing_level": missing_level,
            "PASS_RATING": PASS_RATING,
            "is_self_eval": is_self_eval,
            "self_rating_map": self_rating_map,
        },
    )



@login_required
def nine_box_dashboard(request):
    """
    9-Box: SOLO ADMINS (HR_ADMIN/superuser).
    """
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    cycle, fallback = _cycle_or_admin_redirect(request)
    if fallback:
        return fallback

    settings_obj = TalentMapSettings.get_solo()
    if request.method == "POST":
        method = request.POST.get("qualitative_axis_method")
        if method in {QualitativeAxisMethod.THIRDS, QualitativeAxisMethod.GAUSSIAN}:
            settings_obj.qualitative_axis_method = method

        try:
            settings_obj.top_min_above = max(1, int(request.POST.get("top_min_above", settings_obj.top_min_above)))
            settings_obj.middle_max_below = max(0, int(request.POST.get("middle_max_below", settings_obj.middle_max_below)))
        except (TypeError, ValueError):
            messages.error(request, "Parámetros inválidos para la configuración del eje cualitativo.")
            return redirect("nine_box")

        settings_obj.save()
        _recompute_company(cycle)
        messages.success(request, "Configuración del mapa de talento actualizada.")
        return redirect("nine_box")

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
            "talentmap_settings": settings_obj,
            "qualitative_axis_choices": QualitativeAxisMethod.choices,
        },
    )
