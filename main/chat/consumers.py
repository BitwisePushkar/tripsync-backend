from asgiref.sync import sync_to_async
import json 
import jwt 
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Message
from .models import Conversation
from .serializers import UserListSerializer
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f"WebSocket connection attempt from {self.scope.get('client')}")
        query_string = self.scope['query_string'].decode('utf-8')
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]
        if not token:
            logger.warning("Connection rejected: No token provided")
            await self.close(code=4002)
            return
        try:
            decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            self.user = await self.get_user(decoded_data['user_id'])
            if not self.user:
                logger.warning(f"Connection rejected: User {decoded_data['user_id']} not found")
                await self.close(code=4003)
                return
            self.scope['user'] = self.user
            logger.info(f"User authenticated: {self.user.email}")
            
        except jwt.ExpiredSignatureError:
            logger.warning("Connection rejected: Token expired")
            await self.close(code=4000)
            return
        except jwt.InvalidTokenError as e:
            logger.warning(f"Connection rejected: Invalid token - {str(e)}")
            await self.close(code=4001)
            return
        except Exception as e:
            logger.error(f"Authentication error: {e}", exc_info=True)
            await self.close(code=4003)
            return
        
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        
        is_participant = await self.verify_participant(self.user.id, self.conversation_id)
        if not is_participant:
            logger.warning(
                f"Connection rejected: User {self.user.email} not participant "
                f"in conversation {self.conversation_id}"
            )
            await self.close(code=4004)
            return
        self.room_group_name = f'chat_{self.conversation_id}'
        
        try:
            await self.channel_layer.group_add(self.room_group_name,self.channel_name)
            logger.info(
                f"User {self.user.email} joined room {self.room_group_name} "
                f"with channel {self.channel_name}"
            )
        except Exception as e:
            logger.error(f"Failed to join channel layer group: {e}", exc_info=True)
            await self.close(code=4005)
            return
        
        await self.accept()
        logger.info(f"WebSocket connection accepted for user {self.user.email}")
        try:
            user_data = await self.get_user_data(self.user)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user': user_data,
                    'status': 'online',
                }
            )
        except Exception as e:
            logger.error(f"Failed to broadcast online status: {e}", exc_info=True)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            logger.debug(f"Received {event_type} from {self.user.email}: {text_data[:100]}")

            if event_type == 'chat_message':
                await self.handle_chat_message(data)
            
            elif event_type == 'typing':
                await self.handle_typing_indicator(data)
            
            elif event_type == 'read_receipt':
                await self.handle_read_receipt(data)
            
            else:
                logger.warning(f"Unknown event type: {event_type}")
                await self.send_error("Unknown event type")
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            await self.send_error("Invalid JSON")
        except Exception as e:
            logger.error(f"Error in receive: {e}", exc_info=True)
            await self.send_error("Internal error")

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnecting with code {close_code}")
        
        if hasattr(self, 'room_group_name') and hasattr(self, 'user'):
            try:
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
                logger.info(f"User {self.user.email} left room {self.room_group_name}")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}", exc_info=True)

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
            logger.info(f"Message {message.id} sent by {self.user.email}")
            
        except Exception as e:
            logger.error(f"Error handling chat message: {e}", exc_info=True)
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
            logger.error(f"Error handling typing indicator: {e}", exc_info=True)

    async def handle_read_receipt(self, data):
        message_id = data.get('message_id')
        
        if not message_id:
            return
        
        try:
            success = await self.mark_message_read(message_id, self.user.id)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'read_receipt',
                        'message_id': message_id,
                        'user_id': self.user.id,
                    }
                )
        except Exception as e:
            logger.error(f"Error handling read receipt: {e}", exc_info=True)

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
        User = get_user_model()
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_user_data(self, user):
        return UserListSerializer(user).data

    @database_sync_to_async
    def get_conversation(self, conversation_id):
        try:
            return Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def verify_participant(self, user_id, conversation_id):
        try:
            conversation = Conversation.objects.get(id=conversation_id)
            return conversation.participants.filter(id=user_id).exists()
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, conversation, user, content):
        return Message.objects.create(
            conversation=conversation,
            sender=user,
            content=content
        )

    @database_sync_to_async
    def mark_message_read(self, message_id, user_id):
        try:
            message = Message.objects.get(id=message_id)
            if message.sender.id != user_id:
                message.is_read = True
                message.save()
            return True
        except Message.DoesNotExist:
            logger.warning(f"Message {message_id} not found for read receipt")
            return False