# Backwards-compatible ASGI entrypoint for deployments still targeting esp32_ingest:app.
import sys
from urllib.parse import urlparse

import security_crypto
from app import app
from config import settings
from db import migrations as db_migrations
from db.connections import configure_connections

security_crypto.require_data_secret()

if settings.mysql_public_url:
    url = urlparse(settings.mysql_public_url)
    DB_CONFIG = {
        "host": url.hostname,
        "port": int(url.port or 3306),
        "user": url.username,
        "password": url.password,
        "database": url.path[1:] or "railway",
    }
else:
    DB_CONFIG = {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password,
        "database": settings.mysql_database,
    }

FARMERS_DATABASE = settings.mysql_farmers_database
MYSQL_POOL_SIZE = max(1, settings.mysql_pool_size)
USER_TABLE = "users"
LEGACY_USER_TABLE = "sign-in"
configure_connections(DB_CONFIG, FARMERS_DATABASE, MYSQL_POOL_SIZE)


def run_database_migrations() -> None:
    db_migrations.run_database_migrations(sys.modules[__name__])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
