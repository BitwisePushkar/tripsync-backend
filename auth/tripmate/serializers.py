from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tripmate, FriendRequest, TripShare
from personal.models import Profile
from HomePage.models import ItenaryFields

User = get_user_model()
class UserBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'profile_pic', 'phone_number']
        read_only_fields = ['id', 'email']
    
    def get_full_name(self, obj):
        try:
            return f"{obj.profile.fname} {obj.profile.lname}"
        except:
            return obj.email
    
    def get_profile_pic(self, obj):
        try:
            if obj.profile.profile_pic:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.profile.profile_pic.url)
                return obj.profile.profile_pic.url
        except:
            return None
        return None
    
    def get_phone_number(self, obj):
        try:
            return obj.profile.phone_number
        except:
            return None


