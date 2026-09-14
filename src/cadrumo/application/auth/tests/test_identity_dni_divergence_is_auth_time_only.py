"""Application-owned identity comparison policy.

The profile-persistence proof that a divergent pair can be written and read
back lives with the encrypted persistence adapter tests. These tests keep the
auth-time policy inward and feed it the application-owned credential value it
would receive after profile resolution.
"""

from __future__ import annotations

import pytest

from ....core.auth_provider import AuthProviderKind
from ..sessions import (
    AuthProfileIdentityMismatchError,
    ClaveCredentials,
    _assert_active_profile_identity_matches_provider,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "12345678Z"
_OTHER_TAX_ID = "00000001R"


def _credentials(kind: AuthProviderKind, *, dni_nie: str) -> ClaveCredentials:
    """Build the application credential value handed to the auth-time guard."""
    return ClaveCredentials(
        provider_kind=kind,
        dni_nie=dni_nie,
        profile_tax_id=_TAX_ID,
    )


@pytest.mark.parametrize("kind", [AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE])
def test_live_authentication_is_where_the_divergence_is_refused(kind: AuthProviderKind) -> None:
    """The auth-time guard refuses a credential for another taxpayer."""
    with pytest.raises(AuthProfileIdentityMismatchError) as raised:
        _assert_active_profile_identity_matches_provider(_credentials(kind, dni_nie=_OTHER_TAX_ID))
    assert raised.value.translated_message == "application.auth.sessions.errors.clave_identity_profile_mismatch"


@pytest.mark.parametrize("kind", [AuthProviderKind.CLAVE_MOVIL, AuthProviderKind.CLAVE_PERMANENTE])
def test_the_matching_profile_still_authenticates(kind: AuthProviderKind) -> None:
    """The positive control proves the guard does not refuse every profile."""
    expected_identity = _assert_active_profile_identity_matches_provider(_credentials(kind, dni_nie=_TAX_ID))
    assert expected_identity == _TAX_ID
