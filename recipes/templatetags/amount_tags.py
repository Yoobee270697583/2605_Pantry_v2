from django import template
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def amount(value):
    """A quantity with up to 2 decimal places and no zeros on the end - 7.5 not 7.50, and 2 not 2.00:
        {% load amount_tags %}
        {{ item.quantity|amount }}
    Django's own floatformat:"-2" is nearly this, but it shows 7.5 as 7.50."""
    # floatformat does the rounding - it always gives 2 decimals ("7.50", "2.00"), or "" if it isn't a number
    text = floatformat(value, 2)
    if "." in text:
        # take the zeros off the end, then the dot if nothing is left after it: "7.50" -> "7.5", "2.00" -> "2"
        text = text.rstrip("0").rstrip(".")
    return text
