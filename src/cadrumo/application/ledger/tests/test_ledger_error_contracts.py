"""Ledger refusals keep semantic evidence separate from registered error codes."""

from __future__ import annotations

import pytest

from ....core.errors.error_codes import ErrorCategory, get_registered_error_code
from ..evidence import PurchaseInvoiceEvidenceSnapshotConflictError
from ..ledger_add_command import SourceJurisdictionRequiredError
from ..ledger_add_contracts import LedgerAddSourceJurisdictionCode
from ..ledger_add_results import build_ledger_add_validation_messages

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    "jurisdiction_code", ["source_jurisdiction_required_irnr", "source_jurisdiction_required_beckham"]
)
def test_jurisdiction_refusal_retains_its_finite_code_and_prompt(
    jurisdiction_code: LedgerAddSourceJurisdictionCode,
) -> None:
    """The operation can retain its reason without shadowing the registry code."""
    prompt = "Provide the source jurisdiction before writing."
    error = SourceJurisdictionRequiredError(jurisdiction_code, prompt)

    registered = get_registered_error_code(error)

    assert error.jurisdiction_code == jurisdiction_code
    assert error.message == prompt
    assert error.code == registered
    assert registered.code == "REFUSED_LEDGER_SOURCE_JURISDICTION_REQUIRED"
    assert registered.category is ErrorCategory.REFUSED
    assert registered.retryable is False
    assert build_ledger_add_validation_messages(error) == (prompt,)


def test_evidence_snapshot_change_requires_new_review_before_retrying() -> None:
    """An identical stale witness is not declared safe to retry automatically."""
    error = PurchaseInvoiceEvidenceSnapshotConflictError("purchase invoice evidence changed after preflight")

    registered = get_registered_error_code(error)

    assert registered.code == "REFUSED_PURCHASE_INVOICE_EVIDENCE_SNAPSHOT_CHANGED"
    assert registered.category is ErrorCategory.REFUSED
    assert registered.retryable is False
    assert str(error) == "purchase invoice evidence changed after preflight"
