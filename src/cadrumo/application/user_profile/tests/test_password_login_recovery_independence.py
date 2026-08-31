"""Normal password login never reads recovery custody material."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from ....tests.secure_sql import isolated_profile_storage_root
from ..custody_ports import profile_custody_recovery_envelope_path
from ..login_session import login_profile, logout_active_profile
from ..registration import register_profile_with_credentials

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD = "recovery-independent-password-login-secret"  # noqa: S105 - synthetic test credential


@pytest.mark.parametrize("recovery_state", ["missing", "damaged"])
def test_password_login_ignores_missing_or_damaged_recovery(tmp_path: Path, recovery_state: str) -> None:
    """Recovery loss reduces disaster recovery only; the password still logs in."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(
            label=f"Recovery independent {recovery_state}",
            passphrase=_PASSWORD,
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        )
        material = load_committed_profile_password_material(UUID(outcome.profile_id))
        wrapper = profile_custody_recovery_envelope_path(material.capsule_path)
        if recovery_state == "missing":
            wrapper.unlink()
        else:
            wrapper.write_bytes(b"not-a-recovery-envelope")

        authenticated = login_profile(name=outcome.profile_id, passphrase_callback=lambda: _PASSWORD)
        try:
            assert authenticated.bucket_id == outcome.profile_id
        finally:
            logout_active_profile()
