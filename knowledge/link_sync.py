"""Ссылки из текста статьи автоматически попадают в «Связанные источники» (ФТ-05)."""
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse

GIT_HOSTS = ('gitlab', 'github', 'bitbucket', 'gl.')
DOC_HOSTS = ('confluence', 'wiki', 'notion', 'figma.com',
             'diagrams.net', 'miro.com', 'kaiten')


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self._href, self._text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href, self._text = dict(attrs).get('href'), []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self._href is not None:
            self.links.append((self._href.strip(), ' '.join(''.join(self._text).split())))
            self._href = None


def classify(url, text=''):
    """Тип источника по адресу и тексту ссылки."""
    host = urlparse(url).netloc.lower()
    words = f'{text} {url}'.lower()
    if host.startswith('yt.') or 'youtrack' in host:
        return 'youtrack'
    if any(part in host for part in GIT_HOSTS) or '/merge_requests' in url:
        return 'git'
    if re.search(r'(^|[^а-яa-z])бт([^а-яa-z]|$)|бизнес-?требован', words):
        return 'bt'
    if re.search(r'(^|[^а-яa-z])тз([^а-яa-z]|$)|техническ\w* задани', words):
        return 'tz'
    if host in ('docs.google.com', 'drive.google.com'):
        return 'bt'  # в РАБЛЗ бизнес-требования ведутся в Google Docs
    if any(part in host for part in DOC_HOSTS) or host.startswith('docs.') or '/docs' in url:
        return 'docs'
    return 'other'


def links_in_text(html):
    parser = _Links()
    parser.feed(html or '')
    parser.close()
    found = {}
    for href, text in parser.links:
        href = unescape(href)
        parsed = urlparse(href)
        if parsed.scheme not in ('http', 'https') or '.' not in parsed.netloc:
            continue
        # «DD.MM», «XX.XX» и подобные шаблоны, которые редактор ошибочно сделал ссылками
        if re.fullmatch(r'([a-z])\1\.([a-z])\2', parsed.netloc.lower()):
            continue
        if href in found:
            continue
        label = '' if not text or text.startswith(('http://', 'https://')) or text == href else text
        found[href[:1000]] = (classify(href, text), label[:300])
    return found


def sync_text_links(article, link_model=None):
    """Добавляет новые ссылки из текста и убирает те, что из текста удалены.
    Источники, добавленные вручную, не трогает."""
    if link_model is None:
        from .models import RelatedLink as link_model
    found = links_in_text(article.content)
    existing = {link.url: link for link in link_model.objects.filter(article=article)}
    for url, link in existing.items():
        if link.from_text and url not in found:
            link.delete()
    for url, (link_type, label) in found.items():
        if url not in existing:
            link_model.objects.create(article=article, url=url, link_type=link_type,
                                      label=label, from_text=True)
