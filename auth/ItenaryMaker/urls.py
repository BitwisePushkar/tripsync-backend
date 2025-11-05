from django.urls import path
from .views import (
    TripCreateView, TripListView, TripDetailView,
    ItineraryRegenerateView, ItineraryDetailView, DayPlanDetailView
)

urlpatterns = [
    path('trip/create/', TripCreateView.as_view(), name='create-trip'),
    path('trip/list/', TripListView.as_view(), name='list-trips'),
    path('trip/<int:pk>/', TripDetailView.as_view(), name='trip-detail'),
    path('itinerary/<int:trip_id>/', ItineraryDetailView.as_view(), name='itinerary-detail'),
    path('itinerary/<int:trip_id>/regenerate/', ItineraryRegenerateView.as_view(), name='regenerate-itinerary'),
    path('itinerary/<int:trip_id>/day/<int:day_number>/', DayPlanDetailView.as_view(), name='day-plan-detail'),]