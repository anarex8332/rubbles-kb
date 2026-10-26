"""Экспорт статьи в PDF (НФТ-06): HTML статьи вёрстается в PDF библиотекой xhtml2pdf."""
import io
import re
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.conf import settings

FONTS = Path(__file__).resolve().parent / 'fonts'
MAX_IMAGE_WIDTH = 460  # пунктов: ширина текстовой колонки A4 с полями

CSS = f'''
@page {{ size: A4; margin: 2cm 1.8cm; }}
@font-face {{ font-family: KbSans; src: url("{FONTS / 'DejaVuSans.ttf'}"); }}
@font-face {{ font-family: KbSans; font-weight: bold; src: url("{FONTS / 'DejaVuSans-Bold.ttf'}"); }}
@font-face {{ font-family: KbMono; src: url("{FONTS / 'DejaVuSansMono.ttf'}"); }}
body {{ font-family: KbSans; font-size: 10.5pt; line-height: 1.45; color: #202020; }}
h1 {{ font-size: 20pt; margin: 0 0 6pt; }}
h2 {{ font-size: 15pt; margin: 14pt 0 6pt; }}
h3 {{ font-size: 13pt; margin: 12pt 0 4pt; }}
h4 {{ font-size: 11.5pt; margin: 10pt 0 4pt; }}
p {{ margin: 0 0 6pt; }}
.meta {{ color: #666; font-size: 9pt; margin-bottom: 14pt; }}
a {{ color: #202020; text-decoration: underline; }}
pre {{ font-family: KbMono; font-size: 8.5pt; color: #1f7a3d; border: 1px solid #dededc;
       padding: 6pt; white-space: pre-wrap; }}
code {{ font-family: KbMono; font-size: 9pt; }}
blockquote {{ font-family: KbMono; font-size: 8.5pt; border-left: 2px solid #666;
              padding-left: 10pt; margin: 8pt 0; }}
blockquote p {{ margin: 0 0 3pt; }}
table {{ border: 1px solid #dededc; }}
td, th {{ border: 1px solid #dededc; padding: 3pt; font-size: 9pt; }}
'''


def _local_path(src):
    """Путь к файлу изображения на сервере по его адресу в тексте статьи, или None."""
    path = unquote(urlparse(src).path)
    media = '/' + settings.MEDIA_URL.strip('/') + '/'
    if path.startswith(media):
        file = (Path(settings.MEDIA_ROOT) / path[len(media):]).resolve()
        if Path(settings.MEDIA_ROOT).resolve() in file.parents and file.is_file():
            return file
    match = re.fullmatch(r'/images/(\d+)/', path)
    if match:
        from .models import ArticleImage
        image = ArticleImage.objects.filter(pk=match.group(1)).first()
        if image and image.file and Path(image.file.path).is_file():
            return Path(image.file.path)
    return None


def _prepare_images(html):
    """Локальные картинки подставляются файлом и вписываются в ширину страницы,
    внешние заменяются ссылкой: PDF собирается без обращения к интернету."""
    from PIL import Image

    def replace(match):
        tag = match.group(0)
        src = re.search(r'src="([^"]*)"', tag)
        src = src.group(1) if src else ''
        if src.startswith('data:image/'):
            return tag
        file = _local_path(src)
        if file is None:
            return f'<a href="{escape(src)}">[изображение]</a>' if src.startswith('http') else ''
        try:
            with Image.open(file) as image:
                width, height = image.size
        except OSError:
            return ''
        scale = min(1, MAX_IMAGE_WIDTH / max(width, 1))
        return f'<img src="{file.as_uri()}" width="{int(width * scale)}" height="{int(height * scale)}">'

    return re.sub(r'<img\b[^>]*>', replace, html)


def article_to_pdf(article):
    """Возвращает байты PDF-файла с заголовком и содержимым статьи."""
    from xhtml2pdf import pisa

    meta = [article.get_article_type_display()]
    if article.section:
        meta.append(f'Раздел: {article.section.name}')
    meta.append(f'Версия {article.version}, обновлено {article.updated_at:%d.%m.%Y}')
    body = _prepare_images(article.content or '')
    html = (f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
            f'<h1>{escape(article.title)}</h1><p class="meta">{escape(" · ".join(meta))}</p>'
            f'{body}</body></html>')
    out = io.BytesIO()
    result = pisa.CreatePDF(html, dest=out, encoding='utf-8')
    if result.err:
        raise ValueError('Не удалось собрать PDF')
    return out.getvalue()
