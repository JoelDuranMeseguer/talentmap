from decimal import Decimal

import pytest

from evaluations.models import BehaviorRating, EmployeeCycleScore, QualitativeIndicatorAssessment, QuantitativeGoal
from evaluations.services.scoring import compute_qualitative_score, compute_quantitative_score, recompute_cycle_scores
from people.models import Employee


@pytest.mark.django_db
class TestScoringAndNineBox:
    def test_quantitative_score_weighted_average(self, report_employee, cycle, manager_user):
        QuantitativeGoal.objects.create(
            employee=report_employee,
            cycle=cycle,
            title="Goal A",
            weight_percent=Decimal("70"),
            completion_percent=Decimal("100"),
            created_by=manager_user,
        )
        QuantitativeGoal.objects.create(
            employee=report_employee,
            cycle=cycle,
            title="Goal B",
            weight_percent=Decimal("30"),
            completion_percent=Decimal("50"),
            created_by=manager_user,
        )

        score = compute_quantitative_score(report_employee, cycle)
        assert score.quantize(Decimal("0.01")) == Decimal("85.00")

    def test_qualitative_score_respects_sequential_progression(
        self,
        report_employee,
        cycle,
        competency_setup,
        manager_user,
    ):
        for indicator in [competency_setup["i1"], competency_setup["i2"]]:
            QualitativeIndicatorAssessment.objects.create(
                employee=report_employee,
                cycle=cycle,
                indicator=indicator,
                rating=BehaviorRating.OFTEN,
                assessed_by=manager_user,
            )
        QualitativeIndicatorAssessment.objects.create(
            employee=report_employee,
            cycle=cycle,
            indicator=competency_setup["i3"],
            rating=BehaviorRating.RARELY,
            assessed_by=manager_user,
        )

        score = compute_qualitative_score(report_employee, cycle)
        assert score.quantize(Decimal("0.01")) == Decimal("50.00")

    def test_recompute_cycle_scores_persists_9box_classification(
        self,
        manager_employee,
        report_employee,
        other_employee,
        cycle,
    ):
        recompute_cycle_scores(cycle, Employee.objects.filter(id__in=[manager_employee.id, report_employee.id, other_employee.id]))

        assert EmployeeCycleScore.objects.filter(employee=report_employee, cycle=cycle).exists()
        score = EmployeeCycleScore.objects.get(employee=report_employee, cycle=cycle)
        assert score.box_code
        assert score.box_label
        assert 1 <= score.qual_tercile <= 3
        assert 1 <= score.quant_tercile <= 3
