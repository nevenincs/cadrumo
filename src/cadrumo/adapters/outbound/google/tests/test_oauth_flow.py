"""Tests for Google OAuth flow failure translation."""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlsplit

import pytest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from pydantic import ValidationError

from .....application.user_profile.capsule_record import ProfileRecordIntegrityError
from .....core.config import override_settings
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile, reset_secure_object_store
from .. import oauth_flow
from ..errors import (
    GoogleAuthBrowserOpenError,
    GoogleAuthNetworkError,
    GoogleAuthNonInteractiveError,
    GoogleAuthPreconditionCondition,
    GoogleAuthProfileUnboundError,
    GoogleAuthValidationError,
)
from ..oauth_flow import (
    _LOOPBACK_HOST,
    _oauth_loopback_client_config,
    _oauth_loopback_records,
    _raise_local_server_error,
    credentials_to_records,
    require_interactive_terminal,
    require_resolvable_profile_record,
    run_login_flow,
)
from ..records import REQUIRED_SCOPES, OAuthClient

if TYPE_CHECKING:
    from google_auth_oauthlib.flow import OAuthCredentials

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


def test_consent_url_requests_exactly_the_three_non_sensitive_scopes() -> None:
    """The real installed-app flow, given the stored client, asks Google for no other scope."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(
        _oauth_loopback_client_config(_valid_oauth_client()), scopes=list(REQUIRED_SCOPES)
    )
    flow.redirect_uri = "http://127.0.0.1:1/"
    url, _state = flow.authorization_url()

    requested = parse_qs(urlsplit(url).query)["scope"]
    assert requested == [
        "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive.file"
    ]


def test_credentials_to_records_preserves_utc_metadata_projection() -> None:
    """The direct OAuth-flow handoff preserves canonical metadata instants."""

    issued_at = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    token, metadata = credentials_to_records(
        refresh_token="1//refresh-token",
        client_id="desktop-client.apps.googleusercontent.com",
        token_uri="https://oauth2.googleapis.com/token",
        account_email="operator@example.com",
        granted_scopes=REQUIRED_SCOPES,
        issued_at=issued_at,
    )

    # The token records the client the consent was granted to.
    assert token.client_id == "desktop-client.apps.googleusercontent.com"
    assert metadata.issued_at == issued_at
    assert metadata.last_refresh_at == issued_at
    assert metadata.model_dump(mode="json")["issued_at"] == "2026-05-26T09:00:00Z"
    assert metadata.model_dump(mode="json")["last_refresh_at"] == "2026-05-26T09:00:00Z"


def test_credentials_to_records_refuses_whitespace_only_refresh_token() -> None:
    """The consent-flow boundary refuses a refresh value that cannot authenticate."""

    with pytest.raises(ValidationError, match="non-whitespace"):
        credentials_to_records(
            refresh_token=" \t\r\n",
            client_id="desktop-client.apps.googleusercontent.com",
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


def test_profile_record_guard_refuses_a_missing_profile_bucket_pointer(tmp_path: Path) -> None:
    with (
        override_settings(
            cadrumo_active_profile="missing-profile",
            cadrumo_local_storage_root=tmp_path,
        ),
        pytest.raises(GoogleAuthProfileUnboundError) as raised,
    ):
        require_resolvable_profile_record("missing-profile")

    assert raised.value.context == {
        "profile": "missing-profile",
        "reason": "profile_bucket_pointer_missing",
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

    from cadrumo.adapters.outbound.google.oauth_flow import require_interactive_terminal
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
        pytest.raises(ProfileRecordIntegrityError) as raised,
    ):
        reset_secure_object_store(profile.repository)
        run_login_flow(_valid_oauth_client(), profile.bucket_id)

    assert str(raised.value) == "profile capsule must contain exactly one current record row; it holds 0"
    assert not isinstance(raised.value, GoogleAuthProfileUnboundError)


@pytest.mark.parametrize("refresh_token", (None, "", " \t"), ids=("absent", "empty", "blank"))
def test_a_consent_that_issues_no_refresh_token_is_refused_before_identity_is_read(refresh_token: str | None) -> None:
    """Nothing is stored for a sign-in that would stop working when its access token lapses."""
    credentials = Credentials(
        token="synthetic-access-value",
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id="1234.apps.googleusercontent.com",
        client_secret="GOCSPX-deadbeef",
    )

    with pytest.raises(GoogleAuthValidationError) as refused:
        # CAST-RATIONALE-thirdparty: the real credentials class leaves the attributes the
        # flow's credential protocol names unannotated, so it does not satisfy it structurally.
        _oauth_loopback_records(
            cast("OAuthCredentials", credentials), _valid_oauth_client(), before_handoff=None, acknowledged=None
        )

    error = refused.value
    assert error.code.code == "REFUSED_GOOGLE_VALIDATION"
    assert error.translated_message == "adapters.google.oauth_flow.errors.refresh_token_missing"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == GoogleAuthPreconditionCondition.REFRESH_CREDENTIAL_ISSUED.value
    assert dict(verdict.evidence[0].values) == {"refresh_token_issued": False}
    assert "synthetic-access-value" not in str(error)


def test_consent_redirect_is_received_on_the_loopback_ip_literal() -> None:
    """The listener binds, and Google redirects to, 127.0.0.1 rather than a resolved host name."""
    assert _LOOPBACK_HOST == "127.0.0.1"
    consent_calls = [
        node
        for node in ast.walk(ast.parse(inspect.getsource(oauth_flow)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run_local_server"
    ]
    assert len(consent_calls) == 2
    for call in consent_calls:
        hosts = [keyword.value for keyword in call.keywords if keyword.arg == "host"]
        assert [ast.unparse(host) for host in hosts] == ["_LOOPBACK_HOST"]

    # The real flow, given that host, listens there and names it in the redirect.
    flow = InstalledAppFlow.from_client_config(
        _oauth_loopback_client_config(_valid_oauth_client()), scopes=list(REQUIRED_SCOPES)
    )
    with pytest.raises(WSGITimeoutError):
        flow.run_local_server(
            host=_LOOPBACK_HOST,
            port=0,
            open_browser=False,
            authorization_prompt_message=None,
            timeout_seconds=0.2,
        )
    assert flow.redirect_uri is not None
    redirect = urlsplit(flow.redirect_uri)
    assert redirect.scheme == "http" and redirect.hostname == "127.0.0.1" and redirect.port
