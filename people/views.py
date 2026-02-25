from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta

from .models import Invitation, Employee, Department, Role
from .forms import InviteForm, RegisterForm, DepartmentForm, RoleForm
from .services.access import is_hr
from .excel_import import build_sample_excel, parse_excel_import
from django.views.decorators.http import require_POST
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.models import User


def _create_pending_employee(first_name, last_name, email, department, role, manager):
    """Create (or reuse) a placeholder user+employee before invitation acceptance."""
    base = f"{first_name}_{last_name}".replace(" ", "_").lower()[:30]
    username = base
    n = 0
    while User.objects.filter(username=username).exists():
        n += 1
        username = f"{base}_{n}"[:150]

    user = User.objects.filter(email__iexact=email).first()
    if user:
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        if not user.has_usable_password():
            user.is_active = False
        user.save()
    else:
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=False,
        )
        user.set_unusable_password()
        user.save()

    emp, _ = Employee.objects.get_or_create(
        user=user,
        defaults={
            "department": department,
            "role": role,
            "manager": manager,
            "active": True,
        },
    )
    if not _:
        emp.department = department
        emp.role = role
        emp.manager = manager
        emp.active = True
        emp.save(update_fields=["department", "role", "manager", "active"])
    return emp


@login_required
def logout_confirm(request):
    if request.method == "POST" and request.POST.get("confirm") == "1":
        logout(request)
        return redirect("login")
    return render(request, "registration/logout.html")


@login_required
def api_roles_by_department(request, department_id):
    """JSON: roles for a department (for AJAX dropdowns)."""
    roles = list(
        Role.objects.filter(department_id=department_id).order_by("name").values("id", "name")
    )
    return JsonResponse({"roles": roles})


@require_POST
@login_required
def delete_employee(request, employee_id):
    """Soft-delete employee (HR only). Sets active=False."""
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)
    emp = get_object_or_404(Employee, id=employee_id)
    name = str(emp)
    emp.active = False
    emp.save()
    if emp.user:
        emp.user.is_active = False
        emp.user.save()
    messages.success(request, f"Usuario «{name}» desactivado correctamente.")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "invite_user"
    return redirect(next_url)


@login_required
def api_add_role(request):
    """AJAX: add role and return JSON (no page reload)."""
    if not is_hr(request.user):
        return JsonResponse({"ok": False, "error": "Forbidden"}, status=403)
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)
    form = RoleForm(request.POST)
    if form.is_valid():
        r = form.save()
        return JsonResponse({"ok": True, "id": r.id, "name": r.name, "department": r.department.name})
    return JsonResponse({"ok": False, "error": form.errors.as_json()}, status=400)


@login_required
def download_sample_excel(request):
    """Download Excel sample: template sheet + current users sheet."""
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)
    buffer = build_sample_excel()
    resp = HttpResponse(buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="talentmap_plantilla_usuarios.xlsx"'
    return resp


@login_required
def import_users_excel(request):
    """Import users from Excel upload."""
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)
    if request.method != "POST" or "excel_file" not in request.FILES:
        messages.error(request, "Selecciona un archivo Excel.")
        return redirect("invite_user")

    rows, parse_errors = parse_excel_import(request.FILES["excel_file"])
    if parse_errors:
        for e in parse_errors:
            messages.error(request, e)
        return redirect("invite_user")

    batch_managers_by_email = {}
    deferred_manager_updates = []

    def resolve_manager(r):
        if r.get("manager"):
            return r["manager"]
        manager_email_pending = (r.get("manager_email_pending") or "").strip().lower()
        if manager_email_pending:
            return batch_managers_by_email.get(manager_email_pending)
        mn, ma = r.get("manager_nombre", "").strip(), r.get("manager_apellido", "").strip()
        if mn and ma:
            matches = [
                manager for manager in batch_managers_by_email.values()
                if manager.user.first_name == mn and manager.user.last_name == ma
            ]
            if len(matches) == 1:
                return matches[0]
        return None

    created = 0
    for r in rows:
        first_name = r["first_name"]
        last_name = r["last_name"]
        email = r["email"]
        dept = r["department"]
        role = r["role"]
        manager = resolve_manager(r) or r.get("manager")

        existing_user = User.objects.filter(email__iexact=email).first()
        if (existing_user and existing_user.has_usable_password()) or Invitation.objects.filter(email__iexact=email, used_at__isnull=True, expires_at__gt=timezone.now()).exists():
            messages.warning(request, f"Fila {r['row']}: {email} ya existe o tiene invitación pendiente.")
            continue

        employee = _create_pending_employee(first_name, last_name, email, dept, role, manager)
        batch_managers_by_email[email.lower()] = employee

        inv = Invitation.objects.create(
            email=email,
            department=dept,
            role=role,
            manager=manager,
            employee=employee,
            created_by=request.user,
            expires_at=timezone.now() + timedelta(days=7),
        )

        if r.get("manager_email_pending") and not manager:
            deferred_manager_updates.append((employee, inv, r["manager_email_pending"].lower(), r["row"]))
        site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000")
        register_url = f"{site_url}/accounts/register/?token={inv.token}"
        send_mail(
            subject="Invitación a TalentMap",
            message=f"Hola,\n\nHas sido invitado a unirte a TalentMap.\n\nCrea tu cuenta aquí: {register_url}\n\nEste enlace expira en 7 días.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        created += 1

    for employee, inv, manager_email, row in deferred_manager_updates:
        mgr = batch_managers_by_email.get(manager_email) or Employee.objects.filter(user__email__iexact=manager_email, active=True).first()
        if mgr:
            employee.manager = mgr
            employee.save(update_fields=["manager"])
            inv.manager = mgr
            inv.save(update_fields=["manager"])
        else:
            messages.warning(
                request,
                f"Fila {row}: el manager '{manager_email}' no pudo vincularse automáticamente. Asignarlo manualmente luego.",
            )

    messages.success(request, f"Importados {created} usuarios.")
    return redirect("invite_user")


@login_required
def invite_user(request):
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    if request.method == "POST":
        form = InviteForm(request.POST)
        if form.is_valid():
            email = (form.cleaned_data.get("email") or "").strip()
            first_name = (form.cleaned_data.get("first_name") or "").strip()
            last_name = (form.cleaned_data.get("last_name") or "").strip()
            department = form.cleaned_data["department"]
            role = form.cleaned_data["role"]
            manager = form.cleaned_data.get("manager")

            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user and existing_user.has_usable_password():
                messages.error(request, f"Ya existe un usuario activo con el correo {email}.")
            else:
                pending = Invitation.objects.filter(email=email, used_at__isnull=True, expires_at__gt=timezone.now())
                if pending.exists():
                    messages.error(request, f"Ya existe una invitación pendiente para {email}.")
                else:
                    employee = _create_pending_employee(first_name, last_name, email, department, role, manager)
                    inv = Invitation.objects.create(
                        email=email,
                        department=department,
                        role=role,
                        manager=manager,
                        employee=employee,
                        created_by=request.user,
                        expires_at=timezone.now() + timedelta(days=7),
                    )
                    site_url = getattr(settings, "SITE_URL", f"http://127.0.0.1:8000")
                    register_url = f"{site_url}/accounts/register/?token={inv.token}"
                    send_mail(
                        subject="Invitación a TalentMap",
                        message=(
                            f"Hola {first_name},\n\n"
                            f"Has sido invitado a unirte a TalentMap como {role.name} en {department.name}.\n\n"
                            f"Crea tu cuenta aquí: {register_url}\n\n"
                            "Este enlace expira en 7 días."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    messages.success(request, f"Invitación enviada a {email}.")
                    return redirect("invite_user")
    else:
        dept_id = request.GET.get("department")
        initial = {}
        if dept_id:
            try:
                dept = Department.objects.get(pk=int(dept_id))
                initial["department"] = dept
            except (ValueError, TypeError, Department.DoesNotExist):
                pass
        form = InviteForm(initial=initial)

    pending_invites = Invitation.objects.filter(used_at__isnull=True, expires_at__gt=timezone.now()).select_related(
        "department", "role", "created_by"
    )[:20]

    return render(request, "people/invite.html", {
    "form": form,
    "pending_invites": pending_invites,
    "SITE_URL": getattr(settings, "SITE_URL", "http://127.0.0.1:8000"),
    })



def register_with_token(request):
    token_str = request.GET.get("token")
    if not token_str:
        return render(request, "people/register_invalid.html", {"reason": "missing_token"})

    inv = Invitation.objects.filter(token=token_str).select_related("department", "role", "manager", "employee", "employee__user").first()
    if not inv:
        return render(request, "people/register_invalid.html", {"reason": "invalid_token"})
    if not inv.is_valid:
        return render(request, "people/register_invalid.html", {"reason": "expired_or_used"})

    existing_user = inv.employee.user if inv.employee_id else User.objects.filter(email__iexact=inv.email).first()

    if request.method == "POST":
        form = RegisterForm(request.POST, instance=existing_user) if existing_user else RegisterForm(request.POST)
        if form.is_valid():
            if existing_user:
                user = existing_user
                user.username = form.cleaned_data["username"]
                user.first_name = form.cleaned_data["first_name"]
                user.last_name = form.cleaned_data["last_name"]
                user.email = inv.email
                user.set_password(form.cleaned_data["password1"])
                user.is_active = True
                user.save()
            else:
                user = form.save(commit=False)
                user.email = inv.email
                user.is_active = True
                user.save()

            employee = inv.employee
            if employee:
                if employee.user_id != user.id:
                    employee.user = user
                employee.department = inv.department
                employee.role = inv.role
                employee.manager = inv.manager
                employee.active = True
                employee.save()
            else:
                Employee.objects.update_or_create(
                    user=user,
                    defaults={
                        "department": inv.department,
                        "role": inv.role,
                        "manager": inv.manager,
                        "active": True,
                    },
                )

            inv.used_at = timezone.now()
            inv.accepted_user = user
            inv.save()

            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Cuenta creada correctamente.")
            return redirect("home")
    else:
        initial = {"email": inv.email}
        if existing_user:
            initial["username"] = existing_user.username
            initial["first_name"] = existing_user.first_name
            initial["last_name"] = existing_user.last_name
            form = RegisterForm(instance=existing_user, initial=initial)
        else:
            form = RegisterForm(initial=initial)

    return render(request, "registration/register.html", {"form": form, "invitation": inv})


@login_required
def config(request):
    """Admin-only: create departments and roles."""
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    dept_form = DepartmentForm()
    role_form = RoleForm()

    if request.method == "POST":
        if "add_department" in request.POST:
            dept_form = DepartmentForm(request.POST)
            if dept_form.is_valid():
                dept_form.save()
                messages.success(request, f"Departamento «{dept_form.instance.name}» creado.")
                return redirect("config")
        elif "add_role" in request.POST:
            role_form = RoleForm(request.POST)
            if role_form.is_valid():
                role_form.save()
                messages.success(request, f"Rol «{role_form.instance.name}» creado.")
                return redirect("config")

    departments = Department.objects.all().order_by("name")
    roles = Role.objects.select_related("department").order_by("department__name", "name")

    return render(request, "people/config.html", {
        "dept_form": dept_form,
        "role_form": role_form,
        "departments": departments,
        "roles": roles,
    })

@require_POST
@login_required
def resend_invitation(request, token):
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    inv = get_object_or_404(Invitation, token=token)

    if inv.used_at:
        messages.error(request, "Esta invitación ya fue usada.")
        return redirect("invite_user")

    # Extiende la expiración al reenviar (7 días desde hoy)
    inv.expires_at = timezone.now() + timedelta(days=7)
    inv.save(update_fields=["expires_at"])

    site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000")
    register_url = f"{site_url}/accounts/register/?token={inv.token}"

    send_mail(
        subject="Invitación a TalentMap (reenviada)",
        message=(
            "Hola,\n\n"
            "Te reenviamos tu invitación a TalentMap.\n\n"
            f"Crea tu cuenta aquí: {register_url}\n\n"
            "Este enlace expira en 7 días."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[inv.email],
        fail_silently=False,
    )

    messages.success(request, f"Invitación reenviada a {inv.email}.")
    return redirect("invite_user")


@require_POST
@login_required
def cancel_invitation(request, token):
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    inv = get_object_or_404(Invitation, token=token)

    if inv.used_at:
        messages.error(request, "No puedes cancelar una invitación ya usada.")
        return redirect("invite_user")

    # Soft-cancel: la hacemos expirar ahora (sin borrar registro)
    inv.expires_at = timezone.now()
    inv.save(update_fields=["expires_at"])

    messages.success(request, f"Invitación cancelada: {inv.email}.")
    return redirect("invite_user")
