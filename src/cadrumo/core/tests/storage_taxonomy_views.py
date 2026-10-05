"""Derived views for settings-default and recording-fingerprint contract checks."""

from __future__ import annotations

from typing import Final

from ..storage_taxonomy import FingerprintParticipation, StorageCategory
from ..storage_taxonomy_locations import STORAGE_TAXONOMY

STORAGE_FIELD_CATEGORIES: Final[dict[str, StorageCategory]] = {
    location.settings_field: location.category
    for location in STORAGE_TAXONOMY.values()
    if location.settings_field is not None
}
"""Reverse index from a flat settings field name to the member that governs it."""

FINGERPRINT_EXCLUDED_STORAGE_FIELDS: Final[frozenset[str]] = frozenset(
    location.settings_field
    for location in STORAGE_TAXONOMY.values()
    if location.settings_field is not None and location.fingerprint_participation is FingerprintParticipation.EXCLUDED
)
"""Settings fields whose contents are kept out of the data-root drift digest.

Compared by field NAME wherever it is checked, never by resolved-path
cardinality: two fields may legitimately be overridden onto one directory,
which shrinks a resolved-path set while exactly the same fields are consulted.
"""
