"""Publish a labelled profile custody capsule for CLI storage-scaling and listing tests."""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

from ....adapters.persistence.storage.custody.capsule import publish_profile_custody_capsule
from ....adapters.persistence.storage.custody.capsule_records import ProfileCustodyCapsuleLabel
from ....adapters.persistence.storage.custody.records import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from ....adapters.persistence.storage.custody.sentinel import create_profile_custody_sentinel
from ....core.config import Settings
from ....core.profile_publication import ProfilePublicationKind

_DEK = bytes(range(32))
_EPOCH = base64.b64encode(b"e" * 16).decode("ascii")


def publish_labelled_profile(root: Path, profile_id: UUID, label: str) -> None:
    envelope = ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=_EPOCH,
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=base64.b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"c" * 32).decode("ascii"),
            tag_b64=base64.b64encode(b"t" * 16).decode("ascii"),
        ),
    )
    publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=uuid4(),
        publication_kind=ProfilePublicationKind.ENROLL,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={
            "profile-label.v1.json": ProfileCustodyCapsuleLabel.create(
                profile_id=profile_id,
                label=label,
            ).canonical_json_bytes()
        },
        settings=Settings(cadrumo_storage_root=root),
    )
