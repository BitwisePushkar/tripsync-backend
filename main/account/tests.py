import json
import fakeredis
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from account.views import _get_tokens_for_user
from django.test import override_settings
from account import otp_service

User = get_user_model()

VALID_EMAIL = "testuser@example.com"
VALID_USERNAME = "testuser1"
VALID_PASSWORD = "StrongPass@123"

VALID_REGISTER_PAYLOAD = {
    "email": VALID_EMAIL,
    "username": VALID_USERNAME,
    "password": VALID_PASSWORD,
    "password2": VALID_PASSWORD,
}

class BaseAccountTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.fake_redis = fakeredis.FakeRedis(decode_responses=True)
        self._redis_patcher = patch.object(
            otp_service,
            "get_redis",
            return_value=self.fake_redis,
        )
        self._redis_patcher.start()
        otp_service._redis_client = None
        self._otp_task_patcher = patch("account.views.send_otp_email_task")
        self._welcome_task_patcher = patch("account.views.send_welcome_email_task")
        self.mock_otp_task = self._otp_task_patcher.start()
        self.mock_welcome_task = self._welcome_task_patcher.start()
        self._throttle_patcher = patch("rest_framework.views.APIView.get_throttles",return_value=[],)
        self._throttle_patcher.start()
        self._settings_override = override_settings(
            REST_FRAMEWORK={
                "DEFAULT_THROTTLE_CLASSES": [],
                "DEFAULT_THROTTLE_RATES": {},
            },RATELIMIT_ENABLE=False,
        )
        self._settings_override.enable()


    def tearDown(self):
        self._redis_patcher.stop()
        self._otp_task_patcher.stop()
        self._welcome_task_patcher.stop()
        self.fake_redis.flushall()
        self._throttle_patcher.stop()
        self._settings_override.disable()

    def _create_verified_user(self, email=VALID_EMAIL, username=VALID_USERNAME, password=VALID_PASSWORD,) -> User:
        user = User.objects.create_user(
            email=email,
            username=username,
            password=password,
        )
        user.is_email_verified = True
        user.save()
        return user

    def _get_tokens_for_user(self, user) -> dict:
        return _get_tokens_for_user(user)

    def _post(self, url_name, data):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(data),
            content_type="application/json",
        )

    def _post_authed(self, url_name, data, access_token):
        return self.client.post(
            reverse(url_name),
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
    
    def _data(self, response):
        data = response.json()
        if "errors" in data:
            errors = data["errors"]
        else:
            errors = data
        return {
            "status": response.status_code,
            "data": data,
            "errors": errors,
            "message": data.get("message", ""),
        }

class RegistrationTests(BaseAccountTestCase):

    def test_register_success(self):
        response = self._post("account:register", VALID_REGISTER_PAYLOAD)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["email"], VALID_EMAIL)
        self.mock_otp_task.delay.assert_called_once()
        pending = otp_service.get_unverified_user(VALID_EMAIL)
        self.assertIsNotNone(pending)
        self.assertEqual(pending["username"], VALID_USERNAME)

    def test_register_does_not_write_to_db(self):
        self._post("account:register", VALID_REGISTER_PAYLOAD)
        self.assertFalse(User.objects.filter(email=VALID_EMAIL).exists())

    def test_register_duplicate_verified_email(self):
        self._create_verified_user()
        response = self._post("account:register", VALID_REGISTER_PAYLOAD)
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json().get("errors", response.json()))

    def test_register_duplicate_username(self):
        self._create_verified_user()
        payload = {**VALID_REGISTER_PAYLOAD, "email": "other@example.com"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json().get("errors", response.json()))

    def test_register_passwords_dont_match(self):
        payload = {**VALID_REGISTER_PAYLOAD, "password2": "Different@999"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("password2", response.json().get("errors", response.json()))

    def test_register_weak_password_no_uppercase(self):
        payload = {**VALID_REGISTER_PAYLOAD, "password": "weakpass@1", "password2": "weakpass@1"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)

    def test_register_weak_password_no_special_char(self):
        payload = {**VALID_REGISTER_PAYLOAD, "password": "WeakPass123", "password2": "WeakPass123"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)

    def test_register_weak_password_too_short(self):
        payload = {**VALID_REGISTER_PAYLOAD, "password": "Ab@1", "password2": "Ab@1"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)

    def test_register_invalid_email(self):
        payload = {**VALID_REGISTER_PAYLOAD, "email": "notanemail"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json().get("errors", response.json()))

    def test_register_username_too_short(self):
        payload = {**VALID_REGISTER_PAYLOAD, "username": "ab"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json().get("errors", response.json()))

    def test_register_username_too_long(self):
        payload = {**VALID_REGISTER_PAYLOAD, "username": "a" * 16}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json().get("errors", response.json()))

    def test_register_username_all_numeric(self):
        payload = {**VALID_REGISTER_PAYLOAD, "username": "12345"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json().get("errors", response.json()))

    def test_register_username_invalid_chars(self):
        payload = {**VALID_REGISTER_PAYLOAD, "username": "hello world"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json().get("errors", response.json()))

    def test_register_username_allows_special_chars(self):
        payload = {**VALID_REGISTER_PAYLOAD, "username": "trip@#er"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 200)

    def test_register_email_normalised_to_lowercase(self):
        payload = {**VALID_REGISTER_PAYLOAD, "email": "TESTUSER@EXAMPLE.COM"}
        response = self._post("account:register", payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["email"], "testuser@example.com")

    def test_register_resend_cooldown(self):
        self._post("account:register", VALID_REGISTER_PAYLOAD)
        response = self._post("account:register", VALID_REGISTER_PAYLOAD)
        self.assertEqual(response.status_code, 429)
        self.assertIn("wait", response.json()["message"].lower())

    def test_register_missing_required_fields(self):
        response = self._post("account:register", {})
        self.assertEqual(response.status_code, 400)

class OTPVerificationTests(BaseAccountTestCase):
    def setUp(self):
        super().setUp()
        otp_service.store_unverified_user(VALID_EMAIL, VALID_USERNAME, VALID_PASSWORD)

    def test_verify_otp_success(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(True, "OTP verified successfully.", 5),
        ):
            response = self._post(
                "account:verify-otp",
                {"email": VALID_EMAIL, "otp": "123456"},
            )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("tokens", data["data"])
        self.assertIn("access", data["data"]["tokens"])
        self.assertIn("refresh", data["data"]["tokens"])
        user = User.objects.get(email=VALID_EMAIL)
        self.assertTrue(user.is_email_verified)

    def test_verify_otp_fires_welcome_email(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(True, "OTP verified successfully.", 5),
        ):
            self._post("account:verify-otp", {"email": VALID_EMAIL, "otp": "123456"})
        self.mock_welcome_task.delay.assert_called_once()

    def test_verify_otp_clears_redis_on_success(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(True, "OTP verified successfully.", 5),
        ):
            self._post("account:verify-otp", {"email": VALID_EMAIL, "otp": "123456"})
        self.assertIsNone(otp_service.get_unverified_user(VALID_EMAIL))

    def test_verify_otp_creates_correct_user(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(True, "OTP verified successfully.", 5),
        ):
            self._post("account:verify-otp", {"email": VALID_EMAIL, "otp": "123456"})
        user = User.objects.get(email=VALID_EMAIL)
        self.assertEqual(user.username, VALID_USERNAME)
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

    def test_verify_otp_wrong_code(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(False, "Invalid OTP. 4 attempt(s) remaining.", 4),
        ):
            response = self._post(
                "account:verify-otp",
                {"email": VALID_EMAIL, "otp": "000000"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["attempts_remaining"], 4)

    def test_verify_otp_locks_after_max_attempts(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(False, "Too many failed attempts. Account locked for 60 minute(s).", -1),
        ):
            response = self._post(
                "account:verify-otp",
                {"email": VALID_EMAIL, "otp": "000000"},
            )
        self.assertEqual(response.status_code, 429)

    def test_verify_otp_non_numeric(self):
        response = self._post(
            "account:verify-otp",
            {"email": VALID_EMAIL, "otp": "abcdef"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("otp", response.json().get("errors", response.json()))

    def test_verify_otp_wrong_length(self):
        response = self._post(
            "account:verify-otp",
            {"email": VALID_EMAIL, "otp": "1234"},
        )
        self.assertEqual(response.status_code, 400)

    def test_verify_otp_expired(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(False, "OTP expired or not found. Please request a new one.", 0),
        ):
            response = self._post(
                "account:verify-otp",
                {"email": VALID_EMAIL, "otp": "123456"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["message"].lower())

    def test_verify_otp_type_mismatch(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(False, "Invalid OTP for this operation.", 0),
        ):
            response = self._post(
                "account:verify-otp",
                {"email": VALID_EMAIL, "otp": "123456"},
            )
        self.assertEqual(response.status_code, 400)

    def test_verify_otp_session_expired_in_redis(self):
        self.fake_redis.delete(f"ts:unreg:{VALID_EMAIL}")
        with patch.object(
            otp_service, "verify_otp",
            return_value=(True, "OTP verified successfully.", 5),
        ):
            response = self._post(
                "account:verify-otp",
                {"email": VALID_EMAIL, "otp": "123456"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["message"].lower())

    def test_verify_otp_race_condition_email_taken(self):
        self._create_verified_user()
        with patch.object(
            otp_service, "verify_otp",
            return_value=(True, "OTP verified successfully.", 5),
        ):
            response = self._post(
                "account:verify-otp",
                {"email": VALID_EMAIL, "otp": "123456"},
            )
        self.assertEqual(response.status_code, 409)

    def test_verify_otp_missing_email(self):
        response = self._post("account:verify-otp", {"otp": "123456"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json().get("errors", response.json()))

class ResendOTPTests(BaseAccountTestCase):
    def test_resend_success_registration(self):
        otp_service.store_unverified_user(VALID_EMAIL, VALID_USERNAME, VALID_PASSWORD)
        with patch.object(
            otp_service, "check_resend_eligibility", return_value=(True, "")
        ):
            response = self._post("account:resend-otp", {"email": VALID_EMAIL})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["otp_type"], "registration")
        self.mock_otp_task.delay.assert_called_once()

    def test_resend_success_password_reset(self):
        self._create_verified_user()
        with patch.object(
            otp_service, "check_resend_eligibility", return_value=(True, "")
        ):
            response = self._post("account:resend-otp", {"email": VALID_EMAIL})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["otp_type"], "password_reset")

    def test_resend_cooldown_active(self):
        otp_service.store_unverified_user(VALID_EMAIL, VALID_USERNAME, VALID_PASSWORD)
        with patch.object(
            otp_service, "check_resend_eligibility",
            return_value=(False, "Please wait 95 second(s) before requesting another OTP."),
        ):
            response = self._post("account:resend-otp", {"email": VALID_EMAIL})
        self.assertEqual(response.status_code, 429)
        self.assertIn("wait", response.json()["message"].lower())

    def test_resend_max_exceeded_locks(self):
        otp_service.store_unverified_user(VALID_EMAIL, VALID_USERNAME, VALID_PASSWORD)
        with patch.object(
            otp_service, "check_resend_eligibility",
            return_value=(False, "Maximum OTP resends exceeded. Account locked for 60 minute(s)."),
        ):
            response = self._post("account:resend-otp", {"email": VALID_EMAIL})
        self.assertEqual(response.status_code, 429)

    def test_resend_unknown_email(self):
        response = self._post("account:resend-otp", {"email": "nobody@example.com"})
        self.assertEqual(response.status_code, 400)

    def test_resend_missing_email(self):
        response = self._post("account:resend-otp", {})
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json().get("errors", response.json()))

    def test_resend_invalid_email_format(self):
        response = self._post("account:resend-otp", {"email": "notvalid"})
        self.assertEqual(response.status_code, 400)

class LoginTests(BaseAccountTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_verified_user()

    def test_login_with_email(self):
        response = self._post(
            "account:login",
            {"identifier": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("access", data["data"]["tokens"])
        self.assertIn("refresh", data["data"]["tokens"])

    def test_login_with_username(self):
        response = self._post(
            "account:login",
            {"identifier": VALID_USERNAME, "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)

    def test_login_email_case_insensitive(self):
        response = self._post(
            "account:login",
            {"identifier": VALID_EMAIL.upper(), "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)

    def test_login_username_case_insensitive(self):
        response = self._post(
            "account:login",
            {"identifier": VALID_USERNAME.upper(), "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 200)

    def test_login_returns_correct_user_data(self):
        response = self._post(
            "account:login",
            {"identifier": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        user_data = response.json()["data"]["user"]
        self.assertEqual(user_data["email"], VALID_EMAIL)
        self.assertEqual(user_data["username"], VALID_USERNAME)
        self.assertIn("id", user_data)

    def test_login_wrong_password(self):
        response = self._post(
            "account:login",
            {"identifier": VALID_EMAIL, "password": "WrongPass@999"},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_locks_after_max_attempts(self):
        with patch.object(
            otp_service, "record_failed_login", return_value=(True, 0)
        ):
            response = self._post(
                "account:login",
                {"identifier": VALID_EMAIL, "password": "WrongPass@999"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertIn("locked", response.json()["message"].lower())

    def test_login_locked_account(self):
        with patch.object(
            otp_service, "check_login_lock", return_value=(True, 45)
        ):
            response = self._post(
                "account:login",
                {"identifier": VALID_EMAIL, "password": VALID_PASSWORD},
            )
        self.assertEqual(response.status_code, 429)
        self.assertIn("45", response.json()["message"])

    def test_login_unverified_account(self):
        unverified = User.objects.create_user(
            email="unverified@example.com",
            username="unverif1",
            password=VALID_PASSWORD,
        )
        response = self._post(
            "account:login",
            {"identifier": "unverified@example.com", "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("verified", response.json()["message"].lower())

    def test_login_deactivated_account(self):
        self.user.is_active = False
        self.user.save()
        response = self._post(
            "account:login",
            {"identifier": VALID_EMAIL, "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("deactivated", response.json()["message"].lower())

    def test_login_unknown_email(self):
        response = self._post(
            "account:login",
            {"identifier": "ghost@example.com", "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("not found", response.json()["message"].lower())

    def test_login_unknown_username(self):
        response = self._post(
            "account:login",
            {"identifier": "ghostuser", "password": VALID_PASSWORD},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_clears_lock_on_success(self):
        with patch.object(otp_service, "clear_login_lock") as mock_clear:
            self._post(
                "account:login",
                {"identifier": VALID_EMAIL, "password": VALID_PASSWORD},
            )
        mock_clear.assert_called_once()

    def test_login_missing_fields(self):
        response = self._post("account:login", {"identifier": VALID_EMAIL})
        self.assertEqual(response.status_code, 400)

class LogoutTests(BaseAccountTestCase):
    def setUp(self):
        super().setUp()
        self.user   = self._create_verified_user()
        self.tokens = self._get_tokens_for_user(self.user)

    def test_logout_success(self):
        response = self._post_authed(
            "account:logout",
            {"refresh": self.tokens["refresh"]},
            self.tokens["access"],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_logout_missing_refresh_token(self):
        response = self._post_authed(
            "account:logout", {}, self.tokens["access"]
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("refresh", response.json().get("errors", response.json()))

    def test_logout_invalid_refresh_token(self):
        response = self._post_authed(
            "account:logout",
            {"refresh": "not.a.valid.token"},
            self.tokens["access"],
        )
        self.assertEqual(response.status_code, 400)

    def test_logout_already_blacklisted(self):
        self._post_authed(
            "account:logout",
            {"refresh": self.tokens["refresh"]},
            self.tokens["access"],
        )
        response = self._post_authed(
            "account:logout",
            {"refresh": self.tokens["refresh"]},
            self.tokens["access"],
        )
        self.assertEqual(response.status_code, 400)

    def test_logout_no_auth_header(self):
        response = self._post(
            "account:logout", {"refresh": self.tokens["refresh"]}
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_invalid_access_token(self):
        response = self._post_authed(
            "account:logout",
            {"refresh": self.tokens["refresh"]},
            "invalid.access.token",
        )
        self.assertEqual(response.status_code, 401)

class PasswordResetRequestTests(BaseAccountTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_verified_user()

    def test_reset_request_known_email(self):
        with patch.object(otp_service, "check_resend_eligibility", return_value=(True, "")):
            with patch.object(otp_service, "check_login_lock", return_value=(False, 0)):
                response = self._post(
                    "account:password-reset-request", {"email": VALID_EMAIL}
                )
        self.assertEqual(response.status_code, 200)
        self.mock_otp_task.delay.assert_called_once()

    def test_reset_request_unknown_email_same_response(self):
        response = self._post(
            "account:password-reset-request", {"email": "nobody@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("If that email is registered", response.json()["message"])
        self.mock_otp_task.delay.assert_not_called()

    def test_reset_request_unverified_email_same_response(self):
        User.objects.create_user(
            email="unverified2@example.com",
            username="unverif2",
            password=VALID_PASSWORD,
        )
        response = self._post(
            "account:password-reset-request", {"email": "unverified2@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.mock_otp_task.delay.assert_not_called()

    def test_reset_request_cooldown(self):
        with patch.object(
            otp_service, "check_resend_eligibility",
            return_value=(False, "Please wait 90 second(s) before requesting another OTP."),
        ):
            with patch.object(otp_service, "check_login_lock", return_value=(False, 0)):
                response = self._post(
                    "account:password-reset-request", {"email": VALID_EMAIL}
                )
        self.assertEqual(response.status_code, 429)

    def test_reset_request_account_locked(self):
        with patch.object(otp_service, "check_login_lock", return_value=(True, 55)):
            response = self._post(
                "account:password-reset-request", {"email": VALID_EMAIL}
            )
        self.assertEqual(response.status_code, 429)

    def test_reset_request_missing_email(self):
        response = self._post("account:password-reset-request", {})
        self.assertEqual(response.status_code, 400)

class PasswordResetVerifyOTPTests(BaseAccountTestCase):
    def setUp(self):
        super().setUp()
        self.user = self._create_verified_user()

    def test_reset_verify_success(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(True, "OTP verified successfully.", 5),
        ):
            with patch.object(
                otp_service, "store_reset_token", return_value="fake-reset-token"
            ):
                response = self._post(
                    "account:password-reset-verify-otp",
                    {"email": VALID_EMAIL, "otp": "123456"},
                )
        self.assertEqual(response.status_code, 200)
        self.assertIn("reset_token", response.json()["data"])
        self.assertEqual(response.json()["data"]["reset_token"], "fake-reset-token")

    def test_reset_verify_wrong_otp(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(False, "Invalid OTP. 3 attempt(s) remaining.", 3),
        ):
            response = self._post(
                "account:password-reset-verify-otp",
                {"email": VALID_EMAIL, "otp": "000000"},
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["attempts_remaining"], 3)

    def test_reset_verify_locks_after_max_attempts(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(False, "Too many failed attempts. Account locked for 60 minute(s).", -1),
        ):
            response = self._post(
                "account:password-reset-verify-otp",
                {"email": VALID_EMAIL, "otp": "000000"},
            )
        self.assertEqual(response.status_code, 429)

    def test_reset_verify_expired_otp(self):
        with patch.object(
            otp_service, "verify_otp",
            return_value=(False, "OTP expired or not found. Please request a new one.", 0),
        ):
            response = self._post(
                "account:password-reset-verify-otp",
                {"email": VALID_EMAIL, "otp": "123456"},
            )
        self.assertEqual(response.status_code, 400)

    def test_reset_verify_unknown_email(self):
        response = self._post(
            "account:password-reset-verify-otp",
            {"email": "ghost@example.com", "otp": "123456"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("No account found", response.json()["message"])

    def test_reset_verify_non_numeric_otp(self):
        response = self._post(
            "account:password-reset-verify-otp",
            {"email": VALID_EMAIL, "otp": "abcdef"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("otp", response.json().get("errors", response.json()))

class PasswordResetConfirmTests(BaseAccountTestCase):
    VALID_RESET_TOKEN = "valid-reset-token-xyz"
    NEW_PASSWORD      = "NewSecurePass@456"

    def setUp(self):
        super().setUp()
        self.user = self._create_verified_user()

    def _payload(self, **overrides):
        base = {
            "email":            VALID_EMAIL,
            "reset_token":      self.VALID_RESET_TOKEN,
            "new_password":     self.NEW_PASSWORD,
            "confirm_password": self.NEW_PASSWORD,
        }
        base.update(overrides)
        return base

    def test_reset_confirm_success(self):
        with patch.object(
            otp_service, "verify_and_consume_reset_token", return_value=True
        ):
            response = self._post("account:password-reset-confirm", self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_reset_confirm_password_actually_changed(self):
        with patch.object(
            otp_service, "verify_and_consume_reset_token", return_value=True
        ):
            self._post("account:password-reset-confirm", self._payload())
        user = User.objects.get(email=VALID_EMAIL)
        self.assertTrue(user.check_password(self.NEW_PASSWORD))
        self.assertFalse(user.check_password(VALID_PASSWORD))

    def test_reset_confirm_all_tokens_blacklisted(self):
        tokens = self._get_tokens_for_user(self.user)
        with patch.object(
            otp_service, "verify_and_consume_reset_token", return_value=True
        ):
            self._post("account:password-reset-confirm", self._payload())
        response = self._post_authed(
            "account:logout",
            {"refresh": tokens["refresh"]},
            tokens["access"],
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_confirm_invalid_token(self):
        with patch.object(
            otp_service, "verify_and_consume_reset_token", return_value=False
        ):
            response = self._post("account:password-reset-confirm", self._payload())
        self.assertEqual(response.status_code, 400)
        self.assertIn("reset_token", response.json().get("errors", response.json()))

    def test_reset_confirm_token_one_time_use(self):
        call_count = {"n": 0}
        def consume_once(email, token):
            call_count["n"] += 1
            return call_count["n"] == 1 
        with patch.object(otp_service, "verify_and_consume_reset_token", side_effect=consume_once):
            r1 = self._post("account:password-reset-confirm", self._payload())
            r2 = self._post("account:password-reset-confirm", self._payload())
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 400)

    def test_reset_confirm_passwords_dont_match(self):
        response = self._post(
            "account:password-reset-confirm",
            self._payload(confirm_password="Different@999"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm_password", response.json().get("errors", response.json()))

    def test_reset_confirm_weak_password(self):
        response = self._post(
            "account:password-reset-confirm",
            self._payload(new_password="weak", confirm_password="weak"),
        )
        self.assertEqual(response.status_code, 400)

    def test_reset_confirm_unknown_email(self):
        with patch.object(
            otp_service, "verify_and_consume_reset_token", return_value=True
        ):
            response = self._post(
                "account:password-reset-confirm",
                self._payload(email="ghost@example.com"),
            )
        self.assertEqual(response.status_code, 400)

    def test_reset_confirm_missing_fields(self):
        response = self._post(
            "account:password-reset-confirm", {"email": VALID_EMAIL}
        )
        self.assertEqual(response.status_code, 400)