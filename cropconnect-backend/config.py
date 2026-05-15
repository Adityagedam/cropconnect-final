# Centralized environment settings for the CropConnect API.
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mysql_public_url: str | None = None
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "cropconnect"
    mysql_farmers_database: str = "farmers"
    mysql_pool_size: int = 15
    crop_data_secret_key: str
    crop_auth_token_secret: str
    esp32_api_key: str = ""
    allow_global_esp32_api_key: bool = False
    contact_to_email: str = "cropconnectco@gmail.com"
    frontend_public_url: str = "https://cropconnect01.vercel.app"
    frontend_origins: str = "https://cropconnect01.vercel.app"
    public_landing_sensor_device_id: str = ""
    public_translation_enabled: bool = False
    query_api_key_enabled: bool = False
    esp32_get_write_enabled: bool = False
    public_rate_limit_db_fail_open: bool = False
    trust_proxy_headers: bool = False
    password_reset_token_ttl_minutes: int = 30
    farm_timer_utc_offset_minutes: int = 330
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "none"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    google_api_key: str = ""
    google_cse_id: str = ""
    data_gov_api_key: str = ""
    data_gov_market_resource_url: str = "https://api.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi"
    market_price_limit: int = 100
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""


settings = Settings()
