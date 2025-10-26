from datetime import timedelta
from pathlib import Path
import os
from decouple import config 
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "unsafe-dev-secret-key")

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,51.20.254.52").split(',')

INSTALLED_APPS = ['channels','daphne','django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'account.apps.AccountConfig', 'rest_framework', 'rest_framework_simplejwt', 'rest_framework_simplejwt.token_blacklist', 'corsheaders', 'drf_spectacular','chat.apps.ChatConfig','personal.apps.PersonalConfig']

MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'corsheaders.middleware.CorsMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']

ROOT_URLCONF = 'auth.urls'

TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.debug', 'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]

WSGI_APPLICATION = 'auth.wsgi.application'

ASGI_APPLICATION = 'auth.asgi.application'

REDIS_HOST = config('REDIS_HOST', default='127.0.0.1')
REDIS_PORT = config('REDIS_PORT', default=6379, cast=int)

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    DATABASES = {'default': dj_database_url.parse(database_url, conn_max_age=600, ssl_require=True)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}

REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',), 'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema', 'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer', 'rest_framework.renderers.BrowsableAPIRenderer']}

SPECTACULAR_SETTINGS = {'TITLE': 'TripSync API', 'DESCRIPTION': 'TripSync - API Documentation', 'VERSION': '1.0.0', 'SERVE_INCLUDE_SCHEMA': False, 'CONTACT': {'name': 'TripSync Support', 'email': 'support@tripsync.com'}, 'LICENSE': {'name': 'MIT License'}, 'TAGS': [{'name': 'Authentication', 'description': 'User registration, login and token management'}, {'name': 'Password Reset', 'description': 'Password reset functionality with OTP'}], 'SERVERS': [{'url': 'http://127.0.0.1:8000', 'description': 'Development server'}, {'url': 'https://tripsync-backend-ruak.onrender.com', 'description': 'Production server'}], 'COMPONENT_SPLIT_REQUEST': True, 'SWAGGER_UI_SETTINGS': {'deepLinking': True, 'persistAuthorization': True, 'displayOperationId': False, 'filter': True}}

AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'account.User'

SIMPLE_JWT = {'ACCESS_TOKEN_LIFETIME': timedelta(hours=1), 'REFRESH_TOKEN_LIFETIME': timedelta(days=7), 'ROTATE_REFRESH_TOKENS': True, 'BLACKLIST_AFTER_ROTATION': True, 'UPDATE_LAST_LOGIN': True, 'ALGORITHM': 'HS256', 'SIGNING_KEY': SECRET_KEY, 'AUTH_HEADER_TYPES': ('Bearer',), 'USER_ID_FIELD': 'id', 'USER_ID_CLAIM': 'user_id', 'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',), 'TOKEN_TYPE_CLAIM': 'token_type'}

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:5173').split(',')

CORS_ALLOW_ALL_ORIGINS = DEBUG  
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']

CORS_ALLOW_HEADERS = ['accept', 'accept-encoding', 'authorization', 'content-type', 'dnt', 'origin', 'user-agent', 'x-csrftoken', 'x-requested-with']

if not DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

SENDGRID_API_KEY = config('SENDGRID_API_KEY', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='TripSync <noreply@example.com>')
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = config('SENDGRID_API_KEY', default='')
EMAIL_TIMEOUT = 10

ADMIN_SITE_HEADER = "TripSync Administration"
ADMIN_SITE_TITLE = "TripSync Admin"
ADMIN_INDEX_TITLE = "Welcome to TripSync Admin Portal"

OTP_EXPIRY_MINUTES = 10
MAX_OTP_ATTEMPTS = 5
OTP_LOCKOUT_HOURS = 1

LOGGING = {'version': 1, 'disable_existing_loggers': False, 'formatters': {'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'}}, 'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'}}, 'root': {'handlers': ['console'], 'level': 'INFO'}, 'loggers': {'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False}, 'account': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False}}}