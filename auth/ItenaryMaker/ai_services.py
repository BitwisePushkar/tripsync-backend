from langchain_google_genai import ChatGoogleGenerativeAI
from django.conf import settings
import logging
import json
import re
import os 

logger = logging.getLogger(__name__)

class ItineraryGenerator:
    def __init__(self):
      logger.debug("API key (from settings): %s", settings.GOOGLE_API_KEY)
      logger.debug("API key (from env): %s", os.getenv("GOOGLE_API_KEY"))
      self.llm = ChatGoogleGenerativeAI(
          model="gemini-2.5-flash-lite",
          google_api_key=settings.GOOGLE_API_KEY,
          temperature=0.7,
          max_output_tokens=20000,
      )


    def generate_itinerary(self, trip_data):
        prompt = f"""You are an expert travel planner. Create detailed itineraries in JSON format only.

Create a {trip_data['days']}-day travel itinerary in JSON format.

Trip Details:
- Trip Name: {trip_data['tripname']}
- Destination: {trip_data['destination']}
- From: {trip_data['current_loc']}
- timings: {trip_data['days']} days
- Budget: ${trip_data['budget']}
- Type: {trip_data['trip_type']}
- Preferences: {trip_data['trip_preferences']}

Return ONLY valid JSON (no markdown, no code blocks, no explanations):

{{
  "day_plans": [
    {{
      "day_number": 1,
      "title": "Arrival & City Exploration",
      "activities": [
        {{
          "time": "Morning",
          "title": "Arrival at Delhi Airport",
          "description": "Arrive at Indira Gandhi International Airport and transfer to hotel. Check-in and freshen up.",
          "location": "IGI Airport to Hotel",
          "timings": "6:00-8:00",
          "cost": 20,
          "category": "transportation"
        }},
        {{
          "time": "Afternoon",
          "title": "Visit India Gate",
          "description": "Explore the iconic India Gate monument, a war memorial dedicated to Indian soldiers. Perfect for photos and understanding Delhi's history.",
          "location": "India Gate, Rajpath",
          "timings": "8:00-9:30",
          "cost": 0,
          "category": "sightseeing"
        }},
        {{
          "time": "Afternoon",
          "title": "Lunch at Karim's",
          "description": "Experience authentic Mughlai cuisine at the famous Karim's restaurant. Try their signature kebabs and curries.",
          "location": "Jama Masjid, Old Delhi",
          "timings": "1 hour",
          "cost": 25,
          "category": "dining"
        }},
        {{
          "time": "Evening",
          "title": "Connaught Place Shopping",
          "description": "Visit the heart of Delhi for shopping, dining, and experiencing the local culture. Browse through shops and enjoy street food.",
          "location": "Connaught Place",
          "timings": "2 hours",
          "cost": 30,
          "category": "shopping"
        }},
        {{
          "time": "Night",
          "title": "Dinner at Indian Accent",
          "description": "Fine dining experience with modern Indian cuisine. Book in advance for the best tables.",
          "location": "Lodhi Road",
          "timings": "1.5 hours",
          "cost": 50,
          "category": "dining"
        }}
      ]
    }},
    {{
      "day_number": 2,
      "title": "Historical Delhi Tour",
      "activities": [
        {{
          "time": "Morning",
          "title": "Red Fort Visit",
          "description": "Explore the magnificent Red Fort, a UNESCO World Heritage site and symbol of India's rich history.",
          "location": "Netaji Subhash Marg, Old Delhi",
          "timings": "2 hours",
          "cost": 10,
          "category": "sightseeing"
        }},
        {{
          "time": "Morning",
          "title": "Jama Masjid",
          "description": "Visit one of India's largest mosques with stunning Mughal architecture.",
          "location": "Chandni Chowk",
          "timings": "1 hour",
          "cost": 0,
          "category": "sightseeing"
        }},
        {{
          "time": "Afternoon",
          "title": "Lunch at Paranthe Wali Gali",
          "description": "Try the famous stuffed parathas in the narrow lanes of Old Delhi.",
          "location": "Chandni Chowk",
          "timings": "1 hour",
          "cost": 15,
          "category": "dining"
        }}
      ]
    }}
  ]
}}

IMPORTANT RULES:
1. Create exactly {trip_data['days']} day plans
2. Each day should have 4-6 activities
3. Activities must have: time (Morning/Afternoon/Evening/Night), title, description, location, timings, cost, category
4. Categories: sightseeing, dining, shopping, transportation, adventure, relaxation
5. Make sure activities are alwways within budget and are realistic
6. Return ONLY the JSON, no other text
7. Make descriptions detailed and helpful
8. Add timings throughout the day to make it convinient for the user to plan
"""
        
        try:
            response = self.llm.invoke(prompt)
            response_text = response.content.strip()
            response_text = re.sub(r'^```json\s*', '', response_text)
            response_text = re.sub(r'^```\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
            response_text = response_text.strip()
            
            try:
                itinerary_data = json.loads(response_text)
                return {
                    'success': True,
                    'data': itinerary_data
                }
            except json.JSONDecodeError as je:
                logger.error(f"JSON parse error: {str(je)}")
                logger.error(f"Response: {response_text[:500]}")
                return {
                    'success': False,
                    'error': f"Invalid JSON from AI: {str(je)}"
                }
                
        except Exception as e:
            logger.error(f"Error generating itinerary: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }