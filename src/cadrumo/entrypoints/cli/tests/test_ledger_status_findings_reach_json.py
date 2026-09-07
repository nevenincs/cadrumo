"""``ledger status`` publishes its findings, not just how many there were.

The status command already computed the period's readiness issues and the
bucket's drifted filings, and rendered both as text lines. Neither reached the
``--json`` envelope: a consumer could read ``readiness_issue_count`` but never
which rows, and could not see a stale filing at all. A second frontend cannot
act on a count, which is the whole reason this policy sits in the backend.

The count roll-up has its own hazard. ``OutputSchema`` forbids extra keys and
the result is projected from the report through a genuine JSON round trip, so a
field added to the report without a matching field here does not degrade -- it
raises, and the command fails outright. That is what these tests pin.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....application.ledger.models import LedgerStatusReport
from ....application.ledger.readiness_query import LedgerReadinessIssueV1
from ....application.ledger.stale_filing_query import LedgerStaleFilingV1
from ....core.json_contract import strict_round_trip
from .._ledger_payloads import (
    LedgerReadinessIssuePayload,
    LedgerStaleFilingPayload,
    LedgerStatusResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET = "b" * 32


def _report(**overrides: object) -> LedgerStatusReport:
    return LedgerStatusReport.model_validate(
        {
            "bucket_id": _BUCKET,
            "total_count": 0,
            "active_count": 0,
            "archived_count": 0,
            "stashed_count": 0,
            "pending_review_count": 0,
            "reviewed_count": 0,
            "skipped_count": 0,
            **overrides,
        },
    )


def test_every_report_field_survives_the_strict_json_projection() -> None:
    """The whole report must round-trip, or the status command raises outright.

    ``extra="forbid"`` means a report field with no counterpart on the result
    is a hard failure at emit time rather than a silently dropped key, so this
    is the test that a field added to one side reached the other.
    """
    result = strict_round_trip(LedgerStatusResult, _report(unconverted_currency_count=3))

    assert result.unconverted_currency_count == 3
    assert set(LedgerStatusReport.model_fields) <= set(LedgerStatusResult.model_fields)


def test_a_readiness_issue_reaches_json_with_the_facts_that_explain_it() -> None:
    """A count says something is wrong; the facts say which row and why."""
    issue = LedgerReadinessIssueV1(
        transaction_id="a" * 64,
        reason="missing_category",
        detail="a deductible row carries no category",
        transaction_present=True,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    payload = strict_round_trip(LedgerReadinessIssuePayload, issue)

    assert payload.transaction_id == issue.transaction_id
    assert payload.reason == "missing_category"
    assert payload.transaction_present is True
    assert payload.taxable_base == "100.00"


def test_an_absent_fact_stays_absent_rather_than_becoming_a_zero() -> None:
    """The missing value IS the finding, so it must not be filled in."""
    issue = LedgerReadinessIssueV1(
        transaction_id="b" * 64,
        reason="row_absent",
        detail="the catalogue no longer holds this row",
        transaction_present=False,
    )

    payload = strict_round_trip(LedgerReadinessIssuePayload, issue)

    assert payload.taxable_base is None
    assert payload.iva_amount is None
    assert payload.category_id is None


def test_a_stale_filing_reaches_json_carrying_its_coverage_qualifier() -> None:
    """``covers_current_fact_set`` must travel with the counts it qualifies.

    False means the comparison was sound but narrower than today's fact set.
    Publishing the counts without it would let a consumer read a narrow
    comparison as a complete one.
    """
    finding = LedgerStaleFilingV1(
        modelo="303",
        filing_year=2026,
        period="1T",
        calculation_revision_id="c" * 64,
        work_unit_id="w" * 64,
        changed_count=2,
        removed_count=1,
        covers_current_fact_set=False,
    )

    payload = strict_round_trip(LedgerStaleFilingPayload, finding)

    assert payload.changed_count == 2
    assert payload.removed_count == 1
    assert payload.covers_current_fact_set is False


def test_the_status_result_defaults_both_finding_lists_to_empty() -> None:
    """A bucket with no findings publishes empty lists, not absent keys.

    A consumer that has to distinguish "no stale filings" from "this build does
    not report them" is back to guessing, so the keys are always present.
    """
    result = strict_round_trip(LedgerStatusResult, _report())

    assert result.readiness_issues == []
    assert result.stale_filings == []
