"""Exact current profile binding and DEK sentinel validation for runtime custody."""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID

from .....application.user_profile.access_contracts import ProfileAccessBinding
from .....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .capsule import load_committed_profile_password_material
from .errors import ProfileCustodyRecordError
from .sentinel_contract import verify_profile_custody_sentinel


def current_automation_profile_binding(
    *, profile_id: UUID, installation_id: UUID, os_owner_id: str, root: Path
) -> ProfileAccessBinding:
    """Resolve current immutable custody coordinates from committed profile material."""
    try:
        envelope = load_committed_profile_password_material(profile_id, root=root).envelope
        return ProfileAccessBinding(
            profile_id=profile_id,
            installation_id=installation_id,
            os_owner_id=os_owner_id,
            custody_generation=envelope.password_generation,
            dek_epoch=UUID(bytes=base64.b64decode(envelope.dek_epoch, validate=True)),
        )
    except (OSError, ProfileCustodyRecordError, ValueError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None


def validate_automation_profile_binding(binding: ProfileAccessBinding, *, root: Path, dek: bytes | None = None) -> None:
    """Read committed custody and optionally authenticate the supplied data key."""
    try:
        material = load_committed_profile_password_material(binding.profile_id, root=root)
        envelope = material.envelope
        epoch = UUID(bytes=base64.b64decode(envelope.dek_epoch, validate=True))
        if envelope.password_generation != binding.custody_generation or epoch != binding.dek_epoch:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        if dek is not None:
            verify_profile_custody_sentinel(
                dek=dek, profile_id=binding.profile_id, dek_epoch=envelope.dek_epoch, sentinel=material.sentinel
            )
    except (ProfileCustodyRecordError, ValueError):
        raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
