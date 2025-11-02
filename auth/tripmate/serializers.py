from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tripmate, FriendRequest, TripShare
from personal.models import Profile
from ItenaryMaker.models import Trip

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
            
            return {'full_name': f"{profile.fname} {profile.lname}",
                    'bio': profile.bio,
                    'profile_pic': profile_pic_url,
                    'gender': profile.gender,
                    'preference': profile.prefrence,}
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


class ItenaryBasicSerializer(serializers.ModelSerializer):
    owner_info = UserBasicSerializer(source='user', read_only=True)
    duration_days = serializers.SerializerMethodField()
    
    class Meta:
        model = Trip
        fields = ['id', 'tripname', 'destination', 'start_date', 'end_date', 'duration_days', 'Budget', 'owner_info']
        read_only_fields = ['id']
    
    def get_duration_days(self, obj):
        if obj.start_date and obj.end_date:
            return (obj.end_date - obj.start_date).days + 1
        return obj.days


class TripShareSerializer(serializers.ModelSerializer):
    itenary_info = ItenaryBasicSerializer(source='itenary', read_only=True)
    shared_with_info = UserBasicSerializer(source='shared_with', read_only=True)
    shared_by_info = UserBasicSerializer(source='shared_by', read_only=True)
    
    class Meta:
        model = TripShare
        fields = ['id', 'itenary_info', 'shared_with_info', 'shared_by_info', 'status', 'role', 'invitation_message', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ShareTripSerializer(serializers.Serializer):
    itenary_id = serializers.IntegerField()
    tripmate_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=['viewer', 'editor'], default='viewer')
    invitation_message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_itenary_id(self, value):
        request_user = self.context['request'].user
        try:
            itenary = Trip.objects.get(id=value, user=request_user)
        except Trip.DoesNotExist:
            raise serializers.ValidationError("Trip not found or you don't own this trip")
        return value
    
    def validate_tripmate_id(self, value):
        request_user = self.context['request'].user
        
        if value == request_user.id:
            raise serializers.ValidationError("Cannot share trip with yourself")
        
        try:
            tripmate_user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")
        
        try:
            if not request_user.tripmate_profile.are_tripmates(tripmate_user):
                raise serializers.ValidationError("Can only share trips with tripmates")
        except Tripmate.DoesNotExist:
            raise serializers.ValidationError("You don't have a tripmate profile")
        
        return value
    
    def validate(self, data):
        itenary_id = data.get('itenary_id')
        tripmate_id = data.get('tripmate_id')
        
        if TripShare.objects.filter(itenary_id=itenary_id, shared_with_id=tripmate_id).exists():
            raise serializers.ValidationError("Trip already shared with this tripmate")
        
        return data


class RespondTripShareSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['accept', 'decline'])