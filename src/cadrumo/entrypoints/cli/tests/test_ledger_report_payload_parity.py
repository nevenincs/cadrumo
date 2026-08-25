"""Parity gate: domain report fields must be a subset of their CLI payload.

The ledger lifecycle handlers emit their JSON envelope by validating a domain
report through a genuine JSON-text round trip against the registered
``OutputSchema`` payload (``strict_round_trip(Payload, report)``, i.e.
``Payload.model_validate_json(report.model_dump_json())``). Because
:class:`OutputSchema` is ``extra="forbid"``, a field added to the domain report
but not mirrored onto the payload makes that validation raise at runtime — the
exact regression that broke ``aeat app ledger remove`` when
``stale_draft_revision_references`` landed on
:class:`LedgerTransactionRemovalReport` but not on
:class:`LedgerRemoveResult`.

These tests pin the report -> payload field-superset contract with real
populated models (no mocks) so the next field addition that forgets the payload
mirror fails here instead of at the operator's terminal.
"""

from __future__ import annotations

import pytest

from ....application.ledger.models import LedgerCatalogueResetReport, LedgerRemovalBlocker, LedgerTransactionRemovalReport
from ....core.json_contract import strict_round_trip
from .._ledger_payloads import LedgerRemoveResult, LedgerResetResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

# A valid hex-64 identity satisfies the WorkUnitId / CalculationRevisionId /
# TransactionId StringConstraints (min_length=max_length=64, [0-9a-f]).
_HEX_64_A = "a" * 64
_HEX_64_B = "b" * 64
_HEX_64_C = "c" * 64


def _blocker() -> LedgerRemovalBlocker:
    return LedgerRemovalBlocker(
        work_unit_id=_HEX_64_A,
        calculation_revision_id=_HEX_64_B,
        revision_state="borrador",
        modelo="130",
        filing_year=2026,
        period="1T",
    )


def _populated_removal_report() -> LedgerTransactionRemovalReport:
    """A removal report with every advisory/blocker collection non-empty."""
    blocker = _blocker()
    return LedgerTransactionRemovalReport(
        bucket_id="bucket-0001",
        transaction_id=_HEX_64_C,
        removed=True,
        dry_run=False,
        actor="operator",
        reason="duplicate row",
        cascaded_purchase_invoice_evidence_ids=("ev-1",),
        cascaded_attachment_ids=("att-1",),
        blocking_modelo_references=(blocker,),
        stale_draft_revision_references=(blocker,),
        bucket_event_ids=("evt-1",),
    )


def _populated_reset_report() -> LedgerCatalogueResetReport:
    """A reset report with every advisory/blocker collection non-empty."""
    blocker = _blocker()
    return LedgerCatalogueResetReport(
        bucket_id="bucket-0001",
        removed_transaction_ids=(_HEX_64_C,),
        reset=True,
        dry_run=False,
        actor="operator",
        reason="full reset",
        cascaded_purchase_invoice_evidence_ids=("ev-1",),
        cascaded_attachment_ids=("att-1",),
        blocking_modelo_references=(blocker,),
        stale_draft_revision_references=(blocker,),
        bucket_event_ids=("evt-1",),
    )


def test_remove_report_fields_are_subset_of_payload() -> None:
    """Every field of the removal report must be a field of the payload."""
    report_fields = set(LedgerTransactionRemovalReport.model_fields)
    payload_fields = set(LedgerRemoveResult.model_fields)
    missing = report_fields - payload_fields
    assert not missing, (
        "LedgerRemoveResult is missing fields present on "
        f"LedgerTransactionRemovalReport: {sorted(missing)}. The handler "
        "validates the report's model_dump against the extra-forbid payload, "
        "so an unmirrored field raises ValidationError at runtime."
    )


def test_reset_report_fields_are_subset_of_payload() -> None:
    """Every field of the reset report must be a field of the payload."""
    report_fields = set(LedgerCatalogueResetReport.model_fields)
    payload_fields = set(LedgerResetResult.model_fields)
    missing = report_fields - payload_fields
    assert not missing, (
        "LedgerResetResult is missing fields present on "
        f"LedgerCatalogueResetReport: {sorted(missing)}. The handler validates "
        "the report's model_dump against the extra-forbid payload, so an "
        "unmirrored field raises ValidationError at runtime."
    )


def test_remove_report_dump_validates_against_payload_and_round_trips() -> None:
    """The handler's strict_round_trip(Payload, report) path must not raise.

    Mirrors ``_ledger_lifecycle_cli.ledger_remove`` exactly and asserts the
    non-blocking ``stale_draft_revision_references`` advisory survives the
    boundary populated, not silently dropped.
    """
    report = _populated_removal_report()
    payload = strict_round_trip(LedgerRemoveResult, report)

    assert payload.transaction_id == _HEX_64_C
    assert len(payload.stale_draft_revision_references) == 1
    advisory = payload.stale_draft_revision_references[0]
    assert advisory.work_unit_id == _HEX_64_A
    assert advisory.calculation_revision_id == _HEX_64_B
    assert advisory.revision_state == "borrador"
    assert advisory.modelo == "130"
    assert advisory.filing_year == 2026
    assert advisory.period == "1T"
    # Blocking references must remain distinct from the draft advisory.
    assert len(payload.blocking_modelo_references) == 1


def test_reset_report_dump_validates_against_payload_and_round_trips() -> None:
    """The reset handler's strict_round_trip(Payload, report) path must not raise."""
    report = _populated_reset_report()
    payload = strict_round_trip(LedgerResetResult, report)

    assert payload.removed_transaction_ids == [_HEX_64_C]
    assert len(payload.stale_draft_revision_references) == 1
    advisory = payload.stale_draft_revision_references[0]
    assert advisory.revision_state == "borrador"
    assert advisory.modelo == "130"
    assert len(payload.blocking_modelo_references) == 1
