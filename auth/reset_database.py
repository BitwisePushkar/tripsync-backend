import os
import sys
import psycopg2

database_url = os.environ.get('DATABASE_URL', '')

if database_url:
    try:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Dropping existing tables...")
        
        tables = [
            'account_user',
            'django_migrations',
            'django_admin_log',
            'auth_permission',
            'django_content_type',
            'auth_group',
            'auth_group_permissions',
            'django_session',
            'token_blacklist_blacklistedtoken',
            'token_blacklist_outstandingtoken'
        ]
        
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f"Dropped {table}")
            except Exception as e:
                print(f"Could not drop {table}: {e}")
        
        cursor.close()
        conn.close()
        print("Database reset complete!")
        
    except Exception as e:
        print(f"Error resetting database: {e}")
        sys.exit(1)
else:
    print("No DATABASE_URL found, skipping reset")