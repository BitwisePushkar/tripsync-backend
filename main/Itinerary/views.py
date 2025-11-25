import re
import datetime
import logging
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import (
    Trip, TripBudgetCategory, Itinerary, DayPlan, Activity,
    BUDGET_CATEGORY_CHOICES, ACTIVITY_TIME_CHOICES, ACTIVITY_CATEGORY_CHOICES,
)
from .serializers import (
    TripCreateSerializer, TripUpdateSerializer,
    TripOverviewSerializer, TripDetailSerializer,
    TripBudgetCategorySerializer, BudgetSplitManualSerializer,
    ManualItineraryCreateSerializer, ActivitySerializer,
    ActivityWriteSerializer, ActivityUpdateSerializer,
    ExportSerializer,
)
from .ai_service import generate_budget_split, generate_itinerary
from .places_service import search_and_cache, geocode
from .export_service import generate_pdf, generate_docx

logger = logging.getLogger(__name__)

def ok(data=None, message="Success", status_code=status.HTTP_200_OK):
    body = {"success": True, "message": message}
    if data is not None:
        body["data"] = data
    return Response(body, status=status_code)

def err(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    body = {"success": False, "message": message}
    if errors:
        body["errors"] = errors
    return Response(body, status=status_code)

def _get_trip(user, pk):
    try:
        return Trip.objects.get(pk=pk, user=user)
    except Trip.DoesNotExist:
        return None

def _get_user_language(user):
    try:
        return user.profile.language or "en"
    except Exception:
        return "en"

def _clean_cost(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return max(0.0, float(val))
    try:
        return max(0.0, float(val))
    except (TypeError, ValueError):
        pass
    try:
        s = re.sub(r"[^\d.]", "", str(val))
        return max(0.0, float(s)) if s else 0.0
    except Exception:
        return 0.0

def _clean_time(val) -> datetime.time | None:
    if not val or not isinstance(val, str):
        return None
    val = val.strip().upper()
    val = re.sub(r"\s+", " ", val)
    formats = [
        "%H:%M:%S",
        "%H:%M",
        "%I:%M %p",
        "%I:%M%p",
        "%I %p",
        "%I%p",
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(val, fmt).time()
        except ValueError:
            continue

    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(AM|PM)?$", val)
    if m:
        try:
            hr   = int(m.group(1))
            mn   = int(m.group(2)) if m.group(2) else 0
            sc   = int(m.group(3)) if m.group(3) else 0
            ampm = m.group(4)
            if ampm == "PM" and hr < 12:
                hr += 12
            elif ampm == "AM" and hr == 12:
                hr = 0
            if 0 <= hr < 24 and 0 <= mn < 60 and 0 <= sc < 60:
                return datetime.time(hr, mn, sc)
        except Exception:
            pass
    return None

def _save_itinerary_from_ai(itinerary: Itinerary, ai_data: dict, trip: Trip) -> None:
    valid_budget_cats   = {c[0] for c in BUDGET_CATEGORY_CHOICES}
    valid_times         = {c[0] for c in ACTIVITY_TIME_CHOICES}
    valid_activity_cats = {c[0] for c in ACTIVITY_CATEGORY_CHOICES}
    budget_cat_map: dict[str, TripBudgetCategory] = {
        bc.category: bc for bc in TripBudgetCategory.objects.filter(trip=trip)
    }

    with transaction.atomic():
        for day_data in ai_data.get("day_plans", []):
            day_number = day_data.get("day_number")
            if day_number is None:
                logger.warning("Skipping day plan with missing day_number.")
                continue

            day_plan = DayPlan.objects.create(
                itinerary=itinerary,
                day_number=int(day_number),
                title=day_data.get("title") or f"Day {day_number}",
                tips=day_data.get("tips") or "",
            )

            for act in day_data.get("activities") or []:
                t = str(act.get("time", "morning")).strip().lower()
                if t not in valid_times:
                    t = "morning"

                c = str(act.get("category", "sightseeing")).strip().lower()
                if c not in valid_activity_cats:
                    c = "sightseeing"

                bc_name = act.get("budget_category")
                if bc_name:
                    bc_name = str(bc_name).strip().lower()
                    if bc_name not in valid_budget_cats:
                        bc_name = "other"
                else:
                    bc_name = "other"

                bc    = budget_cat_map.get(bc_name)
                place = None
                query = (act.get("place_search_query") or "").strip()
                if query:
                    try:
                        place = search_and_cache(query)
                    except Exception as e:
                        logger.debug(
                            "Place lookup failed for query '%s' (activity='%s'): %s",
                            query, act.get("title", ""), e,
                        )

                cost = _clean_cost(act.get("estimated_cost", 0))
                st   = _clean_time(act.get("start_time"))
                et   = _clean_time(act.get("end_time"))

                dist = act.get("distance_km")
                if dist is not None:
                    try:
                        dist = float(dist)
                    except (TypeError, ValueError):
                        dist = None

                contacts = act.get("emergency_contacts") or []
                if not isinstance(contacts, list):
                    contacts = []

                Activity.objects.create(
                    day_plans=day_plan,
                    title=act.get("title") or "",
                    description=act.get("description") or "",
                    time=t,
                    start_time=st,
                    end_time=et,
                    category=c,
                    place=place,
                    location_name=act.get("location_name") or "",
                    budget_category=bc,
                    estimated_cost=cost,
                    short_description=act.get("short_description") or "",
                    dos_and_donts=act.get("dos_and_donts") or "",
                    emergency_contacts=contacts,
                    distance_km=dist,
                )

        itinerary.last_generated_at = timezone.now()
        itinerary.save(update_fields=["last_generated_at", "updated_at"])

class TripListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Trip"], summary="List all trips")
    def get(self, request):
        trips = (
            Trip.objects
            .filter(user=request.user)
            .prefetch_related("budget_categories")
            .order_by("-created_at")
        )
        return ok(TripOverviewSerializer(trips, many=True).data)

    @extend_schema(tags=["Trip"], summary="Create trip", request=TripCreateSerializer)
    def post(self, request):
        s = TripCreateSerializer(data=request.data, context={"request": request})
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        data = s.validated_data
        lang = _get_user_language(request.user)
        lat, lng = geocode(data["destination"])

        with transaction.atomic():
            trip = Trip.objects.create(
                user=request.user,
                tripname=data["tripname"],
                current_loc=data["current_loc"],
                destination=data["destination"],
                destination_lat=lat,
                destination_lng=lng,
                start_date=data["start_date"],
                end_date=data["end_date"],
                days=data["days"],
                trip_type=data["trip_type"],
                trip_preferences=data["trip_preferences"],
                total_budget=data["total_budget"],
                language=lang,
            )

        return ok(TripOverviewSerializer(trip).data, "Trip created.", status.HTTP_201_CREATED)

class TripDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Trip"], summary="Get trip overview")
    def get(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
        return ok(TripOverviewSerializer(trip).data)

    @extend_schema(tags=["Trip"], summary="Update trip", request=TripUpdateSerializer)
    def patch(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)

        s = TripUpdateSerializer(instance=trip, data=request.data, partial=True)
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        new_budget = s.validated_data.get("total_budget")
        if new_budget is not None and new_budget < trip.total_allocated:
            return err(
                f"New total budget ({new_budget}) cannot be less than the already "
                f"allocated amount ({trip.total_allocated}). "
                "Please reduce your category allocations first."
            )

        for field, value in s.validated_data.items():
            setattr(trip, field, value)
        if "destination" in s.validated_data:
            lat, lng = geocode(s.validated_data["destination"])
            trip.destination_lat = lat
            trip.destination_lng = lng
        trip.save()
        return ok(TripOverviewSerializer(trip).data, "Trip updated.")

    @extend_schema(tags=["Trip"], summary="Delete trip")
    def delete(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
        trip.delete()
        return ok(message="Trip deleted.")

class TripFullDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Trip"], summary="Get full trip detail (with itinerary)")
    def get(self, request, trip_id):
        try:
            trip = (
                Trip.objects
                .prefetch_related(
                    "budget_categories",
                    "itinerary__day_plans__activities__place",
                    "itinerary__day_plans__activities__budget_category",
                )
                .get(pk=trip_id, user=request.user)
            )
        except Trip.DoesNotExist:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
        return ok(TripDetailSerializer(trip).data)

class TripBudgetAIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Budget"], summary="AI: auto-split trip budget into categories")
    def post(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)

        if trip.budget_categories.exists():
            return err("Budget already split. Delete existing categories first or use manual update.")

        result = generate_budget_split({
            "destination":      trip.destination,
            "days":             trip.days,
            "trip_type":        trip.trip_type,
            "trip_preferences": trip.trip_preferences,
            "total_budget":     float(trip.total_budget),
            "language":         trip.language,
        })

        if not result["success"]:
            return err(f"AI failed: {result['error']}", status_code=status.HTTP_502_BAD_GATEWAY)

        valid_cats = {c[0] for c in BUDGET_CATEGORY_CHOICES}
        seen: dict[str, float] = {}
        for item in result["data"]:
            cat_name = str(item.get("category", "")).strip().lower()
            if cat_name in valid_cats:
                seen[cat_name] = _clean_cost(item.get("allocated", 0))

        if not seen:
            return err("AI returned no valid budget categories.", status_code=status.HTTP_502_BAD_GATEWAY)

        with transaction.atomic():
            trip.budget_split_method = "ai"
            trip.save(update_fields=["budget_split_method", "updated_at"])

            cats = []
            for category, allocated in seen.items():
                obj, _ = TripBudgetCategory.objects.get_or_create(
                    trip=trip,
                    category=category,
                    defaults={"allocated": allocated},
                )
                if not _:
                    obj.allocated = allocated
                    obj.save(update_fields=["allocated", "updated_at"])
                cats.append(obj)

        return ok(
            TripBudgetCategorySerializer(cats, many=True).data,
            "Budget split by AI.",
            status.HTTP_201_CREATED,
        )

class TripBudgetManualView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Budget"], summary="Manual: set trip budget categories", request=BudgetSplitManualSerializer)
    def post(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)

        s = BudgetSplitManualSerializer(data=request.data)
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        cats_data = s.validated_data["categories"]
        total = sum(float(c["allocated"]) for c in cats_data)
        if total > float(trip.total_budget):
            return err(
                f"Total allocated ({total}) exceeds trip budget ({trip.total_budget})."
            )

        with transaction.atomic():
            trip.budget_split_method = "manual"
            trip.save(update_fields=["budget_split_method", "updated_at"])

            new_cats = {c["category"]: c["allocated"] for c in cats_data}
            trip.budget_categories.exclude(category__in=new_cats.keys()).delete()
            cats = []
            for category, allocated in new_cats.items():
                obj, _ = TripBudgetCategory.objects.update_or_create(
                    trip=trip,
                    category=category,
                    defaults={"allocated": allocated},
                )
                cats.append(obj)

        return ok(
            TripBudgetCategorySerializer(cats, many=True).data,
            "Budget categories saved.",
            status.HTTP_201_CREATED,
        )

class TripBudgetCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_cat(self, user, trip_id, cat_id):
        try:
            return TripBudgetCategory.objects.select_related("trip").get(
                pk=cat_id, trip__user=user, trip_id=trip_id
            )
        except TripBudgetCategory.DoesNotExist:
            return None

    @extend_schema(tags=["Budget"], summary="Update a budget category")
    def patch(self, request, trip_id, cat_id):
        cat = self._get_cat(request.user, trip_id, cat_id)
        if not cat:
            return err("Budget category not found.", status_code=status.HTTP_404_NOT_FOUND)

        s = TripBudgetCategorySerializer(cat, data=request.data, partial=True)
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        new_alloc = float(s.validated_data.get("allocated", cat.allocated))
        others_total = (
            cat.trip.budget_categories
            .exclude(pk=cat.pk)
            .aggregate(t=Sum("allocated"))["t"] or 0
        )
        if float(others_total) + new_alloc > float(cat.trip.total_budget):
            return err("Updated allocation would exceed total trip budget.")

        s.save()
        return ok(TripBudgetCategorySerializer(cat).data, "Category updated.")

    @extend_schema(tags=["Budget"], summary="Delete a budget category")
    def delete(self, request, trip_id, cat_id):
        cat = self._get_cat(request.user, trip_id, cat_id)
        if not cat:
            return err("Budget category not found.", status_code=status.HTTP_404_NOT_FOUND)
        cat.delete()
        return ok(message="Budget category deleted.")

class ItineraryAICreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Itinerary"], summary="AI: generate itinerary")
    def post(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)

        if not trip.budget_categories.exists():
            return err("Set trip budget categories before generating an itinerary.")

        if hasattr(trip, "itinerary"):
            return err("Itinerary already exists. Use the regenerate endpoint.")

        budget_cats = [
            {"category": bc.category, "allocated": float(bc.allocated)}
            for bc in trip.budget_categories.all()
        ]

        result = generate_itinerary({
            "tripname":          trip.tripname,
            "destination":       trip.destination,
            "current_loc":       trip.current_loc,
            "days":              trip.days,
            "trip_type":         trip.trip_type,
            "trip_preferences":  trip.trip_preferences,
            "total_budget":      float(trip.total_budget),
            "language":          trip.language,
            "budget_categories": budget_cats,
        })

        if not result["success"]:
            return err(f"AI failed: {result['error']}", status_code=status.HTTP_502_BAD_GATEWAY)

        with transaction.atomic():
            itinerary = Itinerary.objects.create(trip=trip, source="ai")
            try:
                _save_itinerary_from_ai(itinerary, result["data"], trip)
            except Exception as e:
                logger.error("Failed to save AI itinerary for trip %s: %s", trip_id, e, exc_info=True)
                itinerary.delete()
                return err(
                    "Itinerary data could not be saved. Please try regenerating.",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        trip.refresh_from_db()
        response_data = TripDetailSerializer(trip).data
        if "warning" in result:
            return Response(
                {"success": True, "message": result["warning"], "data": response_data},
                status=status.HTTP_201_CREATED,
            )

        return ok(response_data, "Itinerary generated.", status.HTTP_201_CREATED)

class ItineraryManualCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Itinerary"], summary="Manual: create itinerary", request=ManualItineraryCreateSerializer)
    def post(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)

        if hasattr(trip, "itinerary"):
            return err("Itinerary already exists. Delete it first.")

        s = ManualItineraryCreateSerializer(data=request.data)
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        with transaction.atomic():
            itinerary = Itinerary.objects.create(trip=trip, source="manual")
            for day_data in s.validated_data["day_plans"]:
                activities_data = day_data.pop("activities", [])
                day_plan = DayPlan.objects.create(
                    itinerary=itinerary,
                    day_number=day_data["day_number"],
                    title=day_data["title"],
                    tips=day_data.get("tips", ""),
                )
                for act in activities_data:
                    bc_name = act.pop("budget_category", None)
                    bc = None
                    if bc_name:
                        bc = TripBudgetCategory.objects.filter(trip=trip, category=bc_name).first()

                    query = act.pop("place_search_query", None)
                    place = None
                    if query:
                        try:
                            place = search_and_cache(query)
                        except Exception as e:
                            logger.debug("Place lookup failed for query '%s': %s", query, e)

                    Activity.objects.create(
                        day_plans=day_plan,
                        budget_category=bc,
                        place=place,
                        **act,
                    )

        trip.refresh_from_db()
        return ok(TripDetailSerializer(trip).data, "Manual itinerary created.", status.HTTP_201_CREATED)

class ItineraryRegenerateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Itinerary"], summary="AI: regenerate itinerary (5-min cooldown)")
    def post(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)

        if not hasattr(trip, "itinerary"):
            return err("No itinerary to regenerate. Use the generate endpoint.")

        allowed, wait = trip.itinerary.can_regenerate()
        if not allowed:
            return err(
                f"Please wait {wait} more seconds before regenerating.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        budget_cats = [
            {"category": bc.category, "allocated": float(bc.allocated)}
            for bc in trip.budget_categories.all()
        ]

        result = generate_itinerary({
            "tripname":          trip.tripname,
            "destination":       trip.destination,
            "current_loc":       trip.current_loc,
            "days":              trip.days,
            "trip_type":         trip.trip_type,
            "trip_preferences":  trip.trip_preferences,
            "total_budget":      float(trip.total_budget),
            "language":          trip.language,
            "budget_categories": budget_cats,
        })

        if not result["success"]:
            return err(f"AI failed: {result['error']}", status_code=status.HTTP_502_BAD_GATEWAY)

        with transaction.atomic():
            trip.itinerary.day_plans.all().delete()
            trip.itinerary.source = "ai"
            trip.itinerary.save(update_fields=["source", "updated_at"])
            try:
                _save_itinerary_from_ai(trip.itinerary, result["data"], trip)
            except Exception as e:
                logger.error("Failed to save regenerated itinerary for trip %s: %s", trip_id, e, exc_info=True)
                raise 

        trip.refresh_from_db()
        response_data = TripDetailSerializer(trip).data

        if "warning" in result:
            return Response(
                {"success": True, "message": result["warning"], "data": response_data},
                status=status.HTTP_200_OK,
            )

        return ok(response_data, "Itinerary regenerated.")

class ItineraryDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Itinerary"], summary="Delete itinerary")
    def delete(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
        if not hasattr(trip, "itinerary"):
            return err("No itinerary found.", status_code=status.HTTP_404_NOT_FOUND)
        trip.itinerary.delete()
        return ok(message="Itinerary deleted.")

class DayPlanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_day(self, user, trip_id, day_number):
        try:
            return DayPlan.objects.select_related("itinerary__trip").get(
                itinerary__trip__user=user,
                itinerary__trip_id=trip_id,
                day_number=day_number,
            )
        except DayPlan.DoesNotExist:
            return None

    @extend_schema(tags=["Day Plan"], summary="Get day plan")
    def get(self, request, trip_id, day_number):
        from .serializers import DayPlanSerializer
        day = self._get_day(request.user, trip_id, day_number)
        if not day:
            return err("Day plan not found.", status_code=status.HTTP_404_NOT_FOUND)
        return ok(DayPlanSerializer(day).data)

    @extend_schema(tags=["Day Plan"], summary="Update day plan title/tips")
    def patch(self, request, trip_id, day_number):
        from .serializers import DayPlanSerializer
        day = self._get_day(request.user, trip_id, day_number)
        if not day:
            return err("Day plan not found.", status_code=status.HTTP_404_NOT_FOUND)
        update_fields = []
        if "title" in request.data:
            day.title = request.data["title"]
            update_fields.append("title")
        if "tips" in request.data:
            day.tips = request.data["tips"]
            update_fields.append("tips")
        if update_fields:
            update_fields.append("updated_at")
            day.save(update_fields=update_fields)
        return ok(DayPlanSerializer(day).data, "Day plan updated.")

class ActivityListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_day(self, user, trip_id, day_number):
        try:
            return DayPlan.objects.get(
                itinerary__trip__user=user,
                itinerary__trip_id=trip_id,
                day_number=day_number,
            )
        except DayPlan.DoesNotExist:
            return None

    @extend_schema(tags=["Activity"], summary="Add activity to day plan", request=ActivityWriteSerializer)
    def post(self, request, trip_id, day_number):
        day = self._get_day(request.user, trip_id, day_number)
        if not day:
            return err("Day plan not found.", status_code=status.HTTP_404_NOT_FOUND)

        s = ActivityWriteSerializer(data=request.data)
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        data = dict(s.validated_data)
        bc_name = data.pop("budget_category", None)
        bc = None
        if bc_name:
            bc = TripBudgetCategory.objects.filter(trip_id=trip_id, category=bc_name).first()

        query = data.pop("place_search_query", None)
        place = None
        if query:
            try:
                place = search_and_cache(query)
            except Exception as e:
                logger.debug("Place lookup failed for query '%s': %s", query, e)

        activity = Activity.objects.create(
            day_plans=day,
            budget_category=bc,
            place=place,
            **data,
        )
        return ok(ActivitySerializer(activity).data, "Activity added.", status.HTTP_201_CREATED)

class ActivityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_activity(self, user, trip_id, day_number, activity_id):
        try:
            return (
                Activity.objects
                .select_related("place", "budget_category", "day_plans__itinerary__trip")
                .get(
                    pk=activity_id,
                    day_plans__day_number=day_number,
                    day_plans__itinerary__trip_id=trip_id,
                    day_plans__itinerary__trip__user=user,
                )
            )
        except Activity.DoesNotExist:
            return None

    @extend_schema(tags=["Activity"], summary="Update activity", request=ActivityUpdateSerializer)
    def patch(self, request, trip_id, day_number, activity_id):
        act = self._get_activity(request.user, trip_id, day_number, activity_id)
        if not act:
            return err("Activity not found.", status_code=status.HTTP_404_NOT_FOUND)

        s = ActivityUpdateSerializer(data=request.data, partial=True)
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        data = dict(s.validated_data)
        bc_name = data.pop("budget_category", None)
        if bc_name is not None:
            act.budget_category = TripBudgetCategory.objects.filter(
                trip_id=trip_id, category=bc_name
            ).first()

        query = data.pop("place_search_query", None)
        if query is not None:
            place = None
            if query:
                try:
                    place = search_and_cache(query)
                except Exception as e:
                    logger.debug("Place lookup failed for query '%s': %s", query, e)
            act.place = place

        for field, value in data.items():
            setattr(act, field, value)
        act.save()

        from .serializers import ActivitySerializer
        return ok(ActivitySerializer(act).data, "Activity updated.")

    @extend_schema(tags=["Activity"], summary="Delete activity")
    def delete(self, request, trip_id, day_number, activity_id):
        act = self._get_activity(request.user, trip_id, day_number, activity_id)
        if not act:
            return err("Activity not found.", status_code=status.HTTP_404_NOT_FOUND)
        act.delete()
        return ok(message="Activity deleted.")

class ItineraryExportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Export"], summary="Download itinerary as PDF or DOCX", request=ExportSerializer)
    def post(self, request, trip_id):
        trip = _get_trip(request.user, trip_id)
        if not trip:
            return err("Trip not found.", status_code=status.HTTP_404_NOT_FOUND)
        if not hasattr(trip, "itinerary"):
            return err("No itinerary to export.", status_code=status.HTTP_404_NOT_FOUND)

        s = ExportSerializer(data=request.data)
        if not s.is_valid():
            return err("Validation failed.", errors=s.errors)

        fmt       = s.validated_data["format"]
        safe_name = "".join(c if c.isalnum() else "_" for c in trip.tripname)

        try:
            if fmt == "pdf":
                content      = generate_pdf(trip)
                content_type = "application/pdf"
                filename     = f"{safe_name}_itinerary.pdf"
            else:
                content      = generate_docx(trip)
                content_type = (
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                )
                filename = f"{safe_name}_itinerary.docx"
        except Exception as e:
            logger.error("Export error trip=%s fmt=%s: %s", trip_id, fmt, e, exc_info=True)
            return err(
                "Export generation failed.",
                errors={"detail": str(e)},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response