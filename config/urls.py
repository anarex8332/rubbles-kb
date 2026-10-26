from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('knowledge.urls')),
    # Фото профиля отдаются и при DEBUG=False; остальные файлы media идут через проверку доступа
    re_path(r'^media/avatars/(?P<path>[^/]+)$', login_required(serve), {'document_root': settings.MEDIA_ROOT / 'avatars'}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)