# ruff: noqa: F821
from __future__ import annotations

_core = None


def _bind_core(core):
    global _core
    _core = core
    for name in dir(core):
        if not name.startswith("__"):
            globals()[name] = getattr(core, name)


def migrate_legacy_device_api_keys(cursor, table_schema: str) -> None:
    if not column_exists(cursor, table_schema, "devices", "api_key"):
        return

    cursor.execute(
        """
        SELECT device_id, api_key
        FROM devices
        WHERE api_key IS NOT NULL AND TRIM(api_key) <> ''
        """
    )
    rows = cursor.fetchall() or []
    for row in rows:
        device_id = str((row.get("device_id") if isinstance(row, dict) else row[0]) or "").strip()
        legacy_key = str((row.get("api_key") if isinstance(row, dict) else row[1]) or "").strip()
        if not device_id or not legacy_key:
            continue

        key_hash = esp32_key_hash(legacy_key)
        cursor.execute("SELECT id FROM esp32_device_keys WHERE key_hash = %s LIMIT 1", (key_hash,))
        if cursor.fetchone():
            continue
        cursor.execute(
            "SELECT id FROM esp32_device_keys WHERE device_id = %s AND status = 'active' LIMIT 1",
            (device_id,),
        )
        if cursor.fetchone():
            continue
        cursor.execute(
            """
            INSERT INTO esp32_device_keys (device_id, key_hash, encrypted_key, status)
            VALUES (%s, %s, %s, 'active')
            """,
            (device_id, key_hash, encrypt_text(legacy_key)),
        )


def ensure_sensor_tables() -> None:
    database = DB_CONFIG["database"]
    with get_server_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sensor_readings (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL,
                  soil_moisture DECIMAL(6,2) NULL,
                  humidity DECIMAL(6,2) NULL,
                  temperature DECIMAL(6,2) NULL,
                  ph DECIMAL(5,2) NULL,
                  nitrogen DECIMAL(8,2) NULL,
                  phosphorus DECIMAL(8,2) NULL,
                  potassium DECIMAL(8,2) NULL,
                  raw_payload JSON NULL,
                  recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_device_recorded_at (device_id, recorded_at),
                  INDEX idx_recorded_at (recorded_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL UNIQUE,
                  display_name VARCHAR(120) NULL,
                  location VARCHAR(160) NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS esp32_device_keys (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL,
                  key_hash CHAR(64) NOT NULL UNIQUE,
                  encrypted_key TEXT NOT NULL,
                  status VARCHAR(20) NOT NULL DEFAULT 'active',
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  last_used_at TIMESTAMP NULL,
                  rotated_at TIMESTAMP NULL,
                  revoked_at TIMESTAMP NULL,
                  PRIMARY KEY (id),
                  INDEX idx_device_key_status (device_id, status, created_at),
                  INDEX idx_device_key_hash_status (key_hash, status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            migrate_legacy_device_api_keys(cursor, database)
            drop_column_if_exists(cursor, database, "devices", "api_key")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pump_states (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  device_id VARCHAR(80) NULL,
                  pump_id VARCHAR(40) NOT NULL,
                  is_on TINYINT(1) NOT NULL DEFAULT 0,
                  runtime_minutes INT UNSIGNED NOT NULL DEFAULT 0,
                  schedule JSON NULL,
                  sent_to_esp32 TINYINT(1) NOT NULL DEFAULT 0,
                  message VARCHAR(255) NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_pump_user_created (user_id, email, created_at),
                  INDEX idx_pump_device_created (device_id, pump_id, created_at),
                  INDEX idx_pump_id_created (pump_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            add_column_if_missing(cursor, database, "pump_states", "device_id", "VARCHAR(80) NULL")
            if not index_exists(cursor, database, "pump_states", "idx_pump_device_created"):
                cursor.execute("CREATE INDEX idx_pump_device_created ON pump_states (device_id, pump_id, created_at)")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS relay_statuses (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  device_id VARCHAR(80) NOT NULL,
                  relay_number TINYINT UNSIGNED NOT NULL,
                  is_on TINYINT(1) NOT NULL DEFAULT 0,
                  reported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uq_relay_device_number (device_id, relay_number),
                  INDEX idx_relay_device_reported (device_id, reported_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pump_timers (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  device_id VARCHAR(80) NULL,
                  pump_id VARCHAR(40) NOT NULL,
                  timer_key VARCHAR(80) NOT NULL,
                  start_time VARCHAR(10) NOT NULL,
                  duration_minutes INT UNSIGNED NOT NULL,
                  days JSON NULL,
                  active TINYINT(1) NOT NULL DEFAULT 1,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uq_timer_owner (`user_id`, `email`, `pump_id`, `timer_key`),
                  INDEX idx_timer_owner (user_id, email, pump_id),
                  INDEX idx_timer_device_active (device_id, active, pump_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            add_column_if_missing(cursor, database, "pump_timers", "device_id", "VARCHAR(80) NULL")
            if not index_exists(cursor, database, "pump_timers", "idx_timer_device_active"):
                cursor.execute("CREATE INDEX idx_timer_device_active ON pump_timers (device_id, active, pump_id)")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  message_type VARCHAR(20) NOT NULL,
                  text TEXT NOT NULL,
                  related_to_plant_or_soil TINYINT(1) NULL,
                  sensor_data JSON NULL,
                  location VARCHAR(160) NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_chat_owner_created (user_id, email, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dashboard_snapshots (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  user_id BIGINT UNSIGNED NULL,
                  email VARCHAR(255) NULL,
                  device_id VARCHAR(80) NULL,
                  source VARCHAR(40) NULL,
                  sensor_data JSON NULL,
                  pump_data JSON NULL,
                  timers JSON NULL,
                  weather_data JSON NULL,
                  market_data JSON NULL,
                  telemetry_packet JSON NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_snapshot_owner_created (user_id, email, created_at),
                  INDEX idx_snapshot_device_created (device_id, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        conn.commit()


def ensure_farmers_tables() -> None:
    create_db_sql = """
        CREATE DATABASE IF NOT EXISTS {database}
          CHARACTER SET utf8mb4
          COLLATE utf8mb4_unicode_ci
    """.format(database=quote_identifier(FARMERS_DATABASE))
    create_user_sql = """
        CREATE TABLE IF NOT EXISTS `users` (
          `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
          `email` VARCHAR(255) NOT NULL,
          `password` VARCHAR(255) NOT NULL,
          `phone` VARCHAR(30) NULL,
          `name` VARCHAR(120) NULL,
          `state` VARCHAR(120) NULL,
          `location` VARCHAR(255) NULL,
          `land size` DECIMAL(10,2) NULL,
          `sensor_device_id` VARCHAR(80) NULL,
          PRIMARY KEY (`id`),
          UNIQUE KEY `uq_users_email` (`email`),
          UNIQUE KEY `uq_users_sensor_device_id` (`sensor_device_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """

    with get_server_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(create_db_sql)
        conn.commit()

    with get_farmers_connection() as conn:
        with conn.cursor(dictionary=True) as cursor:
            legacy_exists = table_exists(cursor, FARMERS_DATABASE, LEGACY_USER_TABLE)
            users_exists = table_exists(cursor, FARMERS_DATABASE, USER_TABLE)
            if legacy_exists and not users_exists:
                cursor.execute(
                    "RENAME TABLE {database}.{legacy_table} TO {database}.{user_table}".format(
                        database=quote_identifier(FARMERS_DATABASE),
                        legacy_table=quote_identifier(LEGACY_USER_TABLE),
                        user_table=quote_identifier(USER_TABLE),
                    )
                )
                logger.info("Renamed legacy farmers.%s table to %s", LEGACY_USER_TABLE, USER_TABLE)
            elif legacy_exists and users_exists:
                logger.warning("Legacy farmers.%s table still exists alongside %s; leaving it untouched", LEGACY_USER_TABLE, USER_TABLE)

            cursor.execute(create_user_sql)
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "location_type", "VARCHAR(20) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "district", "VARCHAR(120) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "city", "VARCHAR(120) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "village", "VARCHAR(120) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensor_device_id", "VARCHAR(80) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensors", "VARCHAR(20) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "pumps", "VARCHAR(20) NULL")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensor_setup_complete", "TINYINT(1) NOT NULL DEFAULT 0")
            add_column_if_missing(cursor, FARMERS_DATABASE, "users", "sensor_setup_status", "VARCHAR(40) NULL")
            cursor.execute("UPDATE `users` SET `sensor_device_id` = NULL WHERE TRIM(COALESCE(`sensor_device_id`, '')) = ''")
            cursor.execute(
                """
                UPDATE `users` duplicate_user
                INNER JOIN (
                  SELECT `sensor_device_id`, MIN(`id`) AS keep_id
                  FROM `users`
                  WHERE `sensor_device_id` IS NOT NULL AND TRIM(`sensor_device_id`) <> ''
                  GROUP BY `sensor_device_id`
                  HAVING COUNT(*) > 1
                ) keepers ON duplicate_user.`sensor_device_id` = keepers.`sensor_device_id`
                SET
                  duplicate_user.`sensor_device_id` = NULL,
                  duplicate_user.`sensor_setup_complete` = 0,
                  duplicate_user.`sensor_setup_status` = 'pending'
                WHERE duplicate_user.`id` <> keepers.keep_id
                """
            )
            if not (
                index_exists(cursor, FARMERS_DATABASE, "users", "uq_users_sensor_device_id")
                or index_exists(cursor, FARMERS_DATABASE, "users", "uq_sign_in_sensor_device_id")
            ):
                cursor.execute("CREATE UNIQUE INDEX uq_users_sensor_device_id ON `users` (`sensor_device_id`)")
            modify_column_best_effort(cursor, "users", "password", "VARCHAR(255) NOT NULL")
            modify_column_best_effort(cursor, "users", "phone", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "name", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "state", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "location", "TEXT NULL")
            modify_column_best_effort(cursor, "users", "district", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "city", "VARCHAR(512) NULL")
            modify_column_best_effort(cursor, "users", "village", "VARCHAR(512) NULL")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  email VARCHAR(255) NOT NULL,
                  token_hash CHAR(64) NOT NULL,
                  expires_at TIMESTAMP NOT NULL,
                  used_at TIMESTAMP NULL,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  UNIQUE KEY uq_reset_token_hash (token_hash),
                  INDEX idx_reset_email_created (email, created_at),
                  INDEX idx_reset_expires (expires_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        conn.commit()


def ensure_public_rate_limit_table() -> None:
    global PUBLIC_RATE_TABLE_READY
    if PUBLIC_RATE_TABLE_READY:
        return
    database = DB_CONFIG["database"]
    with get_server_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public_rate_limits (
                  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                  bucket VARCHAR(80) NOT NULL,
                  client_host VARCHAR(255) NOT NULL,
                  requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (id),
                  INDEX idx_rate_bucket_client_time (bucket, client_host, requested_at),
                  INDEX idx_rate_requested_at (requested_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
        conn.commit()
    PUBLIC_RATE_TABLE_READY = True


def run_database_migrations(core) -> None:
    _bind_core(core)
    ensure_sensor_tables()
    ensure_farmers_tables()
    ensure_public_rate_limit_table()
