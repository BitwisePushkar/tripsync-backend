import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger("account")

class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, identifier: str = None, password: str = None, **kwargs):
        if not identifier or not password:
            return None
        identifier = identifier.strip().lower()
        try:
            if "@" in identifier:
                user = User.objects.get(email=identifier)
            else:
                user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            User().set_password(password)
            logger.debug("Auth attempt for unknown identifier: %s", identifier)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            logger.debug("Authenticated user: %s", user.email)
            return user
        return None

    def get_user(self, user_id: int):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None