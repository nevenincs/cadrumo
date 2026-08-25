"""Tests for Google OAuth flow failure translation."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....application.user_profile.capsule_record import ProfileRecordIntegrityError
from .....core.config import override_settings
from .....tests.secure_sql import isolated_runtime_profile, reset_secure_object_store
from ..errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthNetworkError,
    GoogleAuthNonInteractiveError,
    GoogleAuthProfileUnboundError,
)
from .._oauth_flow import (
    _raise_local_server_error,
    credentials_to_records,
    require_interactive_terminal,
    resolve_active_tax_id,
    run_login_flow,
)
from .._records import REQUIRED_SCOPES, OAuthClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _valid_oauth_client() -> OAuthClient:
    return OAuthClient(
        client_id="1234.apps.googleusercontent.com",
        client_secret="GOCSPX-deadbeef",
        project_id="test-project-12345",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://localhost",),
    )


def test_credentials_to_records_preserves_utc_metadata_projection() -> None:
    """The direct OAuth-flow handoff preserves canonical metadata instants."""

    issued_at = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    _token, metadata = credentials_to_records(
        refresh_token="1//refresh-token",
        token_uri="https://oauth2.googleapis.com/token",
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=issued_at,
    )

    assert metadata.issued_at == issued_at
    assert metadata.last_refresh_at == issued_at
    assert metadata.model_dump(mode="json")["issued_at"] == "2026-05-26T09:00:00Z"
    assert metadata.model_dump(mode="json")["last_refresh_at"] == "2026-05-26T09:00:00Z"


def test_credentials_to_records_refuses_whitespace_only_refresh_token() -> None:
    """The consent-flow boundary refuses a refresh value that cannot authenticate."""

    with pytest.raises(ValidationError, match="non-whitespace"):
        credentials_to_records(
            refresh_token=" \t\r\n",
            token_uri="https://oauth2.googleapis.com/token",
            account_email="operator@example.com",
            granted_scopes=REQUIRED_SCOPES,
            issued_at=datetime(2026, 5, 26, 9, 0, tzinfo=UTC),
        )


def test_local_server_error_classifier_routes_browser_failures() -> None:
    upstream = RuntimeError("webbrowser launcher failed")

    with pytest.raises(GoogleAuthBrowserOpenError) as raised:
        _raise_local_server_error(upstream)

    assert raised.value.__cause__ is upstream
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.browser_launcher_refused"


def test_local_server_error_classifier_routes_network_failures() -> None:
    upstream = RuntimeError("transport connection refused")

    with pytest.raises(GoogleAuthNetworkError) as raised:
        _raise_local_server_error(upstream)

    assert raised.value.__cause__ is upstream
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.endpoint_unreachable"


def test_local_server_error_classifier_wraps_unclassified_failures() -> None:
    upstream = RuntimeError("access denied")

    with pytest.raises(GoogleAuthNetworkError) as raised:
        _raise_local_server_error(upstream)

    assert raised.value.__cause__ is upstream
    assert raised.value.context == {"error_type": "RuntimeError"}


def test_resolve_active_tax_id_refuses_missing_profile_bucket(tmp_path: Path) -> None:
    with (
        override_settings(
            cadrumo_active_profile="missing-profile",
            cadrumo_local_storage_root=tmp_path,
            cadrumo_secret_store_backend="unsecured",
        ),
        pytest.raises(GoogleAuthProfileUnboundError) as raised,
    ):
        resolve_active_tax_id("missing-profile")

    assert raised.value.context == {
        "profile": "missing-profile",
        "reason": "profile_bucket_manifest_missing",
    }
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.profile_state_unresolved"
    assert not hasattr(raised.value, "suggestion")


# Source for a child process that drives the interactive-terminal guard with
# a genuinely non-interactive (piped, non-TTY) stdin. Run as a subprocess —
# not in-process — so the test exercises the actual interpreter `stdin` a
# non-interactive operator invocation has, with no monkeypatching of
# `sys.stdin`. The audit-M19 bug was that the login path blocked forever on
# the loopback consent receiver; the guard must refuse fast instead. The
# guard is the gate that immediately precedes that blocking receiver in
# `run_login_flow`, and it carries no profile/network dependency, so it is
# the honest unit to drive here.
_LOGIN_PROBE = textwrap.dedent(
    """
    import sys

    from cadrumo.adapters.outbound.google._oauth_flow import require_interactive_terminal
    from cadrumo.adapters.outbound.google.errors import GoogleAuthNonInteractiveError

    if sys.stdin.isatty():
        print("UNEXPECTED_TTY")
    else:
        try:
            require_interactive_terminal()
        except GoogleAuthNonInteractiveError as exc:
            print("REFUSED " + exc.translated_message)
        else:
            print("BLOCKED_OR_PROCEEDED")
    """
)


def test_login_flow_refuses_fast_without_a_controlling_terminal() -> None:
    """The OAuth login guard must refuse, not hang, when stdin is not a TTY.

    Regression for audit M19: `aeat config google login` blocked forever
    in a non-interactive shell because the loopback consent receiver
    (`run_local_server`) waited for a browser redirect that no operator
    could complete. `require_interactive_terminal` is the gate `run_login_flow`
    runs immediately before that blocking receiver. The child process is
    given a real pipe for stdin (`isatty()` is False) and a hard wall-clock
    `timeout`; before the fix there was no guard and the login path blocked,
    so a regression that removes the guard and restores the blocking
    behaviour trips the timeout and fails the test loudly.
    """

    completed = subprocess.run(
        [sys.executable, "-c", _LOGIN_PROBE],
        stdin=subprocess.PIPE,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    assert "REFUSED adapters.google.oauth_flow.errors.non_interactive" in completed.stdout, completed.stdout
    assert "BLOCKED_OR_PROCEEDED" not in completed.stdout
    assert "UNEXPECTED_TTY" not in completed.stdout


def test_interactive_terminal_guard_refuses_a_non_tty_stdin() -> None:
    """`require_interactive_terminal` refuses (does not block) under a non-TTY stdin.

    The pytest runner attaches a non-TTY stdin, so this exercises the
    guard against the real interpreter state a non-interactive invocation
    has. The refusal carries the typed translation and factual reason that
    identifies the interactive-terminal prerequisite — the contract that
    replaces the audit-M19 silent hang.
    """

    with pytest.raises(GoogleAuthNonInteractiveError) as raised:
        require_interactive_terminal()

    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.non_interactive"
    assert raised.value.context == {"reason": "stdin_not_a_tty"}
    assert not hasattr(raised.value, "suggestion")


def test_login_flow_refuses_unavailable_profile_record_session_before_oauth_network(tmp_path: Path) -> None:
    """A committed profile without a live record session reaches the typed refusal."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1f54e86d-e8dd-4327-8651-cc6d9a44843c") as profile:
        storage_root = profile.storage_root
        profile_id = profile.bucket_id

    with (
        override_settings(
            cadrumo_local_storage_root=storage_root,
            cadrumo_active_profile=profile_id,
            cadrumo_secret_store_backend="unsecured",
        ),
        pytest.raises(GoogleAuthProfileUnboundError) as raised,
    ):
        run_login_flow(_valid_oauth_client(), profile_id)

    assert raised.value.context == {
        "profile": "1f54e86d-e8dd-4327-8651-cc6d9a44843c",
        "bucket_id": "1f54e86d-e8dd-4327-8651-cc6d9a44843c",
        "reason": "profile_record_session_unavailable",
    }
    assert raised.value.translated_message == "adapters.google.oauth_flow.errors.profile_state_unresolved"
    assert not hasattr(raised.value, "suggestion")


def test_login_flow_propagates_zero_row_profile_capsule_corruption_before_oauth_network(tmp_path: Path) -> None:
    """Corrupt profile rows are integrity failures, never downgraded to an auth refusal."""
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id="1f54e86d-e8dd-4327-8651-cc6d9a44843c") as profile,
        override_settings(cadrumo_secret_store_backend="unsecured"),
        pytest.raises(ProfileRecordIntegrityError) as raised,
    ):
        reset_secure_object_store(profile.repository)
        run_login_flow(_valid_oauth_client(), profile.bucket_id)

    assert str(raised.value) == "profile capsule must contain exactly one current record row; it holds 0"
    assert not isinstance(raised.value, GoogleAuthProfileUnboundError)
