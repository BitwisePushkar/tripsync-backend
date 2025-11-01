from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from django.conf import settings
import json

class ItenaryGenerator:
    def __init__(self):
        self.llm=ChatGoogleGenerativeAI(model="gemini-pro",google_api_key=settings.GEMINI_API_KEY,temperature=0.7)
        
        self.prompt_template=PromptTemplate(
            input_variables=["tripname","current_loc","destination","start_date","end_date","days","trip_type","trip_preferences","budget"],
            template="""You are an expert travel planner. Generate a detailed day-by-day Itenary based on the following information:

Trip Name: {tripname}
Starting From: {current_loc}
Destination: {destination}
Start Date: {start_date}
End Date: {end_date}
Number of Days: {days}
Trip Type: {trip_type}
Preferences: {trip_preferences}
Budget: ${budget}

Create a detailed Itenary with activities for each day. For each day, organize activities into time slots: Morning (8:00 am - 12:00 pm), Afternoon (12:00 pm - 5:00 pm), Evening (5:00 pm - 8:00 pm), and Night (8:00 pm - 12:00 am).

Return ONLY a valid JSON object in this exact format:
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
          "estimated_cost": 50
        }}
      ]
    }}
  ]
}}

Include realistic activities based on the destination, preferences, and budget. Ensure all costs fit within the total budget."""
        )
    
    def generate_Itenary(self,trip_data):
        try:
            prompt=self.prompt_template.format(**trip_data)
            response=self.llm.invoke(prompt)
            content=response.content.strip()
            
            if content.startswith('```json'):
                content=content[7:]
            if content.endswith('```'):
                content=content[:-3]
            content=content.strip()
            
            Itenary=json.loads(content)
            return Itenary
        except json.JSONDecodeError as e:
            return {"error":"Failed to parse AI response","details":str(e)}
        except Exception as e:
            return {"error":"Failed to generate Itenary","details":str(e)}