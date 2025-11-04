from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(["GET"])
def root_view(request):
    return Response({
        "status": "ok",
        "message": "Welcome to TripSync API",
        "version": "1.0.0",
        "docs": "/api/docs/" if settings.DEBUG else "Docs not available in production",
    })

def health_check(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("", root_view, name="root"),
    path("health/", health_check, name="health-check"),
    path("control/", admin.site.urls),
    path("api/account/", include("account.urls", namespace="account")),
]

if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
        path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)