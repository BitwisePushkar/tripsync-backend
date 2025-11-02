import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

django.setup()

import tripmate.routing
import chat.routing

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            tripmate.routing.websocket_urlpatterns +
            chat.routing.websocket_urlpatterns
        )
    ),
})