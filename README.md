# RUBBLES KB — База знаний

Приложение Django для создания и управления корпоративной базой знаний (KB).

## Деплой на Render.com (бесплатно)

### 1. Зарегистрируйтесь на Render.com
- Перейдите на https://render.com
- Нажмите **Get Started** → зарегистрируйтесь через GitHub
- **Карта НЕ нужна** для бесплатного тарифа

### 2. Создайте новый Web Service
- В панели Render нажмите **New +** → **Web Service**
- Выберите репозиторий: **anarex8332/ubbles-kb**
- Настройте:
  - **Name:** `rubbles-kb` (или любое другое)
  - **Runtime:** `Python 3`
  - **Build Command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
  - **Start Command:** `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`

### 3. Настройте переменные окружения
В разделе **Environment** добавьте:

| Key | Value |
|-----|-------|
| `DJANGO_SECRET_KEY` | любой сложный ключ (например, сгенерировать на https://djecrety.ir) |
| `DJANGO_DEBUG` | `False` |
| `PYTHON_VERSION` | `3.11.0` |

### 4. Создайте базу данных PostgreSQL
- В панели Render нажмите **New +** → **PostgreSQL**
- **Name:** `rubbles-kb-db`
- **Instance Type:** **Free**
- После создания скопируйте **Internal Database URL**
- Перейдите в Web Service → **Environment** → добавьте переменную:
  - **Key:** `DATABASE_URL`
  - **Value:** вставьте скопированный Internal Database URL

### 5. Запустите деплой
- Нажмите **Save** → **Apply**
- Render начнёт сборку и деплой (3-5 минут)

### 6. Создайте суперпользователя
После успешного деплоя перейдите в **Shell** вашего Web Service:

```bash
python manage.py createsuperuser
```

Или через **Render Dashboard** → ваш Web Service → **Shell** → введите команду.

### 7. Готово!
Сайт будет доступен по адресу:
```
https://rubbles-kb.onrender.com
```

## Локальная разработка

```bash
git clone https://github.com/anarex8332/ubbles-kb.git
cd ubbles-kb
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver

## Обновление существующей установки

После получения новой версии обновите схему базы и статические файлы, затем перезапустите сервер:

```bash
git pull origin main
python manage.py migrate
python manage.py collectstatic --noinput
```

Миграция `0004` добавляет форматирование комментариев, стикеры и вложения, сохраняя старые сообщения.
Файлы комментариев сохраняются в `MEDIA_ROOT`: на сервере этот каталог должен находиться на постоянном диске и входить в резервную копию вместе с базой.
Документы выдаются через авторизованный маршрут `/attachments/<id>/`; изображения доступны в обсуждении. Разрешены до пяти файлов по 10 МБ на комментарий.

Живой поиск использует совпадения слов, близкое написание и словарь синонимов в `knowledge/search_tools.py`. Внешние сервисы и модели не требуются; словарь можно дополнять терминологией команды.
