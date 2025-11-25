from __future__ import annotations
import json
import logging
import re
import textwrap
import time
from typing import Any
from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

MAX_RETRIES  = 3
RETRY_DELAY  = 15 

TRANSIENT_ERROR_KEYS = (
    "429",
    "rate limit",
    "quota",
    "503",
    "service unavailable",
    "overloaded",
    "loading",
    "resource exhausted",  
)

LANG_NAMES: dict[str, str] = {
    "en": "English",              "hi": "Hindi",       "fr": "French",
    "de": "German",               "es": "Spanish",     "ar": "Arabic",
    "zh": "Chinese (Simplified)", "ja": "Japanese",
    "pt": "Portuguese",           "ru": "Russian",     "it": "Italian",
    "ko": "Korean",               "ta": "Tamil",       "te": "Telugu",
    "mr": "Marathi",              "bn": "Bengali",
}

BUDGET_CATS: list[str] = [
    "accommodation", "food", "transport", "activities",
    "shopping", "emergency", "other",
]
ACTIVITY_TIMES: list[str] = ["morning", "afternoon", "evening", "night"]
ACTIVITY_CATS: list[str] = [
    "sightseeing", "dining", "shopping", "transportation",
    "adventure", "relaxation", "accommodation", "emergency",
]

_BUDGET_REQUIRED_KEYS = frozenset({
    "destination", "days", "trip_type", "trip_preferences", "total_budget",
})
_ITINERARY_REQUIRED_KEYS = frozenset({
    "tripname", "destination", "current_loc", "days",
    "trip_type", "trip_preferences", "total_budget",
})

class MissingGeminiKeyError(RuntimeError):
    pass

class TruncatedResponseError(ValueError):
    pass

_llm_instance: ChatGoogleGenerativeAI | None = None

def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    api_key: str | None = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise MissingGeminiKeyError(
            "GEMINI_API_KEY is required in Django settings to use the Gemini API."
        )

    model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash")
    temperature = getattr(settings, "GEMINI_TEMPERATURE",  0.3)
    max_tokens = getattr(settings, "GEMINI_MAX_TOKENS",   8192)

    logger.info(
        "Initialising ChatGoogleGenerativeAI: model=%s temperature=%s max_tokens=%d",
        model, temperature, max_tokens,
    )

    try:
        _llm_instance = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",  
            max_retries=1,       
            timeout=60.0,        
            convert_system_message_to_human=False,
        )
    except Exception:
        logger.exception("Failed to initialise ChatGoogleGenerativeAI (model='%s').", model)
        raise

    return _llm_instance

def _reset_llm() -> None:
    global _llm_instance
    _llm_instance = None

def _clean(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _repair_truncated_json(text: str) -> str:
    if not text:
        return text

    open_braces = open_brackets = 0
    in_string = escape_next = False
    last_balanced = 0

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if   ch == "{": open_braces   += 1
        elif ch == "}": open_braces   -= 1
        elif ch == "[": open_brackets += 1
        elif ch == "]": open_brackets -= 1

        if open_braces == 0 and open_brackets == 0 and i > 0:
            last_balanced = i + 1

    if last_balanced and last_balanced < len(text):
        candidate = text[:last_balanced]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    stripped = text

    last_quote = -1
    for i in range(len(text) - 1, -1, -1):
        if text[i] == '"':
            n_bs = 0
            j = i - 1
            while j >= 0 and text[j] == "\\":
                n_bs += 1
                j -= 1
            if n_bs % 2 == 0:
                last_quote = i
                break

    if last_quote != -1:
        has_close = False
        k = last_quote + 1
        while k < len(text):
            if text[k] == "\\":
                k += 2
                continue
            if text[k] == '"':
                has_close = True
                break
            k += 1
        if not has_close:
            stripped = text[:last_quote].rstrip().rstrip(",").rstrip()

    if not stripped:
        return text

    depth_stack: list[str] = []
    in_str = esc = False
    for ch in stripped:
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in ("{", "["):
            depth_stack.append(ch)
        elif ch == "}" and depth_stack and depth_stack[-1] == "{":
            depth_stack.pop()
        elif ch == "]" and depth_stack and depth_stack[-1] == "[":
            depth_stack.pop()

    closing = "".join("}" if o == "{" else "]" for o in reversed(depth_stack))
    return stripped + closing


def _parse_ai_json(raw: str) -> Any:
    cleaned = _clean(raw)
    if not cleaned:
        raise json.JSONDecodeError("Model returned empty content after cleaning.", "", 0)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as original_err:
        logger.warning("Initial JSON parse failed (%s); attempting repair.", original_err)
        repaired = _repair_truncated_json(cleaned)
        try:
            result = json.loads(repaired)
            logger.info("JSON repair succeeded.")
            return result
        except json.JSONDecodeError:
            raise original_err 

def _looks_truncated(content: str) -> bool:
    stripped = _clean(content).rstrip()
    if not stripped:
        return True
    return stripped[-1] not in ("}", "]")

def _invoke_with_retry(prompt: str) -> str:
    llm = _get_llm()
    last_exception: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            content: str = response.content if hasattr(response, "content") else str(response)

            if not content or not content.strip():
                logger.warning(
                    "Empty response from Gemini (attempt %d/%d).",
                    attempt + 1, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                    continue

            if _looks_truncated(content):
                logger.warning(
                    "Response appears truncated (attempt %d/%d).",
                    attempt + 1, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    continue
                logger.warning(
                    "All %d attempts returned truncated output; will try JSON repair.",
                    MAX_RETRIES,
                )

            return content

        except MissingGeminiKeyError:
            raise 

        except Exception as exc:
            last_exception = exc
            error_str = str(exc).lower()
            is_transient = any(k in error_str for k in TRANSIENT_ERROR_KEYS)

            if is_transient and attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt)
                logger.warning(
                    "Gemini transient error (attempt %d/%d). Retrying in %ds. Error: %s",
                    attempt + 1, MAX_RETRIES, delay, exc,
                )
                time.sleep(delay)
                continue

            logger.exception(
                "Gemini API call failed on attempt %d/%d.",
                attempt + 1, MAX_RETRIES,
            )
            raise

    if last_exception:
        raise last_exception
    raise RuntimeError("_invoke_with_retry exhausted all attempts without returning.")

def _validate_keys(trip_data: dict, required: frozenset[str], context: str) -> str | None:
    missing = sorted(required - trip_data.keys())
    if missing:
        return f"{context}: missing required keys: {missing}"
    return None

def _sanitise_user_str(value: str) -> str:
    s = str(value)
    s = s.replace("`", "\\`")
    s = re.sub(r"<[^>]*>", "", s)
    return s.strip()

def generate_budget_split(trip_data: dict) -> dict:
    err = _validate_keys(trip_data, _BUDGET_REQUIRED_KEYS, "generate_budget_split")
    if err:
        logger.error(err)
        return {"success": False, "error": err}

    lang   = LANG_NAMES.get(str(trip_data.get("language", "en")), "English")
    budget = float(trip_data["total_budget"])

    if budget <= 0:
        return {"success": False, "error": "total_budget must be greater than 0."}

    destination = _sanitise_user_str(str(trip_data["destination"]))
    trip_type   = _sanitise_user_str(str(trip_data["trip_type"]))
    trip_prefs  = _sanitise_user_str(str(trip_data["trip_preferences"]))
    days        = int(trip_data["days"])

    prompt = textwrap.dedent(f"""
        You are a travel budget planner. Reply ONLY in {lang}.
        Return ONLY valid JSON — no markdown, no explanation, no extra text.

        Trip details:
        - Destination: {destination}
        - Duration: {days} days
        - Type: {trip_type}
        - Preferences: {trip_prefs}
        - Total budget: {budget}

        Distribute {budget} across EXACTLY these 7 categories: {BUDGET_CATS}

        Rules:
        1. Sum of all "allocated" values MUST equal exactly {budget}.
        2. No negative values. Use 0 if a category is not applicable.
        3. Include ALL 7 categories.
        4. "reason" must be 1 short sentence written in {lang}.

        Return this exact JSON structure:
        {{
          "categories": [
            {{"category": "accommodation", "allocated": 0.0, "reason": "..."}},
            {{"category": "food",          "allocated": 0.0, "reason": "..."}},
            {{"category": "transport",     "allocated": 0.0, "reason": "..."}},
            {{"category": "activities",    "allocated": 0.0, "reason": "..."}},
            {{"category": "shopping",      "allocated": 0.0, "reason": "..."}},
            {{"category": "emergency",     "allocated": 0.0, "reason": "..."}},
            {{"category": "other",         "allocated": 0.0, "reason": "..."}}
          ]
        }}
    """).strip()

    try:
        raw  = _invoke_with_retry(prompt)
        data = _parse_ai_json(raw)
        cats = data.get("categories", [])

        if not cats:
            return {"success": False, "error": "AI returned empty categories list."}
        for c in cats:
            try:
                c["allocated"] = max(0.0, float(c.get("allocated", 0)))
            except (TypeError, ValueError):
                c["allocated"] = 0.0
        total = sum(c["allocated"] for c in cats)

        if total > 0 and abs(total - budget) > 0.01:
            factor = budget / total
            for c in cats:
                c["allocated"] = round(c["allocated"] * factor, 2)
            drift = round(budget - sum(c["allocated"] for c in cats), 2)
            if drift != 0:
                largest = max(cats, key=lambda x: x["allocated"])
                largest["allocated"] = round(largest["allocated"] + drift, 2)

        elif total == 0:
            per = round(budget / len(cats), 2)
            for c in cats:
                c["allocated"] = per
            drift = round(budget - sum(c["allocated"] for c in cats), 2)
            if drift != 0:
                cats[0]["allocated"] = round(cats[0]["allocated"] + drift, 2)

        return {"success": True, "data": cats}

    except json.JSONDecodeError as exc:
        logger.error(
            "Budget split JSON decode error: %s", exc, exc_info=True,
            extra={"trip_id": trip_data.get("id")},
        )
        return {"success": False, "error": f"AI returned invalid JSON: {exc}"}

    except Exception as exc:
        logger.error(
            "Budget split unexpected error: %s", exc, exc_info=True,
            extra={"trip_id": trip_data.get("id")},
        )
        return {"success": False, "error": str(exc)}

def generate_itinerary(trip_data: dict) -> dict:
    err = _validate_keys(trip_data, _ITINERARY_REQUIRED_KEYS, "generate_itinerary")
    if err:
        logger.error(err)
        return {"success": False, "error": err}

    lang = LANG_NAMES.get(str(trip_data.get("language", "en")), "English")
    days = int(trip_data["days"])

    if days < 1:
        return {"success": False, "error": "Trip must be at least 1 day."}
    if days > 30:
        return {"success": False, "error": "Trip cannot exceed 30 days."}

    budget_summary = ", ".join(
        f"{b.get('category', '?')}: {b.get('allocated', 0)}"
        for b in trip_data.get("budget_categories", [])
    ) or "not specified"

    tripname     = _sanitise_user_str(str(trip_data["tripname"]))
    destination  = _sanitise_user_str(str(trip_data["destination"]))
    current_loc  = _sanitise_user_str(str(trip_data["current_loc"]))
    trip_type    = _sanitise_user_str(str(trip_data["trip_type"]))
    trip_prefs   = _sanitise_user_str(str(trip_data["trip_preferences"]))
    total_budget = float(trip_data["total_budget"])

    prompt = textwrap.dedent(f"""
        You are an expert travel planner. Reply ONLY in {lang}.
        Return ONLY valid JSON — no markdown, no explanation, no extra text.

        Trip details:
        - Name: {tripname}
        - Destination: {destination}
        - Travelling from: {current_loc}
        - Duration: {days} days
        - Type: {trip_type}
        - Preference: {trip_prefs}
        - Total budget: {total_budget}
        - Budget by category: {budget_summary}

        Create EXACTLY {days} day plans.
        Each day must have 4-6 activities spread across morning/afternoon/evening (night optional).
        Day 1 morning MUST include hotel check-in with category=accommodation.
        Each day needs at minimum: 1 accommodation mention, 2 sightseeing, 1 dining.

        IMPORTANT — keep all text fields SHORT (1-2 sentences max) to avoid hitting output limits.

        Valid values:
        - time: {ACTIVITY_TIMES}
        - category: {ACTIVITY_CATS}
        - budget_category: {BUDGET_CATS}

        Return this JSON structure:
        {{
          "day_plans": [
            {{
              "day_number": 1,
              "title": "Arrival & Exploration",
              "tips": "brief day tip in {lang}",
              "activities": [
                {{
                  "time": "morning",
                  "start_time": "09:00",
                  "end_time": "11:00",
                  "title": "Check-in at Hotel",
                  "description": "brief description",
                  "short_description": "1-2 sentences about the place",
                  "category": "accommodation",
                  "budget_category": "accommodation",
                  "location_name": "Hotel Name, Area, City",
                  "place_search_query": "Hotel Name City Country",
                  "estimated_cost": 2500.0,
                  "dos_and_donts": "Do: keep valuables safe. Avoid: leaving door unlocked.",
                  "emergency_contacts": [{{"name": "Reception", "phone": "+91-XXXXXXXX", "type": "hotel"}}],
                  "distance_km": 0
                }}
              ]
            }}
          ]
        }}

        CRITICAL RULES:
        1. Total estimated_cost across ALL activities MUST NOT exceed {total_budget}.
        2. Respect per-category allocations: {budget_summary}.
        3. ALL text fields must be in {lang}.
        4. Output ONLY the JSON object. Start with {{ and end with }}.
        5. Do NOT add commentary, markdown, or any text outside the JSON.
    """).strip()

    try:
        raw  = _invoke_with_retry(prompt)
        data = _parse_ai_json(raw)

        if not isinstance(data, dict):
            return {
                "success": False,
                "error": "AI returned unexpected data structure (not a JSON object).",
            }

        day_plans   = data.get("day_plans", [])
        actual_days = len(day_plans)

        if actual_days == 0:
            return {
                "success": False,
                "error": "AI returned no day plans. Please try regenerating.",
            }
        if actual_days != days:
            logger.warning(
                "Itinerary day count mismatch: expected %d, got %d.",
                days, actual_days,
                extra={"trip_id": trip_data.get("id")},
            )
            return {
                "success": True,
                "data": data,
                "warning": (
                    f"Only {actual_days} of {days} days were generated. "
                    "The AI response may have been truncated. "
                    "Please use the regenerate endpoint to get the full itinerary."
                ),
            }
        for day in day_plans:
            activities   = day.get("activities") or []
            cats_present = {
                str(a.get("category", "")).strip().lower()
                for a in activities
            }
            if "accommodation" not in cats_present:
                logger.warning(
                    "Day %s missing accommodation activity.",
                    day.get("day_number"),
                    extra={"trip_id": trip_data.get("id")},
                )

        return {"success": True, "data": data}

    except json.JSONDecodeError as exc:
        logger.error(
            "Itinerary JSON decode error: %s", exc, exc_info=True,
            extra={"trip_id": trip_data.get("id")},
        )
        return {"success": False, "error": f"AI returned invalid JSON: {exc}"}

    except Exception as exc:
        logger.error(
            "Itinerary generation error: %s", exc, exc_info=True,
            extra={"trip_id": trip_data.get("id")},
        )
        return {"success": False, "error": str(exc)}

__all__ = [
    "generate_budget_split",
    "generate_itinerary",
    "LANG_NAMES",
    "BUDGET_CATS",
    "ACTIVITY_TIMES",
    "ACTIVITY_CATS",
    "MissingGeminiKeyError",
    "TruncatedResponseError",
    "_reset_llm",
]