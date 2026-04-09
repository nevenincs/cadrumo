"""Configuration management for AEAT automation.

Loads settings from environment variables and .env files.
See .env.example for all available configuration options.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Project root: three levels up from src/aeat/config.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env file if present (does not override existing env vars)
load_dotenv(PROJECT_ROOT / ".env")


class GoogleOAuthSettings(BaseModel):
    """OAuth 2.0 credentials for interactive/desktop authentication."""

    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    redirect_uri: str = Field(default="http://localhost:8080")


class GoogleCloudSettings(BaseModel):
    """Google Cloud project and service account settings."""

    project_id: str = Field(default="")
    service_account_key_path: str = Field(default="")
    impersonate_email: str = Field(default="")


class GoogleResourceSettings(BaseModel):
    """Target Google Workspace resource identifiers."""

    spreadsheet_id: str = Field(default="")
    drive_folder_id: str = Field(default="")
    storage_bucket: str = Field(default="")


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    google_oauth: GoogleOAuthSettings = Field(default_factory=GoogleOAuthSettings)
    google_cloud: GoogleCloudSettings = Field(default_factory=GoogleCloudSettings)
    google_resources: GoogleResourceSettings = Field(default_factory=GoogleResourceSettings)
    token_dir: Path = Field(default=PROJECT_ROOT / ".tokens")
    aeat_base_url: str = Field(default="https://sede.agenciatributaria.gob.es")


def load_settings() -> Settings:
    """Load settings from environment variables.

    Environment variables take precedence over defaults.
    See .env.example for the full list of supported variables.
    """
    return Settings(
        google_oauth=GoogleOAuthSettings(
            client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            redirect_uri=os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8080"),
        ),
        google_cloud=GoogleCloudSettings(
            project_id=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
            service_account_key_path=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
            impersonate_email=os.environ.get("GOOGLE_IMPERSONATE_EMAIL", ""),
        ),
        google_resources=GoogleResourceSettings(
            spreadsheet_id=os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", ""),
            drive_folder_id=os.environ.get("GOOGLE_DRIVE_FOLDER_ID", ""),
            storage_bucket=os.environ.get("GOOGLE_CLOUD_STORAGE_BUCKET", ""),
        ),
        token_dir=Path(os.environ.get("AEAT_TOKEN_DIR", str(PROJECT_ROOT / ".tokens"))),
        aeat_base_url=os.environ.get("AEAT_BASE_URL", "https://sede.agenciatributaria.gob.es"),
    )
