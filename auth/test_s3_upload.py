import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'auth.settings')
django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

print("=" * 50)
print("S3 Configuration Test")
print("=" * 50)

print(f"USE_S3: {getattr(settings, 'USE_S3', 'NOT SET')}")
print(f"DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"AWS_STORAGE_BUCKET_NAME: {getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'NOT SET')}")
print(f"AWS_S3_REGION_NAME: {getattr(settings, 'AWS_S3_REGION_NAME', 'NOT SET')}")
print(f"AWS_ACCESS_KEY_ID: {getattr(settings, 'AWS_ACCESS_KEY_ID', 'NOT SET')[:10]}...")
print(f"MEDIA_URL: {settings.MEDIA_URL}")

print("\n" + "=" * 50)
print("Testing File Upload to S3")
print("=" * 50)

try:
    # Try to save a test file
    test_content = ContentFile(b'This is a test file')
    file_name = 'test_upload.txt'
    path = default_storage.save(f'media/test/{file_name}', test_content)
    
    print(f"✅ File saved successfully!")
    print(f"Path: {path}")
    print(f"URL: {default_storage.url(path)}")
    print(f"Storage class: {type(default_storage)}")
    
    # Check if file exists
    if default_storage.exists(path):
        print(f"✅ File exists in storage")
    
    # Delete test file
    default_storage.delete(path)
    print(f"✅ Test file deleted")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()