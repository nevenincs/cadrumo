"""Live-gated OAuth Desktop integration tests.

Deselect unless `CADRUMO_LIVE_TESTS_ENABLED=1` AND the operator has
already pre-registered an `OAuthClient` in the secure store for the
named test profile (`AEAT_GOOGLE_LIVE_PROFILE`, default `live-test`).
The tests exercise three real-world paths against the operator's own
Google account:

1. `aeat config google login` — runs the actual loopback IP + PKCE
   consent flow. The first run requires manual operator interaction in
   the OS-default browser to grant the `drive.file` + `spreadsheets`
   scopes.
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

from .....tests.live_gate import requires_live_enabled
from .._oauth_flow import run_login_flow
from .._records import REQUIRED_SCOPES
from ..session_store import (
    delete_session,
    load_client,
    load_metadata,
    load_token,
    save_metadata,
    save_token,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]


def _live_profile() -> str:
    return os.environ.get("AEAT_GOOGLE_LIVE_PROFILE", "live-test")


def _require_live_and_client_registered() -> None:
    requires_live_enabled()
    profile = _live_profile()
    if load_client(profile) is None:
        pytest.fail(
            f"no OAuth client registered for profile {profile!r}; "
            f"run `aeat config google register --client-json <path> --profile {profile}` after live opt-in",
        )


def test_login_persists_token_and_metadata_against_real_google_endpoints() -> None:
    """End-to-end: real consent flow → persisted refresh token + metadata.

    The first run of this test prints a Google consent URL to stdout
    and waits for the operator to grant the requested scopes. Subsequent
    runs (within Google's session window) reuse the existing browser
    cookie and complete without manual interaction.
    """

    _require_live_and_client_registered()
    profile = _live_profile()
    client = load_client(profile)
    assert client is not None  # guard guarantees this; assert for the type checker

    token, metadata = run_login_flow(client, profile)
    save_token(profile, token)
    save_metadata(profile, metadata)

    assert token.refresh_token
    assert metadata.account_email
    for scope in REQUIRED_SCOPES:
        assert scope in metadata.granted_scopes, f"consent screen returned without granting {scope}"


def test_status_round_trips_persisted_metadata() -> None:
    """Reading back the persisted metadata after a live login matches what was saved."""

    _require_live_and_client_registered()
    profile = _live_profile()
    metadata = load_metadata(profile)
    if metadata is None:
        pytest.fail(
            "no persisted OAuth metadata; run the login test first or "
            f"`aeat config google login --profile {profile}` manually after live opt-in",
        )
    assert metadata.account_email
    assert metadata.reauth_required is False
    for scope in REQUIRED_SCOPES:
        assert scope in metadata.granted_scopes


def test_logout_clears_session_records_but_preserves_client() -> None:
    """`logout` must drop the refresh token + metadata while keeping the client.

    The operator can re-acquire a session via `login` without
    re-importing the Cloud Console JSON.
    """

    _require_live_and_client_registered()
    profile = _live_profile()
    client_before = load_client(profile)
    assert client_before is not None

    delete_session(profile)

    assert load_token(profile) is None, "refresh token must be cleared by logout"
    assert load_metadata(profile) is None, "OAuth metadata must be cleared by logout"
    client_after = load_client(profile)
    assert client_after is not None, "registered OAuth client must survive logout"
    assert client_after.client_id == client_before.client_id
