import sys

import mysql.connector

from esp32_ingest import run_database_migrations


if __name__ == "__main__":
    try:
        run_database_migrations()
    except mysql.connector.Error as exc:
        print(f"CropConnect database migration failed: {exc}")
        print("Check MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, and MYSQL_DATABASE in cropconnect-backend/.env.")
        sys.exit(1)
    print("CropConnect database migrations completed.")
