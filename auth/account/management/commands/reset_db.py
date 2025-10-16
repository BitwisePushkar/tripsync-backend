from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Reset database tables for fresh migration'

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            try:
                cursor.execute("DROP TABLE IF EXISTS account_user CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS django_migrations CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS django_admin_log CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS auth_permission CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS django_content_type CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS auth_group CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS auth_group_permissions CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS django_session CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS token_blacklist_blacklistedtoken CASCADE;")
                cursor.execute("DROP TABLE IF EXISTS token_blacklist_outstandingtoken CASCADE;")
                self.stdout.write(self.style.SUCCESS('Successfully dropped all tables'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error dropping tables: {e}'))