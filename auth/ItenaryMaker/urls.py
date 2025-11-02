from django.urls import path
from .views import CreateItenaryView, ItenaryListView, ItenaryDetailView

urlpatterns = [
    path('create/', CreateItenaryView.as_view(), name='create-itinerary'),
    path('list/', ItenaryListView.as_view(), name='list-itineraries'),
    path('<int:pk>/', ItenaryDetailView.as_view(), name='itinerary-detail'),
]