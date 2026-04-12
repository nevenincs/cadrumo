"""Central settings module for AEAT automation.

Single source of truth for all environment variables. Every field in
:class:`Settings` maps 1:1 to an uppercase environment variable
(e.g. ``google_oauth_client_id`` → ``GOOGLE_OAUTH_CLIENT_ID``).

The companion test ``tests/test_config.py`` enforces that ``.env.example``
and this module stay fully aligned.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: three levels up from src/aeat/config.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings populated from environment variables and ``.env``.

    Field names map directly to env var names (uppercased). For example,
    ``google_oauth_client_id`` reads ``GOOGLE_OAUTH_CLIENT_ID``.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "env" / ".env",
        env_file_encoding="utf-8",
    )

    # ── Google OAuth 2.0 (Desktop / Interactive) ────────────────────────────
    google_oauth_client_id: str = Field(
        default="",
        description="OAuth 2.0 client ID from Google Cloud Console",
    )
    google_oauth_client_secret: str = Field(
        default="",
        description="OAuth 2.0 client secret",
    )
    google_oauth_redirect_uri: str = Field(
        default="http://localhost:8080",
        description="OAuth redirect URI for local dev server",
    )
    google_oauth_client_json: str = Field(
        default="",
        description="Path to the downloaded OAuth Desktop client JSON (used by gcloud --client-id-file)",
    )

    # ── Google Service Account (Server / Automation) ────────────────────────
    google_application_credentials: str = Field(
        default="",
        description="Path to service account JSON key file",
    )
    google_impersonate_email: str = Field(
        default="",
        description="Email to impersonate via domain-wide delegation",
    )

    # ── Google Cloud Project ────────────────────────────────────────────────
    google_cloud_project: str = Field(
        default="",
        description="GCP project ID (not project number)",
    )

    # ── Google Resource IDs ─────────────────────────────────────────────────
    google_sheets_spreadsheet_id: str = Field(
        default="",
        description="Target Google Sheets spreadsheet ID",
    )
    google_drive_folder_id: str = Field(
        default="",
        description="Target Google Drive folder ID",
    )
    google_cloud_storage_bucket: str = Field(
        default="",
        description="Cloud Storage bucket name (without gs:// prefix)",
    )

    # ── Token Storage ───────────────────────────────────────────────────────
    aeat_token_dir: Path = Field(
        default=PROJECT_ROOT / ".tokens",
        description="Directory for cached OAuth tokens",
    )

    # ── AEAT ────────────────────────────────────────────────────────────────
    aeat_base_url: str = Field(
        default="https://sede.agenciatributaria.gob.es",
        description="AEAT sede electrónica base URL",
    )

    # ── Trilingual i18n ─────────────────────────────────────────────────────
    aeat_output_language: str = Field(
        default="hu",
        description="Target output language for user-facing content (es, en, hu)",
    )
    aeat_authoritative_language_aeat_terms: str = Field(
        default="es",
        description="Authoritative language for AEAT domain terminology",
    )
    aeat_authoritative_language_project_docs: str = Field(
        default="en",
        description="Authoritative language for internal code and documentation",
    )
    aeat_fallback_languages: str = Field(
        default="en,es",
        description="Comma-separated list of fallback languages if the target language is missing",
    )

    # ── Scratch resources (provisioned by `aeat bootstrap`) ─────────────────
    aeat_scratch_folder_id: str = Field(
        default="",
        description="Drive folder ID for the aeat-scratch sandbox",
    )
    aeat_scratch_sheet_id: str = Field(
        default="",
        description="Spreadsheet ID for the aeat-scratch sandbox sheet",
    )
    aeat_scratch_doc_id: str = Field(
        default="",
        description="Document ID for the aeat-scratch sandbox doc",
    )

    # ── Live tests ──────────────────────────────────────────────────────────
    aeat_live_tests_enabled: bool = Field(
        default=False,
        description="Opt-in flag to run @pytest.mark.live tests against real Google APIs",
    )

    # ── Browser Automation ──────────────────────────────────────────────────
    aeat_browser_channel: str = Field(
        default="chrome",
        description="Playwright browser channel to use (e.g., 'chrome', 'chromium', 'msedge')",
    )
    aeat_browser_headless: bool = Field(
        default=True,
        description="Run browser in headless mode",
    )
    aeat_default_profile_name: str = Field(
        default="default",
        description="Default profile name for the browser session",
    )
    aeat_proxy_url: str = Field(
        default="",
        description="Proxy URL (e.g., 'http://proxy.example.com:8080')",
    )
    aeat_proxy_username: str = Field(
        default="",
        description="Username for proxy authentication",
    )
    aeat_proxy_password_secret: str = Field(
        default="",
        description="Password for proxy authentication",
    )
    aeat_proxy_bypass: str = Field(
        default="",
        description="Comma-separated list of domains to bypass the proxy",
    )
    aeat_rate_limit_delay_seconds: float = Field(
        default=2.0,
        description="Minimum delay between AEAT requests in seconds",
    )

    # ── Introspection ───────────────────────────────────────────────────────

    @classmethod
    def env_var_names(cls) -> set[str]:
        """Return the set of environment variable names this model reads."""
        return {name.upper() for name in cls.model_fields}


def load_settings() -> Settings:
    """Create a Settings instance from environment variables and ``.env`` file."""
    return Settings()
