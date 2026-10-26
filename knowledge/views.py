from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth.models import User
from .audit import log_action
from .forms import ArticleForm, CollectionForm
from .models import (Section, Article, ArticleVersion, Comment, Bookmark, RecentlyViewed,
                      Changelog, Notification, RelatedLink, Remark, RemarkReply, Collection, CollectionItem, ArticleImage)
from .permissions import can_confirm_fresh, can_delete_comment, can_edit_articles, can_resolve_remark
from django.core.exceptions import PermissionDenied
from .article_templates import ARTICLE_TEMPLATES
from .sanitize import clean_article_html
from .link_sync import sync_text_links

COMMENT_REVIEW_DAYS = 3  # регламент 7.3: замечание без решения дольше трёх дней попадает в контроль состояния


def home(request):
    """Главная страница — дашборд базы знаний"""
    if not request.user.is_authenticated:
        return redirect('login')
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
    article = get_object_or_404(Article, slug=slug)
    # Регламент 6.3: архивная статья открывается по прямой ссылке; черновик виден только автору.
    if article.status == 'draft' and not (request.user.is_staff or article.author_id == request.user.pk):
        raise Http404

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
    comments = list(comments)
    for comment in comments:
        comment.can_delete = can_delete_comment(request.user, comment)
    is_bookmarked = False
    if request.user.is_authenticated:
        is_bookmarked = Bookmark.objects.filter(user=request.user, article=article).exists()

    remarks = list(article.remarks.select_related('author', 'resolved_by').prefetch_related('replies__author'))
    for remark in remarks:
        remark.can_resolve = can_resolve_remark(request.user, remark)
    from django.contrib.auth.models import User
    return render(request, 'knowledge/article.html', {
        'article': article,
        'comments': comments,
        'remarks': [r for r in remarks if not r.is_resolved],
        'resolved_remarks': [r for r in remarks if r.is_resolved],
        'is_bookmarked': is_bookmarked,
        'all_users': User.objects.order_by('username'),
        'can_confirm': can_confirm_fresh(request.user, article),
        'my_collections': Collection.objects.filter(owner=request.user),
        'in_collections': article.collection_items.select_related('collection'),
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


def _client_project_choices():
    """Уже введённые клиенты и проекты — подсказки в форме, чтобы не плодить разные написания."""
    def values(field):
        return (Article.objects.exclude(**{field: ''}).values_list(field, flat=True)
                .distinct().order_by(field))
    return {'client_choices': values('client'), 'project_choices': values('project')}


@login_required
def article_create(request):
    """Создание новой статьи"""
    if not can_edit_articles(request.user):
        raise PermissionDenied('Уровень доступа «Читатель» не позволяет создавать статьи')
    form = ArticleForm(_editor_post_data(request), initial={
        'section': request.GET.get('section', ''), 'status': 'draft', 'allow_comments': True,
    })
    if request.method == 'POST':
        if form.is_valid():
            article = form.save(commit=False)
            # Проект выполняется для клиента: если не назван, берём имя клиента
            article.project = form.cleaned_data['project'] or article.client
            article.content = clean_article_html(article.content)
            article.author = request.user
            article.save()
            sync_text_links(article)
            log_action(request.user, 'Создана статья', article, article.get_status_display())
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
        'type_templates': ARTICLE_TEMPLATES,
        **_client_project_choices(),
    })


@login_required
def article_edit(request, slug):
    """Редактирование статьи"""
    article = get_object_or_404(Article, slug=slug)
    if not can_edit_articles(request.user):
        raise PermissionDenied('Уровень доступа «Читатель» не позволяет редактировать статьи')

    # Форма не привязана к article (instance=article), чтобы в apply_new_version
    # можно было прочитать СТАРЫЕ значения article.title/content до их замены.
    form = ArticleForm(_editor_post_data(request), initial={
        'title': article.title, 'content': article.content, 'section': article.section_id,
        'status': article.status, 'allow_comments': article.allow_comments,
        'article_type': article.article_type, 'scope': article.scope, 'keywords': article.keywords,
        'client': article.client, 'project': article.project,
    })
    if request.method == 'POST':
        if form.is_valid():
            article.apply_new_version(
                title=form.cleaned_data['title'],
                content=clean_article_html(form.cleaned_data['content']),
                section=form.cleaned_data['section'],
                change_summary=request.POST.get('change_summary', ''),
            )
            article.status = form.cleaned_data['status']
            article.allow_comments = form.cleaned_data['allow_comments']
            article.article_type = form.cleaned_data['article_type']
            article.scope = form.cleaned_data['scope']
            article.keywords = form.cleaned_data['keywords']
            article.client = form.cleaned_data['client']
            article.project = form.cleaned_data['project'] or article.client  # проект выполняется для клиента
            article.save()
            log_action(request.user, 'Изменена статья', article, f'версия {article.version}')
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
        'type_templates': ARTICLE_TEMPLATES,
        **_client_project_choices(),
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
        log_action(request.user, 'Откат статьи', article, f'к версии {version.version_number}')
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
    log_action(request.user, 'Изменён комментарий' if comment_id else 'Добавлен комментарий', article, f'комментарий {comment.pk}')
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
    articles = ranked_articles(query)[:5] if query else []
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
            log_action(request.user, 'Снята отметка «устаревшая»', article)
            messages.success(request, 'Статья снова актуальна')
        else:
            article.is_outdated = True
            article.save()
            log_action(request.user, 'Статья помечена устаревшей', article)
            messages.warning(request, 'Статья помечена как устаревшая')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def confirm_article_fresh(request, slug):
    """КЗ-04: подтвердить корректность содержания на текущий момент
    (не путать с фактом правки текста — это отдельное действие проверки)."""
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        if not can_confirm_fresh(request.user, article):
            messages.error(request, 'Подтвердить актуальность может только ответственный за статью.')
            return redirect('knowledge:article_detail', slug=slug)
        article.last_verified_at = timezone.now()
        article.last_verified_by = request.user
        article.is_outdated = False
        article.save()
        log_action(request.user, 'Подтверждена актуальность', article)
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
        log_action(request.user, 'Назначен ответственный', article, article.responsible.username if article.responsible else 'не назначен')
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
            RelatedLink.objects.update_or_create(
                article=article, url=url,
                defaults={'link_type': link_type, 'label': label, 'from_text': False})
            log_action(request.user, 'Добавлен связанный источник', article, url)
            messages.success(request, 'Связь добавлена')
        else:
            messages.error(request, 'Укажите ссылку')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def delete_related_link(request, slug, link_id):
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        RelatedLink.objects.filter(pk=link_id, article=article).delete()
        log_action(request.user, 'Удалён связанный источник', article)
        messages.success(request, 'Связь удалена')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def add_remark(request, slug):
    """Регламент 7.1: замечание оставляется к выделенному фрагменту текста статьи."""
    article = get_object_or_404(Article, slug=slug)
    if request.method != 'POST':
        return redirect('knowledge:article_detail', slug=slug)
    quote = request.POST.get('quote', '').strip()[:2000]
    text = request.POST.get('text', '').strip()[:4000]
    if not quote or not text:
        messages.error(request, 'Выделите фрагмент текста и напишите замечание.')
        return redirect('knowledge:article_detail', slug=slug)
    try:
        position = max(0, int(request.POST.get('position', 0)))
    except ValueError:
        position = 0
    remark = Remark.objects.create(
        article=article, author=request.user, quote=quote, text=text, position=position,
        prefix=request.POST.get('prefix', '')[-80:], suffix=request.POST.get('suffix', '')[:80])
    log_action(request.user, 'Оставлено замечание к тексту', article, f'замечание {remark.pk}')
    if article.responsible_id and article.responsible_id != request.user.pk:
        Notification.objects.create(
            user=article.responsible, article=article, from_user=request.user, notification_type='comment_added',
            message=f'{request.user.username} оставил(а) замечание к статье «{article.title}»')
    messages.success(request, 'Замечание добавлено')
    return redirect(reverse('knowledge:article_detail', args=[slug]) + f'#remark-{remark.pk}')


@login_required
def add_remark_reply(request, slug, remark_id):
    """Ответ на замечание; автор замечания получает уведомление."""
    article = get_object_or_404(Article, slug=slug)
    remark = get_object_or_404(Remark, pk=remark_id, article=article)
    text = request.POST.get('text', '').strip()[:4000] if request.method == 'POST' else ''
    if text:
        RemarkReply.objects.create(remark=remark, author=request.user, text=text)
        log_action(request.user, 'Ответ на замечание', article, f'замечание {remark.pk}')
        if remark.author_id != request.user.pk:
            Notification.objects.create(
                user=remark.author, article=article, from_user=request.user, notification_type='comment_added',
                message=f'{request.user.username} ответил(а) на ваше замечание к статье «{article.title}»')
    return redirect(reverse('knowledge:article_detail', args=[slug]) + f'#remark-{remark.pk}')


@login_required
def toggle_remark_resolved(request, slug, remark_id):
    """Регламент 7.2: разрешить замечание или вернуть его в работу; история сохраняется."""
    article = get_object_or_404(Article, slug=slug)
    remark = get_object_or_404(Remark, pk=remark_id, article=article)
    if request.method == 'POST':
        if not can_resolve_remark(request.user, remark):
            messages.error(request, 'Отметить замечание решённым может его автор или ответственный за статью.')
            return redirect('knowledge:article_detail', slug=slug)
        remark.is_resolved = not remark.is_resolved
        remark.resolved_by = request.user if remark.is_resolved else None
        remark.resolved_at = timezone.now() if remark.is_resolved else None
        remark.save()
        log_action(request.user, 'Замечание решено' if remark.is_resolved else 'Замечание возвращено', article, f'замечание {remark.pk}')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def delete_comment(request, slug, comment_id):
    """Раздел 3.2: автор удаляет комментарий; запись остаётся в истории, на странице не показывается."""
    article = get_object_or_404(Article, slug=slug)
    comment = get_object_or_404(Comment, pk=comment_id, article=article, is_active=True)
    if request.method == 'POST':
        if not can_delete_comment(request.user, comment):
            messages.error(request, 'Удалить комментарий может только его автор.')
        else:
            comment.is_active = False
            comment.deleted_at = timezone.now()
            comment.deleted_by = request.user
            comment.save(update_fields=['is_active', 'deleted_at', 'deleted_by', 'updated_at'])
            log_action(request.user, 'Удалён комментарий', article, f'комментарий {comment.pk}')
            messages.success(request, 'Комментарий удалён')
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def status_overview(request):
    """ФТ-11: контроль состояния — списки материалов без ответственного,
    требующих пересмотра, с нерассмотренными замечаниями и архив."""
    Article.mark_expired()  # регламент 5.4: просроченные статьи помечаются устаревшими автоматически
    border = timezone.now() - timedelta(days=COMMENT_REVIEW_DAYS)
    lists = {
        'comments': Article.objects.filter(
            remarks__is_resolved=False, remarks__created_at__lt=border).distinct(),
        'responsible': Article.objects.filter(responsible__isnull=True, status='published'),
        'outdated': Article.objects.filter(is_outdated=True, status='published'),
        # Регламент 6.3: архивные статьи исключены из поиска и общих списков, но собраны здесь
        'archived': Article.objects.filter(status='archived'),
    }
    # Фильтр по модулю: корневой раздел вместе со всеми подразделами
    modules = Section.objects.filter(parent__isnull=True, is_active=True).order_by('tree_id')
    module = modules.filter(slug=request.GET.get('module', '')).first()
    query = request.GET.get('q', '').strip()
    for key, qs in lists.items():
        if module:
            qs = qs.filter(section__in=module.get_descendants(include_self=True))
        if query:
            qs = qs.filter(title__icontains=query)
        lists[key] = qs.select_related('section', 'responsible').order_by('-updated_at')
    tab = request.GET.get('tab', 'comments')
    if tab not in lists:
        tab = 'comments'
    page = Paginator(lists[tab], 30).get_page(request.GET.get('page'))
    return render(request, 'knowledge/status_overview.html', {
        'tab': tab, 'page': page, 'modules': modules, 'module': module, 'query': query,
        'counts': {key: qs.count() for key, qs in lists.items()},
        'comment_days': COMMENT_REVIEW_DAYS,
    })


@login_required
def version_log(request):
    """Общая история версий: все правки статей базы, новые сверху, с поиском и фильтрами."""
    versions = (ArticleVersion.objects.filter(article__status__in=['published', 'draft'])
                .select_related('article', 'article__section', 'author').order_by('-created_at'))
    modules = Section.objects.filter(parent__isnull=True, is_active=True).order_by('tree_id')
    module = modules.filter(slug=request.GET.get('module', '')).first()
    if module:
        versions = versions.filter(article__section__in=module.get_descendants(include_self=True))
    authors = User.objects.filter(pk__in=ArticleVersion.objects.values('author')).order_by('last_name', 'username')
    author_id = request.GET.get('author', '')
    if author_id.isdigit():
        versions = versions.filter(author_id=int(author_id))
    date_from, date_to = request.GET.get('from', ''), request.GET.get('to', '')
    if date_from:
        versions = versions.filter(created_at__date__gte=date_from)
    if date_to:
        versions = versions.filter(created_at__date__lte=date_to)
    query = request.GET.get('q', '').strip()
    if query:
        # SQLite не умеет регистронезависимый поиск по кириллице, поэтому ищем в Python
        needle = query.casefold()
        versions = [v for v in versions
                    if needle in v.article.title.casefold() or needle in (v.change_summary or '').casefold()]
    page = Paginator(versions, 30).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'knowledge/version_log.html', {
        'page': page, 'modules': modules, 'module': module, 'authors': authors,
        'author_id': author_id, 'date_from': date_from, 'date_to': date_to, 'query': query,
        'filtered': bool(module or author_id or date_from or date_to or query),
        'params': params.urlencode(),
    })


@login_required
def client_overview(request):
    """Клиенты и проекты: статьи, собранные по клиенту и проекту."""
    articles = (Article.objects.filter(status='published').exclude(client='', project='')
                .select_related('section').order_by('client', 'project', 'title'))
    client = request.GET.get('client', '')
    clients = {}
    for article in articles:
        name = article.client or 'Без клиента'
        clients.setdefault(name, {}).setdefault(article.project or 'Общее', []).append(article)
    selected = {client: clients[client]} if client in clients else clients
    return render(request, 'knowledge/client_overview.html', {
        'clients': selected, 'client_names': list(clients), 'client': client if client in clients else '',
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


@login_required
def mention_users(request):
    from django.contrib.auth.models import User
    query = request.GET.get('q', '').strip().lower()[:100]
    users = User.objects.filter(is_active=True).exclude(pk=request.user.pk).order_by('username')
    results = []
    for user in users:
        if not query or query in user.username.lower() or query in user.get_full_name().lower():
            results.append({'username': user.username, 'name': user.get_full_name() or user.username})
            if len(results) == 8:
                break
    return JsonResponse({'results': results})


@login_required
def notification_feed(request):
    from django.urls import reverse
    notifications = Notification.objects.filter(user=request.user)
    try:
        after = max(0, int(request.GET.get('after', '0')))
    except ValueError:
        after = 0
    unread = notifications.filter(is_read=False)
    fresh = unread.filter(pk__gt=after).order_by('pk')[:10] if after else unread.order_by('-pk')[:1]
    return JsonResponse({'unread': unread.count(), 'latest': notifications.order_by('-pk').values_list('pk', flat=True).first() or 0,
                         'items': [{'id': n.pk, 'text': n.message, 'url': reverse('knowledge:notification_read', args=[n.pk])} for n in fresh]})


@login_required
def archive_article(request, slug):
    """Регламент 6: перенос статьи в архив и возврат из архива."""
    article = get_object_or_404(Article, slug=slug)
    if request.method == 'POST':
        if article.status == 'archived':
            article.status = 'published'
            log_action(request.user, 'Статья возвращена из архива', article)
            messages.success(request, 'Статья возвращена из архива')
        else:
            article.status = 'archived'
            log_action(request.user, 'Статья перенесена в архив', article)
            messages.warning(request, 'Статья перенесена в архив: из поиска и списков она исключена')
        article.save()
    return redirect('knowledge:article_detail', slug=slug)


@login_required
def export_article_docx(request, slug):
    """НФТ-06: выгрузка статьи в docx или pdf (?format=pdf)."""
    from urllib.parse import quote
    article = get_object_or_404(Article, slug=slug)
    if article.status == 'draft' and not (request.user.is_staff or article.author_id == request.user.pk):
        raise Http404
    if request.GET.get('format') == 'pdf':
        from .pdf_export import article_to_pdf
        extension, content_type, data = 'pdf', 'application/pdf', article_to_pdf(article)
    else:
        from .docx_export import article_to_docx
        extension = 'docx'
        content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        data = article_to_docx(article)
    response = HttpResponse(data, content_type=content_type)
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(article.slug[:80] or 'article')}.{extension}"
    log_action(request.user, f'Экспорт статьи в {extension}', article)
    return response


@login_required
def upload_article_image(request):
    """Изображение статьи сохраняется в файловой области, в тексте остаётся только ссылка (раздел 3.2)."""
    from PIL import Image
    from django.urls import reverse
    if request.method != 'POST' or not request.FILES.get('image'):
        return JsonResponse({'error': 'Нужен файл изображения.'}, status=400)
    file = request.FILES['image']
    if file.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Размер изображения — до 10 МБ.'}, status=400)
    try:
        image = Image.open(file)
        if image.format not in {'PNG', 'JPEG', 'GIF', 'WEBP'} or image.width * image.height > 40000000:
            raise ValueError()
        image.verify()
        file.seek(0)
    except Exception:
        return JsonResponse({'error': 'Не удалось прочитать изображение.'}, status=400)
    saved = ArticleImage.objects.create(file=file, uploaded_by=request.user)
    return JsonResponse({'url': reverse('knowledge:article_image', args=[saved.pk])})


@login_required
def article_image(request, pk):
    from django.http import FileResponse
    saved = get_object_or_404(ArticleImage, pk=pk)
    response = FileResponse(saved.file.open('rb'))
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, max-age=86400'
    return response


@login_required
def collection_list(request):
    return render(request, 'knowledge/collections.html', {
        'collections': Collection.objects.annotate(item_count=Count('items')),
    })


@login_required
def collection_detail(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    items = collection.items.select_related('article', 'article__section', 'article__responsible')
    return render(request, 'knowledge/collection_detail.html', {
        'collection': collection, 'items': items,
        'can_edit': request.user.is_staff or collection.owner_id == request.user.pk,
        'candidates': Article.objects.filter(status='published').exclude(
            pk__in=collection.items.values('article')).order_by('title'),
    })


@login_required
def collection_create(request):
    form = CollectionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        collection = form.save(commit=False)
        collection.owner = request.user
        collection.save()
        log_action(request.user, 'Создана подборка', None, collection.title)
        messages.success(request, 'Подборка создана')
        return redirect('knowledge:collection_detail', pk=collection.pk)
    return render(request, 'knowledge/collection_form.html', {'form': form})


def _own_collection(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    if not (request.user.is_staff or collection.owner_id == request.user.pk):
        raise Http404
    return collection


@login_required
def collection_add_item(request, pk):
    collection = _own_collection(request, pk)
    if request.method == 'POST':
        article = get_object_or_404(Article, pk=request.POST.get('article') or 0, status='published')
        last = collection.items.order_by('-position').values_list('position', flat=True).first() or 0
        item, created = CollectionItem.objects.get_or_create(
            collection=collection, article=article,
            defaults={'position': last + 1, 'note': request.POST.get('note', '')[:300]})
        if created:
            log_action(request.user, 'Статья добавлена в подборку', article, collection.title)
    return redirect(request.POST.get('next') or reverse_collection(collection))


def reverse_collection(collection):
    from django.urls import reverse
    return reverse('knowledge:collection_detail', args=[collection.pk])


@login_required
def collection_move_item(request, pk, item_id):
    collection = _own_collection(request, pk)
    if request.method == 'POST':
        items = list(collection.items.order_by('position', 'pk'))
        index = next((i for i, item in enumerate(items) if item.pk == item_id), None)
        if index is not None:
            target = index - 1 if request.POST.get('direction') == 'up' else index + 1
            if 0 <= target < len(items):
                items[index], items[target] = items[target], items[index]
            for number, item in enumerate(items, 1):
                if item.position != number:
                    item.position = number
                    item.save(update_fields=['position'])
    return redirect('knowledge:collection_detail', pk=collection.pk)


@login_required
def collection_remove_item(request, pk, item_id):
    collection = _own_collection(request, pk)
    if request.method == 'POST':
        collection.items.filter(pk=item_id).delete()
        for number, item in enumerate(collection.items.order_by('position', 'pk'), 1):
            if item.position != number:
                item.position = number
                item.save(update_fields=['position'])
    return redirect('knowledge:collection_detail', pk=collection.pk)


@login_required
def collection_delete(request, pk):
    collection = _own_collection(request, pk)
    if request.method == 'POST':
        log_action(request.user, 'Удалена подборка', None, collection.title)
        collection.delete()
        messages.success(request, 'Подборка удалена')
        return redirect('knowledge:collection_list')
    return redirect('knowledge:collection_detail', pk=collection.pk)
