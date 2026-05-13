CREATE DATABASE IF NOT EXISTS farmers
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE farmers;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `phone` VARCHAR(512) NULL,
  `name` VARCHAR(512) NULL,
  `state` VARCHAR(512) NULL,
  `location` TEXT NULL,
  `land_size` DECIMAL(10,2) NULL,
  `location_type` VARCHAR(20) NULL,
  `district` VARCHAR(512) NULL,
  `city` VARCHAR(512) NULL,
  `village` VARCHAR(512) NULL,
  `sensor_device_id` VARCHAR(80) NULL,
  `sensors` VARCHAR(20) NULL,
  `pumps` VARCHAR(20) NULL,
  `sensor_setup_complete` TINYINT(1) NOT NULL DEFAULT 0,
  `sensor_setup_status` VARCHAR(40) NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email` (`email`),
  UNIQUE KEY `uq_users_sensor_device_id` (`sensor_device_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `password_reset_tokens` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL,
  `token_hash` CHAR(64) NOT NULL,
  `expires_at` TIMESTAMP NOT NULL,
  `used_at` TIMESTAMP NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_reset_token_hash` (`token_hash`),
  INDEX `idx_reset_email_created` (`email`, `created_at`),
  INDEX `idx_reset_expires` (`expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
