from django.urls import path
from .views import (PlaceListCreateView,PlaceDetailView,FunFactListCreateView,FunFactDetailView)

urlpatterns = [
    path('places/', PlaceListCreateView.as_view(), name='place-list-create'),
    path('places/<int:place_id>/', PlaceDetailView.as_view(), name='place-detail'),
    path('funfacts/', FunFactListCreateView.as_view(), name='funfact-list-create'),
    path('funfacts/<int:fact_id>/', FunFactDetailView.as_view(), name='funfact-detail'),
]