from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Trip
from .serializers import TripCreateSerializer,TripSerializer,TripListSerializer,ItenaryUpdateSerializer
from .ai_services import ItenaryGenerator
from functools import wraps
import jwt
from django.conf import settings
from account.models import User
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

def jwt_verification(f):
    @wraps(f)
    def new_decorator(request,*args,**kwargs):
        token=None
        auth_header=request.headers.get("Authorization")
        if auth_header and auth_header.startswith('Bearer '):
            token=auth_header.split(' ')[1]
        if not token:
            return Response({"error":"User not verified"},status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload=jwt.decode(token,settings.SECRET_KEY,algorithms=['HS256'])
            getemail=payload.get('email')
            if not getemail:
                return Response({"error":"Token has no email attached to it"},status=status.HTTP_401_UNAUTHORIZED)
            try:
                getuser=User.objects.get(email=getemail)
                request.user=getuser
            except User.DoesNotExist:
                return Response({"error":"User does not exist with this email"},status=status.HTTP_404_NOT_FOUND)
        except jwt.ExpiredSignatureError:
            return Response({"error":"Token has expired"},status=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return Response({"error":"Invalid token"},status=status.HTTP_401_UNAUTHORIZED)
        return f(request,*args,**kwargs)
    return new_decorator

@swagger_auto_schema(
    method='post',
    request_body=TripCreateSerializer,
    responses={201:TripSerializer,400:'Bad Request',401:'Unauthorized'},
    operation_description="Create a new trip and generate AI Itenary"
)
@swagger_auto_schema(
    method='get',
    responses={200:TripListSerializer(many=True),401:'Unauthorized'},
    operation_description="Get all trips for the authenticated user"
)
@api_view(['POST','GET'])
@jwt_verification
def trip_list_create(request):
    if request.method=='GET':
        trips=Trip.objects.filter(user=request.user)
        serializer=TripListSerializer(trips,many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)
    
    if request.method=='POST':
        serializer=TripCreateSerializer(data=request.data)
        if serializer.is_valid():
            trip=serializer.save(user=request.user)
            
            trip_data={
                'tripname':trip.tripname,
                'current_loc':trip.current_loc,
                'destination':trip.destination,
                'start_date':str(trip.start_date),
                'end_date':str(trip.end_date),
                'days':trip.days,
                'trip_type':trip.trip_type,
                'trip_preferences':trip.trip_preferences,
                'budget':trip.budget
            }
            
            generator=ItenaryGenerator()
            Itenary_data=generator.generate_Itenary(trip_data)
            
            if 'error' in Itenary_data:
                return Response({"message":"Trip created but Itenary generation failed","trip_id":trip.id,"error":Itenary_data},status=status.HTTP_201_CREATED)
            
            trip.Itenary_data=Itenary_data
            trip.is_draft=False
            trip.save()
            
            response_serializer=TripSerializer(trip)
            return Response(response_serializer.data,status=status.HTTP_201_CREATED)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    responses={200:TripSerializer,401:'Unauthorized',404:'Not Found'},
    operation_description="Get trip details with Itenary"
)
@swagger_auto_schema(
    method='put',
    request_body=TripCreateSerializer,
    responses={200:TripSerializer,400:'Bad Request',401:'Unauthorized',404:'Not Found'},
    operation_description="Update trip details"
)
@swagger_auto_schema(
    method='delete',
    responses={204:'No Content',401:'Unauthorized',404:'Not Found'},
    operation_description="Delete a trip"
)
@api_view(['GET','PUT','DELETE'])
@jwt_verification
def trip_detail(request,pk):
    trip=get_object_or_404(Trip,pk=pk,user=request.user)
    
    if request.method=='GET':
        serializer=TripSerializer(trip)
        return Response(serializer.data,status=status.HTTP_200_OK)
    
    if request.method=='PUT':
        serializer=TripCreateSerializer(trip,data=request.data,partial=True)
        if serializer.is_valid():
            serializer.save()
            response_serializer=TripSerializer(trip)
            return Response(response_serializer.data,status=status.HTTP_200_OK)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
    
    if request.method=='DELETE':
        trip.delete()
        return Response({"message":"Trip deleted successfully"},status=status.HTTP_204_NO_CONTENT)

@swagger_auto_schema(
    method='post',
    responses={200:TripSerializer,401:'Unauthorized',404:'Not Found'},
    operation_description="Regenerate AI Itenary for a trip"
)

@api_view(['PUT'])
@jwt_verification
def update_Itenary(request,pk):
    trip=get_object_or_404(Trip,pk=pk,user=request.user)
    
    serializer=ItenaryUpdateSerializer(data=request.data)
    if serializer.is_valid():
        trip.Itenary_data=serializer.validated_data['Itenary_data']
        trip.save()
        
        response_serializer=TripSerializer(trip)
        return Response(response_serializer.data,
                        status=status.HTTP_200_OK)
    return Response(serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='delete',
    responses={200:'Success',401:'Unauthorized',404:'Not Found'},
    operation_description="Delete a specific day from Itenary"
)
@api_view(['DELETE'])
@jwt_verification
def delete_Itenary_day(request,pk,day_number):
    trip=get_object_or_404(Trip,pk=pk,user=request.user)
    
    if not trip.Itenary_data or 'days' not in trip.Itenary_data:
        return Response({"error":"No Itenary data found"},
                        status=status.HTTP_404_NOT_FOUND)
    
    days=trip.Itenary_data['days']
    updated_days=[day for day in days if day.get('day_number')!=day_number]
    
    if len(updated_days)==len(days):
        return Response({"error":"Day not found in Itenary"},
                        status=status.HTTP_404_NOT_FOUND)
    
    trip.Itenary_data['days']=updated_days
    trip.save()
    
    serializer=TripSerializer(trip)
    return Response(serializer.data,
                    status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='post',
    responses={200:TripSerializer,401:'Unauthorized',404:'Not Found'},
    operation_description="Save draft trip and finalize it"
)
@api_view(['POST'])
@jwt_verification
def save_draft(request,pk):
    trip=get_object_or_404(Trip,pk=pk,user=request.user)
    trip.is_draft=True
    trip.save()
    
    serializer=TripSerializer(trip)
    return Response(serializer.data,
                    status=status.HTTP_200_OK)