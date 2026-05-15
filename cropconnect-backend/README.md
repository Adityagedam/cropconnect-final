# CropConnect ESP32 Backend

FastAPI service for receiving ESP32 sensor readings, storing them in MySQL, sending enquiries, serving weather and mandi market data, and proxying AI chat requests.

## Files

- `esp32_ingest.py` - Python API server.
- `http_client.py` - retrying JSON HTTP client for AI provider, Data.gov, and weather calls.
- `db_utils.py` - SQL identifier, schema, and migration helpers.
- `logging_config.py` - structured backend logging setup.
- `migrate_db.py` - explicit MySQL migration runner.
- `schema.sql` - MySQL database and table setup.
- `.env.example` - environment variables.

## Setup

```bash
cd cropconnect-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
mysql -u root -p < schema.sql
```

Use `requirements.txt` only when intentionally refreshing dependency versions; use `requirements.lock.txt` for deploys and repeatable local installs.

Set environment variables, or copy `.env.example` values into your shell.

```bash
export MYSQL_HOST=127.0.0.1
export MYSQL_PORT=3306
export MYSQL_USER=root
export MYSQL_PASSWORD=your_mysql_password
export MYSQL_DATABASE=cropconnect
export MYSQL_POOL_SIZE=5
export CROP_DATA_SECRET_KEY=replace_with_a_long_random_secret
export CROP_AUTH_TOKEN_SECRET=replace_with_a_different_long_random_secret
export AUTH_COOKIE_SECURE=true
export AUTH_COOKIE_SAMESITE=none
export ESP32_API_KEY=legacy_global_fallback_secret
export ALLOW_GLOBAL_ESP32_API_KEY=false
export CONTACT_TO_EMAIL=cropconnectco@gmail.com
export PUBLIC_LANDING_SENSOR_DEVICE_ID=
export FARM_TIMER_UTC_OFFSET_MINUTES=330
export GEMINI_API_KEY=your_gemini_api_key
export GEMINI_MODEL=gemini-1.5-flash
export GOOGLE_API_KEY=your_google_api_key
export GOOGLE_CSE_ID=your_google_cse_id
export DATA_GOV_API_KEY=your_data_gov_api_key
export DATA_GOV_MARKET_RESOURCE_URL=https://api.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi
export MARKET_PRICE_LIMIT=100
```

`MYSQL_PASSWORD`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_CSE_ID`, and `DATA_GOV_API_KEY` are private values. Keep them out of screenshots and commits. Local migrations cannot run until `MYSQL_PASSWORD` matches your local MySQL account. AI chat and crop planning cannot answer until `GEMINI_API_KEY` is set. Live market prices cannot load until `DATA_GOV_API_KEY` is set.

Run:

```bash
python migrate_db.py
uvicorn esp32_ingest:app --host 0.0.0.0 --port 8001 --reload
```

Smoke-test the backend helpers without touching MySQL:

```bash
python -m unittest discover -s tests
```

On Windows after setup, you can also run:

```text
run-tests.cmd
```

Frontend `.env` should use:

```bash
VITE_BACKEND_URL=http://localhost:8001
VITE_PUBLIC_TRANSLATION_ENABLED=false
```

For local HTTP development, set `AUTH_COOKIE_SECURE=false`, `AUTH_COOKIE_SAMESITE=lax`, and `FRONTEND_ORIGINS=http://localhost:3000,http://localhost:5173` in the backend environment. Keep `AUTH_COOKIE_SECURE=true`, `AUTH_COOKIE_SAMESITE=none`, and a production-only `FRONTEND_ORIGINS` value on Railway/production HTTPS.

## ESP32 POST Example

Send readings to:

```text
POST http://localhost:8001/api/telemetry/ingest
Header: X-API-Key: your-device-api-key
Content-Type: application/json
```

Payload:

```json
{
  "device_id": "your-device-id",
  "soil_moisture": 62.4,
  "humidity": 74.2,
  "temperature": 28.6,
  "ph": 6.8,
  "nitrogen": 42,
  "phosphorus": 19,
  "potassium": 31
}
```

Latest readings for the website:

```text
GET http://localhost:8001/api/sensors/latest?device_id=your-device-id
Header: Authorization: Bearer <login-token>
```

Trusted hardware can also read sensor data with `X-API-Key`. Avoid query-string `api_key` in production unless the SIM800L firmware cannot send headers, because query strings can appear in logs.

## ESP32 SIM800L Sensor And Pump Flow

Use the main ESP32 as the SIM800L gateway:

1. Main ESP32 posts sensor readings to MySQL through this backend.
2. Website users press pump controls in the dashboard.
3. Backend stores the desired relay command in MySQL.
4. Main ESP32 polls the backend over SIM800L for relay commands.
5. Main ESP32 forwards the command to the second ESP32 that controls the pump relay.
6. Main ESP32 posts the applied relay status back to the backend.

The website posts pump changes to:

```text
POST https://cropconnect01-production.up.railway.app/api/pump/state
Header: Authorization: Bearer <login-token>
```

The main ESP32 should poll:

```text
GET https://cropconnect01-production.up.railway.app/api/esp32/relay-command?device_id=your-device-id
Header: X-API-Key: your-device-api-key
```

Query-string key form is also supported only when `QUERY_API_KEY_ENABLED=true`:

```text
GET https://cropconnect01-production.up.railway.app/api/esp32/relay-command?api_key=your-device-api-key&device_id=your-device-id
```

`device_id` must match the `sensorDeviceId` shown in the user's dashboard. Pump commands are scoped by this value, so another farm's `pump1` cannot overwrite this farm's `pump1`.

The dashboard loads the ESP32 API key on demand from `/api/esp32/device-key`. The key is stored encrypted in MySQL and verified by hash; it is not included in normal login/profile responses and should not be saved in browser storage.

After forwarding/applying the relay states, the main ESP32 sends status back to:

```text
POST https://cropconnect01-production.up.railway.app/api/esp32/relay-status
Header: X-API-Key: your-device-api-key
```

For SIM800L code that is simpler with query strings, status can also be sent as:

```text
GET https://cropconnect01-production.up.railway.app/api/esp32/relay-status/update?api_key=your-device-api-key&device_id=your-device-id&r1=on&r2=off
```

That query-string status endpoint requires both `QUERY_API_KEY_ENABLED=true` and `ESP32_GET_WRITE_ENABLED=true`. Keep both disabled if your firmware can send JSON POST with `X-API-Key`.

That endpoint returns plain text for 8 relays:

```text
1on 2off 3off 4off 5off 6off 7off 8off
```

You can view the last reported relay status with the ESP32 key:

```text
GET https://cropconnect01-production.up.railway.app/api/esp32/relay-status?device_id=your-device-id
Header: X-API-Key: your-device-api-key
```

### Manual Pump Control

Manual pump control now goes through the authenticated website/API. The backend does not call the pump ESP32 directly; it only queues a command for the main ESP32 SIM800L poll.

**Using curl:**
```bash
# Turn on
curl -X POST "https://cropconnect01-production.up.railway.app/api/pump/state" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <login-token>" \
  -d '{"pump_id": "pump1", "on": true}'

# Turn off
curl -X POST "https://cropconnect01-production.up.railway.app/api/pump/state" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <login-token>" \
  -d '{"pump_id": "pump1", "on": false}'
```

The main ESP32 will receive the command on its next SIM800L poll and forward it to the pump ESP32.

## ESP32 Setup Instructions

SIM800L telemetry can be JSON POST:

```text
POST https://cropconnect01-production.up.railway.app/api/telemetry/ingest
Header: X-API-Key: your-device-api-key
```

Or simple GET query:

```text
GET https://cropconnect01-production.up.railway.app/api/telemetry/ingest?api_key=your-device-api-key&device_id=your-device-id&soil_moisture=55&humidity=70&temperature=28&ph=6.8
```

The GET query style requires both `QUERY_API_KEY_ENABLED=true` and `ESP32_GET_WRITE_ENABLED=true`. Prefer JSON POST with `X-API-Key` for production firmware.

This backend repo does not store the temporary Arduino sketch. Your ESP32/SIM800L firmware only needs to implement the endpoints above.

### Firmware Checklist

1. Configure SIM800L APN and network setup.
2. Set `DEVICE_ID` to the `sensorDeviceId` shown in the user's dashboard.
3. Set `API_KEY` to the active key shown once in the dashboard setup window.
4. Send sensor readings to `/api/telemetry/ingest`.
5. Poll `/api/esp32/relay-command` from the main ESP32.
6. Forward relay commands to the pump ESP32.
7. Report applied relay status to `/api/esp32/relay-status`.
8. Monitor Serial output at 115200 baud to verify telemetry, command polling, and status updates.

### Hardware Connections

- **ESP32 GPIO pins**: 19, 18, 5, 17, 32, 33, 25, 14 (for 8 relays)
- **Relay module**: Connect to 5V/GND and control pins
- **Pumps/Motors**: Connect through relay module NO terminals

Before flashing, set these firmware constants:

```cpp
const char* APN = "YOUR_SIM_APN";
const char* DEVICE_ID = "your-device-id";
const char* API_KEY = "your-device-api-key";
```

Relay pins are configured here:

```cpp
const int RELAY_PINS[RELAY_COUNT] = {19, 18, 5, 17, 32, 33, 25, 14};
```

Set Railway backend variables:

```bash
CROP_DATA_SECRET_KEY=replace-with-a-long-random-secret
CROP_AUTH_TOKEN_SECRET=replace-with-a-different-long-random-secret
MYSQL_POOL_SIZE=5
AUTH_COOKIE_SECURE=true
AUTH_COOKIE_SAMESITE=none
ESP32_API_KEY=
ALLOW_GLOBAL_ESP32_API_KEY=false
FRONTEND_PUBLIC_URL=https://cropconnect01.vercel.app
FRONTEND_ORIGINS=https://cropconnect01.vercel.app
PUBLIC_LANDING_SENSOR_DEVICE_ID=
PUBLIC_TRANSLATION_ENABLED=false
QUERY_API_KEY_ENABLED=false
ESP32_GET_WRITE_ENABLED=false
PUBLIC_RATE_LIMIT_DB_FAIL_OPEN=false
TRUST_PROXY_HEADERS=false
PASSWORD_RESET_TOKEN_TTL_MINUTES=30
FARM_TIMER_UTC_OFFSET_MINUTES=330
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
```

Open Arduino Serial Monitor after upload. You should see SIM800L telemetry POSTs, command GETs, and status POSTs.

Use a relay module between ESP32 and the pump. Do not connect pump power directly to ESP32 pins.

## Production notes

- Use a managed MySQL database and run `python migrate_db.py` before starting or redeploying the backend after schema changes. Railway now runs `python migrate_db.py && python esp32_ingest.py`, so deploy startup applies migrations before serving traffic. Runtime requests and `/api/health` do not create, alter, or clean database schema.
- Set `CROP_DATA_SECRET_KEY` before starting the backend. Keep the same value forever for existing encrypted profile data.
- Set `CROP_AUTH_TOKEN_SECRET` to a different strong secret for login token signing. The backend refuses to start if either production secret is missing.
- Login sessions are stored in an HttpOnly cookie named `cropconnect_auth`. Keep `AUTH_COOKIE_SECURE=true` and `AUTH_COOKIE_SAMESITE=none` for the Vercel frontend calling the Railway API over HTTPS.
- The backend signup flow generates a unique `sensorDeviceId`; ESP32 payloads must send that value as `device_id`.
- ESP32 device keys are stored in MySQL in `esp32_device_keys`: the display key is encrypted and the verification value is hashed. Use the dashboard setup window to load or rotate the key for flashing.
- Existing active ESP32 device keys are hidden after creation. If you lose the displayed key, rotate it and flash the new key to the ESP32.
- `ESP32_API_KEY` is kept only as a legacy/global fallback secret. Keep `ALLOW_GLOBAL_ESP32_API_KEY=false` in production so one farm's ESP32 key cannot write data for another device.
- Keep `QUERY_API_KEY_ENABLED=false` in production when your ESP32 firmware can send `X-API-Key` headers. Set it to `true` only for SIM800L firmware that cannot send headers.
- Keep `ESP32_GET_WRITE_ENABLED=false` in production when firmware can use POST. Set it to `true` only for SIM800L firmware that can only send telemetry/status as GET query requests.
- Keep `PUBLIC_RATE_LIMIT_DB_FAIL_OPEN=false` in production so public endpoints fail closed if MySQL rate limiting is unavailable.
- Keep `TRUST_PROXY_HEADERS=false` unless your hosting layer sanitizes `X-Forwarded-For`; otherwise attackers can spoof rate-limit identity.
- Set `FARM_TIMER_UTC_OFFSET_MINUTES` for pump schedule evaluation. The default is `330` for India Standard Time.
- Set `PUBLIC_LANDING_SENSOR_DEVICE_ID` only if the public landing page should show one device's latest ESP32 reading. Leave it blank to show `--`.
- Set `PUBLIC_TRANSLATION_ENABLED=true` and frontend `VITE_PUBLIC_TRANSLATION_ENABLED=true` only when you want whole-site auto-translation enabled and have AI provider quota/rate limits ready. Leave them `false` for English-only mode.
- Set SMTP variables if you want `/api/enquiries` to send email directly. Without SMTP, the frontend falls back to a pre-filled mail client.
- Set `GEMINI_API_KEY` for AI chat answers, crop planning, translations, and AI market advice. Set `GOOGLE_API_KEY` and `GOOGLE_CSE_ID` only to add Google Custom Search snippets to the AI prompt.
- Set `DATA_GOV_API_KEY` for live `/api/market/prices` mandi rates and `/api/market/insights` AI market advice. The dashboard uses the logged-in user's saved state and city/village as the location filter, then falls back to state-level records when district-level records are unavailable.
- Local `.env` intentionally points the frontend to `http://localhost:8001/api`. Do not point local development at production unless you specifically intend to write production data.
