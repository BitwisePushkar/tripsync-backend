from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from .models import Tripmate, FriendRequest, TripShare
from .serializers import TripmateSerializer, FriendRequestSerializer, SendFriendRequestSerializer,RespondFriendRequestSerializer, UserSearchSerializer, TripShareSerializer,ShareTripSerializer, RespondTripShareSerializer, ItenaryBasicSerializer
from Itinerary.models import Trip
from personal.models import Profile

User = get_user_model()
class SearchUser(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSearchSerializer
    def get_queryset(self):
        search_query = self.request.query_params.get('q', '').strip()
        if not search_query or len(search_query) < 2:
            return User.objects.none()
        users = User.objects.filter(Q(email__icontains=search_query)|Q(profile__fname__icontains=search_query)|Q(profile__lname__icontains=search_query)).exclude(id=self.request.user.id).select_related('profile').distinct()[:20]
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
            description='Search query (name or email)',
            required=True,
            examples=[
                OpenApiExample(
                    "Search by name",
                    value="John",
                    description="Search for users with name containing 'John'"
                ),
                OpenApiExample(
                    "Search by email",
                    value="example@gmail.com",
                    description="Search for users with this email"
                )
            ]
        )
    ],
    responses={
        200: OpenApiResponse(
            description="List of users matching the search query",
            response=UserSearchSerializer(many=True),
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Users retrieved successfully",
                        "data": [
                            {"id": 1, "full_name": "John Doe", "email": "john@example.com"},
                            {"id": 2, "full_name": "Jane Smith", "email": "jane@example.com"}
                        ]
                    },
                    response_only=True
                )
            ]
        )
    }
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
    responses={
        200: OpenApiResponse(
            description="List of tripmates retrieved successfully",
            response=UserSearchSerializer(many=True),
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "status": "success",
                        "message": "Tripmates retrieved successfully",
                        "data": [
                            {"id": 1, "full_name": "John Doe", "email": "john@example.com"},
                            {"id": 2, "full_name": "Jane Smith", "email": "jane@example.com"}
                        ],
                        "count": 2
                    },
                    response_only=True
                )
            ]
        )
    }
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
        201: OpenApiResponse(
            description="Friend request sent successfully",
            response=FriendRequestSerializer,
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "success": True,
                        "message": "Friend request sent successfully",
                        "data": {
                            "id": 10,
                            "sender": {"id": 1, "full_name": "John Doe"},
                            "receiver": {"id": 2, "full_name": "Jane Smith"},
                            "message": "Hey! Let's connect",
                            "status": "pending",
                            "created_at": "2025-11-05T10:32:00Z"
                        }
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Validation error",
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {"receiver_id": ["This field is required."]}
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def post(self, request):
        serializer = SendFriendRequestSerializer(data=request.data, context={'request': request}) 
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        receiver = User.objects.get(id=serializer.validated_data['receiver_id'])
        message = serializer.validated_data.get('message', '')
        tripmate_profile, _ = Tripmate.objects.get_or_create(user=request.user)
        Tripmate.objects.get_or_create(user=receiver)
        friend_request = FriendRequest.objects.create(sender=request.user,receiver=receiver,message=message)
        response_serializer = FriendRequestSerializer(friend_request, context={'request': request})
        return Response({'success': True,'message': 'Friend request sent successfully','data': response_serializer.data}, status=status.HTTP_201_CREATED)

class ReceivedFriendRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FriendRequestSerializer
    def get_queryset(self):
        return FriendRequest.objects.filter(receiver=self.request.user,status='pending').select_related('sender', 'sender__profile').order_by('-created_at')
    
    @extend_schema(
    tags=['Tripmate'],
    summary="Get received friend requests",
    description="Retrieve all pending friend requests you've received.",
    responses={
        200: OpenApiResponse(
            description="List of received friend requests",
            response=FriendRequestSerializer(many=True),
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "success": True,
                        "message": "Received friend requests retrieved successfully",
                        "data": [
                            {
                                "id": 12,
                                "sender": {"id": 3, "full_name": "Alice Johnson"},
                                "receiver": {"id": 1, "full_name": "John Doe"},
                                "message": "Let's connect for the upcoming trip",
                                "status": "pending",
                                "created_at": "2025-11-05T10:32:00Z"
                            },
                            {
                                "id": 15,
                                "sender": {"id": 4, "full_name": "Bob Smith"},
                                "receiver": {"id": 1, "full_name": "John Doe"},
                                "message": "",
                                "status": "pending",
                                "created_at": "2025-11-05T11:00:00Z"
                            }
                        ]
                    },
                    response_only=True
                )
            ]
        )
    }
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
    description="Retrieve all pending friend requests you've sent to other users.",
    responses={
        200: OpenApiResponse(
            description="List of sent friend requests",
            response=FriendRequestSerializer(many=True),
            examples=[
                OpenApiExample(
                    "Success Example",
                    value={
                        "success": True,
                        "message": "Sent friend requests retrieved successfully",
                        "data": [
                            {
                                "id": 20,
                                "sender": {"id": 1, "full_name": "John Doe"},
                                "receiver": {"id": 5, "full_name": "Charlie Brown"},
                                "message": "Join me for the hiking trip!",
                                "status": "pending",
                                "created_at": "2025-11-05T12:15:00Z"
                            },
                            {
                                "id": 22,
                                "sender": {"id": 1, "full_name": "John Doe"},
                                "receiver": {"id": 6, "full_name": "Dana White"},
                                "message": "",
                                "status": "pending",
                                "created_at": "2025-11-05T12:45:00Z"
                            }
                        ]
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class RespondFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    tags=['Tripmate'],
    summary="Accept or decline friend request",
    description="Respond to a received friend request by either accepting or declining it.",
    request=RespondFriendRequestSerializer,
    parameters=[
        OpenApiParameter(
            name='request_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='Friend request ID to respond to'
        )
    ],
    responses={
        200: OpenApiResponse(
            description="Friend request successfully accepted or declined",
            examples=[
                OpenApiExample(
                    "Accepted Request",
                    value={
                        "success": True,
                        "message": "Friend request accepted. You are now tripmates!",
                        "data": {
                            "id": 10,
                            "sender": {"id": 2, "full_name": "Alice Smith"},
                            "receiver": {"id": 1, "full_name": "John Doe"},
                            "message": "Join me for the hiking trip!",
                            "status": "accepted",
                            "created_at": "2025-11-05T12:15:00Z"
                        }
                    },
                    response_only=True
                ),
                OpenApiExample(
                    "Declined Request",
                    value={
                        "success": True,
                        "message": "Friend request declined",
                        "data": {
                            "id": 11,
                            "sender": {"id": 3, "full_name": "Bob Johnson"},
                            "receiver": {"id": 1, "full_name": "John Doe"},
                            "message": "Let's travel together!",
                            "status": "declined",
                            "created_at": "2025-11-05T12:45:00Z"
                        }
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Invalid action or input",
            examples=[
                OpenApiExample(
                    "Invalid Action",
                    value={
                        "success": False,
                        "message": "Invalid action",
                        "errors": {"action": ["This field must be either 'accept' or 'decline'."]}
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Friend request not found",
            examples=[
                OpenApiExample(
                    "Request Not Found",
                    value={
                        "detail": "Not found."
                    },
                    response_only=True
                )
            ]
        )
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
    description="Cancel a friend request that you've previously sent and is still pending.",
    parameters=[OpenApiParameter(name='request_id',type=OpenApiTypes.INT,location=OpenApiParameter.PATH,description='ID of the friend request to cancel')],
    responses={
        204: OpenApiResponse(
            description="Friend request cancelled successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "Friend request cancelled"
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Friend request not found",
            examples=[
                OpenApiExample(
                    "Request Not Found",
                    value={
                        "success": False,
                        "message": "Friend request not found",
                        "error_code": "REQUEST_NOT_FOUND"
                    },
                    response_only=True
                )
            ]
        )
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
    description="Remove a user from your tripmates list. This will remove the relationship from both sides.",
    parameters=[OpenApiParameter(name='user_id',type=OpenApiTypes.INT,location=OpenApiParameter.PATH,description='ID of the user to remove from your tripmates')],
    responses={
        200: OpenApiResponse(
            description="Tripmate removed successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "Tripmate removed successfully"
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Not tripmates with this user",
            examples=[
                OpenApiExample(
                    "Not Tripmates",
                    value={
                        "success": False,
                        "message": "Not tripmates with this user",
                        "error_code": "NOT_TRIPMATES"
                    },
                    response_only=True
                )
            ]
        ),
        404: OpenApiResponse(
            description="Tripmate profile or user not found",
            examples=[
                OpenApiExample(
                    "Profile Not Found",
                    value={
                        "success": False,
                        "message": "Tripmate profile not found",
                        "error_code": "PROFILE_NOT_FOUND"
                    },
                    response_only=True
                ),
                OpenApiExample(
                    "User Not Found",
                    value={
                        "success": False,
                        "message": "User not found",
                        "error_code": "USER_NOT_FOUND"
                    },
                    response_only=True
                )
            ]
        )
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

class ShareTripView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
    tags=['Tripmate'],
    summary="Share trip with tripmate",
    description="Share your trip itinerary with a tripmate.",
    request=ShareTripSerializer,
    responses={
        201: OpenApiResponse(
            description="Trip shared successfully",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "success": True,
                        "message": "Trip shared successfully",
                        "data": {
                            "id": 1,
                            "itenary": 10,
                            "shared_with": {"id": 2, "fname": "Jane", "lname": "Smith"},
                            "shared_by": {"id": 1, "fname": "John", "lname": "Doe"},
                            "role": "viewer",
                            "invitation_message": "Check out my trip!"
                        }
                    },
                    response_only=True
                )
            ]
        ),
        400: OpenApiResponse(
            description="Validation failed",
            examples=[
                OpenApiExample(
                    "Validation Error",
                    value={
                        "success": False,
                        "message": "Validation failed",
                        "errors": {
                            "tripmate_id": ["This user does not exist."],
                            "itenary_id": ["This itinerary does not exist."]
                        }
                    },
                    response_only=True
                )
            ]
        )
    }
    )
    def post(self, request):
        serializer = ShareTripSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Validation failed','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        itenary = Trip.objects.get(id=serializer.validated_data['itenary_id'])
        tripmate_user = User.objects.get(id=serializer.validated_data['tripmate_id'])
        trip_share = TripShare.objects.create(itenary=itenary,shared_with=tripmate_user,shared_by=request.user,role=serializer.validated_data.get('role', 'viewer'),invitation_message=serializer.validated_data.get('invitation_message', '')) 
        response_serializer = TripShareSerializer(trip_share, context={'request': request})
        return Response({'success': True,'message': 'Trip shared successfully','data': response_serializer.data}, status=status.HTTP_201_CREATED)

class MySharedTripsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripShareSerializer
    def get_queryset(self):
        return TripShare.objects.filter(shared_by=self.request.user).select_related('itenary', 'shared_with', 'shared_with__profile').order_by('-created_at')
    @extend_schema(
        tags=['Tripmate'],
        summary="Get trips I've shared",
        description="Retrieve the list of trips you have shared with your tripmates.",
        responses={
            200: OpenApiResponse(
                description="List of shared trips retrieved successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "success": True,
                            "message": "Trips retrieved successfully",
                            "data": [
                                {
                                    "id": 1,
                                    "itenary": {
                                        "id": 10,
                                        "title": "Paris Trip",
                                        "start_date": "2025-12-01",
                                        "end_date": "2025-12-07"
                                    },
                                    "shared_with": {
                                        "id": 2,
                                        "fname": "Jane",
                                        "lname": "Smith"
                                    },
                                    "shared_by": {
                                        "id": 1,
                                        "fname": "John",
                                        "lname": "Doe"
                                    },
                                    "role": "viewer",
                                    "invitation_message": "Check out my trip!",
                                    "created_at": "2025-11-05T10:00:00Z"
                                }
                            ]
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class ReceivedTripSharesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TripShareSerializer
    def get_queryset(self):
        status_filter = self.request.query_params.get('status', 'all')
        
        queryset = TripShare.objects.filter(shared_with=self.request.user).select_related('itenary', 'shared_by', 'shared_by__profile').order_by('-created_at')
        if status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        return queryset
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Get trip invitations received",
        description="Retrieve trips shared with you by your tripmates, optionally filtered by status (pending, accepted, declined, or all).",
        parameters=[
            OpenApiParameter(
                name='status',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Filter trips by status (pending/accepted/declined/all)',
                required=False,
                examples=[
                    OpenApiExample('Pending', value='pending'),
                    OpenApiExample('Accepted', value='accepted'),
                    OpenApiExample('All', value='all')
                ]
            )
        ],
        responses={
            200: OpenApiResponse(
                description="List of received trip shares retrieved successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "success": True,
                            "message": "Trips retrieved successfully",
                            "data": [
                                {
                                    "id": 5,
                                    "itenary": {
                                        "id": 10,
                                        "title": "Paris Trip",
                                        "start_date": "2025-12-01",
                                        "end_date": "2025-12-07"
                                    },
                                    "shared_with": {
                                        "id": 2,
                                        "fname": "Jane",
                                        "lname": "Smith"
                                    },
                                    "shared_by": {
                                        "id": 1,
                                        "fname": "John",
                                        "lname": "Doe"
                                    },
                                    "role": "viewer",
                                    "invitation_message": "Join me in Paris!",
                                    "status": "pending",
                                    "created_at": "2025-11-05T10:00:00Z"
                                }
                            ]
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class RespondTripShareView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=['Tripmate'],
        summary="Accept or decline trip share",
        description="Respond to a trip invitation by accepting or declining it.",
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
            200: OpenApiResponse(
                description="Trip share response recorded successfully",
                examples=[
                    OpenApiExample(
                        "Accepted",
                        value={
                            "success": True,
                            "message": "Trip invitation accepted",
                            "data": {
                                "id": 5,
                                "itenary": {
                                    "id": 10,
                                    "title": "Paris Trip",
                                    "start_date": "2025-12-01",
                                    "end_date": "2025-12-07"
                                },
                                "shared_with": {
                                    "id": 2,
                                    "fname": "Jane",
                                    "lname": "Smith"
                                },
                                "shared_by": {
                                    "id": 1,
                                    "fname": "John",
                                    "lname": "Doe"
                                },
                                "role": "viewer",
                                "invitation_message": "Join me in Paris!",
                                "status": "accepted",
                                "created_at": "2025-11-05T10:00:00Z"
                            }
                        },
                        response_only=True
                    ),
                    OpenApiExample(
                        "Declined",
                        value={
                            "success": True,
                            "message": "Trip invitation declined",
                            "data": {
                                "id": 5,
                                "status": "declined"
                            }
                        },
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid action",
                examples=[
                    OpenApiExample(
                        "Invalid Action",
                        value={
                            "success": False,
                            "message": "Invalid action",
                            "errors": {"action": ["This field is required or invalid"]}
                        },
                        response_only=True
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Trip share not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={
                            "success": False,
                            "message": "Trip share not found or already responded",
                            "error_code": "TRIP_SHARE_NOT_FOUND"
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def post(self, request, share_id):
        trip_share = get_object_or_404(TripShare,id=share_id,shared_with=request.user,status='pending')
        serializer = RespondTripShareSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'success': False,'message': 'Invalid action','errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        action = serializer.validated_data['action']
        if action == 'accept':
            trip_share.status = 'accepted'
            message = 'Trip invitation accepted'
        else:
            trip_share.status = 'declined'
            message = 'Trip invitation declined'
        trip_share.save()
        response_serializer = TripShareSerializer(trip_share, context={'request': request})
        return Response({'success': True,'message': message,'data': response_serializer.data}, status=status.HTTP_200_OK)

class SharedTripDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ItenaryBasicSerializer
    
    def get_queryset(self):
        return Trip.objects.filter(Q(user=self.request.user) |Q(shared_with__shared_with=self.request.user, shared_with__status='accepted')).distinct()
    
    @extend_schema(
        tags=['Tripmate'],
        summary="View shared trip details",
        description="View details of a trip shared with you or owned by you.",
        parameters=[
            OpenApiParameter(
                name='id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Trip ID'
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Trip details retrieved successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "id": 1,
                            "title": "Trip to Paris",
                            "start_date": "2025-12-01",
                            "end_date": "2025-12-10",
                            "user": {"id": 2, "fname": "John", "lname": "Doe"},
                            "locations": [],
                            "notes": ""
                        },
                        response_only=True
                    )
                ]
            ),
            403: OpenApiResponse(
                description="Access forbidden",
                examples=[
                    OpenApiExample(
                        "Forbidden",
                        value={
                            "success": False,
                            "message": "You do not have permission to view this trip",
                            "error_code": "FORBIDDEN"
                        },
                        response_only=True
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Trip not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={
                            "success": False,
                            "message": "Trip not found",
                            "error_code": "TRIP_NOT_FOUND"
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class RevokeTripShareView(APIView):
    permission_classes = [IsAuthenticated]
    @extend_schema(
        tags=['Tripmate'],
        summary="Revoke trip share access",
        description="Remove a tripmate's access to a shared trip.",
        parameters=[
            OpenApiParameter(
                name='share_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Trip share ID to revoke'
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Trip share access revoked successfully",
                examples=[
                    OpenApiExample(
                        "Success",
                        value={
                            "success": True,
                            "message": "Trip share access revoked"
                        },
                        response_only=True
                    )
                ]
            ),
            403: OpenApiResponse(
                description="User is not the owner of the shared trip",
                examples=[
                    OpenApiExample(
                        "Forbidden",
                        value={
                            "success": False,
                            "message": "You are not allowed to revoke this trip share",
                            "error_code": "FORBIDDEN"
                        },
                        response_only=True
                    )
                ]
            ),
            404: OpenApiResponse(
                description="Trip share not found",
                examples=[
                    OpenApiExample(
                        "Not Found",
                        value={
                            "success": False,
                            "message": "Trip share not found",
                            "error_code": "TRIP_SHARE_NOT_FOUND"
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def delete(self, request, share_id):
        trip_share = get_object_or_404(TripShare,id=share_id,shared_by=request.user)
        trip_share.delete()
        return Response({'success': True,'message': 'Trip share access revoked'}, status=status.HTTP_200_OK)