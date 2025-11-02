from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import FriendRequest, TripShare

@receiver(post_save, sender=FriendRequest)
def friend_request_notification(sender, instance, created, **kwargs):
    if created and instance.status == 'pending':
        channel_layer = get_channel_layer()
        try:
            sender_name = f"{instance.sender.profile.fname} {instance.sender.profile.lname}"
        except:
            sender_name = instance.sender.email
        notification_data = {'id': instance.id,'sender_id': instance.sender.id,'sender_name': sender_name,'message': instance.message,'created_at': instance.created_at.isoformat()}
        
        async_to_sync(channel_layer.group_send)(f'notifications_{instance.receiver.id}',{'type': 'friend_request_notification','data': notification_data})
    
    elif instance.status in ['accepted', 'declined'] and not created:
        channel_layer = get_channel_layer()
        try:
            receiver_name = f"{instance.receiver.profile.fname} {instance.receiver.profile.lname}"
        except:
            receiver_name = instance.receiver.email
        notification_data = {'id': instance.id,'responder_id': instance.receiver.id,'responder_name': receiver_name,'status': instance.status,'updated_at': instance.updated_at.isoformat()}
        
        async_to_sync(channel_layer.group_send)(f'notifications_{instance.sender.id}',{'type': 'friend_request_response','data': notification_data})

@receiver(post_save, sender=TripShare)
def trip_share_notification(sender, instance, created, **kwargs):
    if created and instance.status == 'pending':
        channel_layer = get_channel_layer()
        try:
            sharer_name = f"{instance.shared_by.profile.fname} {instance.shared_by.profile.lname}"
        except:
            sharer_name = instance.shared_by.email  
        notification_data = {'id': instance.id,'trip_id': instance.itenary.id,'trip_name': instance.itenary.tripname,'sharer_id': instance.shared_by.id,'sharer_name': sharer_name,'role': instance.role,'message': instance.invitation_message,'created_at': instance.created_at.isoformat()}
        
        async_to_sync(channel_layer.group_send)(f'notifications_{instance.shared_with.id}',{'type': 'trip_share_notification','data': notification_data})
    
    elif instance.status in ['accepted', 'declined'] and not created:
        channel_layer = get_channel_layer()
        try:
            responder_name = f"{instance.shared_with.profile.fname} {instance.shared_with.profile.lname}"
        except:
            responder_name = instance.shared_with.email
        notification_data = {'id': instance.id,'trip_name': instance.itenary.tripname,'responder_id': instance.shared_with.id,'responder_name': responder_name,'status': instance.status,'updated_at': instance.updated_at.isoformat()}
        
        async_to_sync(channel_layer.group_send)(f'notifications_{instance.shared_by.id}',{'type': 'trip_share_response','data': notification_data})