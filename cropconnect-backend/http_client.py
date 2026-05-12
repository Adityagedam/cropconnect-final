import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from typing import Any


logger = logging.getLogger("cropconnect")


def request_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    verify_ssl: bool = True,
    attempts: int = 3,
    retry_delay_seconds: float = 0.4,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST" if payload is not None else "GET",
    )
    context = None if verify_ssl else ssl._create_unverified_context()
    max_attempts = max(1, attempts)
    retryable_statuses = {429, 500, 502, 503, 504}
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=15, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.reason
            try:
                body = exc.read().decode("utf-8")
                parsed = json.loads(body)
                detail = parsed.get("error", {}).get("message") or parsed.get("detail") or body
            except (UnicodeDecodeError, json.JSONDecodeError, OSError) as parse_exc:
                logger.debug("Could not parse HTTP error body from %s: %s", url, parse_exc)

            last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
            if exc.code not in retryable_statuses or attempt == max_attempts:
                raise last_error from exc
            logger.warning("Retrying %s after HTTP %s from %s (attempt %s/%s)", req.get_method(), exc.code, url, attempt, max_attempts)
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"Network error: {repr(exc.reason)}")
            if attempt == max_attempts:
                raise last_error from exc
            logger.warning("Retrying %s after network error from %s (attempt %s/%s): %s", req.get_method(), url, attempt, max_attempts, exc.reason)
        except TimeoutError as exc:
            last_error = RuntimeError("Network timeout")
            if attempt == max_attempts:
                raise last_error from exc
            logger.warning("Retrying %s after timeout from %s (attempt %s/%s)", req.get_method(), url, attempt, max_attempts)

        time.sleep(retry_delay_seconds * (2 ** (attempt - 1)))

    raise last_error or RuntimeError("Request failed")
