from django.contrib import admin
from .models import Trip, Itinerary, DayPlan

@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ['tripname', 'user', 'destination', 'start_date', 'days', 'budget', 'created_at']
    list_filter = ['trip_type', 'created_at']
    search_fields = ['tripname', 'destination', 'user__email']

@admin.register(Itinerary)
class ItineraryAdmin(admin.ModelAdmin):
    list_display = ['trip', 'created_at']

@admin.register(DayPlan)
class DayPlanAdmin(admin.ModelAdmin):
    list_display = ['itinerary', 'day_number', 'title']
    list_filter = ['day_number']