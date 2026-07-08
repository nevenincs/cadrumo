"""Master-key providers carry zero ClassVar mutable state.

The profile-bucket lifecycle substrate invariant forbids any
module-global or class-level mutable state that could
survive a bucket switch. Cache state moves to the per-bucket
:class:`~adapters.persistence.storage.master_key.BucketSession` instance.

Asserts directly against the imported provider classes that they declare
zero class-level annotations naming :class:`~typing.ClassVar`. This is the
regression gate for the master-key substrate invariant.

See Also:
    :class:`~adapters.persistence.storage.master_key.KeyringMasterKeyProvider`
        OS-keychain-backed provider guarded against revived class caches.
    :class:`~adapters.persistence.storage.master_key.FileFallbackMasterKeyProvider`
        File-backed provider guarded against revived class caches.
"""

from __future__ import annotations

from typing import ClassVar, get_origin

import pytest

from .._master_key import FileFallbackMasterKeyProvider, KeyringMasterKeyProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_GUARDED_PROVIDERS = (
    KeyringMasterKeyProvider,
    FileFallbackMasterKeyProvider,
)


def _is_classvar_annotation(annotation: object) -> bool:
    """Return whether ``annotation`` is a ClassVar[...] annotation."""
    if get_origin(annotation) is ClassVar:
        return True
    if isinstance(annotation, str):
        return annotation == "ClassVar" or annotation.startswith("ClassVar[") or ".ClassVar[" in annotation
    return False


def test_master_key_providers_carry_zero_classvar_state() -> None:
    """The guarded providers must declare no ClassVar-annotated attributes."""
    violations: list[str] = []
    for provider in _GUARDED_PROVIDERS:
        for name, annotation in provider.__annotations__.items():
            if _is_classvar_annotation(annotation):
                violations.append(f"{provider.__name__}: ClassVar attribute {name}")

    assert violations == [], (
        "Master-key providers must not carry ClassVar mutable state; "
        "every cache moved to the per-bucket BucketSession. Violations:\n  " + "\n  ".join(violations)
    )
