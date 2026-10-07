"""A stored sign-in that can no longer be used is a typed refusal, never a network failure."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.discovery import build

from .....core.time.clock import now
from ....persistence.storage.secure_object_namespaces import (
    GOOGLE_OAUTH_METADATA_NAMESPACE,
    GOOGLE_OAUTH_TOKEN_NAMESPACE,
)
from ....persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...storage.errors import OutboundStorageNetworkError
from ..api import RequestRetryPolicy, execute_request
from ..errors import GoogleAuthPreconditionCondition, GoogleAuthSignInRequiredError
from ..records import REQUIRED_SCOPES, OAuthMetadata, OAuthToken
from ..sign_in_state import ended_grant_refusal, load_sign_in_record, load_token_minted_for
from . import session_records as google_session_records
from .installation_client_support import SYNTHETIC_CLIENT_ID, synthetic_installation_client
from .token_endpoint_server import (
    ENDED_GRANT_RESPONSE,
    SYNTHETIC_REFRESH_VALUE,
    credentials_needing_refresh,
    token_endpoint,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROFILE = "7b0f6f2e-5a43-4a0e-9d57-1f6f3b1c2d44"
_EXCHANGE_URI = "https://oauth2.googleapis.com/token"


def _token(client_id: str) -> OAuthToken:
    return OAuthToken(refresh_token=SYNTHETIC_REFRESH_VALUE, client_id=client_id, token_uri=_EXCHANGE_URI)


def _assert_sign_in_required(
    error: GoogleAuthSignInRequiredError,
    *,
    condition: GoogleAuthPreconditionCondition,
    facts: dict[str, bool],
) -> None:
    assert error.code.code == "REFUSED_GOOGLE_SIGN_IN_REQUIRED"
    assert error.code.category.value == "REFUSED"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == condition.value
    assert dict(verdict.evidence[0].values) == facts
    assert SYNTHETIC_REFRESH_VALUE not in "\n".join((str(error), repr(error.context)))


def test_a_profile_that_never_signed_in_has_no_token(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        assert load_token_minted_for(_PROFILE, synthetic_installation_client()) is None


def test_a_token_is_returned_to_the_client_that_minted_it(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        google_session_records.save_token(_PROFILE, _token(SYNTHETIC_CLIENT_ID))

        assert load_token_minted_for(_PROFILE, synthetic_installation_client()) == _token(SYNTHETIC_CLIENT_ID)


def test_a_token_minted_for_another_client_is_never_handed_out(tmp_path: Path) -> None:
    """A development client's token cannot be used by an installation with the production client."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        google_session_records.save_token(_PROFILE, _token("development-client.apps.googleusercontent.com"))

        with pytest.raises(GoogleAuthSignInRequiredError) as refused:
            load_token_minted_for(_PROFILE, synthetic_installation_client())

    _assert_sign_in_required(
        refused.value,
        condition=GoogleAuthPreconditionCondition.SIGN_IN_CLIENT_BOUND,
        facts={"stored_token_readable": True, "token_client_matches": False},
    )


def test_a_token_stored_without_a_client_requires_a_new_sign_in(tmp_path: Path) -> None:
    """The earlier stored shape is not read: there is no compatibility path for it."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile:
        profile.repository.save(
            namespace=GOOGLE_OAUTH_TOKEN_NAMESPACE.namespace,
            object_key=_PROFILE,
            classification=GOOGLE_OAUTH_TOKEN_NAMESPACE.sensitivity,
            schema_version=GOOGLE_OAUTH_TOKEN_NAMESPACE.schema_version,
            written_at=now(),
            payload=json.dumps({"refresh_token": SYNTHETIC_REFRESH_VALUE, "token_uri": _EXCHANGE_URI}).encode("utf-8"),
        )

        with pytest.raises(GoogleAuthSignInRequiredError) as refused:
            load_token_minted_for(_PROFILE, synthetic_installation_client())

    _assert_sign_in_required(
        refused.value,
        condition=GoogleAuthPreconditionCondition.SIGN_IN_CLIENT_BOUND,
        facts={"stored_token_readable": False},
    )
    assert refused.value.__cause__ is None and refused.value.__suppress_context__


def test_a_recorded_sign_in_is_read_back_and_its_absence_is_not_an_error(tmp_path: Path) -> None:
    recorded = OAuthMetadata(account_email="operator@example.invalid", granted_scopes=REQUIRED_SCOPES, issued_at=now())
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE):
        assert load_sign_in_record(_PROFILE) is None
        google_session_records.save_metadata(_PROFILE, recorded)

        assert load_sign_in_record(_PROFILE) == recorded


def test_a_sign_in_record_of_the_earlier_shape_requires_a_new_sign_in(tmp_path: Path) -> None:
    """A record carrying the removed refresh fields is refused, so status cannot show stale state."""
    earlier = {
        "account_email": "operator@example.invalid",
        "granted_scopes": list(REQUIRED_SCOPES),
        "issued_at": "2026-05-26T09:00:00Z",
        "last_refresh_at": "2026-05-26T09:00:00Z",
        "reauth_required": False,
    }
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE) as profile:
        profile.repository.save(
            namespace=GOOGLE_OAUTH_METADATA_NAMESPACE.namespace,
            object_key=_PROFILE,
            classification=GOOGLE_OAUTH_METADATA_NAMESPACE.sensitivity,
            schema_version=GOOGLE_OAUTH_METADATA_NAMESPACE.schema_version,
            written_at=now(),
            payload=json.dumps(earlier).encode("utf-8"),
        )

        with pytest.raises(GoogleAuthSignInRequiredError) as refused:
            load_sign_in_record(_PROFILE)

    _assert_sign_in_required(
        refused.value,
        condition=GoogleAuthPreconditionCondition.SIGN_IN_RECORD_READABLE,
        facts={"sign_in_record_readable": False},
    )


@pytest.mark.parametrize(
    "error",
    (
        pytest.param(RefreshError("invalid_client: The OAuth client was not found.", {"error": "invalid_client"})),
        pytest.param(RefreshError("the refresh response carried no body")),
        pytest.param(RefreshError("invalid_grant: named only in the message", "invalid_grant")),
        pytest.param(TransportError("connection refused")),
        pytest.param(ValueError("invalid_grant")),
    ),
    ids=("another-oauth-error", "no-response-body", "non-mapping-body", "transport-failure", "unrelated-error"),
)
def test_only_googles_ended_grant_verdict_is_classified_as_sign_in_required(error: Exception) -> None:
    assert ended_grant_refusal(error, action="drive.files.list") is None


@pytest.mark.parametrize("retry", (RequestRetryPolicy.SINGLE_ATTEMPT, RequestRetryPolicy.REPLAY_SAFE))
def test_a_request_whose_refresh_google_answers_with_an_ended_grant_is_sign_in_required(
    retry: RequestRetryPolicy,
) -> None:
    """The real client library refreshes before sending, so the Drive request never leaves."""
    with token_endpoint(status=400, body=ENDED_GRANT_RESPONSE) as endpoint:
        drive = build(
            "drive",
            "v3",
            credentials=credentials_needing_refresh(endpoint.url, client_id=SYNTHETIC_CLIENT_ID),
            cache_discovery=False,
        )

        with pytest.raises(GoogleAuthSignInRequiredError) as refused:
            execute_request(drive.files().list(q="trashed = false"), action="drive.files.list", retry=retry)

    _assert_sign_in_required(
        refused.value,
        condition=GoogleAuthPreconditionCondition.GRANT_ACTIVE,
        facts={"grant_active": False},
    )
    # A write that was never sent is not reported as possibly applied.
    assert refused.value.context == {"action": "drive.files.list"}
    assert isinstance(refused.value.__cause__, RefreshError)
    assert [request["grant_type"] for request in endpoint.grant_requests] == [["refresh_token"]]


def test_any_other_refresh_failure_stays_a_network_failure() -> None:
    """Only the ended grant has a remedy the operator can apply by signing in."""
    with token_endpoint(status=401, body={"error": "invalid_client"}) as endpoint:
        drive = build(
            "drive",
            "v3",
            credentials=credentials_needing_refresh(endpoint.url, client_id=SYNTHETIC_CLIENT_ID),
            cache_discovery=False,
        )

        with pytest.raises(OutboundStorageNetworkError):
            execute_request(
                drive.files().list(q="trashed = false"),
                action="drive.files.list",
                retry=RequestRetryPolicy.SINGLE_ATTEMPT,
            )
