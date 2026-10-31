"""Exact current profile binding and DEK sentinel validation for runtime custody."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from uuid import UUID

from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from .....application.user_profile.access_contracts import ProfileAccessBinding
from .....core.storage_taxonomy import StorageCategory
from .capsule import load_committed_profile_password_material
from .errors import ProfileCustodyRecordError
from .paths import profile_custody_path
from .records import PROFILE_CUSTODY_ENVELOPE_FILENAME
from .sentinel import PROFILE_CUSTODY_SENTINEL_FILENAME
from .sentinel_contract import verify_profile_custody_sentinel

type _FileIdentity = tuple[int, int, int, int, int]


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


class CommittedProfileBindingWatch:
    """Notice a replaced committed binding without re-reading unchanged custody on every look.

    This serves change detection only. Admission and every authority recheck
    still read committed custody in full through the functions beside it.
    Each committed file and its directories are compared by ``lstat``
    identity, so an atomic replacement, an in-place rewrite, a link or a
    swapped directory forces a full read. The identity is taken before the
    read it vouches for, so a change racing that read is seen on the next look.
    """

    def __init__(self, *, profile_id: UUID, installation_id: UUID, os_owner_id: str, root: Path) -> None:
        """Bind one profile's exact coordinates; read nothing yet."""
        self._coordinates = profile_id, installation_id, os_owner_id, root
        marker = profile_custody_path(profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=root)
        capsule = marker.parent
        self._paths = (
            capsule,
            marker,
            capsule / "custody",
            capsule / "custody" / PROFILE_CUSTODY_ENVELOPE_FILENAME,
            capsule / "data",
            capsule / "data" / PROFILE_CUSTODY_SENTINEL_FILENAME,
        )
        self._observed: tuple[tuple[_FileIdentity, ...], ProfileAccessBinding] | None = None

    def current(self) -> ProfileAccessBinding:
        """Return the committed binding, read in full unless no committed file changed since the last read."""
        identity = self._identity()
        observed = self._observed
        if identity is not None and observed is not None and observed[0] == identity:
            return observed[1]
        self._observed = None
        profile_id, installation_id, os_owner_id, root = self._coordinates
        binding = current_automation_profile_binding(
            profile_id=profile_id, installation_id=installation_id, os_owner_id=os_owner_id, root=root
        )
        if identity is not None:
            self._observed = identity, binding
        return binding

    def _identity(self) -> tuple[_FileIdentity, ...] | None:
        identities: list[_FileIdentity] = []
        for path in self._paths:
            try:
                status = os.lstat(path)
            except OSError:
                return None
            if status.st_ino == 0:
                # A filesystem without stable file ids cannot vouch for an unchanged file.
                return None
            identities.append((status.st_dev, status.st_ino, status.st_mode, status.st_size, status.st_mtime_ns))
        return tuple(identities)


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
