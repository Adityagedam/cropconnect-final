CREATE DATABASE IF NOT EXISTS cropconnect
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE cropconnect;

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
);

CREATE TABLE IF NOT EXISTS devices (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id VARCHAR(80) NOT NULL UNIQUE,
  display_name VARCHAR(120) NULL,
  location VARCHAR(160) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
);

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
);

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
);

CREATE TABLE IF NOT EXISTS relay_statuses (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  device_id VARCHAR(80) NOT NULL,
  relay_number TINYINT UNSIGNED NOT NULL,
  is_on TINYINT(1) NOT NULL DEFAULT 0,
  reported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_relay_device_number (device_id, relay_number),
  INDEX idx_relay_device_reported (device_id, reported_at)
);

CREATE TABLE IF NOT EXISTS public_rate_limits (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  bucket VARCHAR(80) NOT NULL,
  client_host VARCHAR(255) NOT NULL,
  requested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_rate_bucket_client_time (bucket, client_host, requested_at),
  INDEX idx_rate_requested_at (requested_at)
);

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
);

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
);

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
);
