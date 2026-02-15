from decimal import Decimal
from django.db.models import Sum
from evaluations.models import QualitativeGoal, QuantitativeIndicatorAssessment, EmployeeCycleScore
from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement

BOXES = {
    # (qual_tercile, quant_tercile): (code, label)
    (3, 3): ("STAR", "Estrellas"),
    (3, 2): ("GROW_FAST", "Alto potencial"),
    (3, 1): ("SPECIALIST", "Especialistas (calidad alta)"),
    (2, 3): ("EXECUTE", "Alto rendimiento"),
    (2, 2): ("SOLID", "Sólidos"),
    (2, 1): ("INCONSISTENT", "Irregulares"),
    (1, 3): ("RAW_TALENT", "Talento en bruto"),
    (1, 2): ("NEEDS_SUPPORT", "Necesitan apoyo"),
    (1, 1): ("RISK", "En riesgo"),
}

def compute_qualitative_score(employee, cycle) -> Decimal:
    goals = QualitativeGoal.objects.filter(employee=employee, cycle=cycle)
    total = Decimal("0")
    for g in goals:
        # contrib = weight% * completion% / 100
        total += (g.weight_percent * g.completion_percent) / Decimal("100")
    # total ya está en 0..100 si weights suman 100
    return max(Decimal("0"), min(Decimal("100"), total))


def _achieved_level_for_competency(employee, cycle, competency: Competency) -> int:
    """
    Nivel más alto alcanzado: un nivel está alcanzado si TODOS sus indicadores están met=True.
    """
    levels = competency.levels.all().prefetch_related("indicators")
    achieved = 0
    # Para llegar al nivel n, debe cumplir los indicadores de cada nivel (o solo del nivel? aquí usamos "por nivel")
    for lvl in levels:
        inds = list(lvl.indicators.all())
        if not inds:
            # si un nivel no tiene indicadores, lo consideramos alcanzable automáticamente
            achieved = max(achieved, lvl.level)
            continue

        met_count = QuantitativeIndicatorAssessment.objects.filter(
            employee=employee, cycle=cycle, indicator__in=inds, met=True
        ).count()

        if met_count == len(inds):
            achieved = max(achieved, lvl.level)
        else:
            # si falla un nivel, no seguimos subiendo
            break

    return achieved


def compute_quantitative_score(employee, cycle) -> Decimal:
    """
    Compara nivel alcanzado vs nivel requerido por rol en cada competencia.
    Score por competencia: min(achieved/required, 1) * 100
    Agrega ponderado por weight.
    """
    role = employee.role
    reqs = RoleCompetencyRequirement.objects.filter(role=role).select_related("competency")

    if not reqs.exists():
        return Decimal("0")

    weighted_sum = Decimal("0")
    weight_total = Decimal("0")

    for req in reqs:
        required = max(1, int(req.required_level))
        achieved = _achieved_level_for_competency(employee, cycle, req.competency)
        ratio = Decimal(min(achieved / required, 1))
        score = ratio * Decimal("100")
        w = req.weight
        weighted_sum += score * w
        weight_total += w

    if weight_total == 0:
        return Decimal("0")

    total = weighted_sum / weight_total
    return max(Decimal("0"), min(Decimal("100"), total))


def tercile_thresholds(values):
    """
    values: lista Decimal/float
    devuelve (t1, t2) donde:
      <= t1 => tercil 1
      <= t2 => tercil 2
      > t2  => tercil 3
    """
    vals = sorted([float(v) for v in values])
    if not vals:
        return (0.0, 0.0)
    n = len(vals)
    t1 = vals[int(n * 0.3333)]
    t2 = vals[int(n * 0.6666)]
    return (t1, t2)


def assign_tercile(value, t1, t2) -> int:
    v = float(value)
    if v <= t1:
        return 1
    if v <= t2:
        return 2
    return 3


def recompute_cycle_scores(cycle, employees_qs):
    """
    Calcula scores para todos, calcula terciles y asigna 9-box.
    """
    # 1) recalcular ejes
    results = []
    for emp in employees_qs:
        ql = compute_qualitative_score(emp, cycle)
        qt = compute_quantitative_score(emp, cycle)
        results.append((emp, ql, qt))

    # 2) terciles globales
    ql_t1, ql_t2 = tercile_thresholds([r[1] for r in results])
    qt_t1, qt_t2 = tercile_thresholds([r[2] for r in results])

    # 3) persistir
    for emp, ql, qt in results:
        qual_t = assign_tercile(ql, ql_t1, ql_t2)
        quant_t = assign_tercile(qt, qt_t1, qt_t2)
        code, label = BOXES[(qual_t, quant_t)]

        EmployeeCycleScore.objects.update_or_create(
            employee=emp, cycle=cycle,
            defaults={
                "qualitative_score": ql,
                "quantitative_score": qt,
                "qual_tercile": qual_t,
                "quant_tercile": quant_t,
                "box_code": code,
                "box_label": label,
            }
        )
