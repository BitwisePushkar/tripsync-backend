import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth.settings')

django.setup()

<<<<<<< HEAD
import chat.routing

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket':AuthMiddlewareStack(
        URLRouter(chat.routing.websocket_urlpatterns)
    ),
})
=======
>>>>>>> main
