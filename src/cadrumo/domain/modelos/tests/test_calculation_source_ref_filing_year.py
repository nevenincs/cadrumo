"""A persisted source reference keeps its source filing year without moving any stored revision id.

The year is additive and optional: absent means unknown. Revisions persisted
before it existed load unchanged and re-derive the id they were stored under,
which is pinned here from the derivation as it stood before the field. A
recorded year joins the identity, so two revisions that differ only in it are
distinct.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ....core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...calculations.registry.schema_references import RegistrySnapshotRef
from ..calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceRef,
    derive_calculation_revision_id,
    derive_calculation_revision_id_from_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Derived for ``_provenance(None)`` by the revision-id derivation before
#: ``source_filing_year`` existed; a stored revision's id must not move.
_PINNED_ID_WITHOUT_FILING_YEAR = "d43701b3ec3ddbbefb0cbf9872adc9d9950732760be2093e70af7faf094610e5"
_WORK_UNIT_ID = "b" * 64
_PRIMARY_REF = "percepcion:" + "1" * 64
_REGISTRY_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="193",
    revision_id="2025-y-siguientes",
    modelo_year=2026,
    period="0A",
)


def _provenance(source_filing_year: int | None) -> tuple[CalculationSourceRef, ...]:
    return (
        CalculationSourceRef(
            resolver_id="withholding",
            resolved_binding_source=BindingSourceKind.WITHHOLDING,
            contributor_source_kind=BindingSourceKind.WITHHOLDING.value,
            contributor_binding_source=BindingSourceKind.WITHHOLDING,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=_PRIMARY_REF,
            parent_source_ref=None,
        ),
        CalculationSourceRef(
            resolver_id="withholding",
            resolved_binding_source=BindingSourceKind.WITHHOLDING,
            contributor_source_kind=BindingSourceKind.LEDGER_TRANSACTION.value,
            contributor_binding_source=BindingSourceKind.LEDGER_TRANSACTION,
            lineage_role=CalculationSourceLineageRole.CONTRIBUTOR,
            source_ref="retencion:" + "2" * 64,
            parent_source_ref=_PRIMARY_REF,
            source_filing_year=source_filing_year,
        ),
    )


def _revision_id(source_filing_year: int | None) -> str:
    return derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT_ID,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=_provenance(source_filing_year),
    )


def _revision(source_filing_year: int | None) -> CalculationRevision:
    created = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
    return CalculationRevision(
        calculation_revision_id=_revision_id(source_filing_year),
        work_unit_id=_WORK_UNIT_ID,
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=_provenance(source_filing_year),
        created_at=created,
        updated_at=created,
    )


def test_source_refs_without_a_filing_year_keep_the_id_they_were_stored_under() -> None:
    assert _revision_id(None) == _PINNED_ID_WITHOUT_FILING_YEAR


def test_a_recorded_filing_year_joins_the_revision_identity() -> None:
    assert _revision_id(2025) != _PINNED_ID_WITHOUT_FILING_YEAR
    assert _revision_id(2025) != _revision_id(2026)
    assert _revision_id(2025) == _revision_id(2025)


def test_a_revision_persisted_before_the_field_existed_round_trips_with_its_id() -> None:
    """A stored payload with no ``source_filing_year`` key loads as unknown and re-derives its own id."""
    stored = json.loads(_revision(None).model_dump_json())
    for ref in stored["source_provenance"]:
        del ref["source_filing_year"]
    assert all("source_filing_year" not in ref for ref in stored["source_provenance"])

    loaded = CalculationRevision.model_validate_json(json.dumps(stored))

    assert loaded.calculation_revision_id == _PINNED_ID_WITHOUT_FILING_YEAR
    assert derive_calculation_revision_id_from_revision(loaded) == _PINNED_ID_WITHOUT_FILING_YEAR
    assert [ref.source_filing_year for ref in loaded.source_provenance] == [None, None]


def test_a_revision_with_the_field_round_trips_it() -> None:
    revision = _revision(2025)

    loaded = CalculationRevision.model_validate_json(revision.model_dump_json())

    assert loaded == revision
    assert loaded.source_provenance[1].source_filing_year == 2025
    assert derive_calculation_revision_id_from_revision(loaded) == revision.calculation_revision_id
