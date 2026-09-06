"""The filing evidence gate must refuse a row it cannot read, not absolve it.

A frozen evidence bundle stores its enum-valued facts as bare strings so it can
round-trip through the strict persistence boundary. Parsing them back can fail,
and this gate used to answer "no gap" when it did: an unreadable
``lifecycle_state`` is not ``ACTIVE``, an unreadable ``business_classification``
is not business-bearing, and both comparisons are satisfied by the ``None`` a
failed parse produced. A Modelo 303 input-IVA deduction could therefore reach a
filing with no documento justificativo behind it (LIVA art. 97; LGT art. 105.1
puts the burden on the taxpayer).

Refusing more is only half of what these tests hold. The other half is that the
gate must not refuse a row whose unreadable field would not have decided
anything -- a drifted direction on an archived row still raises no question --
because a refusal gate that fires on rows it has no question about teaches the
operator to route around it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.modelos.ledger_filing_snapshot import LedgerEvidenceRow
from .._ledger_evidence_gate import ledger_evidence_row_missing_deductible_iva_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DEDUCTIBLE_PURCHASE = {
    "transaction_id": "a" * 64,
    "fingerprint": "b" * 64,
    "booked_date": "2026-02-15",
    "amount": Decimal("242.00"),
    "currency": "EUR",
    "direction": "OUTGOING",
    "business_classification": "BUSINESS",
    "lifecycle_state": "ACTIVE",
    "taxable_base": Decimal("200.00"),
    "iva_rate": Decimal("0.21"),
    "iva_amount": Decimal("42.00"),
    "legal_refs": ("ley-37-1992-art-97",),
    "source_refs": ("aeat-modelo-303",),
}


def _row(**overrides: object) -> LedgerEvidenceRow:
    """A business purchase deducting input IVA with no evidence attached."""
    return LedgerEvidenceRow.model_validate({**_DEDUCTIBLE_PURCHASE, **overrides})


def test_the_baseline_row_is_the_gap_the_gate_exists_to_catch() -> None:
    """Positive control: without it, every case below could pass vacuously."""
    assert ledger_evidence_row_missing_deductible_iva_evidence(_row()) is True


@pytest.mark.parametrize(
    ("field", "stored_value"),
    [
        ("lifecycle_state", "HIBERNATING"),
        ("business_classification", "QUANTUM"),
        ("direction", "SIDEWAYS"),
    ],
)
def test_a_required_field_this_build_cannot_parse_refuses_the_row(field: str, stored_value: str) -> None:
    """Schema drift on a non-optional field is unjudgeable, so it is a gap.

    These three are ``Field(min_length=1)`` on the evidence row, so the stored
    value is never absent. A value that will not parse is therefore drift, not
    a default, and the row's contribution to the filing cannot be vouched for.
    """
    assert ledger_evidence_row_missing_deductible_iva_evidence(_row(**{field: stored_value})) is True


def test_a_deduction_side_row_whose_cuota_was_never_captured_is_a_gap() -> None:
    """Absent is not zero: the claim was never recorded, not recorded as nil."""
    assert ledger_evidence_row_missing_deductible_iva_evidence(_row(iva_amount=None)) is True


@pytest.mark.parametrize(
    ("description", "overrides"),
    [
        ("an attachment answers the refusal", {"attachment_ids": ("purchase-invoice-scan",)}),
        ("a linked validated invoice answers it too", {"invoice_id": "invoice-1"}),
        ("a stored purchase-invoice record does as well", {"purchase_invoice_evidence_id": "pie-1"}),
        ("a sale is not on the deducible side", {"direction": "INCOMING"}),
        ("an internal transfer has no invoice kind", {"direction": "INTERNAL_TRANSFER"}),
        ("an archived row contributes nothing", {"lifecycle_state": "ARCHIVED"}),
        ("a personal row bears no business IVA", {"business_classification": "PERSONAL"}),
        ("a proven zero cuota deducts nothing", {"iva_amount": Decimal("0.00")}),
    ],
)
def test_rows_that_raise_no_question_are_still_cleared(
    description: str,
    overrides: dict[str, object],
) -> None:
    """Tightening must not turn the gate into a blanket refusal."""
    assert ledger_evidence_row_missing_deductible_iva_evidence(_row(**overrides)) is False, description


@pytest.mark.parametrize(
    ("description", "overrides"),
    [
        (
            "an archived row is excluded before its direction is read",
            {"direction": "SIDEWAYS", "lifecycle_state": "ARCHIVED"},
        ),
        (
            "a personal row is excluded before its direction is read",
            {"direction": "SIDEWAYS", "business_classification": "PERSONAL"},
        ),
        (
            "an evidenced row is cleared before its cuota is read",
            {"iva_amount": None, "attachment_ids": ("purchase-invoice-scan",)},
        ),
        (
            "a sale with no cuota is a sale, not a missing deduction",
            {"iva_amount": None, "direction": "INCOMING"},
        ),
    ],
)
def test_an_unreadable_field_that_would_not_have_decided_anything_does_not_refuse(
    description: str,
    overrides: dict[str, object],
) -> None:
    """The check ORDER is the invariant, not merely which checks exist.

    Each required field is consulted only while the row is still a candidate.
    Reading all three up front would refuse rows that raise no question, and a
    gate that fires on those is one operators learn to work around.
    """
    assert ledger_evidence_row_missing_deductible_iva_evidence(_row(**overrides)) is False, description


def test_an_unreadable_iva_category_cannot_buy_an_exemption() -> None:
    """Category is the one axis still read as optional; drift must not exempt.

    ``iva_category`` keeps its absent-or-unreadable conflation because absence
    is a real state there. That is only safe while both answers route to the
    direction-derived flow rather than to the evidence-exempt set, so this
    pins that they do: a drifted category on a purchase still refuses.
    """
    assert ledger_evidence_row_missing_deductible_iva_evidence(_row(iva_category="NOT_A_CATEGORY")) is True
