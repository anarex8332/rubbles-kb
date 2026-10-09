from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, css=''):
    return format_html(
        '<svg class="icon {}" width="20" height="20" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        css, static('icons.svg') + '?v=20261009-4', name,
    )
