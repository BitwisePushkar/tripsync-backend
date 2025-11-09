from django.urls import path
from .views import SearchUser, ViewTripmates, SendFriendRequestView,ReceivedFriendRequestsView, SentFriendRequestsView,RespondFriendRequestView, CancelFriendRequestView,RemoveTripmateView, AddTripMemberView, TripMembersListView,UpdateTripMemberView, RemoveTripMemberView

urlpatterns = [
    path('search/', SearchUser.as_view(), name='search-users'),
    path('my-tripmates/', ViewTripmates.as_view(), name='my-tripmates'),
    path('friend-request/send/', SendFriendRequestView.as_view(), name='send-friend-request'),
    path('friend-request/received/', ReceivedFriendRequestsView.as_view(), name='received-friend-requests'),
    path('friend-request/sent/', SentFriendRequestsView.as_view(), name='sent-friend-requests'),
    path('friend-request/<int:request_id>/respond/', RespondFriendRequestView.as_view(), name='respond-friend-request'),
    path('friend-request/<int:request_id>/cancel/', CancelFriendRequestView.as_view(), name='cancel-friend-request'),
    path('tripmate/<int:user_id>/remove/', RemoveTripmateView.as_view(), name='remove-tripmate'),
    path('trip/<int:trip_id>/members/', TripMembersListView.as_view(), name='trip-members-list'),
    path('trip/<int:trip_id>/members/add/', AddTripMemberView.as_view(), name='add-trip-member'),
    path('trip/<int:trip_id>/members/<int:member_id>/', UpdateTripMemberView.as_view(), name='update-trip-member'),
    path('trip/<int:trip_id>/members/<int:member_id>/remove/', RemoveTripMemberView.as_view(), name='remove-trip-member'),
]