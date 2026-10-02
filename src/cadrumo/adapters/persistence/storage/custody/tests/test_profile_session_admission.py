"""Admission proves the requested profile against real password custody."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.login_session import (
    ProfileLoginOutcome,
    authenticate_profile_for_invocation,
    logout_active_profile,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.user_profile.session_admission import (
    ProfileCredentialRequestV1,
    ProfileSessionAdmissionState,
    admit_profile_session,
)
from cadrumo.core.errors.hierarchy import InternalInvariantError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.usefixtures("authority_operation"),
]

PROFILE_INPUT = "synthetic-admission-password"


@pytest.fixture
def profiles(tmp_path: Path) -> Iterator[tuple[str, str]]:
    create, decode = profile_authority_contexts()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        identifiers: list[str] = []
        for label in ("First admission profile", "Second admission profile"):
            result = register_profile_with_credentials(
                label=label,
                passphrase=PROFILE_INPUT,
                profile_create_context=create,
                profile_decode_context=decode,
            )
            identifiers.append(result.profile_id)
            logout_active_profile()
        try:
            yield identifiers[0], identifiers[1]
        finally:
            logout_active_profile()


@pytest.mark.parametrize("targeted", [True, False])
def test_credential_admission_proves_target_and_reuses_without_prompt(
    profiles: tuple[str, str], targeted: bool
) -> None:
    _, decode = profile_authority_contexts()
    calls: list[ProfileCredentialRequestV1] = []

    def credentials(request: ProfileCredentialRequestV1) -> ProfileLoginOutcome:
        calls.append(request)
        return authenticate_profile_for_invocation(
            name=profiles[0],
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=request.profile_decode_context,
        )

    result = admit_profile_session(
        bucket_id=profiles[0] if targeted else None, profile_decode_context=decode, credentials=credentials
    )
    assert result.state is ProfileSessionAdmissionState.AUTHENTICATED
    assert result.admitted and result.bucket_id == profiles[0]
    reused = admit_profile_session(bucket_id=profiles[0], profile_decode_context=decode, credentials=credentials)
    assert reused.state is ProfileSessionAdmissionState.ALREADY_ADMITTED
    assert len(calls) == 1


def test_credential_journey_cannot_substitute_another_profile(profiles: tuple[str, str]) -> None:
    _, decode = profile_authority_contexts()

    def credentials(request: ProfileCredentialRequestV1) -> ProfileLoginOutcome:
        assert request.bucket_id == profiles[0]
        return authenticate_profile_for_invocation(
            name=profiles[1],
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=request.profile_decode_context,
        )

    with pytest.raises(InternalInvariantError, match="different profile"):
        admit_profile_session(bucket_id=profiles[0], profile_decode_context=decode, credentials=credentials)


def test_credential_outcome_without_live_custody_is_not_admission(profiles: tuple[str, str]) -> None:
    _, decode = profile_authority_contexts()

    def credentials(request: ProfileCredentialRequestV1) -> ProfileLoginOutcome:
        outcome = authenticate_profile_for_invocation(
            name=profiles[0],
            passphrase_callback=lambda: PROFILE_INPUT,
            profile_decode_context=request.profile_decode_context,
        )
        logout_active_profile()
        return outcome

    with pytest.raises(InternalInvariantError, match="live session"):
        admit_profile_session(bucket_id=profiles[0], profile_decode_context=decode, credentials=credentials)
