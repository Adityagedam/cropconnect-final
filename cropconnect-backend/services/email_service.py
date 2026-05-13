# Outbound enquiry and password-reset email helpers.
import smtplib
from email.message import EmailMessage

from config import settings
from models import EnquiryIn


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def send_enquiry_email(payload: EnquiryIn) -> bool:
    if not smtp_configured():
        return False

    msg = EmailMessage()
    msg["Subject"] = f"CropConnect Enquiry from {payload.name}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.contact_to_email
    msg["Reply-To"] = payload.email
    msg.set_content(
        "\n".join(
            [
                f"Name: {payload.name}",
                f"Email: {payload.email}",
                f"Phone: {payload.phone or '-'}",
                f"Organization/Farm: {payload.organization or '-'}",
                "",
                "Message:",
                payload.message,
            ]
        )
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)

    return True


def send_password_reset_email(email: str, reset_url: str) -> bool:
    if not smtp_configured():
        return False

    msg = EmailMessage()
    msg["Subject"] = "Reset your CropConnect password"
    msg["From"] = settings.smtp_user
    msg["To"] = email
    msg["Reply-To"] = settings.contact_to_email
    msg.set_content(
        "\n".join(
            [
                "We received a request to reset your CropConnect password.",
                "",
                f"Reset link: {reset_url}",
                "",
                f"This link expires in {settings.password_reset_token_ttl_minutes} minutes.",
                "If you did not request this, you can ignore this email.",
                "",
            ]
        )
    )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)

    return True
