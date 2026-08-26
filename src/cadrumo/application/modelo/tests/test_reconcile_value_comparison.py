"""Real-behavior tests for filed-total reconciliation in ``modelo_reconcile``.

These lock the ``reconcile-value-comparison`` contract: the reconcile compare is
no longer receipt-identity-only. Where a revision declares
``reconciliation_total_casilla_ids`` (Modelo 131 casilla ``15`` here) and a
persisted calculation revision exists, the receipt's printed total is reconciled
against the canonical ``revision.casilla_values`` result. A filed-amount
divergence is caught as a typed ``total`` diff carrying the expectation's legal
grounding — never hidden behind an identity ``matches``. Where no total map is
declared (Modelo 130), an explicit ``totals_not_reconciled`` advisory discloses
that the filed amount was not checked, so identity-only ``matches`` is never a
silent false green.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....domain.calculations.registry.authority import bundled_authority
from ...tests import isolated_profile_backend as _isolated_backend

__all__ = ["_isolated_backend"]

from cadrumo.application.workflow.persistence import workflow_state_repository

from ....adapters.inbound.justificante import parse_justificante
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import Period, validated_casilla_id
from ....domain.justificante import Justificante
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_calculation_revision,
    upsert_work_unit,
)
from ....tests import FIXTURES_DIR
from ....tests.registry_observations import registry_grounded_observations
from ..reconciliation import (
    _reconcile_parsed_justificante,
)
from ..reconciliation_records import (
    ModeloReconciliationDiffKind,
    ModeloReconciliationEvidenceKind,
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
_PROFILE_TAX_ID = "00000000T"
_CLOCK = datetime(2025, 4, 15, tzinfo=UTC)


def _seed_work_unit(*, modelo: str, filing_year: int, period: str) -> WorkUnit:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    typed_period = Period.from_year_and_code(filing_year, period)
    # Seed the real law-determined revision id so the snapshot resolver's D1
    # identity assertion holds (a fabricated pin would divert reconcile into a
    # snapshot_unavailable advisory instead of exercising the value compare).
    revision_id = (
        bundled_authority()
        .snapshot(
            modelo,
            filing_year=filing_year,
            period=typed_period.registry_token,
        )
        .revision.id
    )
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
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit


def _persist_filed_revision(work_unit: WorkUnit, *, total_ingresar: Decimal) -> None:
    """Persist a filed Modelo 131 revision whose casilla 15 carries ``total_ingresar``."""
    casilla_values = {validated_casilla_id("15", surface="test"): total_ingresar}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    repo = CalculationRevisionCatalogueRepository()
    repo.save(
        upsert_calculation_revision(
            repo.load(),
            CalculationRevision(
                calculation_revision_id=revision_id,
                work_unit_id=work_unit.work_unit_id,
                state=CalculationRevisionState.PRESENTADO,
                casilla_values=casilla_values,
                observations=registry_grounded_observations(
                    modelo=str(work_unit.modelo),
                    filing_year=work_unit.filing_year,
                    period=work_unit.period.registry_token,
                    casilla_values=casilla_values,
                ),
                created_at=_CLOCK,
                updated_at=_CLOCK,
                verified_at=_CLOCK,
                verified_by="test",
                filed_at=_CLOCK,
                filed_by="test",
                filing_instance_evidence=None,
                source_provenance=(),
            ),
        ),
    )


def _receipt_for_m131(*, total_ingresar: Decimal):
    """A Modelo 131 / 2024 1T receipt derived from the real parsed 130 fixture."""
    parsed = parse_justificante(MODELO_130_FIXTURE)
    return parsed.model_copy(
        update={
            "modelo": "131",
            "ejercicio": "2024",
            "period": Period.from_year_and_code(2024, "1T"),
            "tax_id": _PROFILE_TAX_ID,
            "total_a_ingresar": total_ingresar,
            "total_a_devolver": None,
        },
    )


def _reconcile(work_unit: WorkUnit, justificante: Justificante):
    return _reconcile_parsed_justificante(
        work_unit=work_unit,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref="test://m131",
        actor="operator",
        justificante=justificante,
    )


def test_filed_total_matching_computed_result_reconciles_clean() -> None:
    work_unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    _persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))

    report = _reconcile(work_unit, _receipt_for_m131(total_ingresar=Decimal("500.00")))

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs
    # The total was actually reconciled — no "not reconciled" advisory.
    assert all(a.code != "totals_not_reconciled" for a in report.advisories)


def test_filed_amount_divergence_is_caught_as_typed_total_diff() -> None:
    """A filed amount that differs from the computed result is CAUGHT and
    represented as a typed ``total`` diff with legal grounding — not a silent
    identity ``matches``, and not merely a count."""
    work_unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    _persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))

    report = _reconcile(work_unit, _receipt_for_m131(total_ingresar=Decimal("999.99")))

    assert report.verdict is ModeloReconciliationVerdict.MISMATCHES
    total_diffs = [d for d in report.diffs if d.diff_kind is ModeloReconciliationDiffKind.TOTAL]
    assert len(total_diffs) == 1
    diff = total_diffs[0]
    assert diff.field_name == "total_ingresar"
    assert diff.work_unit_value == "500.00"
    assert diff.evidence_value == "999.99"
    # Provenance rides the divergence (aeat-calculation-grounding).
    assert "rd-439-2007:art-110" in diff.legal_refs
    assert diff.source_refs


def test_divergence_within_tolerance_does_not_flag() -> None:
    """The registry tolerance (0.01) is honoured: a one-cent gap is clean."""
    work_unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    _persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))

    report = _reconcile(work_unit, _receipt_for_m131(total_ingresar=Decimal("500.01")))

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


def test_no_persisted_revision_surfaces_advisory_not_false_green() -> None:
    work_unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    # No revision persisted.
    report = _reconcile(work_unit, _receipt_for_m131(total_ingresar=Decimal("500.00")))

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    codes = {a.code for a in report.advisories}
    assert "totals_not_reconciled" in codes
    reasons = {a.context.get("reason") for a in report.advisories if a.code == "totals_not_reconciled"}
    assert "no_persisted_revision" in reasons


def test_undeclared_total_map_modelo_surfaces_advisory() -> None:
    """Modelo 130 declares no reconciliation_total_casilla_ids: the filed total
    is disclosed as not reconciled, never silently passed."""
    work_unit = _seed_work_unit(modelo="130", filing_year=2026, period="1T")

    receipt = parse_justificante(MODELO_130_FIXTURE).model_copy(update={"tax_id": _PROFILE_TAX_ID})
    report = _reconcile(work_unit, receipt)

    advisory_reasons = {a.context.get("reason") for a in report.advisories if a.code == "totals_not_reconciled"}
    assert advisory_reasons == {"map_not_declared"}


def test_history_persists_which_total_diverged_not_just_a_count() -> None:
    work_unit = _seed_work_unit(modelo="131", filing_year=2024, period="1T")
    _persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))
    _reconcile(work_unit, _receipt_for_m131(total_ingresar=Decimal("999.99")))

    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    entries = list_modelo_reconciliations(bucket_id=bucket_id, work_unit_id=work_unit.work_unit_id)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.diff_count == 1
    # The read-back carries WHICH field diverged, not only how many.
    assert len(entry.diffs) == 1
    assert entry.diffs[0].diff_kind is ModeloReconciliationDiffKind.TOTAL
    assert entry.diffs[0].field_name == "total_ingresar"
    assert "rd-439-2007:art-110" in entry.diffs[0].legal_refs
