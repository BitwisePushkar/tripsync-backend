from django.contrib import admin
from .models import Place, Trip, TripBudgetCategory, Itinerary, DayPlan, Activity, ItineraryExport

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["tripname", "user", "destination", "start_date", "end_date", "days", "total_budget", "created_at"]
    list_filter = ["trip_type", "trip_preferences", "trending"]
    search_fields = ["tripname", "destination", "user__email"]

class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    fields = ["time", "title", "category", "estimated_cost", "location_name"]

@admin.register(DayPlan)
class DayPlanAdmin(admin.ModelAdmin):
    list_display = ["itinerary", "day_number", "title", "date"]
    inlines = [ActivityInline]

@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "time", "category", "estimated_cost", "day_plans"]
    list_filter = ["time", "category"]

@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ["name", "address", "lat", "lng", "rating"]
    search_fields = ["name", "address", "place_id"]

admin.site.register(TripBudgetCategory)
admin.site.register(Itinerary)
admin.site.register(ItineraryExport)