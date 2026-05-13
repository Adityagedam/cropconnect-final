import hashlib
import threading
from contextlib import contextmanager
from typing import Any

import mysql.connector
from mysql.connector import pooling

_db_config: dict[str, Any] = {}
_farmers_database = "farmers"
_mysql_pool_size = 5
_main_db_pool = None
_farmers_db_pools: dict[str, pooling.MySQLConnectionPool] = {}
_main_db_pool_lock = threading.Lock()
_farmers_db_pools_lock = threading.Lock()


def configure_connections(db_config: dict[str, Any], farmers_database: str, mysql_pool_size: int) -> None:
    global _db_config, _farmers_database, _mysql_pool_size
    _db_config = {
        "connection_timeout": 10,
        **dict(db_config),
    }
    _farmers_database = farmers_database
    _mysql_pool_size = max(1, int(mysql_pool_size))


@contextmanager
def get_connection():
    global _main_db_pool
    if _main_db_pool is None:
        with _main_db_pool_lock:
            if _main_db_pool is None:
                _main_db_pool = pooling.MySQLConnectionPool(
                    pool_name="cropconnect_main",
                    pool_size=_mysql_pool_size,
                    pool_reset_session=True,
                    **_db_config,
                )
    conn = _main_db_pool.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_server_connection():
    config = {**_db_config}
    config.pop("database", None)
    conn = mysql.connector.connect(**config)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_farmers_connection(database: str | None = None):
    pool_key = database or _farmers_database
    if pool_key not in _farmers_db_pools:
        with _farmers_db_pools_lock:
            if pool_key not in _farmers_db_pools:
                _farmers_db_pools[pool_key] = pooling.MySQLConnectionPool(
                    pool_name=f"cropconnect_farmers_{hashlib.sha1(pool_key.encode('utf-8')).hexdigest()[:12]}",
                    pool_size=_mysql_pool_size,
                    pool_reset_session=True,
                    **{**_db_config, "database": pool_key},
                )
    conn = _farmers_db_pools[pool_key].get_connection()
    try:
        yield conn
    finally:
        conn.close()
