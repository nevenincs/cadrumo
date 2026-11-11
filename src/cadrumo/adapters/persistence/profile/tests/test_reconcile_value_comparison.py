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

from .....application.modelo.reconciliation_evidence_kind import ModeloReconciliationEvidenceKind
from .....application.modelo.reconciliation_records import (
    ModeloReconciliationDiffKind,
    ModeloReconciliationVerdict,
    list_modelo_reconciliations,
)
from .....application.workflow.persistence import workflow_state_repository
from .....core.period import Period
from .....domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.justificante.schema import Justificante
from .....domain.modelos.work_unit import WorkUnit
from .....tests.inventory import FIXTURES_DIR
from ....inbound.justificante.parser import parse_justificante
from ...storage.tests.active_profile_isolated_backend_fixture import (
    active_profile_isolated_backend_fixture,
)
from .published_authority_support import published_authority_operation
from .reconciliation_persist_support import (
    persist_filed_revision,
    reconcile_parsed_justificante,
    seed_active_work_unit,
)

isolated_backend = active_profile_isolated_backend_fixture(profile_overrides={"identity.tax_id": "00000000T"})

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

MODELO_130_FIXTURE = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
_PROFILE_TAX_ID = "00000000T"
_CLOCK = datetime(1980, 4, 15, tzinfo=UTC)
_M131_YEAR = filing_year_envelope().horizon
#: The ejercicio the 130 fixture prints, read off the fixture's own name.
_M130_FIXTURE_YEAR = int(MODELO_130_FIXTURE.stem.rpartition("_")[2][:4])


def seed_work_unit(*, modelo: str, filing_year: int, period: str) -> WorkUnit:
    return seed_active_work_unit(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        operation=published_authority_operation(),
    )


def reconcile_value_comparison_persist_filed_revision(work_unit: WorkUnit, *, total_ingresar: Decimal) -> None:
    """Persist a filed Modelo 131 revision whose casilla 15 carries ``total_ingresar``."""
    persist_filed_revision(work_unit, casilla_values={"15": total_ingresar}, clock=_CLOCK)


def receipt_for_m131(*, total_ingresar: Decimal):
    """A Modelo 131 first-quarter receipt derived from the real parsed 130 fixture."""
    parsed = parse_justificante(MODELO_130_FIXTURE)
    return parsed.model_copy(
        update={
            "modelo": "131",
            "ejercicio": str(_M131_YEAR),
            "period": Period.from_year_and_code(_M131_YEAR, "1T"),
            "tax_id": _PROFILE_TAX_ID,
            "total_a_ingresar": total_ingresar,
            "total_a_devolver": None,
        },
    )


def _reconcile(
    work_unit: WorkUnit,
    justificante: Justificante,
    *,
    operation: PinnedAuthorityOperation,
):
    return reconcile_parsed_justificante(
        work_unit=work_unit,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref="test://m131",
        actor="operator",
        justificante=justificante,
        operation=operation,
    )


def test_filed_total_matching_computed_result_reconciles_clean(operation: PinnedAuthorityOperation) -> None:
    work_unit = seed_work_unit(modelo="131", filing_year=_M131_YEAR, period="1T")
    reconcile_value_comparison_persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))

    report = _reconcile(work_unit, receipt_for_m131(total_ingresar=Decimal("500.00")), operation=operation)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs
    # The total was actually reconciled — no "not reconciled" advisory.
    assert all(a.code != "totals_not_reconciled" for a in report.advisories)


def test_filed_amount_divergence_is_caught_as_typed_total_diff(operation: PinnedAuthorityOperation) -> None:
    """A filed amount that differs from the computed result is CAUGHT and
    represented as a typed ``total`` diff with legal grounding — not a silent
    identity ``matches``, and not merely a count."""
    work_unit = seed_work_unit(modelo="131", filing_year=_M131_YEAR, period="1T")
    reconcile_value_comparison_persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))

    report = _reconcile(work_unit, receipt_for_m131(total_ingresar=Decimal("999.99")), operation=operation)

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


def test_divergence_within_tolerance_does_not_flag(operation: PinnedAuthorityOperation) -> None:
    """The registry tolerance (0.01) is honoured: a one-cent gap is clean."""
    work_unit = seed_work_unit(modelo="131", filing_year=_M131_YEAR, period="1T")
    reconcile_value_comparison_persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))

    report = _reconcile(work_unit, receipt_for_m131(total_ingresar=Decimal("500.01")), operation=operation)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    assert not report.diffs


def test_no_persisted_revision_surfaces_advisory_not_false_green(operation: PinnedAuthorityOperation) -> None:
    work_unit = seed_work_unit(modelo="131", filing_year=_M131_YEAR, period="1T")
    # No revision persisted.
    report = _reconcile(work_unit, receipt_for_m131(total_ingresar=Decimal("500.00")), operation=operation)

    assert report.verdict is ModeloReconciliationVerdict.MATCHES
    codes = {a.code for a in report.advisories}
    assert "totals_not_reconciled" in codes
    reasons = {a.context.get("reason") for a in report.advisories if a.code == "totals_not_reconciled"}
    assert "no_persisted_revision" in reasons


def test_undeclared_total_map_modelo_surfaces_advisory(operation: PinnedAuthorityOperation) -> None:
    """Modelo 130 declares no reconciliation_total_casilla_ids: the filed total
    is disclosed as not reconciled, never silently passed."""
    work_unit = seed_work_unit(modelo="130", filing_year=_M130_FIXTURE_YEAR, period="1T")

    receipt = parse_justificante(MODELO_130_FIXTURE).model_copy(update={"tax_id": _PROFILE_TAX_ID})
    report = _reconcile(work_unit, receipt, operation=operation)

    advisory_reasons = {a.context.get("reason") for a in report.advisories if a.code == "totals_not_reconciled"}
    assert advisory_reasons == {"map_not_declared"}


def test_history_persists_which_total_diverged_not_just_a_count(operation: PinnedAuthorityOperation) -> None:
    work_unit = seed_work_unit(modelo="131", filing_year=_M131_YEAR, period="1T")
    reconcile_value_comparison_persist_filed_revision(work_unit, total_ingresar=Decimal("500.00"))
    _reconcile(work_unit, receipt_for_m131(total_ingresar=Decimal("999.99")), operation=operation)

    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    with bundled_indexed_authority().operation() as operation:
        entries = list_modelo_reconciliations(
            bucket_id=bucket_id,
            operation=operation,
            work_unit_id=work_unit.work_unit_id,
        )
    assert len(entries) == 1
    entry = entries[0]
    assert entry.diff_count == 1
    # The read-back carries WHICH field diverged, not only how many.
    assert len(entry.diffs) == 1
    assert entry.diffs[0].diff_kind is ModeloReconciliationDiffKind.TOTAL
    assert entry.diffs[0].field_name == "total_ingresar"
    assert "rd-439-2007:art-110" in entry.diffs[0].legal_refs
