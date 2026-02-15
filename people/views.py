from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta

from .models import Invitation, Employee, Department
from .forms import InviteForm, RegisterForm
from .services.access import is_hr


@login_required
def logout_confirm(request):
    if request.method == "POST" and request.POST.get("confirm") == "1":
        logout(request)
        return redirect("login")
    return render(request, "registration/logout.html")


@login_required
def invite_user(request):
    if not is_hr(request.user):
        return render(request, "evaluations/forbidden.html", status=403)

    if request.method == "POST":
        form = InviteForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            department = form.cleaned_data["department"]
            role = form.cleaned_data["role"]

            # Check for existing pending invite
            pending = Invitation.objects.filter(email=email, used_at__isnull=True, expires_at__gt=timezone.now())
            if pending.exists():
                messages.error(request, f"Ya existe una invitación pendiente para {email}.")
            else:
                inv = Invitation.objects.create(
                    email=email,
                    department=department,
                    role=role,
                    created_by=request.user,
                    expires_at=timezone.now() + timedelta(days=7),
                )
                site_url = getattr(settings, "SITE_URL", f"http://127.0.0.1:8000")
                register_url = f"{site_url}/accounts/register/?token={inv.token}"

                send_mail(
                    subject="Invitación a TalentMap",
                    message=f"Hola,\n\nHas sido invitado a unirte a TalentMap.\n\nCrea tu cuenta aquí: {register_url}\n\nEste enlace expira en 7 días.",
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

    return render(request, "people/invite.html", {"form": form, "pending_invites": pending_invites})


def register_with_token(request):
    token_str = request.GET.get("token")
    if not token_str:
        return render(request, "people/register_invalid.html", {"reason": "missing_token"})

    inv = Invitation.objects.filter(token=token_str).select_related("department", "role").first()
    if not inv:
        return render(request, "people/register_invalid.html", {"reason": "invalid_token"})
    if not inv.is_valid:
        return render(request, "people/register_invalid.html", {"reason": "expired_or_used"})

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = inv.email
            user.save()

            Employee.objects.create(user=user, department=inv.department, role=inv.role)

            inv.used_at = timezone.now()
            inv.accepted_user = user
            inv.save()

            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Cuenta creada correctamente.")
            return redirect("home")
    else:
        form = RegisterForm(initial={"email": inv.email})

    return render(request, "registration/register.html", {"form": form, "invitation": inv})
