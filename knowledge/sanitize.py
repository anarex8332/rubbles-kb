import bleach

TAGS = ['p', 'br', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'strong', 'b', 'em', 'i', 'u', 's', 'strike',
        'blockquote', 'pre', 'code', 'hr', 'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'sup', 'sub']


def _attribute(tag, name, value):
    value = value.strip().lower()
    if tag == 'a' and name == 'href':
        return value.startswith(('http://', 'https://', 'mailto:', '/', '#'))
    if tag == 'img' and name == 'src':
        return value.startswith(('http://', 'https://', '/', 'data:image/png', 'data:image/jpeg', 'data:image/gif', 'data:image/webp'))
    if tag in ('th', 'td'):
        # Ширина столбца, заданная перетаскиванием границы в редакторе: только число пикселей.
        return name in ('colspan', 'rowspan') or (name == 'width' and value.isdigit() and 0 < int(value) <= 2000)
    return name in ('title', 'target', 'rel', 'alt', 'width', 'height') and tag in ('a', 'img')


ATTRIBUTES = {
    'a': _attribute,
    'img': _attribute,
    'pre': ['class'], 'div': ['class'], 'span': ['class'], 'code': ['class'],
    'th': _attribute, 'td': _attribute,
}
PROTOCOLS = ['http', 'https', 'mailto', 'data']


def clean_article_html(html):
    """Очистка HTML статьи библиотекой Bleach при сохранении (раздел 3.3 ВКР).

    Допускаются только теги оформления; скрипты, обработчики событий и javascript:-ссылки удаляются.
    Изображения data: допускаются только как картинки (тег img), в ссылках они не работают.
    """
    cleaner = bleach.sanitizer.Cleaner(tags=TAGS, attributes=ATTRIBUTES, protocols=PROTOCOLS, strip=True)
    return cleaner.clean(html or '')
