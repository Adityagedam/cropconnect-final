# Outbound enquiry and password-reset email helpers.
import esp32_ingest as _api

send_enquiry_email = _api.send_enquiry_email
send_password_reset_email = _api.send_password_reset_email
smtp_configured = _api.smtp_configured

__all__ = [
    "send_enquiry_email",
    "send_password_reset_email",
    "smtp_configured",
]
