import re
from difflib import SequenceMatcher
from django.utils.html import strip_tags
from .models import Article

GROUPS = [('отпуск', 'отгул', 'отдых'), ('зарплата', 'оплата', 'выплата', 'вознаграждение'), ('вход', 'доступ', 'пароль', 'авторизация'), ('адаптация', 'онбординг', 'новичок'), ('инструкция', 'руководство', 'регламент'), ('увольнение', 'расторжение')]

def words(text):
    return re.findall(r'[а-яa-z0-9]+', text.lower().replace('ё', 'е'))

STOP_WORDS = {'как', 'что', 'это', 'для', 'или', 'где', 'мне', 'найти', 'про', 'статья', 'статью', 'the', 'and'}

def ranked_articles(query):
    tokens = [token for token in words(query)[:12] if token not in STOP_WORDS and len(token) >= 2]
    if not tokens:
        return []
    normalized = ' '.join(tokens)
    results = []
    for article in Article.objects.filter(status='published').select_related('section').iterator():
        title = words(article.title)
        body = set(words(strip_tags(article.content)))
        score, matches = 0, 0
        for token in tokens:
            value = 0
            if token in title:
                value = 30
            elif any(word.startswith(token) for word in title):
                value = 24
            elif len(token) >= 4 and any(SequenceMatcher(None, token, word).ratio() >= .8 for word in title):
                value = 14
            elif len(token) >= 3 and any(word.startswith(token) for word in body):
                value = 4
            if not value and len(token) >= 4:
                synonyms = {word for group in GROUPS if any(token.startswith(word[:5]) or word.startswith(token) for word in group) for word in group}
                if any(any(word.startswith(synonym[:5]) for word in title) for synonym in synonyms):
                    value = 10
                elif any(any(word.startswith(synonym[:5]) for word in body) for synonym in synonyms):
                    value = 2
            if value:
                matches += 1
                score += value
        if matches >= max(1, len(tokens) * .6):
            if ' '.join(title).startswith(normalized):
                score += 40
            elif normalized in ' '.join(title):
                score += 25
            results.append((score, article))
    results.sort(key=lambda item: (-item[0], item[1].title))
    threshold = results[0][0] * .3 if results else 0
    return [article for score, article in results if score >= threshold]
