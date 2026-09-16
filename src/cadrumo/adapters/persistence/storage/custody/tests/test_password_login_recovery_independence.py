"""Normal password login never reads recovery custody material."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.custody_ports import profile_custody_recovery_envelope_path
from cadrumo.application.user_profile.login_session import login_profile, logout_active_profile
from cadrumo.application.user_profile.recovery_custody import enroll_profile_recovery
from cadrumo.application.user_profile.registration import register_profile_with_credentials

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_CREDENTIAL_INPUT = "recovery-independent-password-login-secret"


@pytest.mark.parametrize("recovery_state", ["never_enrolled", "removed", "damaged"])
def test_password_login_ignores_absent_removed_or_damaged_recovery(tmp_path: Path, recovery_state: str) -> None:
    """Recovery state changes disaster recovery only; the password still logs in.

    A profile is born without recovery, so the never-enrolled case is the
    default shape. The other two enrol through the real door first, so the
    wrapper being unlinked or overwritten is a genuine loss of an installed
    second door rather than the absence of one that never existed.
    """
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label=f"Recovery independent {recovery_state}",
            passphrase=_CREDENTIAL_INPUT,
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        profile_id = UUID(outcome.profile_id)
        material = load_committed_profile_password_material(profile_id)
        wrapper = profile_custody_recovery_envelope_path(material.capsule_path)
        if recovery_state == "never_enrolled":
            assert not wrapper.exists()
        else:
            enroll_profile_recovery(
                profile_id=profile_id,
                current_passphrase=_CREDENTIAL_INPUT,
                recovery_handover=lambda enrollment: enrollment.recovery_key.code,
            )
            assert wrapper.is_file()
            if recovery_state == "removed":
                wrapper.unlink()
            else:
                wrapper.write_bytes(b"not-a-recovery-envelope")
        logout_active_profile()

        authenticated = login_profile(
            name=outcome.profile_id,
            passphrase_callback=lambda: _CREDENTIAL_INPUT,
            profile_decode_context=_profile_decode_context_for_test,
        )
        try:
            assert authenticated.bucket_id == outcome.profile_id
        finally:
            logout_active_profile()
