import requests
from django.conf import settings
from .models import ChatMessage

APP_NAME = "Saarthi"         
APP_PLATFORM = "TripSync"  

TRAVEL_SYSTEM_PROMPT = f"""
You are {APP_NAME}, the official AI travel assistant embedded inside {APP_PLATFORM} — a travel planning application.

YOUR IDENTITY:
- Your name is {APP_NAME}.
- You are part of the {APP_PLATFORM} app.
- You help users plan trips, discover destinations, and travel safely.

WHAT YOU CAN HELP WITH (travel-related topics only):
- Destination recommendations and things to do
- Travel itinerary planning
- Visa, passport, and entry requirements
- Flight, train, bus, or car travel tips
- Hotel, hostel, and accommodation suggestions
- Local food, culture, and customs
- Packing lists and travel gear advice
- Budget travel and cost estimates
- Travel safety and health precautions
- Travel insurance guidance
- Seasonal travel and weather advice
- Solo travel, family travel, adventure travel
- Nearby attractions and hidden gems

STRICT RULES:
1. You ONLY answer travel and trip-related questions.
2. If the user asks about ANYTHING unrelated to travel (e.g., coding, cooking, math, politics, sports), 
   respond EXACTLY with:
   "I'm {APP_NAME}, your travel assistant on {APP_PLATFORM}. I can only help with travel-related questions. 
   Is there a destination or trip you'd like help planning?"
3. Never pretend to be a general-purpose AI. Never say you are ChatGPT, Gemini, or Claude.
4. Keep answers concise, friendly, and practical — no more than 200 words unless the user asks for details.
5. Always stay in character as {APP_NAME}.
""".strip()

MAX_HISTORY_TURNS = 6  

def build_conversation_contents(session_id: str, new_user_message: str) -> list:
    history = (
        ChatMessage.objects
        .filter(session_id=session_id)
        .order_by('-created_at')[:MAX_HISTORY_TURNS]
    )
    history = list(reversed(history))  
    contents = []
    contents.append({"role": "user","parts": [{"text": TRAVEL_SYSTEM_PROMPT}]})
    contents.append({"role": "model","parts": [{"text": f"Understood! I'm {APP_NAME}, your travel assistant. How can I help you plan your next adventure?"}]})
    for msg in history:
        contents.append({
            "role": "user",
            "parts": [{"text": msg.user_message}]
        })
        contents.append({
            "role": "model",
            "parts": [{"text": msg.bot_response}]
        })
    contents.append({
        "role": "user",
        "parts": [{"text": new_user_message}]
    })
    return contents

GEMINI_MODEL = "gemini-2.5-flash-lite"  
GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

GENERATION_CONFIG = {
    "temperature": 0.7,
    "topK": 40,
    "topP": 0.95,
    "maxOutputTokens": 512,  
}

def call_gemini(session_id: str, user_message: str, timeout: int = 30) -> dict:
    url = f"{GEMINI_BASE_URL}?key={settings.GOOGLE_API_KEY}"
    contents = build_conversation_contents(session_id, user_message)
    payload = {
        "contents": contents,
        "generationConfig": GENERATION_CONFIG,
    }
    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return {"success": False, "error": "timeout", "status_code": 0}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": str(exc), "status_code": 0}

    if resp.status_code != 200:
        return {
            "success": False,
            "error": f"Gemini API returned {resp.status_code}",
            "status_code": resp.status_code,
            "details": resp.text,
        }

    try:
        data = resp.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if not text:
            return {"success": False, "error": "Empty response from Gemini", "status_code": 200}
        return {"success": True, "text": text.strip(), "status_code": 200}
    except (KeyError, IndexError, ValueError) as exc:
        return {"success": False, "error": f"Response parse error: {exc}", "status_code": 200}

OFF_TOPIC_KEYWORDS = [
    "python", "javascript", "html", "css", "code", "programming", "algorithm",
    "database", "sql", "django", "react", "api endpoint",
    "recipe", "how to cook", "bake", "baking",
    "equation", "calculus", "physics", "chemistry",
    "movie", "song", "lyrics", "sports score", "game cheat",
]

OFF_TOPIC_RESPONSE = (
    f"I'm {APP_NAME}, your travel assistant on {APP_PLATFORM}. "
    "I can only help with travel-related questions. "
    "Is there a destination or trip you'd like help planning? ✈️"
)

def is_off_topic(message: str) -> bool:
    lower = message.lower()
    return any(kw in lower for kw in OFF_TOPIC_KEYWORDS)