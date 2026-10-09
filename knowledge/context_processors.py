import re
from .models import Section, Notification, Article


def sections_processor(request):
    """Добавляет разделы, недавние статьи, закладки и уведомления в контекст всех шаблонов"""
    # MPTT-порядок гарантирует, что родитель обрабатывается раньше потомков.
    # Строим дерево в памяти, чтобы число запросов не зависело от его глубины.
    sections = []
    visible_sections = {}
    for section in Section.objects.filter(is_active=True).order_by('tree_id', 'lft'):
        if section.parent_id is not None and section.parent_id not in visible_sections:
            # Активный потомок скрытого раздела тоже не попадает в навигацию.
            continue
        section.nav_children = []
        section.nav_articles = []
        visible_sections[section.pk] = section
        if section.parent_id is None:
            sections.append(section)
        else:
            visible_sections[section.parent_id].nav_children.append(section)

    articles = Article.objects.filter(
        section_id__in=visible_sections,
        status='published',
    ).only('id', 'title', 'slug', 'section_id').order_by('-updated_at', '-pk')
    article_sections = {}
    for article in articles:
        section = visible_sections[article.section_id]
        section.nav_articles.append(article)
        article_sections[article.slug] = section.slug
    
    # Определяем slug текущего раздела из URL
    path = request.path
    current_slug = ''
    match = re.search(r'/section/([^/]+)/', path)
    if match:
        current_slug = match.group(1)
    else:
        article_match = re.search(r'/article/([^/]+)/', path)
        if article_match:
            current_slug = article_sections.get(article_match.group(1), '')
    
    ctx = {
        'nav_sections': sections,
        'current_section_slug': current_slug,
        'editor_save_receipt': request.session.pop('editor_save_receipt', None) if hasattr(request, 'session') else None,
    }
    
    if request.user.is_authenticated:
        from .models import RecentlyViewed, Bookmark
        ctx['recently_viewed'] = RecentlyViewed.objects.filter(user=request.user)[:10]
        ctx['bookmarks'] = Bookmark.objects.filter(user=request.user)[:10]
        ctx['unread_notifications'] = Notification.objects.filter(user=request.user, is_read=False)
        ctx['unread_count'] = ctx['unread_notifications'].count()
    
    return ctx
