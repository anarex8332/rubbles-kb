import re
from difflib import SequenceMatcher
from django.utils.html import strip_tags
from .models import Article

GROUPS = [('отпуск', 'отгул', 'отдых'), ('зарплата', 'оплата', 'выплата', 'вознаграждение'), ('вход', 'доступ', 'пароль', 'авторизация'), ('адаптация', 'онбординг', 'новичок'), ('инструкция', 'руководство', 'регламент'), ('увольнение', 'расторжение')]

def words(text):
    return re.findall(r'[а-яa-z0-9]+', text.lower().replace('ё', 'е'))

def ranked_articles(query):
    tokens = words(query)[:12]
    if not tokens:
        return []
    expanded = set(tokens)
    for group in GROUPS:
        if any(any(word.startswith(token) for word in group) for token in tokens if len(token) >= 3):
            expanded.update(group)
    results = []
    for article in Article.objects.filter(status='published').select_related('section').iterator():
        title = words(article.title)
        body = set(words(strip_tags(article.content)))
        score = 0
        for token in tokens:
            score += 12 if any(token in word for word in title) else 0
            score += 3 if any(token in word for word in body) else 0
            if len(token) >= 4 and any(SequenceMatcher(None, token, word).ratio() >= .78 for word in title):
                score += 5
        score += sum(2 for token in expanded - set(tokens) if any(word.startswith(token[:5]) for word in title + list(body)))
        if score:
            results.append((score, article))
    return [article for score, article in sorted(results, key=lambda item: (-item[0], item[1].title))]
