from .services.access import is_hr
from .models import BrandingSettings


def hr_access(request):
    return {"is_hr": is_hr(request.user) if request.user.is_authenticated else False}


def branding(request):
    try:
        b = BrandingSettings.get_solo()
        return {"branding": b}
    except Exception:
        # Durante migraciones iniciales la tabla puede no existir.
        return {"branding": None}
