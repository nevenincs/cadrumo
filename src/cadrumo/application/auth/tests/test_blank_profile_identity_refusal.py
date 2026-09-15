"""Application-owned refusal policy for a cleared profile identity.

The profile-capsule setup is persistence integration and is owned by the
adapter test tree. These tests exercise the inward guard with its application
facts directly, including the deliberate incomplete-profile exemption.
"""

from __future__ import annotations

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)

from ....core.auth_provider import AuthProviderKind
from ....domain.user_profile.values import ProfileSetupState
from ..sessions import (
    AuthProfileIdentityMismatchError,
    ClaveAuthFacts,
    _assert_profile_identity_available_for_deferred_check,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "12345678Z"


def _complete_profile_without_identity() -> ClaveAuthFacts:
    """Return the application facts for a completed record whose id was cleared."""
    return ClaveAuthFacts(profile_setup_state=ProfileSetupState.COMPLETE)


@pytest.mark.parametrize("kind", list(AuthProviderKind))
def test_no_provider_binds_a_session_against_a_blank_profile_identity(kind: AuthProviderKind) -> None:
    """Every provider sweep reaches the same cleared-identity refusal policy."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    del kind
    with pytest.raises(AuthProfileIdentityMismatchError):
        _assert_profile_identity_available_for_deferred_check(
            _complete_profile_without_identity(), profile_decode_context=_profile_decode_context_for_test
        )


def test_a_profile_still_in_setup_may_still_authenticate() -> None:
    """An incomplete profile may authenticate while it records its identity."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    facts = ClaveAuthFacts(profile_setup_state=ProfileSetupState.INCOMPLETE)
    _assert_profile_identity_available_for_deferred_check(
        facts, profile_decode_context=_profile_decode_context_for_test
    )


def test_a_recorded_identity_is_unaffected() -> None:
    """A complete profile carrying its identity is not refused by this guard."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    facts = ClaveAuthFacts(tax_id=_TAX_ID, profile_setup_state=ProfileSetupState.COMPLETE)
    _assert_profile_identity_available_for_deferred_check(
        facts, profile_decode_context=_profile_decode_context_for_test
    )
