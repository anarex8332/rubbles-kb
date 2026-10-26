from django import template
from django.templatetags.static import static
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, css=''):
    return format_html(
        '<svg class="icon {}" width="20" height="20" aria-hidden="true" focusable="false"><use href="{}#{}"></use></svg>',
        css, static('icons.svg') + '?v=20261024-1', name,
    )


# Иконки разделов из спрайта static/icons.svg; поле Section.icon хранит имя иконки.
SECTION_ICONS = {'building-2', 'trending-up', 'tag', 'package', 'settings', 'info'}


@register.filter
def section_icon(section):
    name = (getattr(section, 'icon', '') or '').strip()
    return name if name in SECTION_ICONS else 'folder'


@register.filter
def release_html(text):
    """Описание релиза: короткая строка без точки — подзаголовок, «•» — пункт списка, остальное — абзац."""
    from django.utils.html import escape
    from django.utils.safestring import mark_safe
    out, items = [], []
    for line in (text or '').splitlines():
        line = line.strip()
        if line.startswith('•'):
            items.append(f'<li>{escape(line[1:].strip())}</li>')
            continue
        if items:
            out.append('<ul>' + ''.join(items) + '</ul>')
            items = []
        if not line:
            continue
        if len(line) <= 40 and not line.endswith(('.', ':', ';')):
            out.append(f'<h4>{escape(line)}</h4>')
        else:
            out.append(f'<p>{escape(line)}</p>')
    if items:
        out.append('<ul>' + ''.join(items) + '</ul>')
    return mark_safe(''.join(out))
