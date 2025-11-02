from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import Trip
from .serializers import ItenarySerializer, ItenaryCreateSerializer
from .ai_services import ItineraryGenerator
import logging
import json

logger = logging.getLogger(__name__)

class CreateItenaryView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create trip with AI itinerary",
        request=ItenaryCreateSerializer,
        responses={201: ItenarySerializer},
        tags=['Itinerary']
    )
    def post(self, request):
        serializer = ItenaryCreateSerializer(data=request.data)
        
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
                trip.Itenary_data = result['itinerary']
                trip.Itenary_data = json.dumps({"itinerary": result['itinerary']})
                trip.save()
                
                response_serializer = ItenarySerializer(trip)
                return Response({
                    'success': True,
                    'message': 'Trip and itinerary created successfully',
                    'data': response_serializer.data,
                    'model_used': result.get('model_used')
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'message': 'Trip created but itinerary generation failed',
                    'trip_id': trip.id,
                    'error': result.get('error')
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error in itinerary generation: {str(e)}")
            return Response({
                'success': False,
                'message': 'Trip created but itinerary generation failed',
                'trip_id': trip.id,
                'error': str(e)
            }, status=status.HTTP_201_CREATED)


class ItenaryListView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get user's trips",
        responses={200: ItenarySerializer(many=True)},
        tags=['Itinerary']
    )
    def get(self, request):
        trips = Trip.objects.filter(user=request.user).order_by('-created_at')
        serializer = ItenarySerializer(trips, many=True)
        return Response({
            'success': True,
            'count': trips.count(),
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class ItenaryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get trip details",
        responses={200: ItenarySerializer},
        tags=['Itinerary']
    )
    def get(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, user=request.user)
            serializer = ItenarySerializer(trip)
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
        summary="Delete trip",
        responses={204: None},
        tags=['Itinerary']
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