"""Tests for the service-account impersonation credential source.

The ADC-discovery-failure path is exercised against the REAL
``google.auth.default()`` resolver (no mocks): pointing
``GOOGLE_APPLICATION_CREDENTIALS`` at a nonexistent file deterministically
reproduces the real ``DefaultCredentialsError`` Google's own library raises
on a host with no usable credential, giving a genuine (not simulated)
:class:`GoogleAuthAdcUnavailableError`.

The live token-mint path (a real network round-trip to Google's IAM
credentials endpoint, requiring a real GCP project + a provisioned target
service account) is gated behind
:func:`aeat.tests.live_gate.requires_live_google_enabled` and is not part of
the default test run, per the project's live-external-call safety posture.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....core import GoogleCredentialSourceKind
from .._errors import GoogleAuthError
from .._impersonation import (
    GoogleAuthAdcUnavailableError,
    GoogleAuthImpersonationRefusedError,
    GoogleImpersonationConfig,
    describe_impersonation_target,
    resolve_impersonated_credentials,
)
from .._records import DRIVE_FILE_SCOPE, SHEETS_SCOPE

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TARGET_PRINCIPAL = "aeat-export@example-project.iam.gserviceaccount.com"


# ---------------------------------------------------------------------------
# GoogleCredentialSourceKind — closed taxonomy
# ---------------------------------------------------------------------------


def test_google_credential_source_kind_has_exactly_two_members() -> None:
    """The taxonomy is closed to the two mechanisms this ADR distinguishes."""
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


def test_resolve_refuses_when_adc_is_genuinely_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real, unmocked ``google.auth.default()`` call against a bad ADC path.

    Pointing ``GOOGLE_APPLICATION_CREDENTIALS`` at a path that does not
    exist is the real mechanism Google's own library uses to report "no
    usable ADC source"; this is not a simulated failure.
    """
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json")
    config = GoogleImpersonationConfig(target_principal=_TARGET_PRINCIPAL)

    with pytest.raises(GoogleAuthAdcUnavailableError) as raised:
        resolve_impersonated_credentials(config)

    assert isinstance(raised.value, GoogleAuthError)
    assert raised.value.context == {"target_principal": _TARGET_PRINCIPAL}
    assert raised.value.suggestion == "gcloud auth application-default login"


def test_resolve_refusal_names_the_exact_target_principal_for_a_different_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal context always names the specific SA the caller tried to impersonate."""
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/nonexistent/path/does-not-exist.json")
    other_principal = "another-sa@other-project.iam.gserviceaccount.com"
    config = GoogleImpersonationConfig(target_principal=other_principal)

    with pytest.raises(GoogleAuthAdcUnavailableError) as raised:
        resolve_impersonated_credentials(config)

    assert raised.value.context == {"target_principal": other_principal}


# ---------------------------------------------------------------------------
# Error taxonomy — bound error codes (registration contract)
# ---------------------------------------------------------------------------


def test_impersonation_errors_subclass_google_auth_error() -> None:
    assert issubclass(GoogleAuthAdcUnavailableError, GoogleAuthError)
    assert issubclass(GoogleAuthImpersonationRefusedError, GoogleAuthError)


def test_impersonation_errors_carry_distinct_bound_error_codes() -> None:
    """Each leaf error type is bound to its own registered ErrorCode.

    Regression guard for the adapters error-registry table: if either class
    were left unregistered or accidentally shared a code with a sibling,
    `.code` would raise or collide.
    """
    adc_error = GoogleAuthAdcUnavailableError("adc missing")
    refusal_error = GoogleAuthImpersonationRefusedError("iam refused")
    assert adc_error.code.code == "FAIL_GOOGLE_ADC_UNAVAILABLE"
    assert refusal_error.code.code == "REFUSED_GOOGLE_IMPERSONATION"
    assert adc_error.code.code != refusal_error.code.code
