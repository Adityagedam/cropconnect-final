from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from config import settings
from db.connections import get_connection, get_farmers_connection
from models import EnquiryIn
from services.email_service import send_enquiry_email, smtp_configured
from services.rate_limit import rate_limit_public_request

router = APIRouter()


def raise_public_error(status_code: int, detail: str, _context: str, exc: Exception) -> None:
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/api/health")
def health():
    try:
      with get_connection() as conn:
          conn.ping(reconnect=True, attempts=1, delay=0)
      with get_farmers_connection() as farmers_conn:
          farmers_conn.ping(reconnect=True, attempts=1, delay=0)
      return {"ok": True, "database": "connected", "farmers_database": settings.mysql_farmers_database}
    except Exception as exc:
      raise_public_error(503, "Database not connected", "Health check failed", exc)


@router.get("/")
def root():
    return {
        "service": "CropConnect ESP32 Ingestion API",
        "docs": "/docs",
        "health": "/api/health",
        "esp32_relay_command": "/api/esp32/relay-command",
        "hardware_flow": "Main ESP32 uses SIM800L to ingest sensors and poll pump commands, then forwards commands to the pump ESP32.",
    }


@router.post("/api/enquiries")
def enquiries(payload: EnquiryIn, request: Request):
    rate_limit_public_request(request, "enquiries", limit=5, window_seconds=300)
    if not smtp_configured():
        raise HTTPException(status_code=503, detail="Email delivery is not configured")
    try:
        send_enquiry_email(payload)
    except Exception as exc:
        raise_public_error(502, "Email delivery failed", "Enquiry email delivery failed", exc)

    return {
        "ok": True,
        "message": "Enquiry received",
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
