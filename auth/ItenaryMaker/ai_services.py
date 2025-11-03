import google.generativeai as genai
from django.conf import settings
import logging
import json
import re

logger = logging.getLogger(__name__)

class ItineraryGenerator:
    FREE_MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash-002",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.0-pro-latest",
    ]
    
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = None
        self.model_name = None
        
        for model_name in self.FREE_MODELS:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    generation_config={
                        "temperature": 0.7,
                        "top_p": 0.95,
                        "top_k": 40,
                        "max_output_tokens": 8192,
                    }
                )
                response = model.generate_content("test")
                self.model = model
                self.model_name = model_name
                logger.info(f"Using model: {model_name}")
                break
            except Exception as e:
                logger.warning(f"Model {model_name} failed: {str(e)}")
                continue
        
        if not self.model:
            raise Exception("No working Gemini model found")
    
    def generate_itinerary(self, trip_data):
        prompt = f"""
Create a detailed travel itinerary in JSON format for:

Trip Name: {trip_data.get('tripname')}
Destination: {trip_data.get('destination')}
From: {trip_data.get('current_loc')}
Start Date: {trip_data.get('start_date')}
End Date: {trip_data.get('end_date')}
Duration: {trip_data.get('days')} days
Trip Type: {trip_data.get('trip_type')}
Preferences: {trip_data.get('trip_preferences')}
Budget: ${trip_data.get('budget')}

Return ONLY valid JSON in this exact structure (no markdown, no extra text):

{{
  "trip_overview": {{
    "destination": "{trip_data.get('destination')}",
    "duration_days": {trip_data.get('days')},
    "total_budget": {trip_data.get('budget')},
    "trip_type": "{trip_data.get('trip_type')}"
  }},
  "daily_itinerary": [
    {{
      "day": 1,
      "date": "YYYY-MM-DD",
      "title": "Day title",
      "activities": [
        {{
          "time": "Morning",
          "activity": "Activity description",
          "location": "Place name",
          "duration": "2 hours",
          "cost": 50
        }}
      ],
      "meals": [
        {{
          "type": "Breakfast",
          "restaurant": "Restaurant name",
          "cuisine": "Cuisine type",
          "cost": 20
        }}
      ],
      "accommodation": {{
        "name": "Hotel name",
        "type": "Hotel/Hostel",
        "cost": 100
      }},
      "day_total_cost": 170
    }}
  ],
  "budget_breakdown": {{
    "accommodation": 700,
    "food": 420,
    "activities": 350,
    "transportation": 200,
    "miscellaneous": 100,
    "total": {trip_data.get('budget')}
  }},
  "travel_tips": [
    "Tip 1",
    "Tip 2"
  ],
  "must_see_attractions": [
    {{
      "name": "Attraction name",
      "description": "Description",
      "entry_fee": 10,
      "best_time": "Morning"
    }}
  ]
}}

Generate complete itinerary for all {trip_data.get('days')} days. Return ONLY the JSON, no other text.
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            response_text = re.sub(r'^```json\s*', '', response_text)
            response_text = re.sub(r'^```\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
            response_text = response_text.strip()
            try:
                itinerary_json = json.loads(response_text)
                return {
                    'success': True,
                    'itinerary': json.dumps(itinerary_json, indent=2),
                    'itinerary_json': itinerary_json,
                    'model_used': self.model_name
                }
            except json.JSONDecodeError as je:
                logger.warning(f"JSON parse error: {str(je)}")
                return {
                    'success': True,
                    'itinerary': response_text,
                    'model_used': self.model_name,
                    'format': 'text'
                }
                
        except Exception as e:
            logger.error(f"Error generating itinerary: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }