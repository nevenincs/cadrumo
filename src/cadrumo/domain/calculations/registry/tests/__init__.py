"""Shared registry test-support fixtures re-exported for cross-package reuse.

Colocated unit tests for :mod:`domain.calculations.registry` live next to the
modules they exercise; this facade exists only to re-export the minimal
snapshot-builder helpers from
:mod:`domain.calculations.registry.tests._referential_integrity_support` for
the one cross-package structural gate
(:mod:`application.tests.test_preflight`) that reuses them.
"""

from __future__ import annotations

from ._referential_integrity_support import (
    REFERENCE_LEGAL_ID,
    build_minimal_snapshot,
    build_snapshot_with_missing_legal,
    check_all_id_references,
    minimal_modelo,
    minimal_revision,
)

__all__ = [
    "REFERENCE_LEGAL_ID",
    "build_minimal_snapshot",
    "build_snapshot_with_missing_legal",
    "check_all_id_references",
    "minimal_modelo",
    "minimal_revision",
]
