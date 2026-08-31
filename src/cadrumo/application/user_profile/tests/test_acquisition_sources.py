"""Real proofs for the acquisition-source credential posture contract.

Pure unit tests: `resolve_acquisition_source_credential_postures` takes a
real `AuthState` and returns a real posture per declared source. No mocks
-- `AuthState` is the actual persisted workflow-state model, not a stand-in.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ...auth.models import AuthState
from ..acquisition_sources import (
    ProfileAcquisitionSourceKey,
    known_profile_acquisition_sources,
    resolve_acquisition_source_credential_postures,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_every_known_source_requires_aeat_authentication_today() -> None:
    """Both declared sources route through the shared AEAT live-read gate."""
    sources = known_profile_acquisition_sources()
    assert {source.key for source in sources} == {
        ProfileAcquisitionSourceKey.CENSAL_REVIEW,
        ProfileAcquisitionSourceKey.FILED_HISTORY,
    }
    assert all(source.requires_aeat_authentication for source in sources)


def test_with_no_provider_configured_every_source_reports_the_credential_missing() -> None:
    postures = resolve_acquisition_source_credential_postures(AuthState())

    assert len(postures) == 2
    for posture in postures:
        assert posture.requires_aeat_authentication is True
        assert posture.credential_held is False
        assert posture.provider_id is None


def test_with_an_authenticated_provider_every_source_reports_the_credential_held() -> None:
    auth = AuthState(provider="certificate", authenticated_at=datetime.now(UTC))

    postures = resolve_acquisition_source_credential_postures(auth)

    for posture in postures:
        assert posture.credential_held is True
        assert posture.provider_id == "certificate"


def test_a_configured_but_never_authenticated_provider_still_reports_missing() -> None:
    """`provider` alone (configured, never used) is not the same fact as `authenticated_at`."""
    auth = AuthState(provider="certificate", authenticated_at=None)

    postures = resolve_acquisition_source_credential_postures(auth)

    assert all(posture.credential_held is False for posture in postures)
