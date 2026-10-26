"""Автоматическое описание изменений между двумя версиями статьи.

Если автор не заполнил поле «Что изменилось», история версий всё равно
показывает суть правки: заголовок, разделы, абзацы, изображения, раздел базы.
Модуль не зависит от Django, чтобы его можно было вызвать и из миграции.
"""
import difflib
from collections import Counter
import html
import re

_BLOCK = re.compile(r'<(h[1-6]|p|li|pre|blockquote|td|th|figcaption)\b[^>]*>(.*?)</\1>', re.S | re.I)
_TAG = re.compile(r'<[^>]+>')


def _blocks(content):
    """Список (тег, текст) смысловых блоков HTML-статьи."""
    result = []
    for tag, inner in _BLOCK.findall(content or ''):
        text = re.sub(r'\s+', ' ', html.unescape(_TAG.sub(' ', inner))).strip()
        if text:
            result.append((tag.lower(), text))
    return result


def _short(text, limit=40):
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def describe_changes(old_title, old_content, new_title, new_content,
                     old_section=None, new_section=None):
    parts = []
    if (old_title or '').strip() != (new_title or '').strip():
        parts.append(f'изменён заголовок на «{_short(new_title)}»')
    if old_section != new_section and new_section is not None:
        parts.append(f'статья перенесена в раздел «{_short(str(new_section))}»')

    old_b, new_b = _blocks(old_content), _blocks(new_content)
    old_h = [t for tag, t in old_b if tag.startswith('h')]
    new_h = [t for tag, t in new_b if tag.startswith('h')]
    # Counter, а не set: одинаковые заголовки встречаются в статье не один раз
    added_h = list((Counter(new_h) - Counter(old_h)).elements())
    removed_h = list((Counter(old_h) - Counter(new_h)).elements())
    if added_h:
        word = 'добавлен раздел ' if len(added_h) == 1 else 'добавлены разделы '
        parts.append(word + ', '.join(f'«{_short(h)}»' for h in added_h[:2]))
    if removed_h:
        word = 'удалён раздел ' if len(removed_h) == 1 else 'удалены разделы '
        parts.append(word + ', '.join(f'«{_short(h)}»' for h in removed_h[:2]))

    old_t = [t for tag, t in old_b if not tag.startswith('h')]
    new_t = [t for tag, t in new_b if not tag.startswith('h')]
    added = removed = changed = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old_t, new_t, autojunk=False).get_opcodes():
        if op == 'insert':
            added += j2 - j1
        elif op == 'delete':
            removed += i2 - i1
        elif op == 'replace':
            common = min(i2 - i1, j2 - j1)
            changed += common
            added += (j2 - j1) - common
            removed += (i2 - i1) - common
    paragraphs = []
    if changed:
        paragraphs.append(f'изменено {changed}')
    if added:
        paragraphs.append(f'добавлено {added}')
    if removed:
        paragraphs.append(f'удалено {removed}')
    if paragraphs:
        parts.append('абзацы: ' + ', '.join(paragraphs))

    img_old = len(re.findall(r'<img\b', old_content or '', re.I))
    img_new = len(re.findall(r'<img\b', new_content or '', re.I))
    if img_new > img_old:
        parts.append(f'изображения: добавлено {img_new - img_old}')
    elif img_old > img_new:
        parts.append(f'изображения: удалено {img_old - img_new}')

    if not parts:
        return 'Оформление текста' if (old_content or '') != (new_content or '') else 'Текст не менялся'
    summary = '; '.join(parts)
    return summary[0].upper() + summary[1:]
