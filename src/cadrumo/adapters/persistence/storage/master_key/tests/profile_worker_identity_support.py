"""The worker identity bound to a published test profile capsule."""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from ...custody.capsule import load_committed_profile_password_material


def published_capsule_identity(profile_id: UUID, root: Path) -> ProfileWorkerIdentity:
    """A fresh worker identity bound to the custody generation and DEK epoch the published capsule carries."""
    envelope = load_committed_profile_password_material(profile_id, root=root).envelope
    return ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=profile_id,
            installation_id=uuid4(),
            os_owner_id="synthetic-owner",
            custody_generation=envelope.password_generation,
            dek_epoch=UUID(bytes=base64.b64decode(envelope.dek_epoch)),
        ),
    )
