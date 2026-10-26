from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from .models import Section, Article, ArticleVersion, Comment, Bookmark, RecentlyViewed, Changelog, Notification, Collection, CollectionItem, ActionLog, ArticleImage


@admin.register(Section)
class SectionAdmin(MPTTModelAdmin):
    list_display = ['name', 'slug', 'order', 'is_active', 'created_at']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    mptt_level_indent = 20


class ArticleVersionInline(admin.TabularInline):
    model = ArticleVersion
    extra = 0
    readonly_fields = ['version_number', 'title', 'content', 'author', 'created_at']
    can_delete = False
    max_num = 0


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'section', 'author', 'status', 'version', 'is_outdated', 'views_count', 'updated_at']
    list_filter = ['status', 'article_type', 'section', 'is_outdated']
    search_fields = ['title', 'content', 'keywords', 'scope']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ArticleVersionInline]
    readonly_fields = ['version', 'views_count', 'created_at', 'updated_at']


@admin.register(Changelog)
class ChangelogAdmin(admin.ModelAdmin):
    list_display = ['version', 'title', 'author', 'is_published', 'created_at']
    list_filter = ['is_published']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'article', 'created_at', 'is_active']
    list_filter = ['is_active']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'message', 'is_read', 'created_at']
    list_filter = ['is_read', 'notification_type']
    search_fields = ['user__username', 'message']


admin.site.register(Bookmark)
admin.site.register(RecentlyViewed)


class CollectionItemInline(admin.TabularInline):
    model = CollectionItem
    extra = 0


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'updated_at']
    inlines = [CollectionItemInline]


@admin.register(ActionLog)
class ActionLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'article', 'details']
    list_filter = ['action']
    search_fields = ['user__username', 'details']
    readonly_fields = ['user', 'action', 'article', 'details', 'created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(ArticleImage)
