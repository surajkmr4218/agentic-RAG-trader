from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB — psycopg v3 driver string
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/alphagen"

    # External services (most consumed in later weeks)
    gemini_api_key: str = ""
    fmp_api_key: str = ""

    # SEC REQUIRES a descriptive User-Agent with contact info, or it 403s you.
    sec_user_agent: str = "AlphaGen your-name your@email.com"

    # Set in Week 6 (token encryption) and Week 6 (Clerk auth) — defaults keep boot working.
    fernet_key: str = ""
    clerk_jwks_url: str = ""


settings = Settings()