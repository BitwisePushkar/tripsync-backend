from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from .models import Trip, Itinerary, DayPlan, Activity
from .serializers import TripSerializer, TripCreateUpdateSerializer, RegenerateItinerarySerializer,ActivitySerializer, ActivityUpdateSerializer, DayPlanSerializer, ManualItinerarySerializer, ActivityInputSerializer
import logging
from tripmate.models import TripMember
from expense.models import Budget
from .ai_services import ItineraryGenerator

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
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)  
        try:
            budget_obj = Budget.objects.get(user=request.user)
            budget_amount = float(budget_obj.total)
        except Budget.DoesNotExist:
            return Response({'success': False,'message': 'Please create a budget in expense tracker first'}, status=status.HTTP_400_BAD_REQUEST)
        
        trip = Trip.objects.create(user=request.user,budget=budget_amount,**serializer.validated_data)
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
                    day_plan=DayPlan.objects.create(
                        itinerary=itinerary,
                        day_number=day_data['day_number'],
                        title=day_data['title'])
                    for activity_data in day_data.get('activities',[]):
                            activity = Activity.objects.create(
                                day_plans=day_plan,
                                title=activity_data['title'],
                                time = activity_data['time'],
                                description = activity_data['description'],
                                location =  activity_data['location'],
                                timings = activity_data['timings'],
                                cost = activity_data['cost'],
                                category = activity_data['category'])
                
                response_serializer = TripSerializer(trip)
                return Response({'success': True,'message': 'Trip and itinerary created successfully','data': response_serializer.data}, status=status.HTTP_201_CREATED)
            else:
                return Response({'success': False,'message': 'Trip created but itinerary generation failed','trip_id': trip.id,'error': result.get('error')}, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return Response({'success': False,'message': 'Trip created but itinerary generation failed','trip_id': trip.id,'error': str(e)}, status=status.HTTP_201_CREATED)

class TripListView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get all user trips",
        responses={200: TripSerializer(many=True)},
        tags=['Trip Management']
    )
    def get(self, request):
        trips = Trip.objects.filter(user=request.user).prefetch_related('itinerary__day_plans__activities').order_by('-created_at')
        serializer = TripSerializer(trips, many=True)
        return Response({'success': True,'count': trips.count(),'data': serializer.data}, status=status.HTTP_200_OK)

class TripDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get trip details",
        responses={200: TripSerializer},
        tags=['Trip Management']
    )
    def get(self, request, pk):
        try:
            trip = Trip.objects.prefetch_related('itinerary__day_plans__activities').get(pk=pk, user=request.user)
            serializer = TripSerializer(trip)
            return Response({'success': True,'data': serializer.data}, status=status.HTTP_200_OK)
        except Trip.DoesNotExist:
            return Response({'success': False,'message': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
    
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
            member = TripMember.objects.filter(trip_id=pk, user=request.user, permission='edit').first()
            if not member:
                return Response({'success': False,'message': 'Trip not found or you do not have edit permission'}, status=status.HTTP_404_NOT_FOUND)
            trip = member.trip
        serializer = TripCreateUpdateSerializer(trip, data=request.data)
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        response_serializer = TripSerializer(trip)
        return Response({'success': True,'message': 'Trip updated successfully','data': response_serializer.data}, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Delete trip",
        responses={204: None},
        tags=['Trip Management']
    )
    def delete(self, request, pk):
        try:
            trip = Trip.objects.get(pk=pk, user=request.user)
            trip.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Trip.DoesNotExist:
            return Response({'success': False,'message': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)

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
            return Response({'success': False,'message': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = RegenerateItinerarySerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
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
                    day_plan=DayPlan.objects.create(
                        itinerary=itinerary,
                        day_number=day_data['day_number'],
                        title=day_data['title']
                    )
                    for activity_data in day_data.get('activities',[]):
                        activity = Activity.objects.create(
                            day_plans=day_plan,
                            title=activity_data['title'],
                            time = activity_data['time'],
                            description = activity_data['description'],
                            location =  activity_data['location'],
                            timings = activity_data['timings'],
                            cost = activity_data['cost'],
                            category = activity_data['category'])
                
                response_serializer = TripSerializer(trip)
                return Response({'success': True,'message': 'Itinerary regenerated successfully','data': response_serializer.data}, status=status.HTTP_200_OK)
            else:
                return Response({'success': False,'message': 'Failed to regenerate itinerary','error': result.get('error')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Error regenerating itinerary: {str(e)}")
            return Response({'success': False,'message': 'Failed to regenerate itinerary','error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ItineraryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get itinerary details",
        responses={200: TripSerializer},
        tags=['Itinerary Management']
    )
    def get(self, request, trip_id):
        try:
            trip = Trip.objects.prefetch_related('itinerary__day_plans__activities').get(pk=trip_id, user=request.user)
            if not hasattr(trip, 'itinerary'):
                return Response({'success': False,'message': 'No itinerary found for this trip'}, status=status.HTTP_404_NOT_FOUND)
            serializer = TripSerializer(trip)
            return Response({'success': True,'data': serializer.data}, status=status.HTTP_200_OK)
        except Trip.DoesNotExist:
            return Response({'success': False,'message': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
    
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
                return Response({},status=status.HTTP_200_OK)
            else:
                return Response({'success': False,'message': 'No itinerary found for this trip'}, status=status.HTTP_404_NOT_FOUND)
        except Trip.DoesNotExist:
            return Response({'success': False,'message': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)

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
            day_plan = DayPlan.objects.prefetch_related('activities').get(itinerary__trip=trip,day_number=day_number)
            serializer = DayPlanSerializer(day_plan)
            return Response({'success': True,'data': serializer.data}, status=status.HTTP_200_OK)
        except Trip.DoesNotExist:
            return Response({'success': False,'message': 'Trip not found'}, status=status.HTTP_404_NOT_FOUND)
        except DayPlan.DoesNotExist:
            return Response({'success': False,'message': 'Day plan not found'}, status=status.HTTP_404_NOT_FOUND)

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
        except Trip.DoesNotExist:
            member = TripMember.objects.filter(trip_id=trip_id, user=request.user, permission='edit').first()
            if not member:
                return Response({'success': False,'message': 'Trip not found or you do not have edit permission'}, status=status.HTTP_404_NOT_FOUND)
            trip = member.trip
        try:
            day_plan = DayPlan.objects.get(itinerary__trip=trip,day_number=day_number)
        except DayPlan.DoesNotExist:
            return Response({'success': False,'message': 'Day plan not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = ActivitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(day_plans=day_plan)
        response_serializer = DayPlanSerializer(day_plan)
        return Response({'success': True,'message': 'Activity added successfully','data': response_serializer.data}, status=status.HTTP_201_CREATED)

class ActivityDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Update specific activity",
        request=ActivityUpdateSerializer,
        responses={200: ActivitySerializer}, 
        tags=['Activity Management']
    )
    def put(self, request, trip_id, day_number, activity_id):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
        except Trip.DoesNotExist:
            member = TripMember.objects.filter(trip_id=trip_id, user=request.user, permission='edit').first()
            if not member:
                return Response({'success': False,'message': 'Trip not found or you do not have edit permission'}, status=status.HTTP_404_NOT_FOUND)
            trip = member.trip
        
        try:
            day_plan = DayPlan.objects.get(itinerary__trip=trip,day_number=day_number)
        except DayPlan.DoesNotExist:
            return Response({'success': False,'message': 'Day plan not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            activity = Activity.objects.get(day_plans=day_plan, id=activity_id)
        except Activity.DoesNotExist:
            return Response({'success': False,'message': 'Activity not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ActivityUpdateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        for field, value in serializer.validated_data.items():
            setattr(activity, field, value)
        activity.save()
        
        response_serializer = ActivitySerializer(activity)
        return Response({'success': True,'message': 'Activity updated successfully','data': response_serializer.data}, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Delete specific activity",
        responses={200: None},
        tags=['Activity Management']
    )
    def delete(self, request, trip_id, day_number, activity_id):
        try:
            trip = Trip.objects.get(pk=trip_id, user=request.user)
        except Trip.DoesNotExist:
            member = TripMember.objects.filter(trip_id=trip_id, user=request.user, permission='edit').first()
            if not member:
                return Response({'success': False,'message': 'Trip not found or you do not have edit permission'}, status=status.HTTP_401_UNAUTHORIZED)
            trip = member.trip
        try:
            day_plan = DayPlan.objects.get(itinerary__trip=trip,day_number=day_number)
        except DayPlan.DoesNotExist:
            return Response({'success': False,'message': 'Day plan not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            activity = Activity.objects.get(day_plans=day_plan, id=activity_id) 
            activity.delete()
        except Activity.DoesNotExist:
            return Response({'success': False,'message': 'Activity not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'success': True,'message': 'Activity deleted successfully'}, status=status.HTTP_200_OK)
    
class ManualItineraryCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create trip and itinerary manually without AI",
        request=ManualItinerarySerializer,
        responses={201: TripSerializer},
        tags=['Itinerary Management']
    )
    def post(self, request):
        serializer = ManualItinerarySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            try:
                budget_obj = Budget.objects.get(user=request.user)
                budget_amount = float(budget_obj.total)
            except Budget.DoesNotExist:
                return Response({'success': False,'message': 'Please create a budget in expense tracker first'}, status=status.HTTP_400_BAD_REQUEST)
            
            validated_data = serializer.validated_data
            day_plans_data = validated_data.pop('day_plans')
            
            trip = Trip.objects.create(
                user=request.user,
                budget=budget_amount,
                tripname=validated_data['tripname'],
                current_loc=validated_data['current_loc'],
                destination=validated_data['destination'],
                start_date=validated_data['start_date'],
                end_date=validated_data['end_date'],
                days=validated_data['days'],
                trip_type=validated_data['trip_type'],
                trip_preferences=validated_data['trip_preferences']
            )
            
            itinerary = Itinerary.objects.create(trip=trip)
            for day_plan_data in day_plans_data:
                activities_data = day_plan_data.pop('activities', [])  
                day_plan = DayPlan.objects.create(itinerary=itinerary,day_number=day_plan_data['day_number'],title=day_plan_data['title'])
                for activity_data in activities_data:
                    Activity.objects.create(day_plans=day_plan,**activity_data)
            response_serializer = TripSerializer(trip)
            return Response({'success': True,'message': 'Trip and manual itinerary created successfully','data': response_serializer.data}, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating manual trip and itinerary: {str(e)}")
            if 'trip' in locals():
                trip.delete()
            return Response({'success': False,'message': 'Failed to create manual trip and itinerary','error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
