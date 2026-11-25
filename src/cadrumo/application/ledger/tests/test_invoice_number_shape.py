"""An invoice number with no digit is the label read in its place, and blocks.

Real Decreto 1619/2012, art. 6.1.a, requires each invoice's number, correlative
within its series, so a value without a digit is no number at all.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority

from ....core.confirmation_gate import ConfirmationBlockReason, FindingResolutionAction
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....domain.iva.regime_legend import resolve_regime_legends
from ..confirmation_gate import (
    ConfirmationBlockedError,
    FindingResolution,
    confirmation_blockers,
    resolved_blockers,
)
from ..deterministic_findings import deterministic_findings
from ..invoice_draft_records import InvoiceDraft
from ..invoice_extraction_authority import default_invoice_extraction_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _legends(operation: PinnedAuthorityOperation):
    return resolve_regime_legends(operation=operation, effective_date=default_invoice_extraction_period().end_date)


def _number_findings(invoice_number: str | None) -> list[DraftDiscrepancyKind]:
    with bundled_indexed_authority().operation() as operation:
        findings = deterministic_findings(
            InvoiceDraft(invoice_number=invoice_number),
            legends=_legends(operation),
            operation=operation,
        )
    return [finding.kind for finding in findings if finding.field == "invoice_number"]


@pytest.mark.parametrize("label", ["FACTURA", "Factura", "INVOICE", "N.º", "FACTURA SIMPLIFICADA"])
def test_a_number_with_no_digit_is_refused(label: str) -> None:
    assert _number_findings(label) == [DraftDiscrepancyKind.INVOICE_NUMBER_UNNUMBERED]


@pytest.mark.parametrize("number", ["FA/0044", "RC-17", "7", "A1"])
def test_a_number_with_a_digit_is_not_a_finding(number: str) -> None:
    assert _number_findings(number) == []


@pytest.mark.parametrize("absent", [None, "", "   "])
def test_an_absent_number_raises_nothing_here(absent: str | None) -> None:
    assert _number_findings(absent) == []


def test_the_finding_blocks_until_the_operator_supplies_the_number() -> None:
    with bundled_indexed_authority().operation() as operation:
        draft = InvoiceDraft(invoice_number="FACTURA")
        reviewed = draft.model_copy(
            update={"discrepancies": deterministic_findings(draft, legends=_legends(operation), operation=operation)},
        )

    blockers = confirmation_blockers(reviewed)
    assert [blocker.reason for blocker in blockers] == [ConfirmationBlockReason.UNNUMBERED_INVOICE]

    with pytest.raises(ConfirmationBlockedError):
        resolved_blockers(draft=reviewed, resolutions=())

    supplied = FindingResolution(
        blocker_id=blockers[0].blocker_id,
        action=FindingResolutionAction.SUPPLY_VALUE,
        value="FA/0044",
    )
    assert resolved_blockers(draft=reviewed, resolutions=(supplied,)) == blockers
