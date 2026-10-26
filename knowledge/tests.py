from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase, override_settings

from .context_processors import sections_processor
from .models import Article, Section


class SidebarTreeTests(TestCase):
    def setUp(self):
        # post_migrate запускает seed_data; каждый тест строит собственное дерево.
        Section.objects.all().delete()
        self.factory = RequestFactory()

    def context(self, path='/'):
        request = self.factory.get(path)
        request.user = AnonymousUser()
        return sections_processor(request)

    def article(self, section, title, status='published'):
        return Article.objects.create(section=section, title=title, status=status, content='Text')

    def test_every_level_contains_its_own_sections_and_published_articles(self):
        root = Section.objects.create(name='Company')
        child = Section.objects.create(name='Processes', parent=root)
        grandchild = Section.objects.create(name='Sales', parent=child)
        leaf = Section.objects.create(name='Orders', parent=grandchild)
        articles = [self.article(section, section.name) for section in (root, child, grandchild, leaf)]

        node = self.context()['nav_sections'][0]
        for section, article in zip((root, child, grandchild, leaf), articles):
            self.assertEqual(node.pk, section.pk)
            self.assertEqual([item.pk for item in node.nav_articles], [article.pk])
            if section == leaf:
                self.assertEqual(node.nav_children, [])
            else:
                self.assertEqual(len(node.nav_children), 1)
                node = node.nav_children[0]

    def test_inactive_sections_hide_their_subtree_and_unpublished_articles(self):
        root = Section.objects.create(name='Visible')
        hidden = Section.objects.create(name='Hidden', parent=root, is_active=False)
        hidden_child = Section.objects.create(name='Active child of hidden', parent=hidden)
        hidden_root = Section.objects.create(name='Hidden root', is_active=False)
        Section.objects.create(name='Active child of hidden root', parent=hidden_root)
        shown = self.article(root, 'Published')
        self.article(root, 'Draft', status='draft')
        self.article(root, 'Archived', status='archived')
        self.article(hidden, 'Hidden article')
        self.article(hidden_child, 'Hidden descendant article')

        nodes = self.context()['nav_sections']
        self.assertEqual([node.pk for node in nodes], [root.pk])
        self.assertEqual(nodes[0].nav_children, [])
        self.assertEqual([item.pk for item in nodes[0].nav_articles], [shown.pk])

    def test_roots_and_siblings_keep_mptt_order(self):
        last_root = Section.objects.create(name='Last', order=20)
        first_root = Section.objects.create(name='First', order=10)
        last_child = Section.objects.create(name='Later child', parent=first_root, order=10)
        b_child = Section.objects.create(name='B child', parent=first_root, order=0)
        a_child = Section.objects.create(name='A child', parent=first_root, order=0)

        nodes = self.context()['nav_sections']
        self.assertEqual([node.pk for node in nodes], [first_root.pk, last_root.pk])
        self.assertEqual([node.pk for node in nodes[0].nav_children],
                         [a_child.pk, b_child.pk, last_child.pk])

    def test_tree_and_articles_use_two_queries_regardless_of_depth(self):
        section = None
        for index in range(12):
            section = Section.objects.create(name=f'Level {index}', parent=section)
            self.article(section, f'Article {index}')

        with self.assertNumQueries(2):
            node = self.context()['nav_sections'][0]
            for index in range(12):
                self.assertEqual(len(node.nav_articles), 1)
                if index < 11:
                    node = node.nav_children[0]

    def test_current_section_is_available_on_section_and_article_pages(self):
        root = Section.objects.create(name='Company')
        child = Section.objects.create(name='Processes', parent=root)
        article = self.article(child, 'Sales process')

        self.assertEqual(self.context(f'/section/{child.slug}/')['current_section_slug'], child.slug)
        self.assertEqual(self.context(f'/article/{article.slug}/')['current_section_slug'], child.slug)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class EditorWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('editor_test', password='Local-editor-926!')
        self.client.force_login(self.user)
        self.section = Section.objects.create(name='Editor test section')

    def data(self, **overrides):
        data = {'title': 'Test article', 'content': '<h2>Section</h2><p>Text</p>',
                'section': '', 'status': 'draft', 'save_mode': 'draft',
                'allow_comments': 'on', 'draft_token': 'local-copy-token'}
        data.update(overrides)
        return data

    def article(self, **overrides):
        data = {'title': 'Existing', 'content': '<p>Old text</p>', 'author': self.user,
                'section': self.section, 'allow_comments': False, 'is_outdated': True}
        data.update(overrides)
        return Article.objects.create(**data)

    def test_draft_save_returns_to_editor_with_receipt(self):
        response = self.client.post('/article/new/', self.data(), follow=True)
        article = Article.objects.get(title='Test article')
        self.assertEqual(article.status, 'draft')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], f'/article/{article.slug}/edit/')
        self.assertContains(response, 'editor-save-receipt')
        self.assertContains(response, 'local-copy-token')
        self.assertNotContains(self.client.get(f'/article/{article.slug}/edit/'), 'id="editor-save-receipt"')

    def test_publish_button_overrides_hidden_draft_status(self):
        response = self.client.post('/article/new/', self.data(save_mode='published'), follow=True)
        article = Article.objects.get(title='Test article')
        self.assertEqual(article.status, 'published')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], f'/article/{article.slug}/')

    def test_invalid_create_preserves_input_without_success_receipt(self):
        response = self.client.post('/article/new/', self.data(title='   ', content='<p>Unsaved unique text</p>'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unsaved unique text')
        self.assertTrue(response.context['form'].errors)
        self.assertNotContains(response, 'id="editor-save-receipt"')

    def test_invalid_edit_renders_submitted_values_not_old_article(self):
        article = self.article()
        response = self.client.post(f'/article/{article.slug}/edit/', self.data(title=' ', content='<p>New unsaved content</p>'))
        self.assertContains(response, 'New unsaved content')
        article.refresh_from_db()
        self.assertEqual(article.content, '<p>Old text</p>')
        self.assertEqual(article.version, 1)

    def test_edit_keeps_comments_disabled_and_outdated_and_clears_section(self):
        article = self.article()
        data = self.data(save_mode='published')
        data.pop('allow_comments')
        response = self.client.post(f'/article/{article.slug}/edit/', data)
        self.assertEqual(response.status_code, 302)
        article.refresh_from_db()
        self.assertFalse(article.allow_comments)
        self.assertTrue(article.is_outdated)
        self.assertIsNone(article.section_id)
        self.assertIsNone(article.last_verified_at)
        self.assertEqual(article.version, 2)
        self.assertEqual(article.versions.get(version_number=1).content, '<p>Old text</p>')

    def test_initial_editor_values_match_article_and_key_is_scoped(self):
        article = self.article(status='draft')
        response = self.client.get(f'/article/{article.slug}/edit/')
        self.assertEqual(response.context['form']['title'].value(), article.title)
        self.assertFalse(response.context['form']['allow_comments'].value())
        self.assertContains(response, f'data-draft-key="rubbles-editor:{self.user.pk}:{article.pk}"')

    def test_omitted_section_on_version_restore_keeps_section(self):
        article = self.article()
        article.apply_new_version(title='Restored', content='<p>Restored text</p>')
        article.refresh_from_db()
        self.assertEqual(article.section_id, self.section.pk)
        self.assertTrue(article.is_outdated)

    def test_auth_screens_do_not_render_workspace_navigation(self):
        self.client.logout()
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="sidebar"')
        self.assertContains(response, 'auth-main')
        self.assertNotContains(response, '/accounts/register/')


class CommentAndSearchTests(TestCase):
    def setUp(self):
        import tempfile
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create_user('comment_writer', password='test-password')
        self.other = User.objects.create_user('comment_other')
        self.article = Article.objects.create(title='Оформление отпуска', content='<p>Отдых сотрудников</p>', status='published', author=self.user)
        self.url = f'/article/{self.article.slug}/comment/'
        self.client.force_login(self.user)

    def test_rich_comment_sanitized_and_owner_can_edit(self):
        from .models import Comment
        response = self.client.post(self.url, {'text_html': '<b onclick="alert(1)">Привет</b><script>alert(1)</script>', 'sticker': 'thanks'})
        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get(pk=response.json()['id'])
        self.assertIn('<b>Привет</b>', comment.text_html)
        self.assertNotIn('onclick', comment.text_html)
        self.assertNotIn('<script', comment.text_html)
        edit = f'{self.url}{comment.pk}/edit/'
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(edit, {'text_html': 'Чужая правка'}).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(edit, {'text_html': '<i>Изменено</i>'}).status_code, 200)
        comment.refresh_from_db()
        self.assertEqual(comment.text_html, '<i>Изменено</i>')
        self.assertEqual(comment.sticker, '')

    def test_files_images_download_and_remove(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Comment, CommentAttachment
        image = io.BytesIO(); Image.new('RGB', (2, 2)).save(image, 'PNG')
        response = self.client.post(self.url, {'files': [SimpleUploadedFile('sample.png', image.getvalue(), 'image/png'), SimpleUploadedFile('notes.txt', b'notes')]})
        self.assertEqual(response.status_code, 200)
        comment = Comment.objects.get(pk=response.json()['id'])
        self.assertEqual(comment.attachments.count(), 2)
        attachment = comment.attachments.get(is_image=False)
        download = self.client.get(f'/attachments/{attachment.pk}/')
        self.assertEqual(download.status_code, 200)
        self.assertIn('attachment', download['Content-Disposition'])
        download.close()
        self.client.post(f'{self.url}{comment.pk}/edit/', {'text': 'Обновление', 'remove_attachment': [attachment.pk]})
        self.assertFalse(CommentAttachment.objects.filter(pk=attachment.pk).exists())
        self.client.logout()
        self.assertEqual(self.client.get(f'/attachments/{comment.attachments.first().pk}/').status_code, 302)

    def test_invalid_files_empty_comment_and_closed_comments(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        for data in [{}, {'sticker': 'unknown'}, {'files': SimpleUploadedFile('bad.html', b'<script>')}, {'files': SimpleUploadedFile('bad.png', b'not an image')}]:
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.article.allow_comments = False; self.article.save()
        self.assertEqual(self.client.post(self.url, {'text': 'Hello'}).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_suggestions_typos_synonyms_and_no_drafts(self):
        Article.objects.create(title='Отгул секретный', content='hidden', status='draft')
        for query in ['отпу', 'отпускк', 'отгул']:
            response = self.client.get('/search/suggestions/', {'q': query})
            self.assertEqual(response.status_code, 200)
            titles = [item['title'] for item in response.json()['results']]
            self.assertIn(self.article.title, titles)
            self.assertNotIn('Отгул секретный', titles)
        self.assertEqual(self.client.get('/search/suggestions/?q=я').json()['results'], [])
        self.client.logout()
        self.assertEqual(self.client.get('/search/suggestions/?q=отпуск').status_code, 302)


class MentionsAndKeywordTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user('mention_sender')
        self.recipient = User.objects.create_user('mention.recipient', first_name='Мария')
        self.article = Article.objects.create(title='Миссия и ценности', content='<p>Принципы команды</p>', status='published', author=self.recipient)
        self.client.force_login(self.sender)

    def test_keyword_title_is_first_and_single_letter_suggests(self):
        Article.objects.create(title='Порядок работы', content='миссия и ценности', status='published')
        for query in ['м', 'мисс', 'МИССИЯ', 'миссия ценности']:
            data = self.client.get('/search/suggestions/', {'q': query}).json()
            self.assertEqual(data['results'][0]['title'], self.article.title)
            self.assertLessEqual(len(data['results']), 5)

    def test_mentions_notified_once_with_text_and_private_feed(self):
        from .models import Notification
        response = self.client.post(f'/article/{self.article.slug}/comment/', {'text': '@mention.recipient привет @mention.recipient'})
        self.assertEqual(response.status_code, 200)
        notices = Notification.objects.filter(user=self.recipient)
        self.assertEqual(notices.count(), 1)
        self.assertIn('привет', notices.get().message)
        self.assertEqual(self.client.get('/notifications/feed/').json()['unread'], 0)
        self.client.post(f'/article/{self.article.slug}/comment/{response.json()["id"]}/edit/', {'text': '@mention.recipient исправлено'})
        self.assertEqual(notices.count(), 1)
        self.client.force_login(self.recipient)
        data = self.client.get('/notifications/feed/').json()
        self.assertEqual(data['unread'], 1)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(self.client.get('/notifications/feed/', {'after':data['latest']}).json()['items'], [])
        self.client.get(data['items'][0]['url'])
        self.assertEqual(self.client.get('/notifications/feed/').json()['unread'], 0)

    def test_new_mention_on_edit_and_user_suggestions(self):
        from .models import Notification
        response = self.client.post(f'/article/{self.article.slug}/comment/', {'text': 'Привет'})
        Notification.objects.all().delete()
        self.client.post(f'/article/{self.article.slug}/comment/{response.json()["id"]}/edit/', {'text': '@mention.recipient посмотрите'})
        self.assertEqual(Notification.objects.filter(user=self.recipient, notification_type='comment_mention').count(), 1)
        data = self.client.get('/users/suggestions/', {'q':'мар'}).json()
        self.assertEqual(data['results'][0]['username'], 'mention.recipient')


class RegulationTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user('reg_author', password='Local-reg-926!')
        self.responsible = User.objects.create_user('reg_resp', password='Local-reg-926!')
        self.other = User.objects.create_user('reg_other', password='Local-reg-926!')
        self.article = Article.objects.create(title='Регламент', content='<p>Текст</p>', status='published',
                                              author=self.author, responsible=self.responsible)

    def test_archived_article_opens_by_link_but_not_in_search(self):
        self.client.force_login(self.other)
        self.client.post(f'/article/{self.article.slug}/archive/')
        self.assertEqual(self.client.get(f'/article/{self.article.slug}/').status_code, 200)
        self.assertNotIn(self.article, self.client.get('/search/', {'q': 'Регламент'}).context['articles'])

    def test_only_responsible_confirms_freshness(self):
        self.client.force_login(self.other)
        self.client.post(f'/article/{self.article.slug}/confirm-fresh/')
        self.article.refresh_from_db()
        self.assertIsNone(self.article.last_verified_at)
        self.client.force_login(self.responsible)
        self.client.post(f'/article/{self.article.slug}/confirm-fresh/')
        self.article.refresh_from_db()
        self.assertIsNotNone(self.article.last_verified_at)

    def test_comment_deleted_softly_and_only_by_author(self):
        from .models import Comment
        comment = Comment.objects.create(article=self.article, author=self.author, text='Замечание')
        self.client.force_login(self.other)
        self.client.post(f'/article/{self.article.slug}/comment/{comment.pk}/delete/')
        comment.refresh_from_db()
        self.assertTrue(comment.is_active)
        self.client.force_login(self.author)
        self.client.post(f'/article/{self.article.slug}/comment/{comment.pk}/delete/')
        comment.refresh_from_db()
        self.assertFalse(comment.is_active)
        self.assertIsNotNone(comment.deleted_at)

    def test_registration_is_closed_for_ordinary_users(self):
        self.assertEqual(self.client.get('/accounts/register/').status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/accounts/register/').status_code, 404)
        self.client.force_login(User.objects.create_user('reg_admin', password='x', is_staff=True))
        self.assertEqual(self.client.get('/accounts/register/').status_code, 200)

    def test_expired_article_is_marked_outdated(self):
        from django.utils import timezone
        from datetime import timedelta
        Article.objects.filter(pk=self.article.pk).update(created_at=timezone.now() - timedelta(days=91))
        Article.mark_expired()
        self.article.refresh_from_db()
        self.assertTrue(self.article.is_outdated)

    def test_collection_keeps_order_and_links_articles(self):
        from .models import Collection
        second = Article.objects.create(title='Второй', content='<p>x</p>', status='published', author=self.author)
        self.client.force_login(self.author)
        self.client.post('/collections/new/', {'title': 'Для новичка', 'description': 'Порядок изучения'})
        collection = Collection.objects.get()
        for article in (self.article, second):
            self.client.post(f'/collections/{collection.pk}/add/', {'article': article.pk})
        item = collection.items.get(article=second)
        self.client.post(f'/collections/{collection.pk}/items/{item.pk}/move/', {'direction': 'up'})
        self.assertEqual([i.article for i in collection.items.all()], [second, self.article])
        self.assertEqual(self.client.get(f'/collections/{collection.pk}/').status_code, 200)

    def test_docx_export_and_action_log(self):
        from .models import ActionLog
        self.client.force_login(self.author)
        response = self.client.get(f'/article/{self.article.slug}/export/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'))
        self.assertTrue(ActionLog.objects.filter(action='Экспорт статьи в docx').exists())

    def test_article_html_is_sanitized_on_save(self):
        self.client.force_login(self.author)
        self.client.post('/article/new/', {'title': 'XSS', 'content': '<p onclick="x()">a</p><script>alert(1)</script>',
                                           'save_mode': 'published'})
        content = Article.objects.get(title='XSS').content
        self.assertNotIn('script', content)
        self.assertNotIn('onclick', content)

    def test_section_depth_limited_to_two_levels(self):
        from django.core.exceptions import ValidationError
        root = Section.objects.create(name='Корень')
        child = Section.objects.create(name='Дочерний', parent=root)
        with self.assertRaises(ValidationError):
            Section(name='Третий', parent=child).full_clean()

    def test_docx_export_handles_lists_and_blocks_inside_table_cells(self):
        from .docx_export import article_to_docx
        self.article.content = ('<table><tr><td><ul><li>Один</li><li>Два</li></ul></td>'
                                '<td><p>Абзац</p><h3>Заголовок</h3><pre>x = 1</pre></td></tr></table>')
        self.assertTrue(article_to_docx(self.article).startswith(b'PK'))

    def test_links_from_text_appear_in_related_sources(self):
        from .link_sync import classify
        self.assertEqual(classify('https://yt.sbdagroup.com/issue/RPF-1'), 'youtrack')
        self.assertEqual(classify('https://gl.sbdagroup.com/rpf/-/merge_requests/5'), 'git')
        self.assertEqual(classify('https://docs.google.com/document/d/1', 'БТ по промо'), 'bt')
        self.assertEqual(classify('https://docs.google.com/document/d/1', 'ТЗ на выгрузку'), 'tz')
        self.assertEqual(classify('https://docs.google.com/document/d/1'), 'bt')
        self.assertEqual(classify('https://clickhouse.com/docs/sql'), 'docs')
        self.assertEqual(classify('https://rubbles.ru'), 'other')
        self.client.force_login(self.author)
        self.client.post(f'/article/{self.article.slug}/edit/', {
            'title': self.article.title, 'save_mode': 'published',
            'content': '<p><a href="https://yt.sbdagroup.com/issue/RPF-1">Задача</a> <a href="#x">якорь</a> <a href="http://dd.mm">DD.MM</a></p>'})
        links = list(self.article.related_links.values_list('url', 'link_type', 'label', 'from_text'))
        self.assertEqual(links, [('https://yt.sbdagroup.com/issue/RPF-1', 'youtrack', 'Задача', True)])
        self.client.post(f'/article/{self.article.slug}/edit/', {
            'title': self.article.title, 'save_mode': 'published', 'content': '<p>Без ссылок</p>'})
        self.assertFalse(self.article.related_links.exists())

    def test_pdf_export_and_numbered_lists_in_docx(self):
        import io
        import docx
        from .docx_export import article_to_docx
        self.article.content = ('<ol><li><p>Первый</p></li><li><p>Второй</p></li></ol>'
                                '<ul><li><p>Маркер</p></li></ul><ol><li><p>Снова первый</p></li></ol>')
        self.article.save()
        paragraphs = docx.Document(io.BytesIO(article_to_docx(self.article))).paragraphs
        items = [p for p in paragraphs if p.style.name.startswith('List')]
        self.assertEqual([p.text for p in items], ['Первый', 'Второй', 'Маркер', 'Снова первый'])
        first, last = items[0]._p.pPr.numPr.numId.val, items[3]._p.pPr.numPr.numId.val
        self.assertNotEqual(first, last)
        self.client.force_login(self.author)
        response = self.client.get(f'/article/{self.article.slug}/export/', {'format': 'pdf'})
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))


class SeedCollectionsTests(TestCase):
    def test_command_adds_articles_and_is_idempotent(self):
        from django.core.management import call_command
        from io import StringIO
        from .models import Collection
        User.objects.create_superuser('boss', 'b@example.com', 'x')
        call_command('seed_collections', stdout=StringIO())
        call_command('seed_collections', stdout=StringIO())
        self.assertEqual(Article.objects.filter(title='Регламент жизненного цикла знаний').count(), 1)
        onboarding = Collection.objects.get(title='Онбординг нового аналитика')
        self.assertEqual(onboarding.role, 'аналитик')
        self.assertEqual(onboarding.items.first().article.title, 'Онбординг нового аналитика: порядок и чек-лист')
