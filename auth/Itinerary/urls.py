from django.urls import path
from . import views

urlpatterns = [
    path('trips/', views.trip_list_create, name='trip-list-create'),
    path('trips/<int:pk>/', views.trip_detail, name='trip-detail'),
]