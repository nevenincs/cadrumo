"""Exact schema-version validation for persisted secure objects.

Secure-object readers accept the current consumer schema only. A row written
by a newer application is reported separately so the operator knows that a
newer build is required; a pre-current row is unsupported and is never
migrated or tolerated implicitly.
"""

from __future__ import annotations

from .errors import EnvelopeVersionError


def ensure_schema_version_supported(
    *,
    namespace: str,
    schema_version: int,
    current_version: int,
) -> None:
    """Refuse any stored schema version other than the consumer's current one."""
    if schema_version == current_version:
        return
    if schema_version > current_version:
        raise EnvelopeVersionError(
            context={
                "namespace": namespace,
                "schema_version": schema_version,
                "expected": current_version,
            },
            translated_message="errors.storage.namespace.schema_version_from_future",
        )
    raise EnvelopeVersionError(
        context={
            "namespace": namespace,
            "schema_version": schema_version,
            "expected": current_version,
        },
        translated_message="errors.storage.namespace.schema_version_unsupported",
    )


__all__ = ["ensure_schema_version_supported"]
