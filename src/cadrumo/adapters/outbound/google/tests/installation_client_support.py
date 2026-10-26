"""Supply synthetic publisher client resources through the core settings boundary."""

from __future__ import annotations

import contextvars
import json
from pathlib import Path

import pytest

from .....core import config, config_google
from .....core.config import load_settings, reset_settings_cache
from .....core.config_google import GoogleOAuthClientSettings
from .....core.config_google_client import OAuthClient

SYNTHETIC_CLIENT_ID = "synthetic-installation-client.apps.googleusercontent.com"
SYNTHETIC_CLIENT_CREDENTIAL = "synthetic-installation-client-credential"
_EXCHANGE_URI = "https://oauth2.googleapis.com/token"


def synthetic_installation_client() -> OAuthClient:
    """Return a Desktop client whose every value is synthetic."""
    return OAuthClient(
        client_id=SYNTHETIC_CLIENT_ID,
        client_secret=SYNTHETIC_CLIENT_CREDENTIAL,
        project_id="synthetic-installation-project",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri=_EXCHANGE_URI,
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://localhost",),
    )


def write_installation_client(directory: Path, client: OAuthClient) -> Path:
    """Write ``client`` in the envelope Google uses for a Desktop client download."""
    path = directory / "google" / "oauth_client.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = client.model_dump(mode="json")
    payload["redirect_uris"] = list(client.redirect_uris)
    path.write_text(json.dumps({"installed": payload}), encoding="utf-8")
    return path


def use_installation_client(
    monkeypatch: pytest.MonkeyPatch, directory: Path, client: OAuthClient | None = None
) -> OAuthClient:
    """Make ``client`` the installation's client for the rest of the test."""
    installed = client or synthetic_installation_client()
    use_installation_client_file(monkeypatch, write_installation_client(directory, installed))
    return installed


def use_installation_client_file(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    """Read the installation client from ``path``, whether or not a file is there."""
    monkeypatch.delenv("CADRUMO_GOOGLE_OAUTH_CLIENT_JSON", raising=False)
    monkeypatch.setattr(config_google, "installation_client_source", lambda: path)
    reset_settings_cache()
    effective = load_settings().model_copy(
        update={"cadrumo_google_oauth_client_json": GoogleOAuthClientSettings().cadrumo_google_oauth_client_json}
    )
    monkeypatch.setattr(
        config, "settings_override", contextvars.ContextVar("synthetic_google_settings", default=effective)
    )


def use_absent_installation_client(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    """Make the installation carry no client file for the rest of the test."""
    use_installation_client_file(monkeypatch, directory / "google" / "oauth_client.json")
