"""Saved reconciliation operands remain selectable and auditable over time."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest

from .....application.modelo.action_errors import CalculationRevisionNotFoundError
from .....application.modelo.reconciliation import prepare_parsed_justificante
from .....application.modelo.reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationRecord,
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.modelos.calculation_repository import upsert_calculation_revision
from .....domain.modelos.calculation_revision import CalculationRevisionState
from ..buckets import BucketEventHistoryRepository
from ..modelo_reconciliation import ModeloReconciliationPersistence
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from .test_reconcile_value_comparison import (
    _persist_filed_revision,
    _receipt_for_m131,
    _seed_work_unit,
)
from .test_reconcile_value_comparison import (
    isolated_backend as isolated_backend,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def test_exact_revision_selection_and_historical_provenance(operation: PinnedAuthorityOperation) -> None:
    unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    _persist_filed_revision(unit, total_ingresar=Decimal("500"))
    repository = CalculationRevisionCatalogueRepository()
    filed = repository.load(operation=operation).for_work_unit(unit.work_unit_id)[0]
    _persist_filed_revision(unit, total_ingresar=Decimal("600"))
    catalogue = repository.load(operation=operation)
    draft = next(row for row in catalogue.for_work_unit(unit.work_unit_id) if row != filed)
    draft = draft.model_copy(
        update={
            "state": CalculationRevisionState.BORRADOR,
            "verified_at": None,
            "verified_by": None,
            "filed_at": None,
            "filed_by": None,
            "updated_at": filed.updated_at + timedelta(days=1),
        }
    )
    repository.save(upsert_calculation_revision(catalogue, draft))

    def prepare(revision_id: str | None = None):
        return prepare_parsed_justificante(
            work_unit=unit,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_ref="test://receipt",
            actor="operator",
            justificante=_receipt_for_m131(total_ingresar=Decimal("600")),
            operation=operation,
            calculation_revision_id=revision_id,
        )

    default = prepare().persist()
    selected = prepare(draft.calculation_revision_id).persist()
    assert default.calculation_revision_id == filed.calculation_revision_id
    assert default.verdict is ModeloReconciliationVerdict.MISMATCHES
    assert selected.calculation_revision_id == draft.calculation_revision_id
    assert selected.verdict is ModeloReconciliationVerdict.MATCHES
    records = tuple(ModeloReconciliationPersistence().iter_records())
    events = BucketEventHistoryRepository().load().events
    for record in records:
        assert events[record.bucket_event_id].payload["calculation_revision_id"] == record.calculation_revision_id
    history = list_modelo_reconciliations(bucket_id=unit.bucket_id, operation=operation)
    assert {row.calculation_revision_id for row in history} == {
        filed.calculation_revision_id,
        draft.calculation_revision_id,
    }
    assert all(row.registry_snapshot_ref == filed.registry_snapshot_ref for row in history)
    legacy = records[0].model_dump(mode="json")
    del legacy["calculation_revision_id"]
    assert ModeloReconciliationRecord.model_validate_json(json.dumps(legacy)).calculation_revision_id is None

    other = _seed_work_unit(modelo="131", filing_year=2024, period="2T")
    _persist_filed_revision(other, total_ingresar=Decimal("600"))
    other_revision = repository.load(operation=operation).for_work_unit(other.work_unit_id)[0]
    for target in ["a" * 64, other_revision.calculation_revision_id]:
        with pytest.raises(CalculationRevisionNotFoundError):
            prepare(target)
    assert tuple(ModeloReconciliationPersistence().iter_records()) == records
    assert BucketEventHistoryRepository().load().events == events


def test_history_retains_stored_coordinates_after_authority_changes(operation: PinnedAuthorityOperation) -> None:
    unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    prepared = prepare_parsed_justificante(
        work_unit=unit,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref="test://retired-law",
        actor="operator",
        justificante=_receipt_for_m131(total_ingresar=Decimal("600")),
        operation=operation,
    )
    historic_ref = prepared.record.registry_snapshot_ref.model_copy(update={"revision_id": "retired-law"})
    historic = prepared.record.model_copy(update={"registry_snapshot_ref": historic_ref})
    ModeloReconciliationPersistence().persist_with_event(historic, prepared.event)
    history = list_modelo_reconciliations(bucket_id=unit.bucket_id, operation=operation)
    assert len(history) == 1 and history[0].registry_snapshot_ref == historic_ref
    assert history[0].calculation_revision_id is None
    assert history[0].advisory_count > 0


def test_optional_only_scope_discloses_zero_compared_fields(
    operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    from .....application.modelo import reconciliation

    unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    _persist_filed_revision(unit, total_ingresar=Decimal("600"))
    revision = CalculationRevisionCatalogueRepository().load(operation=operation).for_work_unit(unit.work_unit_id)[0]
    snapshot = operation.snapshot("131", filing_year=2024, period="1T")
    policy = replace(
        snapshot.verification_policy(),
        computed_casilla_ids=frozenset(),
        reconcile_when_present_casilla_ids=frozenset({"15"}),
    )
    monkeypatch.setattr(reconciliation, "_declaracion_registry_context", lambda *args, **kwargs: (snapshot, policy))
    diffs, advisories = reconciliation._reconcile_casilla_values(
        work_unit=unit, revision=revision, filed_values={}, operation=operation
    )
    assert diffs == []
    assert len(advisories) == 1 and advisories[0].code == "totals_not_reconciled"
    assert advisories[0].context["reason"] == "no_comparable_casillas"
