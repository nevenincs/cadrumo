"""Derived views for recording-fingerprint contract checks."""

from __future__ import annotations

from typing import Final

from ..storage_taxonomy import FingerprintParticipation, StorageCategory
from ..storage_taxonomy_locations import STORAGE_TAXONOMY

FINGERPRINT_EXCLUDED_STORAGE_CATEGORIES: Final[frozenset[StorageCategory]] = frozenset(
    location.category
    for location in STORAGE_TAXONOMY.values()
    if location.materialised and location.fingerprint_participation is FingerprintParticipation.EXCLUDED
)
"""Root-materialised members whose contents are kept out of the data-root drift digest."""
