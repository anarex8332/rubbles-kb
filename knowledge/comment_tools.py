import bleach
from pathlib import Path
from PIL import Image
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags

STICKERS = {'thanks': 'Спасибо!', 'done': 'Готово', 'idea': 'Есть идея', 'agree': 'Согласен', 'question': 'Есть вопрос', 'great': 'Отлично!'}

def clean_comment(data, files, existing_count=0):
    html = bleach.clean(data.get('text_html', ''), tags=['p', 'br', 'b', 'strong', 'i', 'em', 'u', 's', 'ul', 'ol', 'li', 'blockquote'], attributes={}, strip=True)
    text = strip_tags(html).strip() if html else data.get('text', '').strip()
    sticker = data.get('sticker', '')
    if sticker and sticker not in STICKERS:
        raise ValidationError('Выберите стикер из набора.')
    if len(text) > 20000:
        raise ValidationError('Комментарий должен быть короче 20 000 символов.')
    if not text and not sticker and not files and not existing_count:
        raise ValidationError('Добавьте текст, стикер или файл.')
    if len(files) + existing_count > 5:
        raise ValidationError('Можно прикрепить до пяти файлов.')
    checked = []
    for file in files:
        ext = Path(file.name).suffix.lower()
        if file.size > 10 * 1024 * 1024:
            raise ValidationError('Размер каждого файла — до 10 МБ.')
        if ext not in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.csv', '.odt'}:
            raise ValidationError('Поддерживаются изображения, PDF и офисные документы.')
        is_image = ext in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        if is_image:
            try:
                image = Image.open(file)
                if image.format not in {'PNG', 'JPEG', 'GIF', 'WEBP'} or image.width * image.height > 40000000:
                    raise ValueError()
                image.verify()
                file.seek(0)
            except Exception:
                raise ValidationError('Не удалось прочитать изображение.')
        checked.append((file, is_image))
    return text, html, sticker, checked
