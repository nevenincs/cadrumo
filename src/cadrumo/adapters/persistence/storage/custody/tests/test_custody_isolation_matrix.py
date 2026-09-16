"""Cross-profile isolation: one profile's material can never open another.

The create-time guard (test_custody_transactions.py:687) refuses custody
material that names the wrong profile at registration. These cases prove the
UNLOCK, RECOVERY-RESET and RECOVERY-READ doors hold the same boundary:
profile A's password envelope and recovery code must refuse to open profile
B's capsule through the real authorities, not merely through a create-time
check.

Every case runs on a real isolated storage root with real supervised KDF
derivation; no mocks, no skips.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)

from ......adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ......application.user_profile.custody_ports import (
    profile_custody_recovery_envelope_path,
    unlock_profile_custody_password,
)
from ......application.user_profile.recovery_custody import (
    ProfileRecoveryError,
    enroll_profile_recovery,
    reset_profile_passphrase_with_recovery,
)
from ......application.user_profile.registration import register_profile_with_credentials
from ..capsule import (
    install_committed_profile_custody_recovery_envelope,
    load_committed_profile_password_material,
    load_committed_profile_recovery_material,
)
from ..errors import ProfileCustodyPasswordError, ProfileCustodyRecordError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_CREDENTIAL_A = "isolation-subject-a-operator-secret"
_CREDENTIAL_B = "isolation-subject-b-operator-secret"
_REPLACEMENT = "isolation-replacement-operator-secret"


def _register(label: str, passphrase: str) -> UUID:
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    outcome = register_profile_with_credentials(
        label=label,
        passphrase=passphrase,
        profile_create_context=_profile_create_context_for_test,
        profile_decode_context=_profile_decode_context_for_test,
    )
    return UUID(outcome.profile_id)


def _enroll(profile_id: UUID, passphrase: str) -> str:
    """Enrol recovery through the real door and return the code it handed over."""
    handed: list[str] = []
    enroll_profile_recovery(
        profile_id=profile_id,
        current_passphrase=passphrase,
        recovery_handover=lambda enrollment: handed.append(enrollment.recovery_key.code) or handed[-1],
    )
    return handed[0]


def test_one_profiles_password_envelope_cannot_unlock_another(tmp_path: Path) -> None:
    """A's envelope under B's passphrase refuses at the real unlock door."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_a = _register("Isolation A", _CREDENTIAL_A)
        _register("Isolation B", _CREDENTIAL_B)

        material = load_committed_profile_password_material(profile_a)
        with pytest.raises(ProfileCustodyPasswordError):
            unlock_profile_custody_password(material, password=_CREDENTIAL_B)


def test_one_profiles_recovery_code_cannot_reset_anothers_passphrase(tmp_path: Path) -> None:
    """A's code proves A's wrapper only; B's reset door refuses it and changes nothing.

    Both profiles are enrolled through the real door, so B's refusal is the
    proof failing against B's own wrapper rather than B having no wrapper at
    all. The same code then resets A, so the refusal is the code's identity,
    not a broken reset path.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_a = _register("Isolation A", _CREDENTIAL_A)
        code_a = _enroll(profile_a, _CREDENTIAL_A)
        profile_b = _register("Isolation B", _CREDENTIAL_B)
        _enroll(profile_b, _CREDENTIAL_B)
        envelope_b_before = load_committed_profile_password_material(profile_b).envelope.canonical_json_bytes()

        with pytest.raises(ProfileRecoveryError) as refused:
            reset_profile_passphrase_with_recovery(
                profile_id=profile_b,
                recovery_code=code_a,
                new_passphrase=_REPLACEMENT,
                new_passphrase_confirmation=_REPLACEMENT,
                profile_decode_context=_profile_decode_context_for_test,
            )
        assert refused.value.translated_message == "application.user_profile.errors.recovery_code_rejected"
        material_b = load_committed_profile_password_material(profile_b)
        assert material_b.envelope.canonical_json_bytes() == envelope_b_before
        assert unlock_profile_custody_password(material_b, password=_CREDENTIAL_B).dek is not None

        reset = reset_profile_passphrase_with_recovery(
            profile_id=profile_a,
            recovery_code=code_a,
            new_passphrase=_REPLACEMENT,
            new_passphrase_confirmation=_REPLACEMENT,
            profile_decode_context=_profile_decode_context_for_test,
        )
        assert reset.profile_id == str(profile_a)
        material_a = load_committed_profile_password_material(profile_a)
        assert unlock_profile_custody_password(material_a, password=_REPLACEMENT).dek is not None


def test_one_profiles_recovery_envelope_cannot_be_installed_or_read_as_anothers(tmp_path: Path) -> None:
    """A's committed wrapper names A; B's capsule refuses it at the write and at the read."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        profile_a = _register("Isolation A", _CREDENTIAL_A)
        _enroll(profile_a, _CREDENTIAL_A)
        profile_b = _register("Isolation B", _CREDENTIAL_B)
        wrapper_a = load_committed_profile_recovery_material(profile_a).recovery_envelope.canonical_json_bytes()
        capsule_b = load_committed_profile_password_material(profile_b).capsule_path
        wrapper_b_path = profile_custody_recovery_envelope_path(capsule_b)

        with pytest.raises(ProfileCustodyRecordError, match="names a different profile"):
            install_committed_profile_custody_recovery_envelope(profile_b, wrapper_a)
        assert not wrapper_b_path.exists()

        wrapper_b_path.write_bytes(wrapper_a)
        with pytest.raises(ProfileCustodyRecordError, match="does not belong to its committed capsule"):
            load_committed_profile_recovery_material(profile_b)
