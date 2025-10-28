from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import requests
from .serializers import WeatherSerializer

class Weather(APIView):
    def get(self, request):
        location = request.query_params.get('location', 'Delhi')
        try:
            url = f"http://api.weatherapi.com/v1/forecast.json"
            params = {
                'key': settings.WEATHER_API_KEY,
                'q': location,
                'days': 1}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                weather_data = {
                    'location': data['location']['name'],
                    'temperature': data['current']['temp_c'],
                    'wind': data['current']['wind_kph'],
                    'chance_of_rain': data['forecast']['forecastday'][0]['day']['daily_chance_of_rain']}
                serializer = WeatherSerializer(data=weather_data)
                if serializer.is_valid():
                    return Response({
                        'status': 'success',
                        'data': serializer.data
                    }, status=status.HTTP_200_OK)
                
            return Response({
                'status': 'error',
                'message': 'Unable to fetch weather data'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)