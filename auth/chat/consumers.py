from asgiref.sync import sync_to_async
import json 
import jwt 
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query_string = self.scope['query_string'].decode('utf-8')
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]
        if not token:
            await self.close(code=4002) 
            return
        try:
            decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            self.user = await self.get_user(decoded_data['user_id'])
            self.scope['user'] = self.user
        except jwt.ExpiredSignatureError:
            await self.close(code=4000)  
            return
        except jwt.InvalidTokenError:
            await self.close(code=4001) 
            return
        except Exception as e:
            print(f"Authentication error: {e}")
            await self.close(code=4003)  
            return
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        is_participant = await self.verify_participant(self.user.id, self.conversation_id)
        if not is_participant:
            await self.close(code=4004)  
            return
        self.room_group_name = f'chat_{self.conversation_id}'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        user_data = await self.get_user_data(self.user)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user': user_data,
                'status': 'online',
            }
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get('type')

            if event_type == 'chat_message':
                await self.handle_chat_message(data)
            
            elif event_type == 'typing':
                await self.handle_typing_indicator(data)
            
            elif event_type == 'read_receipt':
                await self.handle_read_receipt(data)
            
            else:
                await self.send_error("Unknown event type")
        
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")
        except Exception as e:
            print(f"Error in receive: {e}")
            await self.send_error("Internal error")

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name') and hasattr(self, 'user'):
            user_data = await self.get_user_data(self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user': user_data,
                    'status': 'offline',
                }
            )
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def handle_chat_message(self, data):
        message_content = data.get('message', '').strip()      
        if not message_content:
            await self.send_error("Message cannot be empty")
            return
        
        if len(message_content) > 5000:
            await self.send_error("Message too long")
            return

        try:
            is_participant = await self.verify_participant(self.user.id, self.conversation_id)
            if not is_participant:
                await self.send_error("You are not a participant")
                return
            conversation = await self.get_conversation(self.conversation_id)
            if not conversation:
                await self.send_error("Conversation not found")
                return
            message = await self.save_message(conversation, self.user, message_content)
            user_data = await self.get_user_data(self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_id': message.id,
                    'message': message.content,
                    'user': user_data,
                    'timestamp': message.timestamp.isoformat(),
                }
            )
        except Exception as e:
            print(f"Error handling chat message: {e}")
            await self.send_error("Failed to send message")

    async def handle_typing_indicator(self, data):
        is_typing = data.get('is_typing', False)
        
        try:
            user_data = await self.get_user_data(self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user': user_data,
                    'is_typing': is_typing,
                    'sender_channel': self.channel_name,
                }
            )
        except Exception as e:
            print(f"Error handling typing indicator: {e}")

    async def handle_read_receipt(self, data):
        message_id = data.get('message_id')
        
        if not message_id:
            return
        
        try:
            await self.mark_message_read(message_id, self.user.id)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'message_id': message_id,
                    'user_id': self.user.id,
                }
            )
        except Exception as e:
            print(f"Error handling read receipt: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message_id': event['message_id'],
            'message': event['message'],
            'user': event['user'],
            'timestamp': event['timestamp'],
        }))

    async def typing_indicator(self, event):
        if event.get('sender_channel') != self.channel_name:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user': event['user'],
                'is_typing': event['is_typing'],
            }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user': event['user'],
            'status': event['status'],
        }))

    async def read_receipt(self, event):
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
        }))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message
        }))

    @database_sync_to_async
    def get_user(self, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_user_data(self, user):
        from .serializers import UserListSerializer
        return UserListSerializer(user).data

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        from .models import Conversation
        try:
            return Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def verify_participant(self, user_id, conversation_id):
        from .models import Conversation
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            return conversation.participants.filter(id=user_id).exists()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, conversation, user, content):
        from .models import Message
        return Message.objects.create(
            conversation=conversation,
            sender=user,
            content=content
        )

    @database_sync_to_async
    def mark_message_read(self, message_id, user_id):
        from .models import Message
        try:
            message = Message.objects.get(id=message_id)
            if message.sender.id != user_id:
                message.is_read = True
                message.save(update_fields=['is_read'])
            return True
        except Message.DoesNotExist:
            return False