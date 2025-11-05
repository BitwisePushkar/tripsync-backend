import json
import secrets
import hashlib
import logging
from typing import Literal, Optional
import redis
from django.conf import settings

logger = logging.getLogger("account")

_redis_client: Optional[redis.Redis] = None

def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_OTP_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client

def _key_otp(email: str) -> str:
    return f"ts:otp:{email}"

def _key_lock(email: str) -> str:
    return f"ts:otp_lock:{email}"

def _key_cooldown(email: str) -> str:
    return f"ts:otp_cooldown:{email}"

def _key_unreg(email: str) -> str:
    return f"ts:unreg:{email}"

def _key_reset_token(email: str) -> str:
    return f"ts:reset_token:{email}"

def _key_login_lock(email: str) -> str:
    return f"ts:login_lock:{email}"

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

def _generate_otp_code() -> str:
    return str(secrets.randbelow(900000) + 100000)

def _generate_reset_token() -> str:
    return secrets.token_urlsafe(48)

def generate_and_store_otp(email: str, otp_type: Literal["registration", "password_reset"],) -> str:
    r = get_redis()
    otp_code = _generate_otp_code()
    otp_hash = _hash(otp_code)
    existing_raw = r.get(_key_otp(email))
    if existing_raw:
        existing = json.loads(existing_raw)
        resend_count = existing.get("resend_count", 0) + 1
        is_resend = True
    else:
        resend_count = 0
        is_resend = False
    payload = json.dumps({
        "hash": otp_hash,
        "type": otp_type,
        "attempts": 0,
        "resend_count": resend_count,
    })
    expiry_seconds = settings.OTP_EXPIRY_MINUTES * 60
    r.setex(_key_otp(email), expiry_seconds, payload)
    if is_resend:
        r.setex(_key_cooldown(email), settings.OTP_RESEND_COOLDOWN_SECONDS, "1",)
    logger.info(
        "OTP generated for %s (type=%s, resend_count=%d, is_resend=%s)",
        email, otp_type, resend_count, is_resend,
    )
    return otp_code

def verify_otp(email: str, otp_code: str, otp_type: Literal["registration", "password_reset"],) -> tuple[bool, str, int]:
    r = get_redis()
    max_attempts = settings.OTP_MAX_VERIFY_ATTEMPTS
    lock_minutes = settings.OTP_LOCK_DURATION_MINUTES
    lock_ttl = r.ttl(_key_lock(email))
    if lock_ttl > 0:
        minutes_remaining = max(1, lock_ttl // 60)
        return False, f"Account locked. Try again in {minutes_remaining} minute(s).", -1
    raw = r.get(_key_otp(email))
    if not raw:
        return False, "OTP expired or not found. Please request a new one.", 0
    payload = json.loads(raw)
    if payload["type"] != otp_type:
        return False, "Invalid OTP for this operation.", 0
    if payload["hash"] == _hash(otp_code):
        r.delete(_key_otp(email))
        r.delete(_key_cooldown(email))
        logger.info("OTP verified successfully for %s", email)
        return True, "OTP verified successfully.", max_attempts
    payload["attempts"] += 1
    attempts_used = payload["attempts"]
    attempts_remaining = max_attempts - attempts_used
    if attempts_used >= max_attempts:
        r.setex(_key_lock(email), lock_minutes * 60, "1")
        r.delete(_key_otp(email))
        logger.warning("OTP lock triggered for %s after %d attempts", email, attempts_used)
        return (False, f"Too many failed attempts. Account locked for {lock_minutes} minute(s).", -1,)
    remaining_ttl = r.ttl(_key_otp(email))
    if remaining_ttl > 0:
        r.setex(_key_otp(email), remaining_ttl, json.dumps(payload))
    logger.warning("Wrong OTP for %s — %d attempt(s) remaining", email, attempts_remaining)
    return False, f"Invalid OTP. {attempts_remaining} attempt(s) remaining.", attempts_remaining

def check_resend_eligibility(email: str) -> tuple[bool, str]:
    r = get_redis()
    lock_ttl = r.ttl(_key_lock(email))
    if lock_ttl > 0:
        minutes_remaining = max(1, lock_ttl // 60)
        return False, f"Account locked. Try again in {minutes_remaining} minute(s)."
    raw = r.get(_key_otp(email))
    current_resend_count = 0
    if raw:
        payload = json.loads(raw)
        current_resend_count = payload.get("resend_count", 0)
        if current_resend_count >= settings.OTP_MAX_RESEND_ATTEMPTS:
            r.setex(_key_lock(email), settings.OTP_LOCK_DURATION_MINUTES * 60, "1")
            logger.warning("Resend limit reached for %s — account locked", email)
            return (
                False,
                f"Maximum OTP resends exceeded. Account locked for "
                f"{settings.OTP_LOCK_DURATION_MINUTES} minute(s).",
            )
    if current_resend_count >= 1:
        cooldown_ttl = r.ttl(_key_cooldown(email))
        if cooldown_ttl > 0:
            return False, f"Please wait {cooldown_ttl} second(s) before requesting another OTP."
    return True, ""

def store_unverified_user(email: str, username: str, password: str) -> None:
    r = get_redis()
    payload = json.dumps({"email": email, "username": username, "password": password})
    ttl = (settings.OTP_EXPIRY_MINUTES + 5) * 60
    r.setex(_key_unreg(email), ttl, payload)
    logger.debug("Unverified user stored in Redis for %s", email)

def get_unverified_user(email: str) -> Optional[dict]:
    r = get_redis()
    raw = r.get(_key_unreg(email))
    return json.loads(raw) if raw else None

def delete_unverified_user(email: str) -> None:
    r = get_redis()
    r.delete(_key_unreg(email))

def store_reset_token(email: str) -> str:
    r = get_redis()
    token = _generate_reset_token()
    ttl = settings.RESET_TOKEN_EXPIRY_MINUTES * 60
    r.setex(_key_reset_token(email), ttl, _hash(token))
    logger.info("Reset token generated for %s", email)
    return token

def verify_and_consume_reset_token(email: str, token: str) -> bool:
    r = get_redis()
    stored_hash = r.get(_key_reset_token(email))
    if not stored_hash:
        return False
    if stored_hash != _hash(token):
        return False
    r.delete(_key_reset_token(email))
    logger.info("Reset token consumed for %s", email)
    return True

def record_failed_login(identifier: str) -> tuple[bool, int]:
    r = get_redis()
    key = _key_login_lock(identifier)
    max_attempts = settings.LOGIN_MAX_ATTEMPTS
    lock_duration = settings.LOGIN_LOCK_DURATION_MINUTES * 60
    attempts = r.incr(key)
    if attempts == 1:
        r.expire(key, lock_duration)
    if attempts >= max_attempts:
        r.expire(key, lock_duration)
        logger.warning("Login lock triggered for %s", identifier)
        return True, 0
    return False, max_attempts - attempts

def check_login_lock(identifier: str) -> tuple[bool, int]:
    r = get_redis()
    key = _key_login_lock(identifier)
    ttl = r.ttl(key)
    if ttl <= 0:
        return False, 0
    attempts = r.get(key)
    if attempts and int(attempts) >= settings.LOGIN_MAX_ATTEMPTS:
        return True, max(1, ttl // 60)
    return False, 0

def clear_login_lock(identifier: str) -> None:
    get_redis().delete(_key_login_lock(identifier))

def clear_all_otp_keys(email: str) -> None:
    r = get_redis()
    r.delete(
        _key_otp(email),
        _key_lock(email),
        _key_cooldown(email),
        _key_unreg(email),
    )
    logger.debug("All OTP keys cleared for %s", email)