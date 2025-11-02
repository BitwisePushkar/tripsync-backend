from django.apps import AppConfig

class TripmateConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tripmate'
    
    def ready(self):
        import tripmate.signals