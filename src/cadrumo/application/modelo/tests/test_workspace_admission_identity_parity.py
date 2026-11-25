"""A static inspection and a graded snapshot of one revision derive the same schema fingerprint and evidence digest."""

from __future__ import annotations

import pytest

from ....core.hashing import content_hash_hex
from ....domain.calculations.registry.tests.published_authority import published_inspection, published_snapshot
from ..workspace_graded import graded_snapshot_evidence_horizon, resolve_graded_snapshot_schema_identity
from ..workspace_schema import resolve_static_inspection_schema_identity, static_inspection_evidence_horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_both_admissions_fingerprint_the_same_declared_identity_sets() -> None:
    inspection = published_inspection("130", filing_year=2026, period="1T")
    snapshot = published_snapshot("130", filing_year=2026, period="1T")
    assert inspection.revision_id == snapshot.revision.id

    static_identity = resolve_static_inspection_schema_identity(inspection)
    graded_identity = resolve_graded_snapshot_schema_identity(snapshot)

    assert graded_identity.schema_id == static_identity.schema_id
    assert graded_identity.schema_fingerprint == static_identity.schema_fingerprint
    assert static_identity.schema_fingerprint == content_hash_hex(
        {
            "casilla_ids": sorted(casilla.id for casilla in snapshot.revision.casillas),
            "binding_ids": sorted(binding.id for binding in snapshot.revision.bindings),
        }
    )


def test_both_admissions_digest_the_same_retained_source_catalogue() -> None:
    inspection = published_inspection("130", filing_year=2026, period="1T")
    snapshot = published_snapshot("130", filing_year=2026, period="1T")

    static_horizon = static_inspection_evidence_horizon(inspection)
    graded_horizon = graded_snapshot_evidence_horizon(snapshot)

    assert graded_horizon.source_refs == static_horizon.source_refs
    assert graded_horizon.evidence_digest == static_horizon.evidence_digest
    assert static_horizon.evidence_digest == content_hash_hex({"source_refs": tuple(sorted(snapshot.sources))})
