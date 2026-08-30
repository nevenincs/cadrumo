"""Live-gated service-account impersonation integration test.

Deselected unless `CADRUMO_LIVE_TESTS_GOOGLE=1` AND the operator has provisioned
a real target service account and granted the ADC identity
`roles/iam.serviceAccountTokenCreator` on it. This is the live counterpart to
the hermetic tests in `test_impersonation.py` (which prove the ADC-discovery
failure path and every typed-record contract with no network access).

Required environment for a live run:

- `CADRUMO_LIVE_TESTS_GOOGLE=1` — the opt-in itself.
- `AEAT_IMPERSONATION_TARGET_PRINCIPAL` — the fully-qualified service-account
  email to impersonate (e.g.
  `aeat-export@my-project.iam.gserviceaccount.com`). The ADC identity
  resolved by `google.auth.default()` on this host (via
  `GOOGLE_APPLICATION_CREDENTIALS`, `gcloud auth application-default login`,
  or an attached workload identity) must already hold
  `roles/iam.serviceAccountTokenCreator` on this principal.

This test performs a real network round-trip against Google's IAM
credentials endpoint to mint a short-lived impersonated access token. It
does not write to Drive or Sheets, and it never contacts AEAT. Nothing this
test resolves is persisted; the minted token lives only in process memory
for the duration of the test.

See Also:
    `adapters.outbound.google.impersonation.resolve_impersonated_credentials`
        The resolver under test.
"""

from __future__ import annotations

import os

import pytest

from .....tests.live_gate import requires_live_google_enabled
from ..impersonation import (
    GoogleImpersonationConfig,
    describe_impersonation_target,
    resolve_impersonated_credentials,
)

pytestmark = [pytest.mark.aeat_live, pytest.mark.hex_outbound_adapter]

_TARGET_PRINCIPAL_ENV_VAR = "AEAT_IMPERSONATION_TARGET_PRINCIPAL"


def _require_live_and_target_principal_configured() -> str:
    requires_live_google_enabled()
    target_principal = os.environ.get(_TARGET_PRINCIPAL_ENV_VAR, "")
    if not target_principal:
        pytest.fail(
            f"{_TARGET_PRINCIPAL_ENV_VAR} is not set; export the target service-account "
            "email to impersonate (the ADC identity on this host must already hold "
            "roles/iam.serviceAccountTokenCreator on it) after live opt-in",
        )
    return target_principal


def test_resolve_impersonated_credentials_mints_a_real_token_for_a_provisioned_sa() -> None:
    """A correctly-provisioned target SA yields a fresh, valid impersonated token.

    Exercises the real `google.auth.default()` ADC discovery, the real
    `google.auth.impersonated_credentials.Credentials` wrapping, and a real
    `.refresh()` network round-trip against Google's IAM credentials
    endpoint. A misconfigured grant (missing Token Creator role, wrong
    scopes) fails this test with the resolver's own typed refusal rather
    than a bare network error, proving the operator-facing remediation
    message is accurate against a real IAM response.
    """
    target_principal = _require_live_and_target_principal_configured()
    config = GoogleImpersonationConfig(target_principal=target_principal)

    assert describe_impersonation_target(config) == target_principal

    credentials = resolve_impersonated_credentials(config)

    assert credentials.token
    assert credentials.valid
    assert credentials.expired is False
