from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

def debug_urls(request):
    from django.urls import get_resolver
    resolver = get_resolver()
    url_patterns = []
    for pattern in resolver.url_patterns:
        if hasattr(pattern, 'url_patterns'):
            for p in pattern.url_patterns:
                url_patterns.append(str(p.pattern))
        else:
            url_patterns.append(str(pattern.pattern))
    return HttpResponse("<br>".join(url_patterns))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('wiki.urls')),  # ВКЛЮЧАЕМ URL-ы ПРИЛОЖЕНИЯ wiki
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('debug-urls/', debug_urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Для медиафайлов в разработке
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
