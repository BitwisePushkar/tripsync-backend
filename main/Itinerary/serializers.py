from rest_framework import serializers
from django.utils import timezone
from .models import (
    Trip, TripBudgetCategory, Place,
    Itinerary, DayPlan, Activity, ItineraryExport,
    BUDGET_CATEGORY_CHOICES, ACTIVITY_TIME_CHOICES,
    ACTIVITY_CATEGORY_CHOICES,
)

class PlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Place
        fields = [
            "place_id", "name", "address", "lat", "lng",
            "phone", "website", "rating", "photo_url",
            "types", "opening_hours",
        ]

class TripBudgetCategorySerializer(serializers.ModelSerializer):
    spent = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = TripBudgetCategory
        fields = ["id", "category", "allocated", "spent", "remaining", "percentage", "created_at", "updated_at"]
        read_only_fields = ["id", "spent", "remaining", "percentage", "created_at", "updated_at"]

    def get_percentage(self, obj):
        try:
            return round(float(obj.allocated) / float(obj.trip.total_budget) * 100, 2)
        except Exception:
            return 0.0

    def validate_allocated(self, value):
        if value < 0:
            raise serializers.ValidationError("Allocated amount must be ≥ 0.")
        return value

class TripBudgetCategoryCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=[c[0] for c in BUDGET_CATEGORY_CHOICES])
    allocated = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)

class BudgetSplitManualSerializer(serializers.Serializer):
    categories = TripBudgetCategoryCreateSerializer(many=True)

    def validate_categories(self, value):
        seen = set()
        for item in value:
            cat = item["category"]
            if cat in seen:
                raise serializers.ValidationError(f"Duplicate category: {cat}")
            seen.add(cat)
        return value

class ActivitySerializer(serializers.ModelSerializer):
    place = PlaceSerializer(read_only=True)
    budget_category = serializers.CharField(source="budget_category.category", read_only=True, allow_null=True)

    class Meta:
        model = Activity
        fields = [
            "id", "title", "description", "time", "start_time", "end_time",
            "category", "place", "location_name", "estimated_cost",
            "budget_category", "short_description", "dos_and_donts",
            "emergency_contacts", "distance_km", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "place", "created_at", "updated_at"]

class ActivityWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    time = serializers.ChoiceField(choices=[c[0] for c in ACTIVITY_TIME_CHOICES])
    start_time = serializers.TimeField(required=False, allow_null=True)
    end_time = serializers.TimeField(required=False, allow_null=True)
    category = serializers.ChoiceField(choices=[c[0] for c in ACTIVITY_CATEGORY_CHOICES])
    location_name = serializers.CharField(max_length=300, required=False, allow_blank=True)
    estimated_cost = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, default=0)
    budget_category = serializers.ChoiceField(choices=[c[0] for c in BUDGET_CATEGORY_CHOICES], required=False, allow_null=True)
    place_search_query = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    short_description = serializers.CharField(required=False, allow_blank=True)
    dos_and_donts = serializers.CharField(required=False, allow_blank=True)
    emergency_contacts = serializers.ListField(child=serializers.DictField(), required=False, default=list)
    distance_km = serializers.FloatField(required=False, allow_null=True)

class ActivityUpdateSerializer(ActivityWriteSerializer):
    title = serializers.CharField(max_length=200, required=False)
    time = serializers.ChoiceField(choices=[c[0] for c in ACTIVITY_TIME_CHOICES], required=False)
    category = serializers.ChoiceField(choices=[c[0] for c in ACTIVITY_CATEGORY_CHOICES], required=False)

class DayPlanSerializer(serializers.ModelSerializer):
    activities = serializers.SerializerMethodField()

    class Meta:
        model = DayPlan
        fields = ["id", "day_number", "title", "date", "tips", "activities", "created_at", "updated_at"]
        read_only_fields = ["id", "date", "created_at", "updated_at"]

    def get_activities(self, obj):
        qs = obj.activities.ordered_by_time()
        return ActivitySerializer(qs, many=True).data

class ManualDayPlanSerializer(serializers.Serializer):
    day_number = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200)
    tips = serializers.CharField(required=False, allow_blank=True)
    activities = ActivityWriteSerializer(many=True)

class ItinerarySerializer(serializers.ModelSerializer):
    day_plans = DayPlanSerializer(many=True, read_only=True)

    class Meta:
        model = Itinerary
        fields = ["id", "source", "last_generated_at", "day_plans", "created_at", "updated_at"]
        read_only_fields = fields

class TripOverviewSerializer(serializers.ModelSerializer):
    total_allocated = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    budget_remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    budget_categories = TripBudgetCategorySerializer(many=True, read_only=True)
    has_itinerary = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = [
            "id", "tripname", "current_loc", "destination",
            "destination_lat", "destination_lng",
            "start_date", "end_date", "days",
            "trip_type", "trip_preferences", "trending",
            "total_budget", "total_allocated", "budget_remaining",
            "budget_split_method", "budget_categories",
            "language", "has_itinerary",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_has_itinerary(self, obj):
        return hasattr(obj, "itinerary")

class TripDetailSerializer(TripOverviewSerializer):
    itinerary = ItinerarySerializer(read_only=True)

    class Meta(TripOverviewSerializer.Meta):
        fields = TripOverviewSerializer.Meta.fields + ["itinerary"]
        read_only_fields = fields

class TripCreateSerializer(serializers.Serializer):
    tripname = serializers.CharField(max_length=100)
    current_loc = serializers.CharField(max_length=200)
    destination = serializers.CharField(max_length=200)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    trip_type = serializers.ChoiceField(choices=["solo", "group"])
    trip_preferences = serializers.ChoiceField(
        choices=["relaxation", "adventure", "spiritual", "cultural", "food", "nature"]
    )
    total_budget = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=2000, max_value=10000000)

    def validate(self, data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if Trip.objects.filter(user=request.user).count() >= 10:
                raise serializers.ValidationError("Trip limit reached. You can create a maximum of 10 trips.Look forward for subscription")
        today = timezone.now().date()
        if data["start_date"] < today:
            raise serializers.ValidationError({"start_date": "Start date cannot be in the past."})
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError({"end_date": "End date must be after start date."})
        delta = (data["end_date"] - data["start_date"]).days + 1
        if delta > 30:
            raise serializers.ValidationError({"end_date": "Trip cannot exceed 30 days."})
        data["days"] = delta
        return data

class TripUpdateSerializer(serializers.Serializer):
    tripname = serializers.CharField(max_length=100, required=False)
    current_loc = serializers.CharField(max_length=200, required=False)
    destination = serializers.CharField(max_length=200, required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    trip_type = serializers.ChoiceField(choices=["solo", "group"], required=False)
    trip_preferences = serializers.ChoiceField(
        choices=["relaxation", "adventure", "spiritual", "cultural", "food", "nature"],
        required=False,
    )
    total_budget = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False)

    def validate(self, data):
        today = timezone.now().date()
        if "start_date" in data and data["start_date"] < today:
            raise serializers.ValidationError({"start_date": "Start date cannot be changed to a past date."})
        start = data.get("start_date")
        end = data.get("end_date")
        if self.instance:
            if start is None:
                start = self.instance.start_date
            if end is None:
                end = self.instance.end_date

        if start and end:
            if start > end:
                raise serializers.ValidationError({"end_date": "End date must be after start date."})
            delta = (end - start).days + 1
            if delta > 30:
                raise serializers.ValidationError({"end_date": "Trip cannot exceed 30 days."})
            data["days"] = delta
        return data

class ManualItineraryCreateSerializer(serializers.Serializer):
    day_plans = ManualDayPlanSerializer(many=True)
    def validate_day_plans(self, value):
        if not value:
            raise serializers.ValidationError("At least one day plan is required.")
        nums = [d["day_number"] for d in value]
        if len(nums) != len(set(nums)):
            raise serializers.ValidationError("Duplicate day numbers are not allowed.")
        return value

class ExportSerializer(serializers.Serializer):
    format = serializers.ChoiceField(choices=["pdf", "docx"])