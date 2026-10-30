"""The verify-time drift gate compares the inventory rows a draft consumed with those the ledgers yield now.

Hand-worked: a draft recording activity ``alpha`` at fingerprint ``F1`` is current
while the owner yields exactly that row, and stale once the fingerprint moves, the
row disappears or another activity's row joins the cohort.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.calculations.row_source_identity import RowSourceIdentity
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id

from ...aggregation.ledger_membership import LedgerSourceMembership
from .._ledger_drift_gate import ledger_drift_findings
from .advisory_diagnostic_repositories import EmptyTransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "28282828-2828-4828-8828-282828282828"
_AT = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
_KEY = "application.modelo.findings.inventory_register_drift"
_F1, _F2 = "a" * 64, "b" * 64


def _draft(*rows: tuple[str, str]) -> tuple[WorkUnit, CalculationRevision]:
    snapshot = published_snapshot("100", filing_year=2025, period="0A")
    period = Period.from_year_and_code(2025, "0A")
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET,
            modelo="100",
            filing_year=2025,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET,
        modelo=ModeloCode("100"),
        filing_year=2025,
        period=period,
        revision_id=snapshot.revision.id,
        name="100-2025-0A",
        created_at=_AT,
        updated_at=_AT,
    )
    identities = {
        ("inventory-0177", index): RowSourceIdentity(
            source_kind=BindingSourceKind.INVENTORY,
            source_row_identity=activity,
            fingerprint=fingerprint,
        )
        for index, (activity, fingerprint) in enumerate(rows, start=1)
    }
    values = {"inventory-0177": {str(index): "100.00" for index in range(1, len(rows) + 1)}} if rows else {}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            row_binding_values=values,
            row_source_identities=identities,
            casilla_values={},
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
        row_binding_values=values,
        row_source_identities=identities,
    )
    return work_unit, revision


def _gate(draft: tuple[WorkUnit, CalculationRevision], *current: tuple[str, str]) -> list[ModeloVerificationFinding]:
    work_unit, revision = draft
    return ledger_drift_findings(
        target=revision,
        work_unit=work_unit,
        transaction_repository=EmptyTransactionCatalogueRepository(bucket_id=_BUCKET),
        current_membership=LedgerSourceMembership(inventory_row_identities=frozenset(current)),
    )


def test_a_draft_whose_rows_still_match_is_current() -> None:
    assert _gate(_draft(("alpha", _F1)), ("alpha", _F1)) == []


def test_a_draft_that_consumed_no_inventory_row_has_nothing_to_compare() -> None:
    assert _gate(_draft(), ("alpha", _F1)) == []


@pytest.mark.parametrize(
    ("current", "rows_current", "rows_changed"),
    [
        # The fingerprint moved: the old pair left and the new pair joined.
        ((("alpha", _F2),), 1, 2),
        # The owner yields nothing, as an unresolved or retired cohort does.
        ((), 0, 1),
        # Another activity joined the cohort.
        ((("alpha", _F1), ("beta", _F2)), 2, 1),
    ],
)
def test_a_changed_cohort_blocks_the_draft_and_names_only_counts(
    current: tuple[tuple[str, str], ...], rows_current: int, rows_changed: int
) -> None:
    (finding,) = _gate(_draft(("alpha", _F1)), *current)

    assert finding.message_locale_key == _KEY
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_facts["rows_recorded"] == 1
    assert finding.message_facts["rows_current"] == rows_current
    assert finding.message_facts["rows_changed"] == rows_changed
    assert "alpha" not in str(finding.message_facts)
