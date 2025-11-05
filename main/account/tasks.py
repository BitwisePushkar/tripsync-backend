import logging
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger("account")

def _send_html_email(to_email: str, subject: str, template_name: str, context: dict,) -> bool:
    try:
        html_body = render_to_string(f"emails/{template_name}", context)
        plain_body = render_to_string(f"emails/{template_name.replace('.html', '_plain.txt')}", context)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,         
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        logger.info("Email sent successfully to %s (template=%s)", to_email, template_name)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, str(exc))
        raise exc
    
@shared_task(bind=True, max_retries=3, default_retry_delay=10, autoretry_for=(Exception,), retry_backoff=True,             
             retry_jitter=True,)
def send_otp_email_task(self, email: str, otp: str, purpose: str):
    logger.info("Sending OTP email to %s (purpose=%s)", email, purpose)
    if purpose == "registration":
        subject = "Verify your TripSync account"
        template = "otp_verification.html"
    else:
        subject = "TripSync password reset"
        template = "otp_password_reset.html"
    context = {
        "otp": otp,
        "expiry_minutes": settings.OTP_EXPIRY_MINUTES,
        "support_email": "support@tripsync.com",
    }
    _send_html_email(email, subject, template, context)

@shared_task(bind=True, max_retries=3, default_retry_delay=10, autoretry_for=(Exception,), retry_backoff=True,
              retry_jitter=True,)
def send_welcome_email_task(self, email: str, username: str):
    logger.info("Sending welcome email to %s", email)
    context = {
        "username": username,
        "support_email": "support@tripsync.com",
        "app_url": "https://tripsync.com",
    }
    _send_html_email(email, "Welcome to TripSync 🌍", "welcome.html", context,)

@shared_task(bind=True, max_retries=3, default_retry_delay=10, autoretry_for=(Exception,), retry_backoff=True,
              retry_jitter=True,)
def send_goodbye_email_task(self, email: str, username: str):
    logger.info("Sending goodbye email to %s", email)
    context = {
        "username": username,
        "support_email": "support@tripsync.com",
        "app_url": "https://tripsync.com",
    }
    _send_html_email(email, "Goodbye from TripSync", "goodbye.html", context,)