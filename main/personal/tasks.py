import logging
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger("personal")

def _send_html_email(to_email: str, subject: str, template_name: str, context: dict,) -> None:
    html_body = render_to_string(f"emails/{template_name}", context)
    plain_body = render_to_string(f"emails/{template_name.replace('.html', '_plain.txt')}", context)
    msg = EmailMultiAlternatives(subject=subject, body=plain_body, from_email=settings.DEFAULT_FROM_EMAIL, to=[to_email],)
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    logger.info("Email sent to %s (template=%s)", to_email, template_name)

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True,)
def send_emergency_alert_task(self, contact_email: str, contact_name: str, user_full_name: str, user_email: str,
                               blood_group: str, allergies: str, medical: str, profile_pic_url: str, latitude: float,
                                 longitude: float, custom_message: str,):
    logger.info("Sending emergency alert to %s for user %s", contact_email, user_email,)
    maps_link = (f"https://www.google.com/maps?q={latitude},{longitude}")
    context = {
        "contact_name": contact_name,
        "user_full_name": user_full_name,
        "user_email": user_email,
        "blood_group": blood_group,
        "allergies": allergies,
        "medical": medical,
        "profile_pic_url": profile_pic_url,
        "latitude": latitude,
        "longitude": longitude,
        "maps_link": maps_link,
        "custom_message": custom_message,
        "support_email": "support@tripsync.com",
    }
    _send_html_email(
        to_email=contact_email,
        subject=f"🚨 Emergency Alert — {user_full_name} needs help",
        template_name="emergency_alert.html",
        context=context,
    )

@shared_task( bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True,)
def send_emergency_contact_notification_task(self, contact_email: str, contact_name: str, user_full_name: str,
                                              user_email: str, relation: str,):
    logger.info("Sending emergency contact notification to %s (added by %s)", contact_email, user_email,)
    context = {
        "contact_name": contact_name,
        "user_full_name": user_full_name,
        "user_email": user_email,
        "relation": relation,
        "support_email": "support@tripsync.com",
        "app_url": "https://tripsync.com",
    }
    _send_html_email(
        to_email=contact_email,
        subject=f"You've been added as an emergency contact on TripSync",
        template_name="emergency_contact_added.html",
        context=context,
    )