from django.core.management.base import BaseCommand
from people.models import Employee
from evaluations.models import EvaluationCycle
from evaluations.services.scoring import recompute_cycle_scores

class Command(BaseCommand):
    help = "Recalcula scores y 9-box para un ciclo"

    def add_arguments(self, parser):
        parser.add_argument("cycle_id", type=int)

    def handle(self, *args, **opts):
        cycle = EvaluationCycle.objects.get(id=opts["cycle_id"])
        employees = Employee.objects.filter(active=True).select_related("role", "department", "user")
        recompute_cycle_scores(cycle, employees)
        self.stdout.write(self.style.SUCCESS(f"OK: scores recalculados para {cycle.name}"))
