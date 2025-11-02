from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Trip
from .serializers import TripCreateSerializer, TripSerializer, TripListSerializer, ItineraryUpdateSerializer
from .ai_services import ItenaryGenerator
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from expense.models import Budget  

@extend_schema(
    methods=['POST'],
    request=TripCreateSerializer,
    responses={
        201: TripSerializer,
        400: OpenApiTypes.OBJECT,
        401: OpenApiTypes.OBJECT
    },
    description="Create a new trip and generate AI itinerary.",
    examples=[
        OpenApiExample(
            'Trip Creation Example',
            value={
                "tripname": "Summer Vacation",
                "current_loc": "New York",
                "destination": "Paris",
                "start_date": "2025-07-01",
                "end_date": "2025-07-05",
                "trip_type": "solo",
                "trip_preferences": "adventure"
            },
            request_only=True
        )
    ]
)
@extend_schema(
    methods=['GET'],
    responses={
        200: TripListSerializer(many=True),
        401: OpenApiTypes.OBJECT
    },
    description="Get all trips for the authenticated user with itinerary status"
)

@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated]) 
def trip_list_create(request):
    if request.method == 'GET':
        trips = Trip.objects.filter(user=request.user)
        serializer = TripListSerializer(trips, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)   
    if request.method == 'POST':
        serializer = TripCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user_budget = Budget.objects.get(user=request.user)
                budget = float(user_budget.total) 
            except Budget.DoesNotExist:
                return Response({"error": "No budget found in expense app."},status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": f"Failed to fetch budget from expense app: {str(e)}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            trip = serializer.save(user=request.user, budget=budget)            
            trip_data = {
                'tripname': trip.tripname,
                'current_loc': trip.current_loc,
                'destination': trip.destination,
                'start_date': str(trip.start_date),
                'end_date': str(trip.end_date),
                'days': trip.days,
                'trip_type': trip.trip_type,
                'trip_preferences': trip.trip_preferences,
                'budget': trip.budget  
            }
            generator = ItenaryGenerator()
            itinerary_data = generator.generate_itinerary(trip_data)           
            if 'error' in itinerary_data:
                return Response(
                    {"message": "Trip created but itinerary generation failed","trip_id": trip.id,"error": itinerary_data},status=status.HTTP_201_CREATED)            
            trip.itinerary_data = itinerary_data
            trip.save()           
            response_serializer = TripSerializer(trip)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)       
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    methods=['GET'],
    responses={
        200: TripSerializer,
        401: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    },
    description="Get trip details with complete itinerary data"
)
@extend_schema(
    methods=['PUT'],
    request=ItineraryUpdateSerializer,
    responses={
        200: TripSerializer,
        400: OpenApiTypes.OBJECT,
        401: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    },
    description="Update itinerary data for a specific trip",
    examples=[
        OpenApiExample(
            'Itinerary Update Example',
            value={
                "itinerary_data": {
                    "days": [
                        {
                            "day_number": 1,
                            "title": "Day 1 - Arrival",
                            "activities": [
                                {
                                    "time_slot": "morning",
                                    "title": "Check-in Hotel",
                                    "description": "Settle into hotel",
                                    "location": "Hotel Central",
                                    "duration": "2 hours",
                                    "estimated_cost": 0
                                }
                            ]
                        }
                    ]
                }
            },
            request_only=True
        )
    ]
)
@extend_schema(
    methods=['DELETE'],
    responses={
        204: OpenApiTypes.OBJECT,
        401: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    },
    description="Delete entire trip with all itinerary data"
)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated]) 
def trip_detail(request, pk):
    trip = get_object_or_404(Trip, pk=pk, user=request.user)   
    if request.method == 'GET':
        serializer = TripSerializer(trip)
        return Response(serializer.data, status=status.HTTP_200_OK)    
    if request.method == 'PUT':
        serializer = ItineraryUpdateSerializer(data=request.data)
        if serializer.is_valid():
            trip.itinerary_data = serializer.validated_data['itinerary_data']
            trip.save()            
            response_serializer = TripSerializer(trip)
            return Response(response_serializer.data, status=status.HTTP_200_OK)        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    if request.method == 'DELETE':
        trip.delete()
        return Response({"message": "Trip and itinerary deleted successfully"},status=status.HTTP_204_NO_CONTENT)
