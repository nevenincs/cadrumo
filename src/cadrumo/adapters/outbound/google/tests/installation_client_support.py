"""Point the installation client reader at a synthetic file for one test.

The product reads its Google client from one installation location and offers
no way to supply another. A test therefore redirects the location itself and
leaves the reader, the envelope parsing and the record validation real.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .. import installation_client
from ..records import OAuthClient

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
    monkeypatch.setattr(installation_client, "installation_client_source", lambda: path)


def use_absent_installation_client(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    """Make the installation carry no client file for the rest of the test."""
    use_installation_client_file(monkeypatch, directory / "google" / "oauth_client.json")
