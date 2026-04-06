from django import template
register = template.Library()

@register.filter
def get(d, key):
    if not d:
        return None
    return d.get(key)


@register.filter
def rating_label(value):
    mapping = {
        1: "Nunca",
        2: "Casi nunca",
        3: "Casi siempre",
        4: "Siempre",
    }
    try:
        return mapping.get(int(value), "Sin dato")
    except (TypeError, ValueError):
        return "Sin dato"
