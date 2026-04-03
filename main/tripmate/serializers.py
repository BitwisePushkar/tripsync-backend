from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tripmate, FriendRequest, TripMember
from personal.models import Profile
from Itinerary.models import Trip

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

class UserSearchSerializer(serializers.ModelSerializer):
    profile_data = serializers.SerializerMethodField()
    is_tripmate = serializers.SerializerMethodField()
    request_status = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'profile_data', 'is_tripmate', 'request_status']
    
    def get_profile_data(self, obj):
        try:
            profile = obj.profile
            request = self.context.get('request')
            profile_pic_url = None
            if profile.profile_pic:
                if request:
                    profile_pic_url = request.build_absolute_uri(profile.profile_pic.url)
                else:
                    profile_pic_url = profile.profile_pic.url
            
            return {
                'full_name': f"{profile.fname} {profile.lname}",
                'bio': profile.bio,
                'profile_pic': profile_pic_url,
                'gender': profile.gender,
                'preference': profile.prefrence,
            }
        except:
            return None
    
    def get_is_tripmate(self, obj):
        request_user = self.context.get('request').user
        try:
            return request_user.tripmate_profile.are_tripmates(obj)
        except:
            return False
    
    def get_request_status(self, obj):
        request_user = self.context.get('request').user
        
        sent_req = FriendRequest.objects.filter(sender=request_user, receiver=obj, status='pending').first()
        if sent_req:
            return 'sent'
        
        received_req = FriendRequest.objects.filter(sender=obj, receiver=request_user, status='pending').first()
        if received_req:
            return 'received'
        
        return None


class TripmateSerializer(serializers.ModelSerializer):
    user_info = UserBasicSerializer(source='user', read_only=True)
    tripmate_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tripmate
        fields = ['id', 'user_info', 'tripmate_count', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_tripmate_count(self, obj):
        return obj.get_tripmate_count()


class FriendRequestSerializer(serializers.ModelSerializer):
    sender_info = UserBasicSerializer(source='sender', read_only=True)
    receiver_info = UserBasicSerializer(source='receiver', read_only=True)
    
    class Meta:
        model = FriendRequest
        fields = ['id', 'sender_info', 'receiver_info', 'status', 'message', 'created_at', 'updated_at']
        read_only_fields = ['id', 'sender_info', 'receiver_info', 'created_at', 'updated_at']


class SendFriendRequestSerializer(serializers.Serializer):
    receiver_id = serializers.IntegerField()
    message = serializers.CharField(max_length=300, required=False, allow_blank=True)
    
    def validate_receiver_id(self, value):
        request_user = self.context['request'].user
        
        if value == request_user.id:
            raise serializers.ValidationError("Cannot send friend request to yourself")
        
        try:
            receiver = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        
        try:
            if request_user.tripmate_profile.are_tripmates(receiver):
                raise serializers.ValidationError("Already tripmates")
        except Tripmate.DoesNotExist:
            pass
        
        if FriendRequest.objects.filter(sender=request_user, receiver=receiver, status='pending').exists():
            raise serializers.ValidationError("Friend request already sent")
        
        if FriendRequest.objects.filter(sender=receiver, receiver=request_user, status='pending').exists():
            raise serializers.ValidationError("This user has already sent you a friend request")
        
        return value


class RespondFriendRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['accept', 'decline'])


class TripMemberSerializer(serializers.ModelSerializer):
    user_info = UserBasicSerializer(source='user', read_only=True)
    added_by_info = UserBasicSerializer(source='added_by', read_only=True)
    trip_name = serializers.CharField(source='trip.tripname', read_only=True)
    
    class Meta:
        model = TripMember
        fields = ['id', 'user_info', 'trip_name', 'added_by_info', 'permission', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class AddTripMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    permission = serializers.ChoiceField(choices=['view', 'edit'], default='view')
    
    def validate_user_id(self, value):
        request_user = self.context['request'].user
        trip_id = self.context.get('trip_id')
        
        if value == request_user.id:
            raise serializers.ValidationError("Cannot add yourself to the trip")
        
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        
        try:
            trip = Trip.objects.get(id=trip_id)
            if user.id == trip.user.id:
                raise serializers.ValidationError("Trip owner is already part of the trip")
        except Trip.DoesNotExist:
            raise serializers.ValidationError("Trip not found")
        
        try:
            if not request_user.tripmate_profile.are_tripmates(user):
                raise serializers.ValidationError("Can only add tripmates to your trip")
        except Tripmate.DoesNotExist:
            raise serializers.ValidationError("You don't have a tripmate profile")
        
        if TripMember.objects.filter(trip_id=trip_id, user_id=value).exists():
            raise serializers.ValidationError("User is already a member of this trip")
        
        return value


class UpdateTripMemberSerializer(serializers.Serializer):
    permission = serializers.ChoiceField(choices=['view', 'edit'])