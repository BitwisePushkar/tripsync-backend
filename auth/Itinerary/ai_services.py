import google.generativeai as genai
from django.conf import settings
import json

class ItineraryGenerator:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.generation_config = {'temperature': 0.7,'top_p': 0.95,'top_k': 40,'max_output_tokens': 8192,}
    def create_prompt(self, trip_data):
        prompt = f"""You are an expert travel planner. Generate a detailed day-by-day itinerary based on the following information:

Trip Name: {trip_data['tripname']}
Starting From: {trip_data['current_loc']}
Destination: {trip_data['destination']}
Start Date: {trip_data['start_date']}
End Date: {trip_data['end_date']}
Number of Days: {trip_data['days']}
Trip Type: {trip_data['trip_type']}
Preferences: {trip_data['trip_preferences']}
Budget: ₹{trip_data['budget']}

Create a detailed itinerary with activities for each day. For each day, organize activities into time slots:
- Morning (8:00 AM - 12:00 PM)
- Afternoon (12:00 PM - 5:00 PM)
- Evening (5:00 PM - 8:00 PM)
- Night (8:00 PM - 12:00 AM)

Return ONLY a valid JSON object in this EXACT format (no markdown, no extra text):
{{
  "days": [
    {{
      "day_number": 1,
      "title": "Day 1 - Arrival",
      "activities": [
        {{
          "time_slot": "morning",
          "title": "Activity Title",
          "description": "Detailed description of the activity",
          "location": "Specific location",
          "duration": "2 hours",
          "estimated_cost": 500
        }}
      ]
    }}
  ]
}}

Important guidelines:
1. Create exactly {trip_data['days']} days of activities
2. Include 2-4 activities per day across different time slots
3. Make activities realistic and suitable for {trip_data['trip_preferences']} preference
4. Ensure total estimated costs across all days stay within ₹{trip_data['budget']}
5. Consider {trip_data['trip_type']} trip type when suggesting activities
6. Use Indian Rupees (₹) for all cost estimates
7. Return ONLY the JSON object, no other text"""        
        return prompt   
    
    def generate_itinerary(self, trip_data):
        try:
            prompt = self.create_prompt(trip_data)
            response = self.model.generate_content(prompt,generation_config=self.generation_config)
            content = response.text.strip()
            if content.startswith('```json'):
                content = content[7:]
            elif content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            itinerary = json.loads(content)
            if 'days' not in itinerary:
                return {"error": "Invalid AI response structure","details": "Missing 'days' key in response"}           
            if not isinstance(itinerary['days'], list):
                return {"error": "Invalid AI response structure","details": "'days' should be a list"}           
            if len(itinerary['days']) != trip_data['days']:
                return {"error": "Incorrect number of days","details": f"Expected {trip_data['days']} days, got {len(itinerary['days'])}"}
            for idx, day in enumerate(itinerary['days']):
                if 'day_number' not in day or 'title' not in day or 'activities' not in day:
                    return {"error": f"Invalid day {idx + 1} structure","details": "Each day must have day_number, title, and activities"}            
            return itinerary            
        except json.JSONDecodeError as e:
            return {"error": "Failed to parse AI response as JSON","details": str(e),"raw_response": content[:500] if 'content' in locals() else "No response"}
        except Exception as e:
            return {"error": "Failed to generate itinerary","details": str(e),"error_type": type(e).__name__}
