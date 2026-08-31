"""Tests for the service-account impersonation credential source.

The ADC-discovery-failure path is exercised against the REAL
``google.auth.default()`` resolver: pointing
``GOOGLE_APPLICATION_CREDENTIALS`` at a nonexistent file deterministically
reproduces the real ``DefaultCredentialsError`` Google's own library raises
on a host with no usable credential, giving a genuine (not simulated)
:class:`GoogleAuthAdcUnavailableError`.

The live token-mint path (a real network round-trip to Google's IAM
credentials endpoint, requiring a real GCP project + a provisioned target
service account) is gated behind
:func:`~tests.live_gate.requires_live_google_enabled` and is not part of
the default test run, per the project's live-external-call safety posture.

See Also:
    :class:`GoogleCredentialSourceKind`:
        Closed taxonomy that distinguishes OAuth Desktop from service-account
        impersonation.
    :class:`~adapters.outbound.google.GoogleImpersonationConfig`:
        Frozen target-principal and scope record under test.
    :func:`~adapters.outbound.google.resolve_impersonated_credentials`:
        ADC discovery and impersonation wrapper validated by these tests.
    :mod:`~entrypoints.cli._config._google_credential_source_cli`:
        CLI surface that persists the chosen credential source.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from .....core.google_credential_source import GoogleCredentialSourceKind
from .....tests.env_scope import scoped_env_var
from ..errors import GoogleAuthError
from ..impersonation import (
    GoogleAuthAdcStaleError,
    GoogleAuthAdcUnavailableError,
    GoogleAuthImpersonationRefusedError,
    GoogleCredentialSourceSelection,
    GoogleImpersonationConfig,
    _ensure_source_credential_is_fresh,
    describe_impersonation_target,
    resolve_impersonated_credentials,
)
from ..records import DRIVE_FILE_SCOPE, SHEETS_SCOPE

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

_TARGET_PRINCIPAL = "aeat-export@example-project.iam.gserviceaccount.com"


# ---------------------------------------------------------------------------
# GoogleCredentialSourceKind — closed taxonomy
# ---------------------------------------------------------------------------


def test_google_credential_source_kind_has_exactly_two_members() -> None:
    """The taxonomy is closed to the two supported credential mechanisms."""
    assert {member.value for member in GoogleCredentialSourceKind} == {
        "oauth_desktop",
        "service_account_impersonation",
    }


# ---------------------------------------------------------------------------
# GoogleImpersonationConfig — strict, frozen record contract
# ---------------------------------------------------------------------------


def test_config_defaults_to_data_access_scopes_only() -> None:
    """The default target_scopes excludes the OAuth identity scopes (openid/email).

    A service account has no signed-in-user identity to surface via those
    scopes; only the Drive/Sheets data-access scopes apply.
    """
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)
    assert config.target_scopes == (DRIVE_FILE_SCOPE, SHEETS_SCOPE)
    assert "openid" not in config.target_scopes
    assert "https://www.googleapis.com/auth/userinfo.email" not in config.target_scopes


def test_config_defaults_delegates_empty_and_subject_none() -> None:
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)
    assert config.delegates == ()
    assert config.subject is None
    assert config.lifetime_s == 3600


def test_config_is_frozen() -> None:
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)
    with pytest.raises(ValidationError, match="frozen"):
        config.target_principal = "someone-else@example-project.iam.gserviceaccount.com"


def test_config_forbids_extra_fields() -> None:
    data: dict[str, object] = {"target_principal": _TARGET_PRINCIPAL, "unexpected_field": "should not be accepted"}
    with pytest.raises(ValidationError, match="Extra"):
        GoogleImpersonationConfig.model_validate(data)


def test_config_rejects_blank_target_principal() -> None:
    with pytest.raises(ValidationError):
        GoogleImpersonationConfig(target_principal="   ")


def test_config_rejects_target_principal_without_at_sign() -> None:
    with pytest.raises(ValidationError):
        GoogleImpersonationConfig(target_principal="not-an-email")


def test_config_strips_whitespace_from_target_principal() -> None:
    config = GoogleImpersonationConfig(target_principal=f"  {_TARGET_PRINCIPAL}  ")
    assert config.target_principal == _TARGET_PRINCIPAL


def test_config_rejects_malformed_delegate() -> None:
    with pytest.raises(ValidationError):
        GoogleImpersonationConfig(
            target_principal=_TARGET_PRINCIPAL,
            delegates=("not-an-email",),
        )


def test_config_accepts_a_valid_delegate_chain() -> None:
    config = GoogleImpersonationConfig(
        target_principal=_TARGET_PRINCIPAL,
        delegates=("delegate-a@example-project.iam.gserviceaccount.com",),
    )
    assert config.delegates == ("delegate-a@example-project.iam.gserviceaccount.com",)


def test_config_rejects_lifetime_beyond_googles_one_hour_ceiling() -> None:
    with pytest.raises(ValidationError):
        GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL, lifetime_s=3601)


def test_config_rejects_non_positive_lifetime() -> None:
    with pytest.raises(ValidationError):
        GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL, lifetime_s=0)


def test_config_accepts_domain_wide_delegation_subject() -> None:
    config = GoogleImpersonationConfig(
        target_principal=_TARGET_PRINCIPAL,
        subject="taxpayer@example-workspace-domain.com",
    )
    assert config.subject == "taxpayer@example-workspace-domain.com"


# ---------------------------------------------------------------------------
# describe_impersonation_target — exact SA email surfacing
# ---------------------------------------------------------------------------


def test_describe_impersonation_target_returns_exact_principal() -> None:
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)
    assert describe_impersonation_target(config) == _TARGET_PRINCIPAL


# ---------------------------------------------------------------------------
# resolve_impersonated_credentials — real ADC discovery, no network mint
# ---------------------------------------------------------------------------


def test_resolve_refuses_when_adc_is_genuinely_unavailable() -> None:
    """A real ``google.auth.default()`` call against a bad ADC path.

    Pointing ``GOOGLE_APPLICATION_CREDENTIALS`` at a path that does not
    exist is the real mechanism Google's own library uses to report "no
    usable ADC source"; this is not a simulated failure.
    """
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)

    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        pytest.raises(GoogleAuthAdcUnavailableError) as raised,
    ):
        resolve_impersonated_credentials(config)

    assert isinstance(raised.value, GoogleAuthError)
    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}
    assert not hasattr(raised.value, "suggestion")


def test_resolve_refusal_names_the_exact_target_principal_for_a_different_config() -> None:
    """The refusal context always names the specific SA the caller tried to impersonate."""
    other_principal = "another-sa@other-project.iam.gserviceaccount.com"
    config = GoogleImpersonationConfig(target_principal=other_principal)

    with (
        scoped_env_var("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json"),
        pytest.raises(GoogleAuthAdcUnavailableError) as raised,
    ):
        resolve_impersonated_credentials(config)

    assert raised.value.context == {"target_principal": other_principal}


# ---------------------------------------------------------------------------
# _ensure_source_credential_is_fresh — ADC freshness auto-remediation
#
# Every credential built below is a real
# ``google.oauth2.credentials.Credentials`` instance; ``token_state`` and
# ``.refresh()`` are the real google-auth implementations. The "genuinely
# stale/unrefreshable" case reproduces a real, hermetic (no-network)
# ``RefreshError``: google-auth's own ``_perform_refresh_token`` raises it
# synchronously, before any HTTP request, when the credential lacks the
# fields (``refresh_token``/``token_uri``/``client_id``/``client_secret``)
# needed to even attempt a refresh — the exact shape of a dead/never-
# completed ADC grant. The "fresh" case is a real credential whose
# ``expiry`` is in the future, so ``token_state`` is ``FRESH`` and no
# refresh is attempted at all.
# ---------------------------------------------------------------------------

_TARGET_PRINCIPAL_FOR_FRESHNESS = "aeat-export@example-project.iam.gserviceaccount.com"

_A_REFRESH_TOKEN = "a-refresh-token"
_A_TOKEN_URI = "https://oauth2.googleapis.com/token"
_A_CLIENT_ID = "a-client-id"
_A_CLIENT_SECRET = "a-client-secret"
_A_TOKEN = "a-token"


def _build_real_oauth2_credential(
    *,
    expiry: datetime.datetime | None,
    refresh_token: str | None,
    token_uri: str | None,
    client_id: str | None,
    client_secret: str | None,
    token: str | None,
) -> Credentials:
    import google.oauth2.credentials

    return google.oauth2.credentials.Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=[DRIVE_FILE_SCOPE, SHEETS_SCOPE],
        expiry=expiry,
    )


def test_ensure_source_credential_is_fresh_leaves_a_fresh_credential_untouched() -> None:
    """A credential whose access token has not yet expired is not refreshed at all."""
    future = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(hours=1)
    credential = _build_real_oauth2_credential(
        expiry=future,
        refresh_token=_A_REFRESH_TOKEN,
        token_uri=_A_TOKEN_URI,
        client_id=_A_CLIENT_ID,
        client_secret=_A_CLIENT_SECRET,
        token=_A_TOKEN,
    )

    import google.auth.credentials

    assert credential.token_state is google.auth.credentials.TokenState.FRESH

    _ensure_source_credential_is_fresh(credential, target_principal=_TARGET_PRINCIPAL_FOR_FRESHNESS)

    # Untouched: still the same token, no refresh side effect occurred.
    assert credential.token == _A_TOKEN


def test_ensure_source_credential_is_fresh_raises_adc_stale_when_refresh_cannot_succeed() -> None:
    """A stale credential missing the fields needed to refresh raises GoogleAuthAdcStaleError.

    Reproduces the real, hermetic google-auth ``RefreshError`` raised by
    ``_perform_refresh_token`` when ``client_secret`` is absent — no network
    call occurs; the failure is synchronous field validation inside
    google-auth itself.
    """
    past = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(hours=2)
    credential = _build_real_oauth2_credential(
        expiry=past,
        refresh_token=_A_REFRESH_TOKEN,
        token_uri=_A_TOKEN_URI,
        client_id=_A_CLIENT_ID,
        client_secret=None,
        token=_A_TOKEN,
    )

    import google.auth.credentials

    assert credential.token_state is google.auth.credentials.TokenState.INVALID

    with pytest.raises(GoogleAuthAdcStaleError) as raised:
        _ensure_source_credential_is_fresh(credential, target_principal=_TARGET_PRINCIPAL_FOR_FRESHNESS)

    assert isinstance(raised.value, GoogleAuthError)
    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL_FOR_FRESHNESS}
    assert not hasattr(raised.value, "suggestion")


def test_ensure_source_credential_is_fresh_names_the_exact_target_principal() -> None:
    """The stale-ADC refusal always names the specific SA the caller was resolving for."""
    past = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) - datetime.timedelta(hours=2)
    credential = _build_real_oauth2_credential(
        expiry=past,
        refresh_token=_A_REFRESH_TOKEN,
        token_uri=_A_TOKEN_URI,
        client_id=_A_CLIENT_ID,
        client_secret=None,
        token=_A_TOKEN,
    )
    other_principal = "another-sa@other-project.iam.gserviceaccount.com"

    with pytest.raises(GoogleAuthAdcStaleError) as raised:
        _ensure_source_credential_is_fresh(credential, target_principal=other_principal)

    assert raised.value.context == {"target_principal": other_principal}


# ---------------------------------------------------------------------------
# Error taxonomy — bound error codes (registration contract)
# ---------------------------------------------------------------------------


def test_impersonation_errors_subclass_google_auth_error() -> None:
    assert issubclass(GoogleAuthAdcUnavailableError, GoogleAuthError)
    assert issubclass(GoogleAuthAdcStaleError, GoogleAuthError)
    assert issubclass(GoogleAuthImpersonationRefusedError, GoogleAuthError)


def test_impersonation_errors_carry_distinct_bound_error_codes() -> None:
    """Each leaf error type is bound to its own registered ErrorCode.

    Regression guard for the adapters error-registry table: if either class
    were left unregistered or accidentally shared a code with a sibling,
    `.code` would raise or collide.
    """
    adc_error = GoogleAuthAdcUnavailableError("adc missing")
    stale_error = GoogleAuthAdcStaleError("adc stale")
    refusal_error = GoogleAuthImpersonationRefusedError("iam refused")
    assert adc_error.code.code == "FAIL_GOOGLE_ADC_UNAVAILABLE"
    assert stale_error.code.code == "FAIL_GOOGLE_ADC_STALE"
    assert refusal_error.code.code == "REFUSED_GOOGLE_IMPERSONATION"
    assert len({adc_error.code.code, stale_error.code.code, refusal_error.code.code}) == 3


# ---------------------------------------------------------------------------
# GoogleCredentialSourceSelection — the per-profile persisted dispatch choice
# ---------------------------------------------------------------------------


def test_selection_defaults_to_oauth_desktop_with_no_impersonation_config() -> None:
    selection = GoogleCredentialSourceSelection()
    assert selection.kind is GoogleCredentialSourceKind.OAUTH_DESKTOP
    assert selection.impersonation is None


def test_selection_accepts_impersonation_kind_with_a_config() -> None:
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)
    selection = GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=config,
    )
    assert selection.kind is GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION
    assert selection.impersonation == config


def test_selection_rejects_impersonation_kind_without_a_config() -> None:
    with pytest.raises(ValidationError, match="impersonation must be set"):
        GoogleCredentialSourceSelection(kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION)


def test_selection_rejects_oauth_desktop_kind_with_a_config() -> None:
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)
    with pytest.raises(ValidationError, match="impersonation must be unset"):
        GoogleCredentialSourceSelection(
            kind=GoogleCredentialSourceKind.OAUTH_DESKTOP,
            impersonation=config,
        )


def test_selection_is_frozen() -> None:
    selection = GoogleCredentialSourceSelection()
    with pytest.raises(ValidationError, match="frozen"):
        selection.kind = GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION


def test_selection_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra"):
        GoogleCredentialSourceSelection.model_validate({"kind": "oauth_desktop", "unexpected_field": "x"})


def test_selection_json_roundtrip_preserves_impersonation_config() -> None:
    """A JSON roundtrip (as persisted/loaded by the session store) preserves every field."""
    config = GoogleImpersonationConfig(
        target_principal=_TARGET_PRINCIPAL,
        delegates=("delegate-a@example-project.iam.gserviceaccount.com",),
        subject="taxpayer@example-workspace-domain.com",
        lifetime_s=1800,
    )
    selection = GoogleCredentialSourceSelection(
        kind=GoogleCredentialSourceKind.SERVICE_ACCOUNT_IMPERSONATION,
        impersonation=config,
    )
    reloaded = GoogleCredentialSourceSelection.model_validate_json(selection.model_dump_json())
    assert reloaded == selection
