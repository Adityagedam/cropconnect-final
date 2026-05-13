# Pytest fixtures for DB-backed endpoint integration tests.
import os
from contextlib import contextmanager

import pytest
from mysql.connector import IntegrityError

os.environ.setdefault("CROP_DATA_SECRET_KEY", "test-data-secret-for-unit-tests")
os.environ.setdefault("CROP_AUTH_TOKEN_SECRET", "test-auth-secret-for-unit-tests")

from routers import auth as auth_routes  # noqa: E402
from routers import sensors as sensor_routes  # noqa: E402
from services import rate_limit as rate_limit_service  # noqa: E402
from services import sensor_service  # noqa: E402


class FakeCursor:
    def __init__(self, db, dictionary=False):
        self.db = db
        self.dictionary = dictionary
        self.lastrowid = None
        self._row = None
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql, params=None):
        params = params or ()
        normalized = " ".join(sql.lower().split())
        self._row = None
        self._rows = []

        if normalized.startswith("insert into `users`"):
            email = params[0]
            if email in self.db["users_by_email"]:
                raise IntegrityError("Duplicate entry for email")
            user_id = len(self.db["users"]) + 1
            row = {
                "id": user_id,
                "email": email,
                "password": params[1],
                "phone": params[2],
                "name": params[3],
                "state": params[4],
                "location": params[5],
                "land_size": params[6],
                "location_type": params[7],
                "district": params[8],
                "city": params[9],
                "village": params[10],
                "sensor_device_id": params[11],
                "sensors": params[12],
                "pumps": params[13],
                "sensor_setup_complete": params[14],
                "sensor_setup_status": params[15],
            }
            self.db["users"].append(row)
            self.db["users_by_email"][email] = row
            self.db["users_by_id"][user_id] = row
            self.lastrowid = user_id
            return

        if "select * from `users` where `id`" in normalized:
            self._row = self.db["users_by_id"].get(params[0])
            return

        if "select * from `users` where `email`" in normalized:
            self._row = self.db["users_by_email"].get(params[0])
            return

        if normalized.startswith("insert into sensor_readings"):
            reading_id = len(self.db["readings"]) + 1
            row = {
                "id": reading_id,
                "device_id": params[0],
                "soil_moisture": params[1],
                "humidity": params[2],
                "temperature": params[3],
                "ph": params[4],
                "nitrogen": params[5],
                "phosphorus": params[6],
                "potassium": params[7],
                "recorded_at": self.db["now"],
            }
            self.db["readings"].append(row)
            self.lastrowid = reading_id
            return

        if "from sensor_readings" in normalized and "limit 1" in normalized:
            device_id = params[0]
            rows = [row for row in self.db["readings"] if row["device_id"] == device_id]
            self._row = rows[-1] if rows else None
            return

        if "from public_rate_limits" in normalized and "count(*)" in normalized:
            bucket, client_host, _window = params
            self._row = {"count": sum(1 for item in self.db["rate_limits"] if item[:2] == (bucket, client_host))}
            return

        if normalized.startswith("insert into public_rate_limits"):
            self.db["rate_limits"].append((params[0], params[1]))
            return

        if normalized.startswith("delete from public_rate_limits"):
            return

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self, **kwargs):
        return FakeCursor(self.db, dictionary=kwargs.get("dictionary", False))

    def commit(self):
        return None


@pytest.fixture
def fake_db(monkeypatch):
    db = {
        "users": [],
        "users_by_email": {},
        "users_by_id": {},
        "readings": [],
        "rate_limits": [],
        "now": "2026-05-13T00:00:00+00:00",
    }

    @contextmanager
    def farmers_connection():
        yield FakeConnection(db)

    @contextmanager
    def main_connection():
        yield FakeConnection(db)

    monkeypatch.setattr(auth_routes, "get_farmers_connection", farmers_connection)
    monkeypatch.setattr(rate_limit_service, "get_connection", main_connection)
    monkeypatch.setattr(sensor_service, "get_connection", main_connection)
    monkeypatch.setattr(sensor_routes, "get_connection", main_connection)
    monkeypatch.setattr(auth_routes, "get_connection", main_connection)
    return db
