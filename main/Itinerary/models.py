import datetime
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Case, When, Value, IntegerField, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

TRIP_TYPE_CHOICES = [
    ("solo",  "Solo"),
    ("group", "Group"),
]
TRIP_PREFERENCE_CHOICES = [
    ("relaxation", "Relaxation"),
    ("adventure",  "Adventure"),
    ("spiritual",  "Spiritual"),
    ("cultural",   "Cultural"),
    ("food",       "Food & Culinary"),
    ("nature",     "Nature"),
]
BUDGET_CATEGORY_CHOICES = [
    ("accommodation", "Accommodation"),
    ("food",          "Food & Dining"),
    ("transport",     "Transport"),
    ("activities",    "Activities & Sightseeing"),
    ("shopping",      "Shopping"),
    ("emergency",     "Emergency"),
    ("other",         "Other"),
]
BUDGET_SPLIT_CHOICES = [
    ("ai",     "AI Generated"),
    ("manual", "Manually Set"),
]
ACTIVITY_TIME_CHOICES = [
    ("morning",   "Morning"),
    ("afternoon", "Afternoon"),
    ("evening",   "Evening"),
    ("night",     "Night"),
]
ACTIVITY_CATEGORY_CHOICES = [
    ("sightseeing",     "Sightseeing"),
    ("dining",          "Dining"),
    ("shopping",        "Shopping"),
    ("transportation",  "Transportation"),
    ("adventure",       "Adventure"),
    ("relaxation",      "Relaxation"),
    ("accommodation",   "Accommodation"),
    ("emergency",       "Emergency"),
]
ITINERARY_SOURCE_CHOICES = [
    ("ai",     "AI Generated"),
    ("manual", "Manual"),
]
EXPORT_FORMAT_CHOICES = [
    ("pdf",  "PDF"),
    ("docx", "Word Document"),
]

class Place(models.Model):
    place_id        = models.CharField(max_length=200, unique=True, db_index=True)
    name            = models.CharField(max_length=300)
    address         = models.CharField(max_length=500, blank=True)
    lat             = models.FloatField()
    lng             = models.FloatField()
    phone           = models.CharField(max_length=50, blank=True)
    website         = models.URLField(blank=True)
    rating          = models.FloatField(null=True, blank=True)
    photo_reference = models.CharField(max_length=600, blank=True)
    photo_url       = models.URLField(max_length=1000, blank=True)
    types           = models.JSONField(default=list)
    opening_hours   = models.JSONField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Place"

    def __str__(self):
        return self.name or f"Place({self.place_id})"

class Trip(models.Model):
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trips"
    )
    tripname        = models.CharField(max_length=100)
    current_loc     = models.CharField(max_length=200)
    destination     = models.CharField(max_length=200)
    destination_lat = models.FloatField(null=True, blank=True)
    destination_lng = models.FloatField(null=True, blank=True)
    trending        = models.BooleanField(default=False)
    start_date      = models.DateField()
    end_date        = models.DateField()
    days            = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(30)])
    trip_type       = models.CharField(max_length=20, choices=TRIP_TYPE_CHOICES)
    trip_preferences= models.CharField(max_length=20, choices=TRIP_PREFERENCE_CHOICES)
    total_budget    = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    budget_split_method = models.CharField(
        max_length=10, choices=BUDGET_SPLIT_CHOICES, default="ai"
    )
    language        = models.CharField(max_length=10, default="en")
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trip"
        ordering     = ["-created_at"]

    def __str__(self):
        return f"{self.tripname or 'Trip'} → {self.destination or '?'}"

    def save(self, *args, **kwargs):
        is_new         = self.pk is None
        old_start_date = None
        old_days       = None

        if not is_new:
            try:
                old = Trip.objects.get(pk=self.pk)
                old_start_date = old.start_date
                old_days       = old.days
            except Trip.DoesNotExist:
                pass

        super().save(*args, **kwargs)
        if not is_new:
            try:
                itinerary = self.itinerary
            except Exception:
                itinerary = None

            if itinerary is not None:
                if old_days is not None and self.days != old_days:
                    if self.days < old_days:
                        itinerary.day_plans.filter(day_number__gt=self.days).delete()
                    else:
                        for d in range(old_days + 1, self.days + 1):
                            DayPlan.objects.get_or_create(
                                itinerary=itinerary,
                                day_number=d,
                                defaults={"title": f"Day {d} Plan", "tips": ""},
                            )

                if old_start_date is not None and (
                    self.start_date != old_start_date or self.days != old_days
                ):
                    for dp in itinerary.day_plans.all():
                        dp.date = self.start_date + datetime.timedelta(days=dp.day_number - 1)
                        dp.save(update_fields=["date", "updated_at"])

    @property
    def total_allocated(self):
        return self.budget_categories.aggregate(t=Sum("allocated"))["t"] or 0

    @property
    def budget_remaining(self):
        return self.total_budget - self.total_allocated

class TripBudgetCategory(models.Model):
    trip      = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="budget_categories")
    category  = models.CharField(max_length=20, choices=BUDGET_CATEGORY_CHOICES)
    allocated = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["trip", "category"]
        ordering        = ["category"]
        verbose_name    = "Trip Budget Category"

    def __str__(self):
        return f"{self.trip.tripname}/{self.category}: {self.allocated}"

    @property
    def spent(self):
        return (
            Activity.objects
            .filter(
                day_plans__itinerary__trip=self.trip,
                budget_category=self,
            )
            .aggregate(t=Sum("estimated_cost"))["t"] or 0
        )

    @property
    def remaining(self):
        return self.allocated - self.spent

class Itinerary(models.Model):
    COOLDOWN_SECONDS = 300

    trip              = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="itinerary")
    source            = models.CharField(max_length=10, choices=ITINERARY_SOURCE_CHOICES, default="ai")
    last_generated_at = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Itinerary"

    def __str__(self):
        return f"Itinerary — {self.trip.tripname}"

    def can_regenerate(self) -> tuple[bool, int]:
        if not self.last_generated_at:
            return True, 0
        elapsed = (timezone.now() - self.last_generated_at).total_seconds()
        wait    = self.COOLDOWN_SECONDS - elapsed
        return (True, 0) if wait <= 0 else (False, int(wait))

class DayPlan(models.Model):
    itinerary  = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name="day_plans")
    day_number = models.IntegerField()
    title      = models.CharField(max_length=200)
    date       = models.DateField(null=True, blank=True)
    tips       = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering       = ["day_number"]
        unique_together = ["itinerary", "day_number"]
        verbose_name   = "Day Plan"

    def __str__(self):
        return f"Day {self.day_number}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.date:
            try:
                self.date = (
                    self.itinerary.trip.start_date
                    + datetime.timedelta(days=self.day_number - 1)
                )
            except Exception:
                pass
        super().save(*args, **kwargs)


class ActivityQuerySet(models.QuerySet):
    def ordered_by_time(self):
        return self.annotate(
            _order=Case(
                When(time="morning",   then=Value(1)),
                When(time="afternoon", then=Value(2)),
                When(time="evening",   then=Value(3)),
                When(time="night",     then=Value(4)),
                output_field=IntegerField(),
            )
        ).order_by("_order")


class Activity(models.Model):
    day_plans         = models.ForeignKey(
        DayPlan, on_delete=models.CASCADE, related_name="activities"
    )
    title             = models.CharField(max_length=200)
    description       = models.TextField(blank=True)
    time              = models.CharField(max_length=10, choices=ACTIVITY_TIME_CHOICES)
    start_time        = models.TimeField(null=True, blank=True)
    end_time          = models.TimeField(null=True, blank=True)
    category          = models.CharField(max_length=20, choices=ACTIVITY_CATEGORY_CHOICES)
    place             = models.ForeignKey(
        Place, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities"
    )
    location_name     = models.CharField(max_length=300, blank=True)
    budget_category   = models.ForeignKey(
        TripBudgetCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="activities",
    )
    estimated_cost    = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    short_description = models.TextField(blank=True)
    dos_and_donts     = models.TextField(blank=True)
    emergency_contacts= models.JSONField(default=list)
    distance_km       = models.FloatField(null=True, blank=True)
    objects           = ActivityQuerySet.as_manager()
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Activity"

    def __str__(self):
        return f"[{self.time}] {self.title}"

class ItineraryExport(models.Model):
    trip       = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="exports")
    format     = models.CharField(max_length=10, choices=EXPORT_FORMAT_CHOICES)
    file       = models.FileField(upload_to="exports/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering     = ["-created_at"]
        verbose_name = "Itinerary Export"

    def __str__(self):
        return f"{self.trip.tripname} — {self.format}"