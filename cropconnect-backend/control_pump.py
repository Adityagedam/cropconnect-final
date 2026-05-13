#!/usr/bin/env python3
"""
Developer helper to queue a pump command through the CropConnect backend.

The backend does not contact the pump ESP32 directly. It stores the desired
relay state, then the main ESP32 polls the command over SIM800L and forwards it
to the pump ESP32.
"""
import json
import os
import urllib.error
import urllib.request

from logging_config import configure_logging

logger = configure_logging()


def control_pump(pump_id="pump1", turn_on=True):
    """
    Queue a pump command in the backend.

    Args:
        pump_id (str): ID of the pump, for example "pump1".
        turn_on (bool): True to queue ON, False to queue OFF.
    """
    token = os.getenv("CROPCONNECT_AUTH_TOKEN", "")
    if not token:
        logger.error("Set CROPCONNECT_AUTH_TOKEN to a dashboard login token before using this helper.")
        return False

    api_base_url = os.getenv("CROPCONNECT_API_URL", "http://localhost:8001/api").rstrip("/")
    url = f"{api_base_url}/pump/state"
    payload = {"pump_id": pump_id, "on": turn_on}
    device_id = os.getenv("CROPCONNECT_DEVICE_ID", "").strip()
    if device_id:
        payload["device_id"] = device_id
    data = json.dumps(payload).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            logger.info("Pump %s command queued: %s", pump_id, "ON" if turn_on else "OFF")
            logger.info("Response: %s", result)
            return True

    except urllib.error.HTTPError as exc:
        logger.error("HTTP Error %s: %s", exc.code, exc.reason)
        return False
    except urllib.error.URLError as exc:
        logger.error("Network Error: %s", exc.reason)
        return False
    except Exception as exc:
        logger.exception("Pump command helper failed: %s", exc)
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
        pump_id = sys.argv[2] if len(sys.argv) > 2 else "pump1"

        if action in ["on", "true", "1"]:
            control_pump(pump_id, True)
        elif action in ["off", "false", "0"]:
            control_pump(pump_id, False)
        else:
            logger.info("Usage: python control_pump.py [on|off] [pump_id]")
    else:
        logger.info("CropConnect Pump Command Queue Helper")
        logger.info("Usage: python control_pump.py [on|off] [pump_id]")
        logger.info("Requires CROPCONNECT_AUTH_TOKEN in the environment.")
        logger.info("Optional: set CROPCONNECT_DEVICE_ID to queue for a specific sensorDeviceId.")
        logger.info("Optional: set CROPCONNECT_API_URL to target another backend API base URL.")
