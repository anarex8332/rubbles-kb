from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.utils import timezone
from .forms import ArticleForm
from .models import (Section, Article, ArticleVersion, Comment, Bookmark, RecentlyViewed,
                      Changelog, Notification, RelatedLink)


def home(request):
    """Главная страница — дашборд базы знаний"""
    if not request.user.is_authenticated:
        return redirect('register')
    recent_articles = Article.objects.filter(status='published').order_by('-updated_at')[:5]
    popular_articles = Article.objects.filter(status='published').order_by('-views_count')[:5]
    recent_changelogs = Changelog.objects.filter(is_published=True)[:3]
    return render(request, 'knowledge/home.html', {
        'recent_articles': recent_articles,
        'recent_changelogs': recent_changelogs,
        'popular_articles': popular_articles,
    })


@login_required
def section_detail(request, slug):
    """Страница раздела со списком статей"""
    section = get_object_or_404(Section, slug=slug, is_active=True)
    articles = Article.objects.filter(section=section, status='published')
    sub_sections = section.get_children().filter(is_active=True)
    return render(request, 'knowledge/section.html', {
        'section': section,
        'articles': articles,
        'sub_sections': sub_sections,
    })


@login_required
def article_detail(request, slug):
    """Страница статьи"""
    article = get_object_or_404(Article, slug=slug, status='published')

    # Увеличиваем счетчик просмотров
    article.views_count += 1
    Article.objects.filter(pk=article.pk).update(views_count=article.views_count)

    # Сохраняем в недавние, если пользователь авторизован
    if request.user.is_authenticated:
        RecentlyViewed.objects.update_or_create(
            user=request.user,
            article=article,
            defaults={'viewed_at': __import__('django').utils.timezone.now()}
        )

    comments = article.comments.filter(is_active=True).select_related('author').prefetch_related('attachments')
    is_bookmarked = False
    if request.user.is_authenticated:
        is_bookmarked = Bookmark.objects.filter(user=request.user, article=article).exists()

    from django.contrib.auth.models import User
    return render(request, 'knowledge/article.html', {
        'article': article,
        'comments': comments,
        'is_bookmarked': is_bookmarked,
        'all_users': User.objects.order_by('username'),
    })


@login_required
def search(request):
    """Поиск по статьям"""
    query = request.GET.get('q', '').strip()
    from .search_tools import ranked_articles
    articles = ranked_articles(query) if query else []
    return render(request, 'knowledge/search.html', {
        'query': query,
        'articles': articles,
    })


def _editor_post_data(request):
    if request.method != 'POST':
        return None
    data = request.POST.copy()
    if data.get('save_mode') in ('draft', 'published'):
        data['status'] = data['save_mode']
    return data


@login_required
def article_create(request):
    """Создание новой статьи"""
    form = ArticleForm(_editor_post_data(request), initial={
        'section': request.GET.get('section', ''), 'status': 'draft', 'allow_comments': True,
    })
    if request.method == 'POST':
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            request.session['editor_save_receipt'] = {
                'key': f'rubbles-editor:{request.user.pk}:new',
                'token': request.POST.get('draft_token', ''),
            }
            messages.success(request, 'Статья успешно создана!')
            return redirect('knowledge:article_detail' if article.status == 'published' else 'knowledge:article_edit', slug=article.slug)
        messages.error(request, 'Заполните заголовок и содержание статьи.')

    sections = Section.objects.filter(is_active=True)
    return render(request, 'knowledge/article_form.html', {
        'form': form,
        'sections': sections,
        'is_edit': False,
    })


@login_required
def article_edit(request, slug):
    """Редактирование статьи"""
    article = get_object_or_404(Article, slug=slug)

    # Форма не привязана к article (instance=article), чтобы в apply_new_version
    # можно было прочитать СТАРЫЕ значения article.title/content до их замены.
    form = ArticleForm(_editor_post_data(request), initial={
        'title': article.title, 'content': article.content, 'section': article.section_id,
        'status': article.status, 'allow_comments': article.allow_comments,
    })
    if request.method == 'POST':
        if form.is_valid():
            article.apply_new_version(
                title=form.cleaned_data['title'],
                content=form.cleaned_data['content'],
                section=form.cleaned_data['section'],
                change_summary=request.POST.get('change_summary', ''),
            )
            article.status = form.cleaned_data['status']
            article.allow_comments = form.cleaned_data['allow_comments']
            article.save()
            request.session['editor_save_receipt'] = {
                'key': f'rubbles-editor:{request.user.pk}:{article.pk}',
                'token': request.POST.get('draft_token', ''),
            }
            messages.success(request, 'Статья обновлена!')
            return redirect('knowledge:article_detail' if article.status == 'published' else 'knowledge:article_edit', slug=article.slug)
        messages.error(request, 'Заполните заголовок и содержание статьи.')

    sections = Section.objects.filter(is_active=True)
    return render(request, 'knowledge/article_form.html', {
        'article': article,
        'form': form,
        'sections': sections,
        'is_edit': True,
    })


@login_required
def article_version_history(request, slug):
    """История версий статьи"""
    article = get_object_or_404(Article, slug=slug)
    versions = article.versions.all()
    return render(request, 'knowledge/version_history.html', {
        'article': article,
        'versions': versions,
    })


@login_required
def article_restore_version(request, slug, version_number):
    """Восстановить версию статьи"""
    article = get_object_or_404(Article, slug=slug)
    version = get_object_or_404(ArticleVersion, article=article, version_number=version_number)
    if request.method == 'POST':
        article.apply_new_version(
            title=version.title,
            content=version.content,
            content_markdown=version.content_markdown,
            snapshot_author=request.user,
            change_summary=f'Откат к версии {version.version_number}',
            mark_fresh=False,
        )
        messages.success(request, f'Статья восстановлена к версии {version_number}')
        return redirect('knowledge:article_detail', slug=article.slug)
    return render(request, 'knowledge/version_restore.html', {
        'article': article,
        'version': version,
    })


@login_required
def toggle_bookmark(request, slug):
    """Добавить/удалить закладку"""
    article = get_object_or_404(Article, slug=slug)
    bookmark, created = Bookmark.objects.get_or_create(user=request.user, article=article)
    if not created:
        bookmark.delete()
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def add_comment(request, slug):
    return save_comment(request, slug)


@login_required
def edit_comment(request, slug, comment_id):
    return save_comment(request, slug, comment_id)


def save_comment(request, slug, comment_id=None):
    from django.core.exceptions import ValidationError
    from django.db import transaction
    from .comment_tools import clean_comment
    from .models import CommentAttachment
    if request.method != 'POST':
        return JsonResponse({'error': 'Нужен POST-запрос.'}, status=405)
    article = get_object_or_404(Article, slug=slug, status='published')
    if not article.allow_comments:
        return JsonResponse({'error': 'Комментарии отключены.'}, status=403)
    comment = get_object_or_404(Comment, pk=comment_id, article=article, author=request.user, is_active=True) if comment_id else None
    removed = request.POST.getlist('remove_attachment')
    remaining = comment.attachments.exclude(pk__in=[x for x in removed if x.isdigit()]).count() if comment else 0
    try:
        text, html, sticker, files = clean_comment(request.POST, request.FILES.getlist('files'), remaining)
    except ValidationError as error:
        return JsonResponse({'error': ' '.join(error.messages)}, status=400)
    with transaction.atomic():
        if comment is None:
            comment = Comment.objects.create(article=article, author=request.user, text=text, text_html=html, sticker=sticker)
        else:
            comment.text, comment.text_html, comment.sticker = text, html, sticker
            comment.save(update_fields=['text', 'text_html', 'sticker', 'updated_at'])
            comment.attachments.filter(pk__in=[x for x in removed if x.isdigit()]).delete()
        for file, is_image in files:
            CommentAttachment.objects.create(comment=comment, file=file, name=file.name[:255], is_image=is_image)
    return JsonResponse({'ok': True, 'id': comment.pk})


@login_required
def comment_attachment(request, attachment_id):
    from django.http import FileResponse
    from .models import CommentAttachment
    attachment = get_object_or_404(CommentAttachment, pk=attachment_id, comment__is_active=True, comment__article__status='published')
    response = FileResponse(attachment.file.open('rb'), as_attachment=not attachment.is_image, filename=attachment.name)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def search_suggestions(request):
    from .search_tools import ranked_articles
    from django.urls import reverse
    query = request.GET.get('q', '').strip()[:200]
    articles = ranked_articles(query)[:5] if len(query) >= 2 else []
    return JsonResponse({'results': [{'title': a.title, 'section': a.section.name if a.section else 'Без раздела', 'url': reverse('knowledge:article_detail', args=[a.slug])} for a in articles]})


@login_required
def changelog_list(request):
    """Список релизов"""
    changelogs = Changelog.objects.filter(is_published=True)
    return render(request, 'knowledge/changelog.html', {'changelogs': changelogs})


@login_required
def mark_article_outdated(request, slug):
    """Переключить статус устаревшей статьи (toggle)"""
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        if article.is_outdated:
            article.is_outdated = False
            article.save()
            messages.success(request, 'Статья снова актуальна')
        else:
            article.is_outdated = True
            article.save()
            messages.warning(request, 'Статья помечена как устаревшая')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def confirm_article_fresh(request, slug):
    """КЗ-04: подтвердить корректность содержания на текущий момент
    (не путать с фактом правки текста — это отдельное действие проверки)."""
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        article.last_verified_at = timezone.now()
        article.last_verified_by = request.user
        article.is_outdated = False
        article.save()
        messages.success(request, 'Актуальность подтверждена')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def set_responsible(request, slug):
    """КЗ-07: назначить ответственного за содержание статьи"""
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        user_id = request.POST.get('responsible')
        if user_id:
            from django.contrib.auth.models import User
            article.responsible = get_object_or_404(User, pk=user_id)
        else:
            article.responsible = None
        article.save()
        messages.success(request, 'Ответственный обновлён')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def add_related_link(request, slug):
    """ФТ-05/КЗ-05: привязать статью к БТ/ТЗ, задаче YouTrack, Git или другому источнику"""
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        url = request.POST.get('url', '').strip()
        link_type = request.POST.get('link_type', 'other')
        label = request.POST.get('label', '').strip()
        if url:
            RelatedLink.objects.create(article=article, url=url, link_type=link_type, label=label)
            messages.success(request, 'Связь добавлена')
        else:
            messages.error(request, 'Укажите ссылку')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def delete_related_link(request, slug, link_id):
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        RelatedLink.objects.filter(pk=link_id, article=article).delete()
        messages.success(request, 'Связь удалена')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def toggle_comment_resolved(request, slug, comment_id):
    """ФТ-08: отметить обсуждение разрешённым, сохранив его историю"""
    article = get_object_or_404(Article, slug=slug)
    comment = get_object_or_404(Comment, pk=comment_id, article=article)
    if request.method == 'POST':
        if comment.is_resolved:
            comment.is_resolved = False
            comment.resolved_by = None
            comment.resolved_at = None
        else:
            comment.is_resolved = True
            comment.resolved_by = request.user
            comment.resolved_at = timezone.now()
        comment.save()
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def status_overview(request):
    """ФТ-11: контроль состояния — списки материалов без ответственного,
    требующих пересмотра и с нерассмотренными замечаниями."""
    without_responsible = Article.objects.filter(
        responsible__isnull=True, status='published'
    ).order_by('-updated_at')
    outdated = Article.objects.filter(is_outdated=True).order_by('-updated_at')
    with_unresolved_comments = Article.objects.filter(
        comments__is_active=True, comments__is_resolved=False
    ).distinct().order_by('-updated_at')
    return render(request, 'knowledge/status_overview.html', {
        'without_responsible': without_responsible,
        'outdated': outdated,
        'with_unresolved_comments': with_unresolved_comments,
    })


@login_required
def recently_viewed_list(request):
    """Страница со списком недавних статей"""
    articles = RecentlyViewed.objects.filter(user=request.user)
    return render(request, 'knowledge/recently_viewed.html', {
        'articles': articles,
    })


@login_required
def bookmark_list(request):
    """Страница со списком закладок"""
    bookmarks = Bookmark.objects.filter(user=request.user)
    return render(request, 'knowledge/bookmarks.html', {
        'bookmarks': bookmarks,
    })


@login_required
def notification_list(request):
    """Список уведомлений пользователя"""
    notifications = Notification.objects.filter(user=request.user)
    return render(request, 'knowledge/notifications.html', {
        'notifications': notifications,
    })


@login_required
def notification_read(request, pk):
    """Отметить уведомление как прочитанное"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.article:
        return redirect('knowledge:article_detail', slug=notification.article.slug)
    return redirect('knowledge:notification_list')
