from django.urls import path
from .views import (
    SearchUsersView, MyTripmatesView, SendFriendRequestView,
    ReceivedFriendRequestsView, SentFriendRequestsView,
    RespondFriendRequestView, CancelFriendRequestView,
    RemoveTripmateView, ShareTripView, MySharedTripsView,
    ReceivedTripSharesView, RespondTripShareView,
    SharedTripDetailView, RevokeTripShareView
)

urlpatterns = [
    path('search/', SearchUsersView.as_view(), name='search-users'),
    path('my-tripmates/', MyTripmatesView.as_view(), name='my-tripmates'),
    path('friend-request/send/', SendFriendRequestView.as_view(), name='send-friend-request'),
    path('friend-request/received/', ReceivedFriendRequestsView.as_view(), name='received-friend-requests'),
    path('friend-request/sent/', SentFriendRequestsView.as_view(), name='sent-friend-requests'),
    path('friend-request/<int:request_id>/respond/', RespondFriendRequestView.as_view(), name='respond-friend-request'),
    path('friend-request/<int:request_id>/cancel/', CancelFriendRequestView.as_view(), name='cancel-friend-request'),
    path('tripmate/<int:user_id>/remove/', RemoveTripmateView.as_view(), name='remove-tripmate'),
    path('trip/share/', ShareTripView.as_view(), name='share-trip'),
    path('trip/shared/', MySharedTripsView.as_view(), name='my-shared-trips'),
    path('trip/invitations/', ReceivedTripSharesView.as_view(), name='received-trip-shares'),
    path('trip/invitations/<int:share_id>/respond/', RespondTripShareView.as_view(), name='respond-trip-share'),
    path('trip/shared/<int:pk>/', SharedTripDetailView.as_view(), name='shared-trip-detail'),
    path('trip/share/<int:share_id>/revoke/', RevokeTripShareView.as_view(), name='revoke-trip-share'),
]