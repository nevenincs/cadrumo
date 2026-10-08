"""Keep developer-tool tests independent of publisher credentials."""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def synthetic_publisher_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override local dotenv and inherited CI publisher configuration in every test."""
    monkeypatch.setenv(
        "CADRUMO_GOOGLE_OAUTH_CLIENT_JSON",
        json.dumps(
            {
                "installed": {
                    "client_id": "synthetic-dev-test-client",
                    "client_secret": "synthetic-dev-test-secret",
                    "project_id": "synthetic-dev-test-project",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
    )
