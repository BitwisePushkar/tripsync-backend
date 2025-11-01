from django.urls import path
from . import views

urlpatterns=[
    path('trips/',views.trip_list_create,name='trip-list-create'),
    path('trips/<int:pk>/',views.trip_detail,name='trip-detail'),
    path('trips/<int:pk>/Itenary/',views.update_Itenary,name='update-Itenary'),
    path('trips/<int:pk>/Itenary/day/<int:day_number>/',views.delete_Itenary_day,name='delete-Itenary-day'),
    path('trips/<int:pk>/draft/',views.save_draft,name='save-draft'),
]