import re
from html import unescape
from difflib import SequenceMatcher
from django.utils.html import strip_tags
from .models import Article

GROUPS = [('отпуск', 'отгул', 'отдых'), ('зарплата', 'оплата', 'выплата'), ('вход', 'доступ', 'пароль', 'авторизация'), ('адаптация', 'онбординг', 'новичок')]
STOP_WORDS = {'как', 'что', 'это', 'для', 'или', 'где', 'мне', 'найти', 'про', 'статья', 'статью', 'the', 'and'}

def words(text):
    return re.findall(r'[а-яa-z0-9]+', unescape(text).lower().replace('ё', 'е'))

def ranked_articles(query):
    tokens = [t for t in words(query)[:12] if t not in STOP_WORDS]
    if not tokens:
        return []
    phrase = ' '.join(tokens)
    direct, related = [], []
    for article in Article.objects.filter(status='published').select_related('section').iterator():
        title = words(article.title)
        body = words(strip_tags(article.content))
        section = words(article.section.name) if article.section else []
        scores = []
        for token in tokens:
            scores.append(40 if token in title else 30 if any(w.startswith(token) for w in title) else 12 if token in section else 8 if any(w.startswith(token) for w in section) else 6 if len(token) >= 2 and token in body else 3 if len(token) >= 3 and any(w.startswith(token) for w in body) else 0)
        if all(scores):
            title_phrase = ' '.join(title)
            bonus = 200 if title_phrase == phrase else 100 if title_phrase.startswith(phrase) else 60 if phrase in title_phrase else 0
            direct.append((sum(scores) + bonus, article))
            continue
        related_scores = []
        for token, score in zip(tokens, scores):
            if not score and len(token) >= 4:
                score = 5 if any(SequenceMatcher(None, token, word).ratio() >= .82 for word in title) else 0
                synonyms = {word for group in GROUPS if token in group for word in group}
                if not score and any(any(w.startswith(synonym[:5]) for w in title) for synonym in synonyms):
                    score = 4
            related_scores.append(score)
        if all(related_scores):
            related.append((sum(related_scores), article))
    # Exact keyword results always win; approximate matches are a fallback only.
    results = direct if direct else related
    results.sort(key=lambda item: (-item[0], item[1].title))
    return [article for score, article in results]
