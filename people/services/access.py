from people.models import Employee

def is_hr(user) -> bool:
    return user.is_superuser or user.groups.filter(name="HR_ADMIN").exists()

def managed_employees_qs(user):
    if is_hr(user):
        return Employee.objects.all()
    try:
        me = user.employee
    except Employee.DoesNotExist:
        return Employee.objects.none()
    # versión simple: solo reportes directos
    return Employee.objects.filter(manager=me)
