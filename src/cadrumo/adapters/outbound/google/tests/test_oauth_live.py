"""Live-gated OAuth Desktop integration tests.

Deselect unless `CADRUMO_LIVE_TESTS_ENABLED=1` AND this checkout holds a
Google OAuth Desktop client file at the installation location. The named
test profile is `AEAT_GOOGLE_LIVE_PROFILE`, default `live-test`.
The tests exercise three real-world paths against the operator's own
Google account:

1. `aeat config google login` — runs the actual loopback IP + PKCE
   consent flow. The first run requires manual operator interaction in
   the OS-default browser to grant the `drive.file` scope.
2. `aeat config google status` — reads back the persisted records and
   confirms the account email + scopes round-tripped.
3. `aeat config google logout` — clears the token + metadata records
   and confirms a subsequent status reports `session_present=False`.

These tests intentionally do NOT submit to AEAT or write to Drive; the
goal is to verify the OAuth credential lifecycle against Google's
real endpoints. Test isolation is per-operator: the test profile name
defaults to `live-test` so the operator's primary `default` profile is
not disturbed.
"""

from __future__ import annotations

import os

import pytest

from .....core.resources.bundled_data import packaged_data
from .....tests.live_gate import requires_live_enabled
from ..errors import GoogleAuthClientMetadataUnavailableError
from ..installation_client import INSTALLATION_CLIENT_DATA_PARTS, load_installation_client
from ..oauth_flow import run_login_flow
from ..records import REQUIRED_SCOPES, OAuthClient
from ..session_store import (
    delete_session,
    load_metadata,
    load_token,
    save_metadata,
    save_token,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def _live_profile() -> str:
    return os.environ.get("AEAT_GOOGLE_LIVE_PROFILE", "live-test")


def _require_live_and_installation_client(monkeypatch: pytest.MonkeyPatch) -> OAuthClient:
    """Read the checkout's real client file, which every other test is kept away from."""
    requires_live_enabled()
    monkeypatch.setattr(
        "cadrumo.adapters.outbound.google.installation_client.installation_client_source",
        lambda: packaged_data(*INSTALLATION_CLIENT_DATA_PARTS),
    )
    try:
        return load_installation_client()
    except GoogleAuthClientMetadataUnavailableError:
        pytest.fail("this checkout holds no usable Google OAuth client file at its installation location")


def test_login_persists_token_and_metadata_against_real_google_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: real consent flow → persisted refresh token + metadata.

    The first run of this test prints a Google consent URL to stdout
    and waits for the operator to grant the requested scopes. Subsequent
    runs (within Google's session window) reuse the existing browser
    cookie and complete without manual interaction.
    """

    client = _require_live_and_installation_client(monkeypatch)
    profile = _live_profile()

    token, metadata = run_login_flow(client, profile)
    save_token(profile, token)
    save_metadata(profile, metadata)

    assert token.refresh_token
    assert metadata.account_email
    for scope in REQUIRED_SCOPES:
        assert scope in metadata.granted_scopes, f"consent screen returned without granting {scope}"


def test_status_round_trips_persisted_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading back the persisted metadata after a live login matches what was saved."""

    _require_live_and_installation_client(monkeypatch)
    profile = _live_profile()
    metadata = load_metadata(profile)
    if metadata is None:
        pytest.fail(
            "no persisted OAuth metadata; run the login test first or "
            f"`aeat config google login --profile {profile}` manually after live opt-in",
        )
    assert metadata.account_email
    for scope in REQUIRED_SCOPES:
        assert scope in metadata.granted_scopes


def test_logout_clears_session_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """`logout` must drop the refresh token and its metadata."""

    _require_live_and_installation_client(monkeypatch)
    profile = _live_profile()

    delete_session(profile)

    assert load_token(profile) is None, "refresh token must be cleared by logout"
    assert load_metadata(profile) is None, "OAuth metadata must be cleared by logout"
