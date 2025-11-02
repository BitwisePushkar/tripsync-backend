from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import Tripmate, FriendRequest, TripShare
from .serializers import TripmateSerializer, FriendRequestSerializer, SendFriendRequestSerializer,RespondFriendRequestSerializer, UserSearchSerializer, TripShareSerializer,ShareTripSerializer, RespondTripShareSerializer, ItenaryBasicSerializer
from ItenaryMaker.models import Trip
from personal.models import Profile

User = get_user_model()
class SearchUser(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchSerializer
    def get_queryset(self):
        search_query = self.request.query_params.get('q', '').strip()
        if not search_query or len(search_query) < 2:
            return User.objects.none()
        
        users = User.objects.filter(Q(email__icontains=search_query)
                                    |Q(profile__fname__icontains=search_query)
                                    |Q(profile__lname__icontains=search_query)
                                    ).exclude(id=self.request.user.id).select_related('profile').distinct()[:20]
        return users
    
    @extend_schema(summary="Search users by name or email",
        description="Search for users to send friend requests. Minimum 2 characters required.",
        parameters=[OpenApiParameter(
                name='q',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Search query (name or email)',
                required=True)],
        responses={200: UserSearchSerializer(many=True)},
        tags=['Tripmate - Search'])
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
    
    @extend_schema(summary="Get my tripmates list",
        description="Retrieve list of all your tripmates",
        responses={200: UserSearchSerializer(many=True)},
        tags=['Tripmate - Friends']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SendFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Send friend request",
        description="Send a friend request to another user",
        request=SendFriendRequestSerializer,
        responses={
            201: FriendRequestSerializer,
            400: OpenApiTypes.OBJECT},
        tags=['Tripmate - Friends']
    )
    def post(self, request):
        serializer = SendFriendRequestSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        receiver = User.objects.get(id=serializer.validated_data['receiver_id'])
        message = serializer.validated_data.get('message', '')
        
        tripmate_profile, _ = Tripmate.objects.get_or_create(user=request.user)
        Tripmate.objects.get_or_create(user=receiver)
        
        friend_request = FriendRequest.objects.create(
            sender=request.user,
            receiver=receiver,
            message=message
        )
        
        response_serializer = FriendRequestSerializer(friend_request, context={'request': request})
        
        return Response({
            'success': True,
            'message': 'Friend request sent successfully',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class ReceivedFriendRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    
    def get_queryset(self):
        return FriendRequest.objects.filter(
            receiver=self.request.user,
            status='pending'
        ).select_related('sender', 'sender__profile').order_by('-created_at')
    
    @extend_schema(
        summary="Get received friend requests",
        description="Get all pending friend requests you've received",
        responses={200: FriendRequestSerializer(many=True)},
        tags=['Tripmate - Friends']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SentFriendRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    
    def get_queryset(self):
        return FriendRequest.objects.filter(
            sender=self.request.user,
            status='pending'
        ).select_related('receiver', 'receiver__profile').order_by('-created_at')
    
    @extend_schema(
        summary="Get sent friend requests",
        description="Get all pending friend requests you've sent",
        responses={200: FriendRequestSerializer(many=True)},
        tags=['Tripmate - Friends']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RespondFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Accept or decline friend request",
        description="Respond to a received friend request",
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
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Tripmate - Friends']
    )
    def post(self, request, request_id):
        friend_request = get_object_or_404(
            FriendRequest,
            id=request_id,
            receiver=request.user,
            status='pending'
        )
        
        serializer = RespondFriendRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid action',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
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
        
        return Response({
            'success': True,
            'message': message,
            'data': response_serializer.data
        }, status=status.HTTP_200_OK)


class CancelFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Cancel sent friend request",
        description="Cancel a friend request you've sent",
        parameters=[
            OpenApiParameter(
                name='request_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Friend request ID'
            )
        ],
        responses={
            204: None,
            404: OpenApiTypes.OBJECT
        },
        tags=['Tripmate - Friends']
    )
    def delete(self, request, request_id):
        friend_request = get_object_or_404(
            FriendRequest,
            id=request_id,
            sender=request.user,
            status='pending'
        )
        
        friend_request.delete()
        
        return Response({
            'success': True,
            'message': 'Friend request cancelled'
        }, status=status.HTTP_204_NO_CONTENT)


class RemoveTripmateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Remove tripmate",
        description="Remove a user from your tripmates list",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to remove'
            )
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Tripmate - Friends']
    )
    def delete(self, request, user_id):
        try:
            tripmate_profile = request.user.tripmate_profile
        except Tripmate.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Tripmate profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        user_to_remove = get_object_or_404(User, id=user_id)
        
        if not tripmate_profile.are_tripmates(user_to_remove):
            return Response({
                'success': False,
                'message': 'Not tripmates with this user'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        tripmate_profile.friends.remove(user_to_remove)
        
        try:
            other_profile = user_to_remove.tripmate_profile
            other_profile.friends.remove(request.user)
        except Tripmate.DoesNotExist:
            pass
        
        return Response({
            'success': True,
            'message': 'Tripmate removed successfully'
        }, status=status.HTTP_200_OK)


class ShareTripView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Share trip with tripmate",
        description="Share your trip itenary with a tripmate",
        request=ShareTripSerializer,
        responses={
            201: TripShareSerializer,
            400: OpenApiTypes.OBJECT
        },
        tags=['Tripmate - Trip Sharing']
    )
    def post(self, request):
        serializer = ShareTripSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        itenary = Trip.objects.get(id=serializer.validated_data['itenary_id'])
        tripmate_user = User.objects.get(id=serializer.validated_data['tripmate_id'])
        
        trip_share = TripShare.objects.create(
            itenary=itenary,
            shared_with=tripmate_user,
            shared_by=request.user,
            role=serializer.validated_data.get('role', 'viewer'),
            invitation_message=serializer.validated_data.get('invitation_message', '')
        )
        
        response_serializer = TripShareSerializer(trip_share, context={'request': request})
        
        return Response({
            'success': True,
            'message': 'Trip shared successfully',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)


class MySharedTripsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripShareSerializer
    
    def get_queryset(self):
        return TripShare.objects.filter(
            shared_by=self.request.user
        ).select_related('itenary', 'shared_with', 'shared_with__profile').order_by('-created_at')
    
    @extend_schema(
        summary="Get trips I've shared",
        description="Get list of trips you've shared with tripmates",
        responses={200: TripShareSerializer(many=True)},
        tags=['Tripmate - Trip Sharing']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ReceivedTripSharesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripShareSerializer
    
    def get_queryset(self):
        status_filter = self.request.query_params.get('status', 'all')
        
        queryset = TripShare.objects.filter(
            shared_with=self.request.user
        ).select_related('itenary', 'shared_by', 'shared_by__profile').order_by('-created_at')
        
        if status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    @extend_schema(
        summary="Get trip invitations received",
        description="Get trips shared with you by tripmates",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter by status (pending/accepted/declined/all)',
                required=False
            )
        ],
        responses={200: TripShareSerializer(many=True)},
        tags=['Tripmate - Trip Sharing']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RespondTripShareView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Accept or decline trip share",
        description="Respond to a trip invitation",
        request=RespondTripShareSerializer,
        parameters=[
            OpenApiParameter(
                name='share_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Trip share ID'
            )
        ],
        responses={
            200: TripShareSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Tripmate - Trip Sharing']
    )
    def post(self, request, share_id):
        trip_share = get_object_or_404(
            TripShare,
            id=share_id,
            shared_with=request.user,
            status='pending'
        )
        
        serializer = RespondTripShareSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid action',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        action = serializer.validated_data['action']
        
        if action == 'accept':
            trip_share.status = 'accepted'
            message = 'Trip invitation accepted'
        else:
            trip_share.status = 'declined'
            message = 'Trip invitation declined'
        
        trip_share.save()
        
        response_serializer = TripShareSerializer(trip_share, context={'request': request})
        
        return Response({
            'success': True,
            'message': message,
            'data': response_serializer.data
        }, status=status.HTTP_200_OK)


class SharedTripDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ItenaryBasicSerializer
    
    def get_queryset(self):
        return Trip.objects.filter(
            Q(user=self.request.user) |
            Q(shared_with__shared_with=self.request.user, shared_with__status='accepted')
        ).distinct()
    
    @extend_schema(
        summary="View shared trip details",
        description="View details of a trip shared with you or owned by you",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Trip ID'
            )
        ],
        responses={
            200: ItenaryBasicSerializer,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Tripmate - Trip Sharing']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RevokeTripShareView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Revoke trip share access",
        description="Remove trip access from a tripmate",
        parameters=[
            OpenApiParameter(
                name='share_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Trip share ID'
            )
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Tripmate - Trip Sharing']
    )
    def delete(self, request, share_id):
        trip_share = get_object_or_404(
            TripShare,
            id=share_id,
            shared_by=request.user
        )
        
        trip_share.delete()
        
        return Response({
            'success': True,
            'message': 'Trip share access revoked'
        }, status=status.HTTP_200_OK)