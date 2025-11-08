from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Tripmate, FriendRequest, TripMember
from .serializers import (TripmateSerializer, FriendRequestSerializer, SendFriendRequestSerializer,RespondFriendRequestSerializer, UserSearchSerializer, TripMemberSerializer,AddTripMemberSerializer, UpdateTripMemberSerializer)
from Itinerary.models import Trip

User = get_user_model()

class SearchUser(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchSerializer
    
    def get_queryset(self):
        search_query = self.request.query_params.get('q', '').strip()
        if not search_query or len(search_query) < 2:
            return User.objects.none()
        users = User.objects.filter(
            Q(email__icontains=search_query)|
            Q(profile__fname__icontains=search_query)|
            Q(profile__lname__icontains=search_query)
        ).exclude(id=self.request.user.id).select_related('profile').distinct()[:20]
        return users
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Search users by name or email",
        description="Search for users to send friend requests. Minimum 2 characters required.",
        parameters=[
            OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query',
                required=True
            )
        ],
        responses={200: UserSearchSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class ViewTripmates(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchSerializer
    
    def get_queryset(self):
        try:
            tripmate_profile = self.request.user.tripmate_profile
            return tripmate_profile.friends.select_related('profile').all()
        except Tripmate.DoesNotExist:
            return User.objects.none()
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Get my tripmates list",
        description="Retrieve list of all your tripmates.",
        responses={200: UserSearchSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class SendFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Send friend request",
        description="Send a friend request to another user.",
        request=SendFriendRequestSerializer,
        responses={
            201: FriendRequestSerializer,
            400: OpenApiResponse(description="Validation error")
        }
    )
    def post(self, request):
        serializer = SendFriendRequestSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        receiver = User.objects.get(id=serializer.validated_data['receiver_id'])
        message = serializer.validated_data.get('message', '')
        
        Tripmate.objects.get_or_create(user=request.user)
        Tripmate.objects.get_or_create(user=receiver)
        
        friend_request = FriendRequest.objects.create(sender=request.user,receiver=receiver, message=message)
        response_serializer = FriendRequestSerializer(friend_request, context={'request': request})
        return Response({'success': True,'message': 'Friend request sent successfully','data': response_serializer.data}, status=status.HTTP_201_CREATED)

class ReceivedFriendRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    
    def get_queryset(self):
        return FriendRequest.objects.filter( receiver=self.request.user, status='pending').select_related('sender', 'sender__profile').order_by('-created_at')
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Get received friend requests",
        description="Retrieve all pending friend requests you've received.",
        responses={200: FriendRequestSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class SentFriendRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    
    def get_queryset(self):
        return FriendRequest.objects.filter(sender=self.request.user,status='pending').select_related('receiver', 'receiver__profile').order_by('-created_at')
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Get sent friend requests",
        description="Retrieve all pending friend requests you've sent.",
        responses={200: FriendRequestSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class RespondFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Accept or decline friend request",
        description="Respond to a received friend request.",
        request=RespondFriendRequestSerializer,
        parameters=[
            OpenApiParameter(
                name='request_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Friend request ID'
            )
        ],
        responses={
            200: FriendRequestSerializer,
            400: OpenApiResponse(description="Invalid action"),
            404: OpenApiResponse(description="Request not found")
        }
    )
    def post(self, request, request_id):
        friend_request = get_object_or_404(FriendRequest,id=request_id,receiver=request.user,status='pending')
        
        serializer = RespondFriendRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Invalid action','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        
        if action == 'accept':
            friend_request.status = 'accepted'
            friend_request.save()
            
            sender_profile, _ = Tripmate.objects.get_or_create(user=friend_request.sender)
            receiver_profile, _ = Tripmate.objects.get_or_create(user=friend_request.receiver)
            
            sender_profile.friends.add(friend_request.receiver)
            receiver_profile.friends.add(friend_request.sender)
            
            message = 'Friend request accepted. You are now tripmates!'
        else:
            friend_request.status = 'declined'
            friend_request.save()
            message = 'Friend request declined'
        
        response_serializer = FriendRequestSerializer(friend_request, context={'request': request})
        
        return Response({'success': True,'message': message,'data': response_serializer.data}, status=status.HTTP_200_OK)


class CancelFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Cancel sent friend request",
        description="Cancel a friend request that you've sent.",
        parameters=[
            OpenApiParameter(
                name='request_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Friend request ID'
            )
        ],
        responses={
            204: OpenApiResponse(description="Request cancelled"),
            404: OpenApiResponse(description="Request not found")
        }
    )
    def delete(self, request, request_id):
        friend_request = get_object_or_404(FriendRequest,id=request_id,sender=request.user,status='pending')
        friend_request.delete()
        
        return Response({'success': True,'message': 'Friend request cancelled'}, status=status.HTTP_204_NO_CONTENT)

class RemoveTripmateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Remove tripmate",
        description="Remove a user from your tripmates list.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to remove'
            )
        ],
        responses={
            200: OpenApiResponse(description="Tripmate removed"),
            400: OpenApiResponse(description="Not tripmates"),
            404: OpenApiResponse(description="User or profile not found")
        }
    )
    def delete(self, request, user_id):
        try:
            tripmate_profile = request.user.tripmate_profile
        except Tripmate.DoesNotExist:
            return Response({'success': False,'message': 'Tripmate profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        user_to_remove = get_object_or_404(User, id=user_id)
        
        if not tripmate_profile.are_tripmates(user_to_remove):
            return Response({'success': False,'message': 'Not tripmates with this user'}, status=status.HTTP_400_BAD_REQUEST)
        
        tripmate_profile.friends.remove(user_to_remove)
        
        try:
            other_profile = user_to_remove.tripmate_profile
            other_profile.friends.remove(request.user)
        except Tripmate.DoesNotExist:
            pass
        
        return Response({'success': True,'message': 'Tripmate removed successfully'}, status=status.HTTP_200_OK)

class TripMembersListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripMemberSerializer
    
    def get_queryset(self):
        trip_id = self.kwargs['trip_id']
        trip = get_object_or_404(Trip, id=trip_id)
        
        if trip.user != self.request.user:
            member = TripMember.objects.filter(trip=trip, user=self.request.user).first()
            if not member:
                return TripMember.objects.none()
        
        return TripMember.objects.filter(trip_id=trip_id).select_related('user', 'user__profile', 'added_by', 'added_by__profile')
    
    @extend_schema(
        tags=['Trip Members'],
        summary="Get all members of a trip",
        description="Retrieve list of all users who have access to view or edit this trip.",
        parameters=[
            OpenApiParameter(
                name='trip_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Trip ID'
            )
        ],
        responses={
            200: TripMemberSerializer(many=True),
            403: OpenApiResponse(description="Access denied"),
            404: OpenApiResponse(description="Trip not found")
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AddTripMemberView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Trip Members'],
        summary="Add member to trip",
        description="Add a tripmate to your trip with view or edit permissions.",
        request=AddTripMemberSerializer,
        parameters=[
            OpenApiParameter(
                name='trip_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Trip ID'
            )
        ],
        responses={
            201: TripMemberSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Trip not found")
        }
    )
    def post(self, request, trip_id):
        trip = get_object_or_404(Trip, id=trip_id)
        
        if trip.user != request.user:
            member = TripMember.objects.filter(trip=trip, user=request.user, permission='edit').first()
            if not member:
                return Response({'success': False,'message': 'Only trip owner or members with edit permission can add others'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AddTripMemberSerializer(data=request.data, context={'request': request, 'trip_id': trip_id})
        
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        user = User.objects.get(id=serializer.validated_data['user_id'])
        permission = serializer.validated_data.get('permission', 'view')
        
        trip_member = TripMember.objects.create(trip=trip,user=user,added_by=request.user,permission=permission)
        response_serializer = TripMemberSerializer(trip_member, context={'request': request})
        return Response({ 'success': True,'message': 'Member added to trip successfully','data': response_serializer.data}, status=status.HTTP_201_CREATED)

class UpdateTripMemberView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Trip Members'],
        summary="Update member permission",
        description="Update permission level for a trip member.",
        request=UpdateTripMemberSerializer,
        parameters=[
            OpenApiParameter(name='trip_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH),
            OpenApiParameter(name='member_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH)
        ],
        responses={
            200: TripMemberSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Member not found")
        }
    )
    def put(self, request, trip_id, member_id):
        trip = get_object_or_404(Trip, id=trip_id)
        
        if trip.user != request.user:
            return Response({'success': False,'message': 'Only trip owner can update member permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        trip_member = get_object_or_404(TripMember, id=member_id, trip=trip)
        
        serializer = UpdateTripMemberSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        trip_member.permission = serializer.validated_data['permission']
        trip_member.save()
        response_serializer = TripMemberSerializer(trip_member, context={'request': request})
        return Response({'success': True,'message': 'Member permission updated successfully','data': response_serializer.data}, status=status.HTTP_200_OK)

class RemoveTripMemberView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Trip Members'],
        summary="Remove member from trip",
        description="Remove a member from the trip.",
        parameters=[
            OpenApiParameter(name='trip_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH),
            OpenApiParameter(name='member_id', type=OpenApiTypes.INT, location=OpenApiParameter.PATH)
        ],
        responses={
            200: OpenApiResponse(description="Member removed"),
            403: OpenApiResponse(description="Permission denied"),
            404: OpenApiResponse(description="Member not found")
        }
    )
    def delete(self, request, trip_id, member_id):
        trip = get_object_or_404(Trip, id=trip_id)
        if trip.user != request.user:
            member = TripMember.objects.filter(trip=trip, user=request.user, permission='edit').first()
            if not member:
                return Response({'success': False,'message': 'Only trip owner or members with edit permission can remove others'}, status=status.HTTP_403_FORBIDDEN)
        
        trip_member = get_object_or_404(TripMember, id=member_id, trip=trip)
        trip_member.delete()
        return Response({'success': True,'message': 'Member removed from trip successfully'}, status=status.HTTP_200_OK)