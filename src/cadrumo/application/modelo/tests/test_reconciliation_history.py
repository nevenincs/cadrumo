"""Real-behavior tests for the reconciliation-history read-back surface.

Authority: ``2026-06-10-cli-operator-surface`` decision D7 (read-back
baseline guarantee); CRUD-matrix audit finding F-07 (no reconciliation-history list).

``modelo_reconcile`` persists a stored record per run, co-written with the slim
``MODELO_RECONCILED`` bucket event in one unit of work.
``list_modelo_reconciliations`` reads that record store back. These tests drive
the production path end to end on a real isolated bucket: run several
reconciliations, list them, assert the typed fields, narrow to one work unit,
prove an empty bucket lists clean, and an anti-tautology proof shows an
unreconciled work unit is absent. The store's own format obligations —
roundtrip, anti-tautology, the N-per-work-unit key, atomicity — live in
``test_reconciliation_record_store``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ...tests import isolated_profile_backend as _isolated_backend

__all__ = ["_isolated_backend"]

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ...workflow.persistence import workflow_state_repository
from ..reconciliation import (
    ModeloReconciliationCommand,
    modelo_reconcile,
)
from ..reconciliation_records import (
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationHistoryEntry,
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
_WORK_UNIT_TIMESTAMP = datetime(2026, 5, 28, 13, 30, 0, tzinfo=UTC)


def _active_bucket_id() -> str:
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_work_unit(*, modelo: str, filing_year: int, period: str, revision_suffix: str = "0") -> str:
    bucket_id = _active_bucket_id()
    revision_id = "r" + revision_suffix * 63
    typed_period = Period.from_year_and_code(filing_year, period)
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=typed_period,
        revision_id=revision_id,
        name=f"{modelo}-{filing_year}-{typed_period.registry_token}",
        created_at=_WORK_UNIT_TIMESTAMP,
        updated_at=_WORK_UNIT_TIMESTAMP,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def _reconcile(work_unit_id: str) -> None:
    modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
            source_path=MODELO_130_FIXTURE,
            actor="tester",
        ),
    )


def test_history_lists_recorded_reconciliations_with_typed_fields() -> None:
    """Several reconciliations all surface in the history with their typed fields.

    A modelo=130 work unit matches the modelo_130 fixture (verdict MATCHES,
    zero diffs); a modelo=303 work unit mismatches it (verdict MISMATCHES, a
    modelo diff). The history projects both with the right verdict, source kind,
    diff count, and actor.
    """
    matching_unit = _seed_work_unit(modelo="130", filing_year=2026, period="1T", revision_suffix="0")
    mismatching_unit = _seed_work_unit(modelo="303", filing_year=2026, period="1T", revision_suffix="1")
    _reconcile(matching_unit)
    _reconcile(mismatching_unit)

    entries = list_modelo_reconciliations(bucket_id=_active_bucket_id())

    assert all(isinstance(entry, ModeloReconciliationHistoryEntry) for entry in entries)
    by_unit = {entry.work_unit_id: entry for entry in entries}
    assert set(by_unit) == {matching_unit, mismatching_unit}

    matched = by_unit[matching_unit]
    assert matched.verdict is ModeloReconciliationVerdict.MATCHES
    assert matched.diff_count == 0
    assert matched.source_kind is ModeloReconciliationEvidenceKind.JUSTIFICANTE
    assert matched.actor == "tester"
    assert matched.source_path.endswith("modelo_130_2026Q1.pdf")

    mismatched = by_unit[mismatching_unit]
    assert mismatched.verdict is ModeloReconciliationVerdict.MISMATCHES
    assert mismatched.diff_count >= 1


def test_history_narrows_to_one_work_unit() -> None:
    """The optional work_unit_id filter narrows the history to one work unit."""
    unit_a = _seed_work_unit(modelo="130", filing_year=2026, period="1T", revision_suffix="0")
    unit_b = _seed_work_unit(modelo="130", filing_year=2026, period="2T", revision_suffix="1")
    _reconcile(unit_a)
    _reconcile(unit_b)

    only_a = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=unit_a)

    assert {entry.work_unit_id for entry in only_a} == {unit_a}


def test_history_orders_oldest_first() -> None:
    """Repeated reconciliations of one unit list oldest-first by reconciled_at."""
    unit = _seed_work_unit(modelo="130", filing_year=2026, period="1T")
    _reconcile(unit)
    _reconcile(unit)

    entries = list_modelo_reconciliations(bucket_id=_active_bucket_id(), work_unit_id=unit)

    timestamps = [entry.reconciled_at for entry in entries]
    assert timestamps == sorted(timestamps)


def test_history_on_empty_bucket_returns_clean_empty() -> None:
    """A bucket with no reconciliations lists a clean empty tuple, not an error."""
    entries = list_modelo_reconciliations(bucket_id=_active_bucket_id())

    assert entries == ()


def test_anti_tautology_unreconciled_unit_absent_from_history() -> None:
    """A work unit that was never reconciled is absent from the history.

    Anti-tautology proof: reconcile one unit, create a second unit but never
    reconcile it, then assert the history lists only the first. If this passed
    with the unreconciled unit present, the read-back would be tautological.
    """
    reconciled_unit = _seed_work_unit(modelo="130", filing_year=2026, period="1T", revision_suffix="0")
    never_reconciled_unit = _seed_work_unit(modelo="130", filing_year=2026, period="3T", revision_suffix="2")
    _reconcile(reconciled_unit)

    listed_units = {entry.work_unit_id for entry in list_modelo_reconciliations(bucket_id=_active_bucket_id())}

    assert reconciled_unit in listed_units
    assert never_reconciled_unit not in listed_units
