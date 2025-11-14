from django.urls import path
from personal import views

app_name = "personal"

urlpatterns = [
    path("profile/", views.ProfileDetailView.as_view(), name="profile-detail",),
    path("profile/picture/", views.ProfilePictureView.as_view(), name="profile-picture",),
    path("emergency-contacts/", views.EmergencyContactListView.as_view(), name="emergency-contact-list",),
    path("emergency-contacts/<int:pk>/", views.EmergencyContactDetailView.as_view(), name="emergency-contact-detail",),
    path("emergency/sos/", views.EmergencySOSView.as_view(), name="emergency-sos",),
    path("users/", views.UserListView.as_view(), name="user-list",),
    path("users/search/", views.UserSearchView.as_view(), name="user-search",),
]