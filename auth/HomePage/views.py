from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import requests
import logging
from .serializers import WeatherSerializer
from .models import WeatherCache
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes

logger = logging.getLogger(__name__)

class Weather(APIView):
    CACHE_DURATION_MINUTES = 30 
    @extend_schema(
    tags=['Weather'],
    summary='Get weather information for a location',
    description='Fetch current weather data including temperature, wind speed, and chance of rain. Data is cached for 30 minutes.',
    parameters=[
        OpenApiParameter(
            name='location',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='City name or location (max 100 characters)',
            required=False,
            examples=[
                OpenApiExample('Delhi', value='Delhi', description='Capital city of India'),
                OpenApiExample('Mumbai', value='Mumbai', description='Financial capital of India'),
                OpenApiExample('London', value='London', description='Capital of United Kingdom')
            ]
        )
    ],
    responses={
        200: OpenApiResponse(
            description='Weather data retrieved successfully',
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    'Success Response',
                    value={
                        'status': 'success',
                        'data': {
                            'location': 'Delhi',
                            'temperature': 28.5,
                            'wind': 15.2,
                            'chance_of_rain': 10
                        },
                        'cached': False
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            description='Invalid location provided',
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    'Bad Request',
                    value={'status': 'error', 'message': 'Invalid location parameter'}
                )
            ]
        ),
        500: OpenApiResponse(
            description='Server configuration error',
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    'Server Error',
                    value={'status': 'error', 'message': 'Weather service is not properly configured'}
                )
            ]
        ),
        503: OpenApiResponse(
            description='Weather service temporarily unavailable',
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    'Service Unavailable',
                    value={'status': 'error', 'message': 'Please try again later.'}
                )
            ]
        ),
        504: OpenApiResponse(
            description='Request timeout',
            response=OpenApiTypes.OBJECT,
            examples=[
                OpenApiExample(
                    'Gateway Timeout',
                    value={'status': 'error', 'message': 'Please try again.'}
                )
            ]
        )
    }
    )
    def get(self, request):
        location = request.query_params.get('location', 'Delhi').strip()       
        if not location or len(location) > 100:
            return Response({'status': 'error','message': 'Invalid location parameter'}, status=status.HTTP_400_BAD_REQUEST)

        if not settings.WEATHER_API_KEY:
            logger.error('Weather API key not configured')
            return Response({'status': 'error','message': 'Weather service is not properly configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        cached_data = self._get_cached_weather(location)
        if cached_data:
            return Response({'status': 'success','data': cached_data,'cached': True}, status=status.HTTP_200_OK)
        
        try:
            weather_data = self._fetch_weather_from_api(location)
            self._save_to_cache(location, weather_data)
            serializer = WeatherSerializer(data=weather_data)
            if serializer.is_valid():
                return Response({'status': 'success','data': serializer.data,'cached': False}, status=status.HTTP_200_OK)
            return Response({'status': 'error','message': 'Invalid data format','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            
        except requests.exceptions.Timeout:
            logger.error(f'Timeout while fetching weather for {location}')
            return Response({'status': 'error','message': 'Please try again.'}, status=status.HTTP_504_GATEWAY_TIMEOUT)
            
        except requests.exceptions.RequestException as e:
            logger.error(f'Request error for {location}: {str(e)}')
            return Response({'status': 'error','message': 'Please try again later.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        except ValueError as e:
            logger.error(f'Invalid response data for {location}: {str(e)}')
            return Response({'status': 'error','message': 'Received invalid data from weather service'}, status=status.HTTP_502_BAD_GATEWAY)
            
        except Exception as e:
            logger.exception(f'Unexpected error for {location}: {str(e)}')
            return Response({'status': 'error','message': 'Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _get_cached_weather(self, location):
        try:
            cache_entry = WeatherCache.objects.filter(location__iexact=location,updated_at__gte=timezone.now() - timedelta(minutes=self.CACHE_DURATION_MINUTES)).first()
            
            if cache_entry:
                return {'location': cache_entry.location,'temperature': cache_entry.temperature,'wind': cache_entry.wind,'chance_of_rain': cache_entry.chance_of_rain}
        except Exception as e:
            logger.warning(f'Error retrieving cache for {location}: {str(e)}')       
        return None
    
    def _fetch_weather_from_api(self, location):
        url = "https://api.weatherapi.com/v1/forecast.json"
        params = {'key': settings.WEATHER_API_KEY,'q': location,'days': 1,'aqi': 'no'}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            error_detail = response.json() if response.content else {}
            logger.error(f'Weather API error for {location}: {error_detail}')
            raise requests.exceptions.RequestException(f'Weather API returned status {response.status_code}')
        
        data = response.json()
        try:
            weather_data = {
                'location': data['location']['name'],
                'temperature': float(data['current']['temp_c']),
                'wind': float(data['current']['wind_kph']),
                'chance_of_rain': int(data['forecast']['forecastday'][0]['day']['daily_chance_of_rain'])
            }
        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.error(f'Failed to parse weather data for {location}: {str(e)}')
            raise ValueError(f'Invalid weather data structure: {str(e)}')
        
        return weather_data
    
    def _save_to_cache(self, location, weather_data):
        try:
            WeatherCache.objects.update_or_create(
                location__iexact=location,
                defaults={
                    'location': weather_data['location'],
                    'temperature': weather_data['temperature'],
                    'wind': weather_data['wind'],
                    'chance_of_rain': weather_data['chance_of_rain']
                }
            )
        except Exception as e:
            logger.warning(f'Failed to cache weather data for {location}: {str(e)}')