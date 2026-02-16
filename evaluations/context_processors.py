from evaluations.views import get_current_cycle
from evaluations.models import EvaluationCycle


def current_cycle(request):
    """Injects current_cycle and all_cycles for templates."""
    cycle = get_current_cycle(request) if request.user.is_authenticated else None
    all_cycles = list(EvaluationCycle.objects.order_by("-end_date")[:12]) if request.user.is_authenticated else []
    return {
        "current_cycle": cycle,
        "all_cycles": all_cycles,
    }
