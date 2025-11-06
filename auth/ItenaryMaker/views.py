from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import Trip, Itinerary, DayPlan
from .serializers import (
    TripSerializer, TripCreateUpdateSerializer, RegenerateItinerarySerializer,
    ActivitySerializer, ActivityUpdateSerializer, DayPlanSerializer
)
from .ai_services import ItineraryGenerator
import logging

logger = logging.getLogger(__name__)

class TripCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create trip with AI itinerary",
        request=TripCreateUpdateSerializer,
        responses={201: TripSerializer},
        tags=['Trip Management']
    )
    def post(self, request):
        serializer = TripCreateUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        trip = Trip.objects.create(
            user=request.user,
            **serializer.validated_data
        )
        
        try:
            generator = ItineraryGenerator()
            result = generator.generate_itinerary({
                'tripname': trip.tripname,
                'destination': trip.destination,
                'current_loc': trip.current_loc,
                'start_date': trip.start_date,
                'end_date': trip.end_date,
                'days': trip.days,
                'trip_type': trip.trip_type,
                'trip_preferences': trip.trip_preferences,
                'budget': trip.budget
            })
            
            if result['success']:
                data = result['data']
                
                itinerary = Itinerary.objects.create(trip=trip)
                
                for day_data in data.get('day_plans', []):
                    DayPlan.objects.create(
                        itinerary=itinerary,
                        day_number=day_data['day_number'],
                        title=day_data['title'],
                        activities=day_data['activities']
                    )
                
                response_serializer = TripSerializer(trip)
                return Response({
                    'success': True,
                    'message': 'Trip and itinerary created successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': 'Trip created but itinerary generation failed',
                    'trip_id': trip.id,
                    'error': result.get('error')
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return Response({
                'success': False,
                'message': 'Trip created but itinerary generation failed',
                'trip_id': trip.id,
                'error': str(e)
            }, status=status.HTTP_201_CREATED)


class TripListView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get all user trips",
        responses={200: TripSerializer(many=True)},
        tags=['Trip Management']
    )
    def get(self, request):
        trips = Trip.objects.filter(user=request.user).prefetch_related(
            'itinerary__day_plans'
        ).order_by('-created_at')
        serializer = TripSerializer(trips, many=True)
        return Response({
            'success': True,
            'count': trips.count(),
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class TripDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get trip details",
        responses={200: TripSerializer},
        tags=['Trip Management']
    )
    def get(self, request, pk):
        try:
            trip = Trip.objects.prefetch_related(
                'itinerary__day_plans'
            ).get(pk=pk, user=request.user)
            serializer = TripSerializer(trip)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        summary="Update trip details",
        request=TripCreateUpdateSerializer,
        responses={200: TripSerializer},
        tags=['Trip Management']
    )
    def put(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, user=request.user)
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = TripCreateUpdateSerializer(trip, data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        
        response_serializer = TripSerializer(trip)
        return Response({
            'success': True,
            'message': 'Trip updated successfully',
            'data': response_serializer.data
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Delete trip",
        responses={204: None},
        tags=['Trip Management']
    )
    def delete(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, user=request.user)
            trip.delete()
            return Response({
                'success': True,
                'message': 'Trip deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ItineraryRegenerateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Regenerate itinerary with updated parameters",
        request=RegenerateItinerarySerializer,
        responses={200: TripSerializer},
        tags=['Itinerary Management']
    )
    def post(self, request, trip_id):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = RegenerateItinerarySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        updated_data = serializer.validated_data
        
        for field, value in updated_data.items():
            setattr(trip, field, value)
        trip.save()
        
        try:
            if hasattr(trip, 'itinerary'):
                trip.itinerary.day_plans.all().delete()
                trip.itinerary.delete()
            
            generator = ItineraryGenerator()
            result = generator.generate_itinerary({
                'tripname': trip.tripname,
                'destination': trip.destination,
                'current_loc': trip.current_loc,
                'start_date': trip.start_date,
                'end_date': trip.end_date,
                'days': trip.days,
                'trip_type': trip.trip_type,
                'trip_preferences': trip.trip_preferences,
                'budget': trip.budget
            })
            
            if result['success']:
                data = result['data']
                
                itinerary = Itinerary.objects.create(trip=trip)
                
                for day_data in data.get('day_plans', []):
                    DayPlan.objects.create(
                        itinerary=itinerary,
                        day_number=day_data['day_number'],
                        title=day_data['title'],
                        activities=day_data['activities']
                    )
                
                response_serializer = TripSerializer(trip)
                return Response({
                    'success': True,
                    'message': 'Itinerary regenerated successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': 'Failed to regenerate itinerary',
                    'error': result.get('error')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error regenerating itinerary: {str(e)}")
            return Response({
                'success': False,
                'message': 'Failed to regenerate itinerary',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ItineraryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get itinerary details",
        responses={200: TripSerializer},
        tags=['Itinerary Management']
    )
    def get(self, request, trip_id):
        try:
            trip = Trip.objects.prefetch_related(
                'itinerary__day_plans'
            ).get(pk=trip_id, user=request.user)
            
            if not hasattr(trip, 'itinerary'):
                return Response({
                    'success': False,
                    'message': 'No itinerary found for this trip'
                }, status=status.HTTP_404_NOT_FOUND)
            
            serializer = TripSerializer(trip)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @extend_schema(
        summary="Delete itinerary",
        responses={204: None},
        tags=['Itinerary Management']
    )
    def delete(self, request, trip_id):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
            
            if hasattr(trip, 'itinerary'):
                trip.itinerary.delete()
                return Response({
                    'success': True,
                    'message': 'Itinerary deleted successfully'
                }, status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({
                    'success': False,
                    'message': 'No itinerary found for this trip'
                }, status=status.HTTP_404_NOT_FOUND)
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)


class DayPlanDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get day plan details",
        responses={200: None},
        tags=['Itinerary Management']
    )
    def get(self, request, trip_id, day_number):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
            day_plan = DayPlan.objects.get(
                itinerary__trip=trip,
                day_number=day_number
            )
            
            serializer = DayPlanSerializer(day_plan)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except DayPlan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Day plan not found'
            }, status=status.HTTP_404_NOT_FOUND)


class ActivityManagementView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Add new activity to day plan",
        request=ActivitySerializer,
        responses={201: DayPlanSerializer},
        tags=['Activity Management']
    )
    def post(self, request, trip_id, day_number):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
            day_plan = DayPlan.objects.get(
                itinerary__trip=trip,
                day_number=day_number
            )
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except DayPlan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Day plan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ActivitySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        activities = day_plan.activities if day_plan.activities else []
        activities.append(serializer.validated_data)
        day_plan.activities = activities
        day_plan.save()
        
        response_serializer = DayPlanSerializer(day_plan)
        return Response({
            'success': True,
            'message': 'Activity added successfully',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class ActivityDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Update specific activity",
        request=ActivityUpdateSerializer,
        responses={200: DayPlanSerializer},
        tags=['Activity Management']
    )
    def put(self, request, trip_id, day_number, activity_index):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
            day_plan = DayPlan.objects.get(
                itinerary__trip=trip,
                day_number=day_number
            )
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except DayPlan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Day plan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        activities = day_plan.activities if day_plan.activities else []
        
        if activity_index < 0 or activity_index >= len(activities):
            return Response({
                'success': False,
                'message': 'Activity index out of range'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ActivityUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        for field, value in serializer.validated_data.items():
            activities[activity_index][field] = value
        
        day_plan.activities = activities
        day_plan.save()
        
        response_serializer = DayPlanSerializer(day_plan)
        return Response({
            'success': True,
            'message': 'Activity updated successfully',
            'data': response_serializer.data
        }, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Delete specific activity",
        responses={200: DayPlanSerializer},
        tags=['Activity Management']
    )
    def delete(self, request, trip_id, day_number, activity_index):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
            day_plan = DayPlan.objects.get(
                itinerary__trip=trip,
                day_number=day_number
            )
        except Trip.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Trip not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except DayPlan.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Day plan not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        activities = day_plan.activities if day_plan.activities else []
        
        if activity_index < 0 or activity_index >= len(activities):
            return Response({
                'success': False,
                'message': 'Activity index out of range'
            }, status=status.HTTP_404_NOT_FOUND)
        
        activities.pop(activity_index)
        day_plan.activities = activities
        day_plan.save()
        
        response_serializer = DayPlanSerializer(day_plan)
        return Response({
            'success': True,
            'message': 'Activity deleted successfully',
            'data': response_serializer.data
        }, status=status.HTTP_200_OK)