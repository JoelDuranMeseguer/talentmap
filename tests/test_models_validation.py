from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from competencies.models import Competency
from competencies.models import RoleCompetencyRequirement
from evaluations.models import QuantitativeGoal, QualitativeIndicatorAssessment


@pytest.mark.django_db
class TestModelValidation:
    def test_quantitative_goal_rejects_invalid_ranges(self, report_employee, cycle, manager_user):
        goal = QuantitativeGoal(
            employee=report_employee,
            cycle=cycle,
            title="Invalid",
            weight_percent=Decimal("110"),
            completion_percent=Decimal("-1"),
            created_by=manager_user,
        )
        with pytest.raises(ValidationError):
            goal.full_clean()

    def test_role_competency_requirement_rejects_invalid_values(self, role):
        comp = Competency.objects.create(name="System Design")
        req = RoleCompetencyRequirement(
            role=role,
            competency=comp,
            required_level=0,
            weight=Decimal("0"),
        )
        with pytest.raises(ValidationError):
            req.clean()

    def test_qualitative_assessment_rejects_invalid_rating(self, report_employee, cycle, competency_setup, manager_user):
        assessment = QualitativeIndicatorAssessment(
            employee=report_employee,
            cycle=cycle,
            indicator=competency_setup["i1"],
            rating=5,
            assessed_by=manager_user,
        )
        with pytest.raises(ValidationError):
            assessment.full_clean()
