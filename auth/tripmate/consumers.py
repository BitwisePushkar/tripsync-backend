import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import FriendRequest, TripShare

User = get_user_model()

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.notification_group = f'notifications_{self.user.id}'
        
        await self.channel_layer.group_add(
            self.notification_group,
            self.channel_name
        )
        
        await self.accept()
        
        pending_count = await self.get_pending_notifications_count()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'pending_count': pending_count
        }))
    
    async def disconnect(self, close_code):
        if hasattr(self, 'notification_group'):
            await self.channel_layer.group_discard(
                self.notification_group,
                self.channel_name
            )
    
    async def receive(self, text_data):
        pass
    
    async def friend_request_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'friend_request',
            'data': event['data']
        }))
    
    async def trip_share_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'trip_share',
            'data': event['data']
        }))
    
    async def friend_request_response(self, event):
        await self.send(text_data=json.dumps({
            'type': 'friend_request_response',
            'data': event['data']
        }))
    
    async def trip_share_response(self, event):
        await self.send(text_data=json.dumps({
            'type': 'trip_share_response',
            'data': event['data']
        }))
    
    @database_sync_to_async
    def get_pending_notifications_count(self):
        friend_requests_count = FriendRequest.objects.filter(
            receiver=self.user,
            status='pending'
        ).count()
        
        trip_shares_count = TripShare.objects.filter(
            shared_with=self.user,
            status='pending'
        ).count()
        
        return {
            'friend_requests': friend_requests_count,
            'trip_shares': trip_shares_count,
            'total': friend_requests_count + trip_shares_count
        }