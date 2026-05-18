"""Startup checks that fence the AEAT runtime against legacy on-disk state.

The per-bucket directory layout mandated by the
2026-05-14 profile-bucket-lifecycle ADR replaces the historical
interleaved ``var/`` layout (one shared ``aeat.db``, one shared
secrets directory, one shared blob store). Mixing the two on the
same operator root corrupts the active-profile pointer chain:
``<aeat-root>/active-profile`` cannot agree with a legacy
``aeat.db`` that has no bucket dimension. The runtime refuses to
operate against a half-migrated tree by raising
:class:`LegacyLayoutDetectedError` at the entry of any verb that
touches persisted state.

The check is intentionally conservative. It fires only when the
operator's AEAT root carries a sibling ``var/`` subdirectory AND
the per-bucket ``buckets/`` subdirectory is absent. This is the
exact pattern that survives a partial copy of legacy state into a
fresh root and that the May-14 ADR forbids the runtime from
operating against.
"""

from __future__ import annotations

from pathlib import Path

from ..adapters.persistence.storage.bucket._errors import LegacyLayoutDetectedError
from ..core.config import Settings, load_settings


def detect_legacy_layout(settings: Settings | None = None) -> bool:
    """Return True when the AEAT root carries the legacy var/ layout.

    "Legacy" means: ``<aeat-root>/var/`` exists AND
    ``<aeat-root>/buckets/`` does not. A fresh install or a fully
    migrated install has only the latter; a half-migrated install
    that copied legacy ``var/`` content under the new root has both
    paths in disagreement.
    """

    resolved = settings if settings is not None else load_settings()
    root = resolved.aeat_local_storage_root
    legacy_var = root / "var"
    new_buckets = root / "buckets"
    return legacy_var.exists() and not new_buckets.exists()


def assert_no_legacy_layout(settings: Settings | None = None) -> None:
    """Raise :class:`LegacyLayoutDetectedError` when legacy state is on disk.

    Called at the entry of every verb that writes persisted state so
    the runtime never silently mixes per-bucket and legacy storage.
    Verbs that resolve through the active-profile precedence chain
    are unaffected when only ``<aeat-root>/buckets/`` exists.
    """

    if detect_legacy_layout(settings):
        resolved = settings if settings is not None else load_settings()
        raise LegacyLayoutDetectedError(
            "legacy var/ layout detected under AEAT root; "
            "back up var/ to cold storage and run `aeat config init` "
            "against a fresh root to migrate",
            context={"aeat_root": str(resolved.aeat_local_storage_root)},
            suggestion="aeat config init --profile NAME --tax-id <NIF>",
        )


__all__ = ["assert_no_legacy_layout", "detect_legacy_layout"]
