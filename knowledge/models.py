import re

SECTION_UNSET = object()

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
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

    MAX_DEPTH = 2  # раздел и один уровень подразделов (раздел 3.2 ВКР)

    def clean(self):
        super().clean()
        if self.parent_id and self.parent.get_level() + 1 >= self.MAX_DEPTH:
            raise ValidationError({'parent': 'Глубина дерева разделов ограничена двумя уровнями.'})
        if self.pk and self.parent_id and self.get_descendants().exists():
            raise ValidationError({'parent': 'У раздела есть подразделы, его нельзя сделать подразделом.'})

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

    TYPE_CHOICES = [
        ('context', 'Контекст проекта и клиента'),
        ('product', 'Описание продукта или компонента'),
        ('rule', 'Бизнес-правило'),
        ('decision', 'Обоснование решения'),
        ('instruction', 'Рабочая инструкция'),
        ('task_doc', 'Документация по реализованной задаче'),
        ('problem', 'Разбор проблемы'),
        ('term', 'Термин или определение'),
    ]
    REVIEW_DAYS = 90  # срок подтверждения актуальности, регламент 5.4

    title = models.CharField('Заголовок', max_length=500)
    slug = models.SlugField('Slug', max_length=500, unique=True, blank=True)
    article_type = models.CharField('Тип материала', max_length=20, choices=TYPE_CHOICES, default='instruction')
    scope = models.CharField('Область применения', max_length=300, blank=True,
                             help_text='Где и для кого действует материал: продукт, проект, роль')
    keywords = models.CharField('Ключевые слова', max_length=300, blank=True,
                                help_text='Через запятую')
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

    @classmethod
    def mark_expired(cls, now=None):
        """Регламент 5.4: не подтверждённая за квартал статья становится устаревшей."""
        border = (now or timezone.now()) - timedelta(days=cls.REVIEW_DAYS)
        expired = cls.objects.filter(status='published', is_outdated=False).filter(
            models.Q(last_verified_at__lt=border) |
            models.Q(last_verified_at__isnull=True, created_at__lt=border))
        return expired.update(is_outdated=True)

    def apply_new_version(self, *, title, content, section=SECTION_UNSET, content_markdown='',
                           snapshot_author=None, change_summary='', mark_fresh=False):
        """Сохраняет текущее состояние статьи как версию истории и применяет новые данные.

        Используется и при редактировании, и при откате к старой версии — раньше
        обе view-функции дублировали один и тот же блок кода.
        """
        if not change_summary.strip():
            from .change_summary import describe_changes
            new_section = self.section if section is SECTION_UNSET else section
            change_summary = describe_changes(self.title, self.content, title, content,
                                              self.section, new_section)
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
        from .link_sync import sync_text_links
        sync_text_links(self)

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
    from_text = models.BooleanField('Взята из текста статьи', default=False)
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
    text_html = models.TextField(blank=True)
    sticker = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField('Активен', default=True)
    # ФТ-08: обсуждение можно отметить разрешённым, не удаляя его историю
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='deleted_comments')
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


class Remark(models.Model):
    """Замечание к фрагменту текста статьи (регламент 7): выделенный текст, его автор, дата и решение."""
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='remarks')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='remarks')
    quote = models.TextField('Выделенный фрагмент')
    # Соседний текст и позиция помогают найти фрагмент, если такая же фраза встречается в статье несколько раз
    prefix = models.CharField(max_length=80, blank=True)
    suffix = models.CharField(max_length=80, blank=True)
    position = models.PositiveIntegerField(default=0)
    text = models.TextField('Текст замечания')
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField('Разрешено', default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='resolved_remarks')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Замечание к тексту'
        verbose_name_plural = 'Замечания к тексту'
        ordering = ['position', 'created_at']

    def __str__(self):
        return f"{self.author.username}: {self.quote[:40]}"


class RemarkReply(models.Model):
    """Ответ на замечание к тексту: обсуждение фрагмента между автором замечания и другими сотрудниками."""
    remark = models.ForeignKey(Remark, on_delete=models.CASCADE, related_name='replies')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='remark_replies')
    text = models.TextField('Текст ответа')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ответ на замечание'
        verbose_name_plural = 'Ответы на замечания'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username}: {self.text[:40]}"


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


def mentioned_names(text):
    return set(re.findall(r'(?<![\w@])@([\w.+-]+)', text))


@receiver(pre_save, sender=Comment)
def remember_comment_mentions(sender, instance, **kwargs):
    old = sender.objects.filter(pk=instance.pk).values_list('text', flat=True).first() if instance.pk else ''
    instance._previous_mentions = mentioned_names(old or '')


@receiver(post_save, sender=Comment)
def notify_on_comment(sender, instance, created, **kwargs):
    comment = instance
    if not comment.is_active:
        return
    new_names = mentioned_names(comment.text) - getattr(comment, '_previous_mentions', set())
    recipients = list(User.objects.filter(username__in=new_names, is_active=True).exclude(pk=comment.author_id))
    excerpt = comment.text[:300]
    for recipient in recipients:
        Notification.objects.create(user=recipient, article=comment.article,
            message=f'{comment.author.username} упомянул вас: {excerpt}'[:500],
            notification_type='comment_mention', from_user=comment.author)
    if created and comment.article.author_id and comment.article.author_id != comment.author_id and comment.article.author_id not in [user.pk for user in recipients]:
        Notification.objects.create(user=comment.article.author, article=comment.article,
            message=f'{comment.author.username}: {excerpt}'[:500],
            notification_type='comment_added', from_user=comment.author)


class CommentAttachment(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='comments/%Y/%m/')
    name = models.CharField(max_length=255)
    is_image = models.BooleanField(default=False)


class Collection(models.Model):
    """Подборка материалов для передачи знаний (ФТ-09): ссылки на статьи в порядке изучения"""
    title = models.CharField('Название', max_length=300)
    description = models.TextField('Для кого и зачем', blank=True)
    # Раздел 2.8 ВКР: новый сотрудник открывает подборку, связанную с проектом и своей ролью.
    role = models.CharField('Роль', max_length=120, blank=True, help_text='Например: аналитик, разработчик')
    project = models.CharField('Проект или продукт', max_length=200, blank=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='collections')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Подборка'
        verbose_name_plural = 'Подборки'
        ordering = ['title']

    def __str__(self):
        return self.title


class CollectionItem(models.Model):
    """Строка подборки: ссылка на статью, а не её копия"""
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='collection_items')
    position = models.PositiveIntegerField('Порядок изучения', default=1)
    note = models.CharField('Пояснение', max_length=300, blank=True)

    class Meta:
        verbose_name = 'Материал подборки'
        verbose_name_plural = 'Материалы подборки'
        ordering = ['position', 'pk']
        unique_together = ['collection', 'article']

    def __str__(self):
        return f'{self.collection}: {self.position}. {self.article}'


class ArticleImage(models.Model):
    """Изображение статьи в файловой области; в тексте остаётся только ссылка на него"""
    file = models.ImageField(upload_to='articles/%Y/%m/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ActionLog(models.Model):
    """Журнал основных действий пользователей (НФТ-08)"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='actions')
    action = models.CharField('Действие', max_length=60)
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name='actions')
    details = models.CharField('Подробности', max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Запись журнала'
        verbose_name_plural = 'Журнал действий'
        ordering = ['-created_at', '-pk']

    def __str__(self):
        return f'{self.created_at:%d.%m.%Y %H:%M} {self.user} {self.action}'
