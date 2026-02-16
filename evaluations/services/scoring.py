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


def assign_tercile_by_rank(sorted_pairs):
    """
    Garantiza 1/3 de la población en cada tercil.
    sorted_pairs: [(employee, value), ...] ordenado por value ascendente.
    Devuelve {employee: tercile} con tercile en 1..3.
    """
    n = len(sorted_pairs)
    if n == 0:
        return {}
    third = max(1, n // 3)
    result = {}
    for i, (emp, _) in enumerate(sorted_pairs):
        if i < third:
            result[emp] = 1
        elif i < 2 * third:
            result[emp] = 2
        else:
            result[emp] = 3
    return result


def terciles_for_scores(scores):
    """
    Para una lista de EmployeeCycleScore (p. ej. filtrada por dept/rol),
    asigna terciles por rango sobre esa población.
    Devuelve {(qual_tercile, quant_tercile): [score_objs]}.
    """
    if not scores:
        return {}
    # Ordenar por cualitativo y cuantitativo para terciles
    ql_pairs = sorted(
        [(s, float(s.qualitative_score)) for s in scores],
        key=lambda x: (x[1], x[0].employee_id),
    )
    qt_pairs = sorted(
        [(s, float(s.quantitative_score)) for s in scores],
        key=lambda x: (x[1], x[0].employee_id),
    )
    n = len(scores)
    third = max(1, n // 3)

    qual_map = {}
    for i, (s, _) in enumerate(ql_pairs):
        qual_map[s.employee_id] = 1 if i < third else (2 if i < 2 * third else 3)

    quant_map = {}
    for i, (s, _) in enumerate(qt_pairs):
        quant_map[s.employee_id] = 1 if i < third else (2 if i < 2 * third else 3)

    grid = {}
    for s in scores:
        qt = (qual_map[s.employee_id], quant_map[s.employee_id])
        grid.setdefault(qt, []).append(s)
    return grid


def recompute_cycle_scores(cycle, employees_qs):
    """
    Calcula scores para todos, asigna terciles por rango (1/3 población en cada eje)
    y persiste el 9-box.
    """
    # 1) recalcular ejes
    results = []
    for emp in employees_qs:
        ql = compute_qualitative_score(emp, cycle)
        qt = compute_quantitative_score(emp, cycle)
        results.append((emp, ql, qt))

    # 2) terciles por rango: garantiza ~1/3 en cada tercil
    ql_sorted = sorted(results, key=lambda r: (float(r[1]), r[0].id))  # asc, ties by id
    qt_sorted = sorted(results, key=lambda r: (float(r[2]), r[0].id))

    qual_tercile_map = assign_tercile_by_rank([(r[0], r[1]) for r in ql_sorted])
    quant_tercile_map = assign_tercile_by_rank([(r[0], r[2]) for r in qt_sorted])

    # 3) persistir
    for emp, ql, qt in results:
        qual_t = qual_tercile_map.get(emp, 1)
        quant_t = quant_tercile_map.get(emp, 1)
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
