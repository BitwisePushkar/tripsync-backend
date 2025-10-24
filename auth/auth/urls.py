from django.contrib import admin
from django.urls import path, include
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
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
