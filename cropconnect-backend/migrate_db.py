import sys

import mysql.connector

from esp32_ingest import run_database_migrations
from logging_config import configure_logging

logger = configure_logging()


if __name__ == "__main__":
    try:
        run_database_migrations()
    except mysql.connector.Error as exc:
        logger.exception("CropConnect database migration failed: %s", exc)
        logger.error("Check MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE in cropconnect-backend/.env.")
        sys.exit(1)
    logger.info("CropConnect database migrations completed.")
