from decimal import Decimal

from competencies.models import Competency, RoleCompetencyRequirement
from evaluations.models import (
    EmployeeCycleScore,
    QualitativeIndicatorAssessment,
    QuantitativeGoal,
)

# Para subir de nivel, el comportamiento debe estar en Casi siempre (3) o Siempre (4)
PASS_RATING = 3

BOXES = {
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


def compute_quantitative_score(employee, cycle) -> Decimal:
    """
    CUANTITATIVO = metas con pesos (suman 100) y % completado.
    """
    goals = QuantitativeGoal.objects.filter(employee=employee, cycle=cycle)
    total = Decimal("0")
    for g in goals:
        total += (g.weight_percent * g.completion_percent) / Decimal("100")
    return max(Decimal("0"), min(Decimal("100"), total))


def _achieved_level_for_competency(employee, cycle, competency: Competency) -> int:
    """
    CUALITATIVO: nivel alcanzado si TODOS los comportamientos del nivel están en rating >= PASS_RATING.
    Regla: si fallas un nivel, no sigues subiendo (secuencial).
    """
    levels = competency.levels.all().prefetch_related("indicators").order_by("level")
    achieved = 0

    for lvl in levels:
        inds = list(lvl.indicators.all())
        if not inds:
            # Nivel sin comportamientos = configuración incompleta.
            # No lo contamos como "logrado" y detenemos la progresión secuencial.
            break

        ok = QualitativeIndicatorAssessment.objects.filter(
            employee=employee,
            cycle=cycle,
            indicator__in=inds,
            rating__gte=PASS_RATING,
        ).count()

        if ok == len(inds):
            achieved = max(achieved, lvl.level)
        else:
            break

    return achieved


def compute_qualitative_score(employee, cycle) -> Decimal:
    """
    CUALITATIVO = compara nivel alcanzado vs nivel requerido por rol para cada competencia.
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


def assign_tercile_by_rank(sorted_pairs):
    """
    sorted_pairs: [(obj, value), ...] ordenado ascendente por value.
    Devuelve {obj: tercile} con tercile 1..3 garantizando ~1/3 en cada tercil.
    """
    n = len(sorted_pairs)
    if n == 0:
        return {}

    third = max(1, n // 3)
    result = {}
    for i, (obj, _) in enumerate(sorted_pairs):
        if i < third:
            result[obj] = 1
        elif i < 2 * third:
            result[obj] = 2
        else:
            result[obj] = 3
    return result


def terciles_for_scores(scores):
    """
    scores: lista de EmployeeCycleScore filtrada (p.ej. por dept/rol).
    Devuelve {(qual_tercile, quant_tercile): [score_objs]} asignando terciles por rango en ESA población.
    """
    if not scores:
        return {}

    ql_pairs = sorted([(s, float(s.qualitative_score)) for s in scores], key=lambda x: (x[1], x[0].employee_id))
    qt_pairs = sorted([(s, float(s.quantitative_score)) for s in scores], key=lambda x: (x[1], x[0].employee_id))

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
        key = (qual_map[s.employee_id], quant_map[s.employee_id])
        grid.setdefault(key, []).append(s)
    return grid


def recompute_cycle_scores(cycle, employees_qs):
    """
    Calcula scores para employees_qs, asigna terciles por rango y persiste el 9-box.
    """
    results = []
    for emp in employees_qs:
        ql = compute_qualitative_score(emp, cycle)
        qt = compute_quantitative_score(emp, cycle)
        results.append((emp, ql, qt))

    ql_sorted = sorted(results, key=lambda r: (float(r[1]), r[0].id))
    qt_sorted = sorted(results, key=lambda r: (float(r[2]), r[0].id))

    qual_tercile_map = assign_tercile_by_rank([(r[0], r[1]) for r in ql_sorted])
    quant_tercile_map = assign_tercile_by_rank([(r[0], r[2]) for r in qt_sorted])

    for emp, ql, qt in results:
        qual_t = qual_tercile_map.get(emp, 1)
        quant_t = quant_tercile_map.get(emp, 1)
        code, label = BOXES[(qual_t, quant_t)]

        EmployeeCycleScore.objects.update_or_create(
            employee=emp,
            cycle=cycle,
            defaults={
                "qualitative_score": ql,
                "quantitative_score": qt,
                "qual_tercile": qual_t,
                "quant_tercile": quant_t,
                "box_code": code,
                "box_label": label,
            },
        )
