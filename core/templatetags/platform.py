from django import template

from core.models import SiteSettings

register = template.Library()


@register.filter
def steps(n):
    """12 → «12 степов» с правильным склонением."""
    n = n or 0
    return f"{n} {SiteSettings.get().plural(n)}"


@register.filter
def get_item(d, key):
    return d.get(key) if d else None
