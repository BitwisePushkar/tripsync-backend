from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse

@api_view(['GET'])
def root_redirect(request):
    return Response({
        'message': 'Welcome to TripSync API',
        'documentation': request.build_absolute_uri('/api/docs/'),
        'admin': request.build_absolute_uri('/admin/'),
    })
def health_check(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('', root_redirect),
     path('health/', health_check, name='health-check'),
    path('admin/', admin.site.urls),
    path('api/account/', include('account.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/profile/', include('personal.urls')), 
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)