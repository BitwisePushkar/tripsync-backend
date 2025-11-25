import logging
import requests
from django.conf import settings
from .models import Place

logger = logging.getLogger(__name__)

_BASE  = "https://maps.googleapis.com/maps/api/place"
_GEO   = "https://maps.googleapis.com/maps/api/geocode/json"
_PHOTO = f"{_BASE}/photo"

_FIND_FIELDS = (
    "place_id,name,formatted_address,geometry,rating,photos,types"
)

_DETAIL_FIELDS = (
    "place_id,name,formatted_address,geometry,rating,photos,types,"
    "formatted_phone_number,website,opening_hours"
)

_DEFAULT_TIMEOUT = 8  

def _key() -> str:
    return getattr(settings, "GOOGLE_PLACES_API_KEY", "")

def _photo_width() -> int:
    return getattr(settings, "GOOGLE_PLACES_PHOTO_MAX_WIDTH", 800)

def build_photo_url(ref: str) -> str:
    key = _key()
    if not ref or not key:
        return ""
    return f"{_PHOTO}?maxwidth={_photo_width()}&photoreference={ref}&key={key}"

def geocode(location: str) -> tuple[float | None, float | None]:
    key = _key()
    if not key:
        logger.warning("GOOGLE_PLACES_API_KEY not set — geocode skipped for '%s'.", location)
        return None, None
    try:
        r = requests.get(
            _GEO,
            params={"address": location, "key": key},
            timeout=_DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            loc = results[0]["geometry"]["location"]
            return float(loc["lat"]), float(loc["lng"])
        logger.warning("Geocode returned no results for '%s'.", location)
    except requests.RequestException as e:
        logger.error("Geocode network error for '%s': %s", location, e)
    except Exception as e:
        logger.error("Geocode unexpected error for '%s': %s", location, e)
    return None, None

def _parse_candidate(result: dict) -> dict:
    loc    = result.get("geometry", {}).get("location", {})
    photos = result.get("photos", [])
    photo_ref = photos[0].get("photo_reference", "") if photos else ""

    hours_raw = result.get("opening_hours") or {}
    opening_hours = hours_raw.get("weekday_text") or None  # list[str] or None

    return {
        "place_id":        result.get("place_id", ""),
        "name":            result.get("name", ""),
        "address":         result.get("formatted_address", ""),
        "lat":             float(loc.get("lat", 0.0)),
        "lng":             float(loc.get("lng", 0.0)),
        "phone":           result.get("formatted_phone_number", ""),
        "website":         result.get("website", ""),
        "rating":          result.get("rating"),          # float or None
        "photo_reference": photo_ref,
        "photo_url":       build_photo_url(photo_ref),
        "types":           result.get("types", []),
        "opening_hours":   opening_hours,
    }


def _fetch_place_details(place_id: str) -> dict | None:
    key = _key()
    if not key or not place_id:
        return None
    try:
        r = requests.get(
            f"{_BASE}/details/json",
            params={"place_id": place_id, "fields": _DETAIL_FIELDS, "key": key},
            timeout=_DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        payload = r.json()
        if payload.get("status") != "OK":
            logger.warning(
                "Place Details non-OK status '%s' for place_id=%s",
                payload.get("status"), place_id,
            )
            return None
        return payload.get("result")
    except requests.RequestException as e:
        logger.error("Place Details network error for place_id=%s: %s", place_id, e)
    except Exception as e:
        logger.error("Place Details unexpected error for place_id=%s: %s", place_id, e)
    return None

def search_and_cache(query: str, location_bias: str = "") -> "Place | None":
    key = _key()
    if not key:
        logger.warning("GOOGLE_PLACES_API_KEY not set — skipping place lookup for '%s'.", query)
        return None

    if not query or not query.strip():
        logger.debug("search_and_cache called with empty query — skipping.")
        return None

    params: dict = {
        "input":     query.strip(),
        "inputtype": "textquery",
        "fields":    _FIND_FIELDS,
        "key":       key,
    }
    if location_bias:
        params["locationbias"] = location_bias

    try:
        r = requests.get(
            f"{_BASE}/findplacefromtext/json",
            params=params,
            timeout=_DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        payload    = r.json()
        status     = payload.get("status", "")
        candidates = payload.get("candidates", [])

        if status not in ("OK", "ZERO_RESULTS"):
            logger.warning(
                "Find Place returned status '%s' for query '%s'. Error: %s",
                status, query, payload.get("error_message", ""),
            )

        if not candidates:
            logger.debug("No place candidates for query '%s'.", query)
            return None

        candidate = candidates[0]
        place_id  = candidate.get("place_id", "")
        if not place_id:
            logger.warning("Find Place candidate missing place_id for query '%s'.", query)
            return None

    except requests.RequestException as e:
        logger.error("Find Place network error for query '%s': %s", query, e)
        return None
    except Exception as e:
        logger.error("Find Place unexpected error for query '%s': %s", query, e)
        return None

    details = _fetch_place_details(place_id)
    source  = details if details else candidate

    data = _parse_candidate(source)
    if not data["place_id"]:
        logger.warning("Parsed data has no place_id for query '%s'.", query)
        return None


    try:
        place, created = Place.objects.update_or_create(
            place_id=data["place_id"],
            defaults=data,
        )
        if created:
            logger.debug("New Place cached: %s (query='%s')", place.name, query)
        return place
    except Exception as e:
        logger.error("DB upsert error for place_id=%s query='%s': %s", data["place_id"], query, e)
        return None