import re

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.html import escape
from django.utils.safestring import mark_safe, SafeData

register = template.Library()


def _symbol_replace(matchobj):
    """Helper function for regex symbol replace."""

    code = matchobj.group(1).upper()

    # Special cases for Unicode text replace.  Anything else, use MTG symbol tags.
    if code == "-":
        return "&#8212;"
    elif code == ".":
        return "&#8226;"
    else:
        return f"""<abbr class="card-symbol card-symbol-{code}" title="{code}">{matchobj.group(0)}</abbr>"""


def _reminder_text_replace(matchobj):
    """Helper function for regex italic reminder text replace."""

    return f"""<em>{matchobj.group(1)}</em>"""


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def replacesymbols(value, autoescape=True):
    """Replace symbols in card text with images using CSS classes."""

    autoescape = autoescape and not isinstance(value, SafeData)
    if autoescape:
        value = escape(value)

    # Replace reminder text italics with surrounding span tag.
    value = re.sub(r'{i}(.*){/i}', _reminder_text_replace, value, flags=re.IGNORECASE)

    # Replace symbols last.
    return mark_safe(re.sub(r'\{([^}]+)}', _symbol_replace, value, flags=re.IGNORECASE))


@register.filter(is_safe=True, needs_autoescape=True)
@stringfilter
def removesymbols(value, autoescape=True):
    """Remove all curly bracket symbols (e.g. for card name or type lines)."""

    autoescape = autoescape and not isinstance(value, SafeData)
    if autoescape:
        value = escape(value)

    return mark_safe(re.sub(r'\{([^}]+)}', '', value, flags=re.IGNORECASE))
