from .services.access import is_hr


def hr_access(request):
    return {"is_hr": is_hr(request.user) if request.user.is_authenticated else False}
