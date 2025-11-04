import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from django.conf import settings

logger = logging.getLogger("personal")

_s3_client = None

def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=settings.AWS_S3_REGION_NAME,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    return _s3_client

def upload_image_to_s3(file_obj, upload_path: str, media_type: str = "img") -> tuple[bool, str]:
    if media_type == "vid":
        allowed_extensions = ["mp4", "mov", "avi", "mkv", "webm"]
        content_type_map = {
            "mp4": "video/mp4",
            "mov": "video/quicktime",
            "avi": "video/x-msvideo",
            "mkv": "video/x-matroska",
            "webm": "video/webm",
        }
        max_bytes = 100 * 1024 * 1024
        limit_msg = "100MB"
    else:
        allowed_extensions = ["jpg", "jpeg", "png", "webp"]
        content_type_map = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }
        max_bytes = 5 * 1024 * 1024
        limit_msg = "5MB"

    file_size = file_obj.size if hasattr(file_obj, "size") else len(file_obj.read())
    if file_size > max_bytes:
        return False, f"File size exceeds the {limit_msg} limit."

    file_name = getattr(file_obj, "name", "") or ""
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if ext not in allowed_extensions:
        return False, f"Unsupported format. Allowed: {', '.join(allowed_extensions)}."
    content_type = content_type_map.get(ext, "image/jpeg" if media_type == "img" else "video/mp4")

    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    file_bytes = file_obj.read()
    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)

    if not bucket_name:
        logger.error("AWS_STORAGE_BUCKET_NAME not configured")
        return False, "S3 storage is not configured on this server."
    
    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=bucket_name,
            Key=upload_path,
            Body=file_bytes,
            ContentType=content_type,
            ContentDisposition="inline",
            CacheControl="max-age=86400",
        )
        region = settings.AWS_S3_REGION_NAME
        s3_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{upload_path}"
        logger.info("Image uploaded to S3: %s", upload_path)
        return True, s3_url

    except ClientError as e:
        error_msg = e.response["Error"]["Message"]
        logger.error("S3 ClientError uploading %s: %s", upload_path, error_msg)
        return False, f"S3 upload failed: {error_msg}"

    except BotoCoreError as e:
        logger.error("S3 BotoCoreError uploading %s: %s", upload_path, str(e))
        return False, "S3 connection error. Please try again."

    except Exception as e:
        logger.error("Unexpected S3 upload error for %s: %s", upload_path, str(e))
        return False, "Failed to upload image. Please try again later."

def delete_image_from_s3(upload_path: str) -> tuple[bool, str]:
    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    if not bucket_name:
        return False, "S3 storage is not configured."

    if not upload_path:
        return False, "No upload path provided."

    try:
        client = _get_s3_client()
        client.delete_object(Bucket=bucket_name, Key=upload_path)
        logger.info("Deleted S3 object: %s", upload_path)
        return True, f"Deleted {upload_path}"

    except ClientError as e:
        error_msg = e.response["Error"]["Message"]
        logger.error("S3 delete error for %s: %s", upload_path, error_msg)
        return False, f"S3 delete failed: {error_msg}"

    except Exception as e:
        logger.error("Unexpected S3 delete error for %s: %s", upload_path, str(e))
        return False, "Failed to delete file from S3."


def extract_s3_key_from_url(s3_url: str) -> str:
    if not s3_url:
        return ""
    
    try:
        parts = s3_url.split(".amazonaws.com/", 1)
        return parts[1] if len(parts) == 2 else ""
    except Exception:
        return ""