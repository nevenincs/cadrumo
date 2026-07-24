"""Schema-lineage policy for persisted secure-object payloads.

Persisted rows carry the ``schema_version`` they were written under, while
the consumer contract names the current version. This module owns the
policy that keeps every version from the durability floor to the current
version readable: the version gate is a *ceiling* — a version above the
consumer's current version is refused as written-by-a-newer-application,
and a version below it is readable exactly when the per-hop upgrade chain
up to the current version is complete. Registered upgraders transform
decrypted plaintext payload bytes one version step at a time; ciphertext,
AEAD associated data, and revision-lineage metadata are never rewritten by
a read.

The upgrader registry is EMPTY while every registered namespace sits at
schema version 1. A future schema bump MUST land the one-hop upgrader for
its namespace in the same change, or the lineage gate
(``tests/test_schema_lineage.py``) fails — that gate is what makes "a
version bump strands years-old taxpayer data" structurally impossible.
:data:`SECURE_OBJECT_DURABILITY_FLOOR` moves forward only deliberately, once
every version below it is no longer readable by any live consumer.

See Also:
    :func:`~adapters.persistence.storage.sql._secure_object_row_codec.secure_object_record_from_row`
        Row decode path that applies this policy before returning a record.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Final

from .errors import EnvelopeVersionError, StorageValidationError

#: Upgrades one decrypted plaintext payload from ``from_version`` to
#: ``from_version + 1`` for its namespace. Pure bytes-to-bytes; never touches
#: ciphertext or row metadata.
SecureObjectSchemaUpgrader = Callable[[bytes], bytes]

#: Oldest secure-object schema version every read path keeps readable.
#: Starts at the from-birth version; moves forward only deliberately.
SECURE_OBJECT_DURABILITY_FLOOR: Final[int] = 1

_SCHEMA_UPGRADERS: dict[tuple[str, int], SecureObjectSchemaUpgrader] = {}


def register_secure_object_schema_upgrader(
    namespace: str,
    from_version: int,
    upgrader: SecureObjectSchemaUpgrader,
) -> None:
    """Register the one-hop payload upgrader for ``(namespace, from_version)``.

    A schema bump for a namespace lands its upgrader through this function in
    the same change that raises the namespace's declared ``schema_version``;
    the lineage gate fails until it does.

    Raises:
        StorageValidationError: When an upgrader for the hop is already
            registered — two competing transformations for one hop is a
            wiring error, never a merge.
    """
    key = (namespace, from_version)
    if key in _SCHEMA_UPGRADERS:
        raise StorageValidationError(
            context={"namespace": namespace, "from_version": from_version},
            translated_message="errors.storage.namespace.schema_upgrader_already_registered",
        )
    _SCHEMA_UPGRADERS[key] = upgrader


def deregister_secure_object_schema_upgrader(namespace: str, from_version: int) -> None:
    """Remove a registered upgrader hop.

    Production wiring never removes a hop — dropping one would re-open the
    stranding gap the lineage gate closes. This exists so tests that
    register a real upgrader against a scratch namespace can restore the
    registry in their teardown.
    """
    _SCHEMA_UPGRADERS.pop((namespace, from_version), None)


def missing_upgrade_hops(
    *,
    namespace: str,
    from_version: int,
    to_version: int,
    upgraders: Mapping[tuple[str, int], SecureObjectSchemaUpgrader] | None = None,
) -> tuple[int, ...]:
    """Return the ``from_version`` of every unregistered hop in the chain.

    An empty tuple means every step from ``from_version`` to ``to_version``
    has a registered upgrader (vacuously so when the versions are equal).
    """
    source = _SCHEMA_UPGRADERS if upgraders is None else upgraders
    return tuple(version for version in range(from_version, to_version) if (namespace, version) not in source)


def ensure_schema_version_readable(
    *,
    namespace: str,
    schema_version: int,
    current_version: int,
    upgraders: Mapping[tuple[str, int], SecureObjectSchemaUpgrader] | None = None,
) -> None:
    """Refuse a stored version the current application cannot read.

    The gate is a ceiling, not an equality: a version above
    ``current_version`` was written by a newer application and is refused
    outright; a version below it is accepted exactly when the registered
    upgrade chain up to ``current_version`` is complete, and refused loudly
    — naming the first missing hop — when it is not.

    Raises:
        EnvelopeVersionError: When ``schema_version`` exceeds
            ``current_version`` (future shape) or the upgrade chain has a
            missing hop (readable only after the missing upgrader ships).
    """
    if schema_version > current_version:
        raise EnvelopeVersionError(
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": current_version,
            },
            translated_message="errors.storage.namespace.schema_version_from_future",
        )
    missing = missing_upgrade_hops(
        namespace=namespace,
        from_version=schema_version,
        to_version=current_version,
        upgraders=upgraders,
    )
    if missing:
        raise EnvelopeVersionError(
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": current_version,
                "missing_from_version": missing[0],
            },
            translated_message="errors.storage.namespace.schema_upgrade_path_missing",
        )


def upgrade_secure_object_payload(
    payload: bytes,
    *,
    namespace: str,
    from_version: int,
    to_version: int,
    upgraders: Mapping[tuple[str, int], SecureObjectSchemaUpgrader] | None = None,
) -> bytes:
    """Chain-upgrade a decrypted payload from ``from_version`` to ``to_version``.

    Validates the chain first (so a missing hop refuses before any
    transformation runs), then applies each registered one-hop upgrader in
    order. Equal versions return the payload unchanged.

    Raises:
        EnvelopeVersionError: When ``from_version`` exceeds ``to_version``
            or the chain has a missing hop.
    """
    ensure_schema_version_readable(
        namespace=namespace,
        schema_version=from_version,
        current_version=to_version,
        upgraders=upgraders,
    )
    source = _SCHEMA_UPGRADERS if upgraders is None else upgraders
    for version in range(from_version, to_version):
        payload = source[(namespace, version)](payload)
    return payload


__all__ = [
    "SECURE_OBJECT_DURABILITY_FLOOR",
    "SecureObjectSchemaUpgrader",
    "deregister_secure_object_schema_upgrader",
    "ensure_schema_version_readable",
    "missing_upgrade_hops",
    "register_secure_object_schema_upgrader",
    "upgrade_secure_object_payload",
]
