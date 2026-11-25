"""The drift gate compares the ledger rows a draft withheld for inventory purchases with those the books claim now.

A claim moves a purchase between the ledger expenses and the book's acquisition
cost, so a draft stays current only while the claimed rows it withheld are exactly
the rows the books claim now.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.calculation_revision_sources import CalculationSourceIssue
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

from ...aggregation.ledger_membership import (
    BOOK_CLAIMED_REASON,
    LedgerSourceMembership,
    recorded_book_claimed_transaction_ids,
)
from ..ledger_drift_gate import ledger_drift_findings
from .advisory_diagnostic_repositories import EmptyTransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "29292929-2929-4929-8929-292929292929"
_YEAR = newest_authored_edition("100")
_AT = datetime(_YEAR, 4, 20, 12, 0, tzinfo=UTC)
_ROW_A, _ROW_B = "a" * 64, "b" * 64


def _draft(*claimed: str) -> tuple[WorkUnit, CalculationRevision]:
    snapshot = published_snapshot("100", filing_year=_YEAR, period="0A")
    period = Period.from_year_and_code(_YEAR, "0A")
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET, modelo="100", filing_year=_YEAR, period=period, revision_id=snapshot.revision.id
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("100"),
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"100-{_YEAR}-0A",
        created_at=_AT,
        updated_at=_AT,
    )
    issues = tuple(
        CalculationSourceIssue(
            reason=BOOK_CLAIMED_REASON,
            binding_source=BindingSourceKind.LEDGER_RENTA_GASTOS_ESTIMACION_DIRECTA_AGGREGATION,
            message="withheld: the inventory book declares this purchase",
            source_ref=f"transaction:{transaction_id}",
        )
        for transaction_id in claimed
    )
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            source_issues=issues,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        observations=(),
        created_at=_AT,
        updated_at=_AT,
        filing_instance_evidence=None,
        source_provenance=(),
        source_issues=issues,
    )
    return work_unit, revision


def _gate(draft: tuple[WorkUnit, CalculationRevision], *current: str) -> list[ModeloVerificationFinding]:
    work_unit, revision = draft
    return ledger_drift_findings(
        target=revision,
        work_unit=work_unit,
        transaction_repository=EmptyTransactionCatalogueRepository(bucket_id=_BUCKET),
        current_membership=LedgerSourceMembership(book_claimed_transaction_ids=frozenset(current)),
    )


def test_the_draft_records_the_rows_it_withheld_for_the_books() -> None:
    _work_unit, revision = _draft(_ROW_A, _ROW_B)

    assert recorded_book_claimed_transaction_ids(revision) == {_ROW_A, _ROW_B}


@pytest.mark.parametrize("claimed", [(), (_ROW_A,)])
def test_a_draft_whose_claimed_rows_still_match_is_current(claimed: tuple[str, ...]) -> None:
    assert _gate(_draft(*claimed), *claimed) == []


@pytest.mark.parametrize(
    ("recorded", "current", "rows_changed"),
    [
        # A purchase now claims a row the draft still deducted as an expense.
        ((), (_ROW_A,), 1),
        # A claim was withdrawn, so the draft withheld a row that is an expense again.
        ((_ROW_A,), (), 1),
        # The purchase now claims another row.
        ((_ROW_A,), (_ROW_B,), 2),
    ],
)
def test_a_changed_claim_blocks_the_draft_and_names_only_counts(
    recorded: tuple[str, ...], current: tuple[str, ...], rows_changed: int
) -> None:
    (finding,) = _gate(_draft(*recorded), *current)

    assert finding.message_locale_key == "application.modelo.findings.inventory_register_drift"
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["rows_recorded"] == len(recorded)
    assert finding.message_facts["rows_current"] == len(current)
    assert finding.message_facts["rows_changed"] == rows_changed
    assert _ROW_A not in str(finding.message_facts)
