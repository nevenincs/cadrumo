"""Anchored, nonsecret installation metadata independent of optional credential stores."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.installation import RuntimeInstallation
from ...core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant
from ..persistence.storage.custody.errors import ProfileCustodyRecordError
from ..persistence.storage.custody.filesystem import (
    profile_custody_local_lock,
    read_optional_profile_custody_local_record,
    write_profile_custody_local_record,
)
from ..persistence.storage.custody.filesystem_primitives import ensure_profile_custody_local_directory


def runtime_installation(*, storage_root: Path, os_owner_id: str, storage_identity: str) -> RuntimeInstallation:
    """Read or atomically create an owner/root identity, refusing corrupt or displaced state.

    This short metadata transaction has its own lock. It is neither the runtime
    lifetime ownership lock nor the profile custody transaction lock.
    """
    if not storage_root.is_absolute():
        raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
    directory = storage_root / ".runtime"
    try:
        ensure_profile_custody_local_directory(directory)
        with profile_custody_local_lock(directory / "installation.lock", timeout_seconds=5):
            path = directory / "installation.json"
            raw = read_optional_profile_custody_local_record(path, maximum_bytes=4096)
            if raw is None:
                identity = RuntimeInstallation(
                    installation_id=uuid4(),
                    os_owner_id=os_owner_id,
                    storage_identity=storage_identity,
                )
                write_profile_custody_local_record(
                    path, canonical_json_bytes(identity.model_dump(mode="json")), publish_once=True
                )
            else:
                parsed = json.loads(
                    raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
                )
                identity = RuntimeInstallation.model_validate_json(canonical_json_bytes(parsed))
            if identity.os_owner_id != os_owner_id or identity.storage_identity != storage_identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
            return identity
    except (OSError, ProfileCustodyRecordError, ValueError, TypeError, RecursionError, ValidationError):
        raise RuntimeRefusalError(RuntimeRefusalCode.ENDPOINT_UNTRUSTED) from None
