import pytest
from datetime import date
from django.contrib.auth.models import User
from people.models import Department, Role, Employee
from evaluations.models import EvaluationCycle
from competencies.models import Competency, CompetencyLevel, LevelIndicator, RoleCompetencyRequirement
from playwright.sync_api import sync_playwright

@pytest.mark.django_db
def test_levels_lock_and_unlock(live_server):
    dep = Department.objects.create(name="Tech")
    role = Role.objects.create(name="Dev", department=dep)

    mgr_user = User.objects.create_user("mgr", password="pass")
    emp_user = User.objects.create_user("emp", password="pass")

    mgr = Employee.objects.create(user=mgr_user, department=dep, role=role)
    emp = Employee.objects.create(user=emp_user, department=dep, role=role, manager=mgr)

    cycle = EvaluationCycle.objects.create(name="2026", start_date=date(2026,1,1), end_date=date(2026,12,31))

    comp = Competency.objects.create(name="Comms", description="")
    levels = []
    for n in [1,2,3,4]:
        lvl = CompetencyLevel.objects.create(competency=comp, level=n, title=f"L{n}")
        LevelIndicator.objects.create(level=lvl, text=f"Beh {n}")
        levels.append(lvl)

    RoleCompetencyRequirement.objects.create(role=role, competency=comp, required_level=4, weight=1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # login
        page.goto(live_server.url + "/accounts/login/")
        page.fill('input[name="username"]', "mgr")
        page.fill('input[name="password"]', "pass")
        page.click('button[type="submit"]')

        # ir a la página de edición cualitativa (competencias)
        page.goto(live_server.url + f"/evaluations/employee/{emp.id}/competency/{comp.id}/qualitative/")

        # Nivel 4 debería estar bloqueado al inicio (data-locked="1")
        page.wait_for_selector('.js-level[data-level="4"]')
        assert page.locator('.js-level[data-level="4"]').get_attribute("data-locked") == "1"

        # helper: abrir el accordion del nivel si no está abierto
        def open_level(lvl):
            # botón del header del nivel
            btn = page.locator(f'.js-level[data-level="{lvl}"] .accordion-button')
            # si está colapsado, lo abrimos
            if "collapsed" in (btn.get_attribute("class") or ""):
                btn.click()
            # espera a que el contenido esté visible
            page.wait_for_selector(f'#collapse-{lvl}.show')

        # Marca nivel 1-3 como "Casi siempre" (value=3)
        for lvl in [1, 2, 3]:
            open_level(lvl)
            # como en el setup hay 1 indicador por nivel, este selector es único y estable:
            page.check(f'#collapse-{lvl} input.js-rating[value="3"]', force=True)

        page.wait_for_timeout(300)
        assert page.locator('.js-level[data-level="4"]').get_attribute("data-locked") == "0"

        open_level(2)
        page.check('#collapse-2 input.js-rating[value="1"]', force=True)
        page.wait_for_timeout(300)
        assert page.locator('.js-level[data-level="4"]').get_attribute("data-locked") == "1"


        browser.close()
