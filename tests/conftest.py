from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone


@pytest.fixture
def department():
    from people.models import Department

    return Department.objects.create(name="Engineering")


@pytest.fixture
def role(department):
    from people.models import Role

    return Role.objects.create(name="Backend Engineer", department=department)


@pytest.fixture
def cycle():
    from evaluations.models import EvaluationCycle

    return EvaluationCycle.objects.create(name="FY2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31))


@pytest.fixture
def hr_user():
    from django.contrib.auth.models import User

    return User.objects.create_superuser("hr", "hr@example.com", "pass")


@pytest.fixture
def manager_user():
    from django.contrib.auth.models import User

    return User.objects.create_user("manager", password="pass")


@pytest.fixture
def report_user():
    from django.contrib.auth.models import User

    return User.objects.create_user("report", password="pass")


@pytest.fixture
def other_user():
    from django.contrib.auth.models import User

    return User.objects.create_user("other", password="pass")


@pytest.fixture
def manager_employee(manager_user, department, role):
    from people.models import Employee

    return Employee.objects.create(user=manager_user, department=department, role=role)


@pytest.fixture
def report_employee(report_user, manager_employee, department, role):
    from people.models import Employee

    return Employee.objects.create(
        user=report_user,
        department=department,
        role=role,
        manager=manager_employee,
    )


@pytest.fixture
def other_employee(other_user, department, role):
    from people.models import Employee

    return Employee.objects.create(user=other_user, department=department, role=role)


@pytest.fixture
def invitation(hr_user, department, role):
    from people.models import Invitation

    return Invitation.objects.create(
        email="invitee@example.com",
        department=department,
        role=role,
        created_by=hr_user,
        expires_at=timezone.now() + timedelta(days=7),
    )


@pytest.fixture
def competency_setup(role):
    from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement

    comp = Competency.objects.create(name="Communication")
    l1 = CompetencyLevel.objects.create(competency=comp, level=1, title="L1")
    l2 = CompetencyLevel.objects.create(competency=comp, level=2, title="L2")
    i1 = LevelIndicator.objects.create(level=l1, text="Clear updates")
    i2 = LevelIndicator.objects.create(level=l1, text="Active listening")
    i3 = LevelIndicator.objects.create(level=l2, text="Constructive feedback")
    RoleCompetencyRequirement.objects.create(role=role, competency=comp, required_level=2, weight=Decimal("1"))
    return {"competency": comp, "l1": l1, "l2": l2, "i1": i1, "i2": i2, "i3": i3}
