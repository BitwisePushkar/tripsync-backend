from django.urls import path
from .views import (
    TripListCreateView, TripDetailView, TripFullDetailView,
    TripBudgetAIView, TripBudgetManualView, TripBudgetCategoryDetailView,
    ItineraryAICreateView, ItineraryManualCreateView,
    ItineraryRegenerateView, ItineraryDeleteView,
    ItineraryExportView,
    DayPlanDetailView,
    ActivityListCreateView, ActivityDetailView,
)

app_name = "Itinerary"

urlpatterns = [
    path("trips/", TripListCreateView.as_view(), name="trip-list-create"),
    path("trips/<int:trip_id>/", TripDetailView.as_view(), name="trip-detail"),
    path("trips/<int:trip_id>/full/", TripFullDetailView.as_view(), name="trip-full"),
    path("trips/<int:trip_id>/budget/ai/", TripBudgetAIView.as_view(), name="trip-budget-ai"),
    path("trips/<int:trip_id>/budget/manual/", TripBudgetManualView.as_view(), name="trip-budget-manual"),
    path("trips/<int:trip_id>/budget/<int:cat_id>/",
         TripBudgetCategoryDetailView.as_view(), name="trip-budget-cat"),
    path("trips/<int:trip_id>/itinerary/ai/", ItineraryAICreateView.as_view(), name="itinerary-ai"),
    path("trips/<int:trip_id>/itinerary/manual/", ItineraryManualCreateView.as_view(), name="itinerary-manual"),
    path("trips/<int:trip_id>/itinerary/regen/",  ItineraryRegenerateView.as_view(), name="itinerary-regen"),
    path("trips/<int:trip_id>/itinerary/delete/", ItineraryDeleteView.as_view(), name="itinerary-delete"),
    path("trips/<int:trip_id>/itinerary/export/", ItineraryExportView.as_view(), name="itinerary-export"),
    path("trips/<int:trip_id>/day/<int:day_number>/", DayPlanDetailView.as_view(), name="day-plan"),
    path("trips/<int:trip_id>/day/<int:day_number>/activity/", ActivityListCreateView.as_view(), name="activity-create"),
    path("trips/<int:trip_id>/day/<int:day_number>/activity/<int:activity_id>/", ActivityDetailView.as_view(), name="activity-detail"),
]