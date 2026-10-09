import re

SECTION_UNSET = object()

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from slugify import slugify
from mptt.models import MPTTModel, TreeForeignKey


class Section(MPTTModel):
    """Раздел базы знаний"""
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Slug', max_length=200, unique=True, blank=True)
    description = models.TextField('Описание', blank=True)
    icon = models.CharField('Иконка', max_length=50, blank=True, help_text='Emoji для раздела')
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                            related_name='children', verbose_name='Родительский раздел')
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class MPTTMeta:
        order_insertion_by = ['order', 'name']

    class Meta:
        verbose_name = 'Раздел'
        verbose_name_plural = 'Разделы'
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Article(models.Model):
    """Статья базы знаний"""
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликовано'),
        ('archived', 'В архиве'),
    ]

    title = models.CharField('Заголовок', max_length=500)
    slug = models.SlugField('Slug', max_length=500, unique=True, blank=True)
    content = models.TextField('Содержимое (HTML)')
    # Редактор — contenteditable HTML (editor.js), markdown-версию он не формирует;
    # поле оставлено под будущий markdown-источник и сейчас не заполняется.
    content_markdown = models.TextField('Содержимое (Markdown)', blank=True)
    section = TreeForeignKey(Section, on_delete=models.CASCADE, related_name='articles',
                             verbose_name='Раздел', null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                               related_name='articles', verbose_name='Автор')
    # КЗ-07: проверяющий/ответственный за содержание — отдельно от автора,
    # т.к. по регламенту их может назначать тимлид, а не сам автор статьи.
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='responsible_articles',
                                    verbose_name='Ответственный за содержание')
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='published')
    is_outdated = models.BooleanField('Устаревшая', default=False)
    outdated_notification_sent = models.BooleanField(default=False)
    # КЗ-04: дата именно подтверждения корректности, а не дата правки текста —
    # правка опечатки не означает, что содержание перепроверено.
    last_verified_at = models.DateTimeField('Дата подтверждения актуальности', null=True, blank=True)
    last_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='verified_articles',
                                         verbose_name='Кто подтвердил актуальность')
    version = models.PositiveIntegerField('Версия', default=1)
    allow_comments = models.BooleanField('Разрешить комментарии', default=True)
    views_count = models.PositiveIntegerField('Просмотры', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'updated_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            counter = 1
            while Article.objects.filter(slug=slug).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def apply_new_version(self, *, title, content, section=SECTION_UNSET, content_markdown='',
                           snapshot_author=None, change_summary='', mark_fresh=False):
        """Сохраняет текущее состояние статьи как версию истории и применяет новые данные.

        Используется и при редактировании, и при откате к старой версии — раньше
        обе view-функции дублировали один и тот же блок кода.
        """
        ArticleVersion.objects.create(
            article=self,
            version_number=self.version,
            title=self.title,
            content=self.content,
            content_markdown=self.content_markdown,
            author=snapshot_author if snapshot_author is not None else self.author,
            change_summary=change_summary,
        )
        self.title = title
        self.content = content
        self.content_markdown = content_markdown
        if section is not SECTION_UNSET:
            self.section = section
        self.version += 1
        if mark_fresh:
            self.is_outdated = False
        self.save()

    def __str__(self):
        return self.title


class RelatedLink(models.Model):
    """Связь статьи с БТ, ТЗ, задачей YouTrack, Git или другим внешним источником (ФТ-05, КЗ-05)"""
    LINK_TYPES = [
        ('bt', 'БТ'),
        ('tz', 'ТЗ'),
        ('youtrack', 'Задача YouTrack'),
        ('git', 'Git'),
        ('docs', 'Документация'),
        ('other', 'Другое'),
    ]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='related_links')
    link_type = models.CharField('Тип связи', max_length=20, choices=LINK_TYPES, default='other')
    url = models.URLField('Ссылка', max_length=1000)
    label = models.CharField('Назначение связи', max_length=300, blank=True,
                             help_text='Например: БТ по доработке X, задача на реализацию Y')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Связанный источник'
        verbose_name_plural = 'Связанные источники'
        ordering = ['link_type', 'created_at']

    def __str__(self):
        return f'{self.get_link_type_display()}: {self.label or self.url}'


class ArticleVersion(models.Model):
    """Версия статьи"""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField('Номер версии')
    title = models.CharField(max_length=500)
    content = models.TextField()
    content_markdown = models.TextField(blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    change_summary = models.TextField('Описание изменений', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Версия статьи'
        verbose_name_plural = 'Версии статей'
        ordering = ['-version_number']
        unique_together = ['article', 'version_number']

    def __str__(self):
        return f"{self.article.title} v{self.version_number}"


class Comment(models.Model):
    """Комментарий к статье"""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField('Текст комментария')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField('Активен', default=True)
    # ФТ-08: обсуждение можно отметить разрешённым, не удаляя его историю
    is_resolved = models.BooleanField('Разрешено', default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='resolved_comments')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} - {self.article.title[:50]}"


class Bookmark(models.Model):
    """Закладка (избранное) пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Закладка'
        verbose_name_plural = 'Закладки'
        unique_together = ['user', 'article']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} -> {self.article.title[:50]}"


class RecentlyViewed(models.Model):
    """Недавно просмотренные статьи"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recently_viewed')
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Недавний просмотр'
        verbose_name_plural = 'Недавние просмотры'
        ordering = ['-viewed_at']
        unique_together = ['user', 'article']

    def __str__(self):
        return f"{self.user.username} -> {self.article.title[:50]}"


class Changelog(models.Model):
    """Запись о релизе/изменении"""
    version = models.CharField('Версия', max_length=50)
    title = models.CharField('Заголовок', max_length=300)
    description = models.TextField('Описание изменений', blank=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_published = models.BooleanField('Опубликовано', default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Релиз'
        verbose_name_plural = 'Релизы'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.version} - {self.title}"


class Notification(models.Model):
    """Уведомление пользователя"""
    NOTIFICATION_TYPES = [
        ('comment_mention', 'Упоминание в комментарии'),
        ('comment_added', 'Новый комментарий к статье'),
        ('article_updated', 'Статья изменена'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications',
                             verbose_name='Пользователь')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, null=True, blank=True,
                                verbose_name='Статья')
    message = models.TextField('Сообщение', max_length=500)
    notification_type = models.CharField('Тип', max_length=50, choices=NOTIFICATION_TYPES)
    from_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='sent_notifications', verbose_name='От кого')
    is_read = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{'✓' if self.is_read else '○'}] {self.user.username}: {self.message[:50]}"


@receiver(post_save, sender=Comment)
def notify_on_comment(sender, instance, created, **kwargs):
    """Создаёт уведомления автору статьи и упомянутым через @username при новом комментарии"""
    if not created:
        return
    comment = instance
    if comment.article.author and comment.article.author != comment.author:
        Notification.objects.create(
            user=comment.article.author,
            article=comment.article,
            message=f'Новый комментарий от {comment.author.username} к статье "{comment.article.title[:50]}"',
            notification_type='comment_added',
            from_user=comment.author,
        )

    for username in re.findall(r'@(\w+)', comment.text):
        try:
            mentioned_user = User.objects.get(username=username)
        except User.DoesNotExist:
            continue
        if mentioned_user != comment.author:
            Notification.objects.create(
                user=mentioned_user,
                article=comment.article,
                message=f'{comment.author.username} упомянул вас в комментарии к статье "{comment.article.title[:50]}"',
                notification_type='comment_mention',
                from_user=comment.author,
            )
