from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from competencies.excel_profiles import build_role_profile_template, import_role_profile_template
from competencies.models import Competency, RoleCompetencyRequirement
from people.models import Role
from people.services.access import is_hr


@login_required
def role_profile_config(request):
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    roles = Role.objects.select_related("department").order_by("department__name", "name")
    competencies = Competency.objects.order_by("name")

    selected_role_id = request.GET.get("role") or request.POST.get("role")
    selected_role = None
    req_map = {}

    if selected_role_id:
        selected_role = get_object_or_404(Role, id=selected_role_id)
        req_map = {
            r.competency_id: r
            for r in RoleCompetencyRequirement.objects.filter(role=selected_role).select_related("competency")
        }

    if request.method == "POST":
        if "save_profile" in request.POST:
            if not selected_role:
                messages.error(request, "Selecciona un rol para guardar su perfil ideal.")
                return redirect("role_profile_config")

            saved = 0
            for competency in competencies:
                raw = (request.POST.get(f"comp_{competency.id}") or "").strip()
                if not raw:
                    continue
                try:
                    level = int(raw)
                except ValueError:
                    messages.error(request, f"Nivel inválido para {competency.name}.")
                    return redirect(f"{request.path}?role={selected_role.id}")

                RoleCompetencyRequirement.objects.update_or_create(
                    role=selected_role,
                    competency=competency,
                    defaults={"required_level": level, "weight": 1},
                )
                saved += 1

            messages.success(request, f"Perfil ideal actualizado para {selected_role.name}. ({saved} filas)")
            return redirect(f"{request.path}?role={selected_role.id}")

        if "import_profile" in request.POST:
            if "excel_file" not in request.FILES:
                messages.error(request, "Selecciona un archivo Excel para importar.")
                return redirect("role_profile_config")

            upserts, errors = import_role_profile_template(request.FILES["excel_file"])
            for e in errors:
                messages.error(request, e)
            if upserts:
                messages.success(request, f"Importación completada. Celdas aplicadas: {upserts}.")
            return redirect("role_profile_config")

    return render(
        request,
        "competencies/role_profile_config.html",
        {
            "roles": roles,
            "competencies": competencies,
            "selected_role": selected_role,
            "req_map": req_map,
        },
    )


@login_required
def download_role_profile_template(request):
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    buffer = build_role_profile_template()
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="perfil_ideal_roles.xlsx"'
    return response
