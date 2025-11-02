from langchain_google_genai import ChatGoogleGenerativeAI
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class ItineraryGenerator:
    FREE_MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash-002",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.0-pro-latest",
        "gemini-1.0-pro",
    ]
    
    def __init__(self):
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp",
                    google_api_key=settings.GOOGLE_API_KEY,
                    temperature=0.7,
                    convert_system_message_to_human=True,
                    max_output_tokens=2048,
                )
        test_response = llm.invoke("test")
        self.llm = llm

  
        
        if not self.llm:
            raise Exception("No working Gemini model found. Check API key.")
    
    def generate_itinerary(self, trip_data):
      prompt = f"""
You are an expert travel planner.

Create a detailed travel itinerary for:

Trip Name: {trip_data.get('tripname')}
Destination: {trip_data.get('destination')}
From: {trip_data.get('current_loc')}
Start Date: {trip_data.get('start_date')}
End Date: {trip_data.get('end_date')}
Duration: {trip_data.get('days')} days
Trip Type: {trip_data.get('trip_type')}
Preferences: {trip_data.get('trip_preferences')}
Budget: ${trip_data.get('budget')}

Provide:
1. Day-by-day itinerary with morning, afternoon, evening activities
2. Restaurant recommendations with estimated costs
3. Budget breakdown
4. Travel tips
5. Must-see attractions

Format clearly with day numbers and timings.
"""
      try:
        response = self.llm.invoke(prompt)
        return {
            'success': True,
            'itinerary': response.content,
            'model_used': "gemini-2.0-flash-exp"
        }
      except Exception as e:
        logger.error(f"Error generating itinerary: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
