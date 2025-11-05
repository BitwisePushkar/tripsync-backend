from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Trip
from .serializers import (TripCreateSerializer, TripSerializer, TripListSerializer, ItineraryUpdateSerializer,TripManualCreateSerializer)
from .ai_services import ItineraryGenerator
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from expense.models import Budget  

@extend_schema(
    methods=['GET'],
    tags=['Trips'],
    summary="Get all trips",
    description="Retrieve all trips for the authenticated user with itinerary status.",
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trips retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "success": True,
                        "message": "Trips retrieved successfully",
                        "data": [
                            {
                                "id": 1,
                                "tripname": "Summer Vacation",
                                "current_loc": "New York",
                                "destination": "Paris",
                                "start_date": "2025-07-01",
                                "end_date": "2025-07-05",
                                "trip_type": "solo",
                                "trip_preferences": "adventure",
                                "budget": 1500,
                                "days": [
                                    {
                                        "day_number": 1,
                                        "title": "Day 1 - Arrival",
                                        "activities": []
                                    }
                                ]
                            }
                        ]
                    }
                )
            ]
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Unauthorized - user not authenticated",
            examples=[
                OpenApiExample(
                    name="Unauthorized",
                    value={"detail": "Authentication credentials were not provided."}
                )
            ]
        )
    }
)

@extend_schema(
    methods=['POST'],
    tags=['Trips'],
    summary="Create a new trip",
    description="Create a new trip. AI-based or manual itinerary creation supported.",
    request=TripCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trip created successfully",
            examples=[
                OpenApiExample(
                    name="Success - AI Itinerary",
                    value={
                        "success": True,
                        "message": "Trip created successfully",
                        "data": {
                            "id": 1,
                            "tripname": "Summer Vacation",
                            "current_loc": "New York",
                            "destination": "Paris",
                            "start_date": "2025-07-01",
                            "end_date": "2025-07-05",
                            "trip_type": "solo",
                            "trip_preferences": "adventure",
                            "budget": 1500,
                            "days": [
                                {
                                    "day_number": 1,
                                    "title": "Day 1 - Arrival",
                                    "activities": []
                                }
                            ]
                        }
                    }
                ),
                OpenApiExample(
                    name="Trip created but AI itinerary failed",
                    value={
                        "success": True,
                        "message": "Trip created but itinerary generation failed",
                        "trip_id": 1,
                        "error": {"error": "Failed to generate itinerary due to API limit"}
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Validation failed or budget not found",
            examples=[
                OpenApiExample(
                    name="Validation Error",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {"tripname": ["This field is required."]}
                    }
                ),
                OpenApiExample(
                    name="Budget Not Found",
                    value={"error": "No budget found in expense app."}
                )
            ]
        ),
        500: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Internal server error fetching budget",
            examples=[
                OpenApiExample(
                    name="Budget Fetch Error",
                    value={"error": "Failed to fetch budget from expense app: connection timeout"}
                )
            ]
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Unauthorized - user not authenticated",
            examples=[
                OpenApiExample(
                    name="Unauthorized",
                    value={"detail": "Authentication credentials were not provided."}
                )
            ]
        )
    }
)

@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated]) 
def trip_list_create(request):
    if request.method == 'GET':
        trips = Trip.objects.filter(user=request.user)
        serializer = TripListSerializer(trips, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)   
    if request.method == 'POST':
        try:
            user_budget = Budget.objects.get(user=request.user)
            budget = float(user_budget.total) 
        except Budget.DoesNotExist:
            return Response({"error": "No budget found in expense app."},status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Failed to fetch budget from expense app: {str(e)}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        use_ai = request.data.get('use_ai', True)         
        if use_ai:
            serializer = TripCreateSerializer(data=request.data)
            if serializer.is_valid():
                trip = serializer.save(user=request.user, budget=budget)
                trip_data = {'tripname': trip.tripname,'current_loc': trip.current_loc,'destination': trip.destination,'start_date': str(trip.start_date),'end_date': str(trip.end_date),'days': trip.days,'trip_type': trip.trip_type,'trip_preferences': trip.trip_preferences,'budget': trip.budget  }
                generator = ItineraryGenerator()
                itinerary_data = generator.generate_itinerary(trip_data)               
                if 'error' in itinerary_data:
                    return Response({"message": "Trip created but itinerary generation failed","trip_id": trip.id,"error": itinerary_data},status=status.HTTP_201_CREATED)              
                trip.itinerary_data = itinerary_data
                trip.save()       
                response_serializer = TripSerializer(trip)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)       
        else:
            serializer = TripManualCreateSerializer(data=request.data)
            if serializer.is_valid():
                trip = serializer.save(user=request.user, budget=budget)               
                response_serializer = TripSerializer(trip)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)           
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    methods=['GET'],
    tags=['Trips'],
    summary="Get trip details",
    description="Retrieve details of a trip including complete itinerary data for a specific trip.",
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trip retrieved successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "success": True,
                        "message": "Trip retrieved successfully",
                        "data": {
                            "id": 1,
                            "tripname": "Summer Vacation",
                            "current_loc": "New York",
                            "destination": "Paris",
                            "start_date": "2025-07-01",
                            "end_date": "2025-07-05",
                            "trip_type": "solo",
                            "trip_preferences": "adventure",
                            "budget": 1500,
                            "itinerary_data": {
                                "days": [
                                    {
                                        "day_number": 1,
                                        "title": "Day 1 - Arrival",
                                        "activities": []
                                    }
                                ]
                            }
                        }
                    }
                )
            ]
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Unauthorized - user not authenticated",
            examples=[
                OpenApiExample(
                    name="Unauthorized",
                    value={"detail": "Authentication credentials were not provided."}
                )
            ]
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trip not found",
            examples=[
                OpenApiExample(
                    name="Not Found",
                    value={"success": False, "message": "Trip not found."}
                )
            ]
        )
    }
)

@extend_schema(
    methods=['PUT'],
    tags=['Trips'],
    summary="Update trip itinerary",
    description="Update itinerary data for a specific trip.",
    request=ItineraryUpdateSerializer,
    responses={
        200: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trip updated successfully",
            examples=[
                OpenApiExample(
                    name="Success Response",
                    value={
                        "success": True,
                        "message": "Trip updated successfully",
                        "data": {
                            "id": 1,
                            "tripname": "Summer Vacation",
                            "itinerary_data": {
                                "days": [
                                    {
                                        "day_number": 1,
                                        "title": "Day 1 - Arrival",
                                        "activities": []
                                    }
                                ]
                            }
                        }
                    }
                )
            ]
        ),
        400: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Validation failed",
            examples=[
                OpenApiExample(
                    name="Validation Error",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {"itinerary_data": ["This field is required."]}
                    }
                )
            ]
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Unauthorized",
            examples=[
                OpenApiExample(
                    name="Unauthorized",
                    value={"detail": "Authentication credentials were not provided."}
                )
            ]
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trip not found",
            examples=[
                OpenApiExample(
                    name="Not Found",
                    value={"success": False, "message": "Trip not found."}
                )
            ]
        )
    }
)

@extend_schema(
    methods=['DELETE'],
    tags=['Trips'],
    summary="Delete trip",
    description="Delete an entire trip along with its itinerary data.",
    responses={
        204: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trip deleted successfully",
            examples=[
                OpenApiExample(
                    name="Deleted",
                    value={"success": True, "message": "Trip and itinerary deleted successfully"}
                )
            ]
        ),
        401: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Unauthorized",
            examples=[
                OpenApiExample(
                    name="Unauthorized",
                    value={"detail": "Authentication credentials were not provided."}
                )
            ]
        ),
        404: OpenApiResponse(
            response=OpenApiTypes.OBJECT,
            description="Trip not found",
            examples=[
                OpenApiExample(
                    name="Not Found",
                    value={"success": False, "message": "Trip not found."}
                )
            ]
        )
    }
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