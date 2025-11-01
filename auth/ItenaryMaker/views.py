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
            return Response({"error":"User not verified"},
                            status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload=jwt.decode(token,settings.SECRET_KEY,algorithms=['HS256'])
            user_id=payload.get('user_id')
            getemail=payload.get('email')
            sub=payload.get('sub')
            
            try:
                if user_id:
                    getuser=User.objects.get(id=user_id)
                elif getemail:
                    getuser=User.objects.get(email=getemail)
                elif sub:
                    getuser=User.objects.get(email=sub)
                else:
                    return Response({"error":"Token has no user identifier"},
                                    status=status.HTTP_401_UNAUTHORIZED)
                request.user=getuser
            except User.DoesNotExist:
                return Response({"error":"User does not exist with this email"},
                                status=status.HTTP_404_NOT_FOUND)
        except jwt.ExpiredSignatureError:
            return Response({"error":"Token has expired"},
                            status=status.HTTP_401_UNAUTHORIZED)
        except jwt.InvalidTokenError:
            return Response({"error":"Invalid token"},
                            status=status.HTTP_401_UNAUTHORIZED)
        return f(request,*args,**kwargs)
    return new_decorator

@swagger_auto_schema(
    method='post',
    request_body=TripCreateSerializer,
    responses={201:TripSerializer,
               400:'Bad Request',
               401:'Unauthorized'},
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
        return Response(serializer.data,
                        status=status.HTTP_200_OK)
    
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
            trip.save()
            response_serializer=TripSerializer(trip)
            return Response(response_serializer.data,
                            status=status.HTTP_201_CREATED)
        return Response(serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    responses={200:TripSerializer,
               401:'Unauthorized',
               404:'Not Found'},
            operation_description="Get trip details with Itenary")
@swagger_auto_schema(
    method='put',
    request_body=ItenaryUpdateSerializer,
    responses={200:TripSerializer,400:'Bad Request',
               401:'Unauthorized',
               404:'Not Found'},
    operation_description="Update Itenary data"
)
@swagger_auto_schema(
    method='delete',
    responses={204:'No Content',
               401:'Unauthorized',
               404:'Not Found'},
    operation_description="Delete entire trip with Itenary")

@api_view(['GET','PUT','DELETE'])
@jwt_verification
def trip_detail(request,pk):
    trip=get_object_or_404(Trip,pk=pk,user=request.user)
    
    if request.method=='GET':
        serializer=TripSerializer(trip)
        return Response(serializer.data,
                        status=status.HTTP_200_OK)
    
    if request.method=='PUT':
        serializer=ItenaryUpdateSerializer(data=request.data)
        if serializer.is_valid():
            trip.Itenary_data=serializer.validated_data['Itenary_data']
            trip.save()
            
            response_serializer=TripSerializer(trip)
            return Response(response_serializer.data,status=status.HTTP_200_OK)
        return Response(serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST)
    
    if request.method=='DELETE':
        trip.delete()
        return Response({"message":"Trip and Itenary deleted successfully"},
                        status=status.HTTP_204_NO_CONTENT)


