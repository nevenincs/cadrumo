"""Stable pseudonymous workspace identifier for telemetry payloads.

Every :class:`~core.telemetry.TelemetryEventPayload` must carry a
``workspace_hash`` rather than the operator's profile id or NIF. This
module derives that hash deterministically from the local storage root path
-- a value that already exists per-deployment, is never the taxpayer's
identity, and is stable across repeated runs of the same installation without
needing any new persisted state.

See Also:
    :func:`~core.telemetry.workspace_hash`
        Public facade export of this pseudonymous deployment-id helper.
    :class:`~core.telemetry.TelemetryEventPayload`
        Payload shape that carries the derived workspace hash.
    :class:`~core.config.Settings`
        Source of the local storage root used as the stable hash input.
"""

from __future__ import annotations

from pathlib import Path

from ..hashing import sha256_hex

__all__ = ["workspace_hash"]


def workspace_hash(storage_root: Path) -> str:
    """Derive a stable, non-identifying pseudonym for this local deployment.

    Args:
        storage_root: The deployment's local storage root
            (``settings.cadrumo_local_storage_root``). Only its resolved path
            string is hashed; no file contents, profile data, or identity
            fields are read.

    Returns:
        A 64-character lowercase hex SHA-256 digest of the resolved storage
        root path. Two processes pointed at the same storage root produce the
        same hash; the hash cannot be reversed to recover the path or any
        taxpayer identity.
    """
    return sha256_hex(str(Path(storage_root).resolve()).encode("utf-8"))
