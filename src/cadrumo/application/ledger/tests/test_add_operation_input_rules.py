"""Manual add refuses the same bad input whichever frontend submits it."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ..ledger_add_command import resolve_ledger_add_flow, resolve_ledger_add_irpf_category
from ..ledger_add_contracts import LedgerAddRequest
from .ledger_input_rule_support import PROFILE

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _request(**values: str) -> LedgerAddRequest:
    return LedgerAddRequest.model_validate(
        {
            "profile_id": PROFILE,
            "booked_date": date(_YEAR, 4, 15).isoformat(),
            "amount": "10.00",
            "direction": "OUTGOING",
            "description": "Office materials",
            **values,
        },
    )


def test_a_negative_amount_names_the_magnitude_rule() -> None:
    """Direction carries the flow, so the sign is refused with that remedy."""
    with pytest.raises(ValidationError, match="non-negative magnitude"):
        _request(amount="-49.99")

    assert _request(amount="0.01").amount == "0.01"


@pytest.mark.parametrize("field", ["amount", "taxable_base", "iva_amount", "recargo_amount"])
def test_amounts_carry_at_most_euro_cent_precision(field: str) -> None:
    with pytest.raises(ValidationError, match="canonical decimal text"):
        _request(**{field: "10.1234"})

    assert getattr(_request(**{field: "10.12"}), field) == "10.12"


@pytest.mark.parametrize("field", ["iva_rate", "business_pct"])
@pytest.mark.parametrize("fraction", ["0.333", "0.052", "0.075", "0.0175", "0.005"])
def test_a_share_or_a_rate_keeps_the_fraction_digits_it_has(field: str, fraction: str) -> None:
    assert getattr(_request(**{field: fraction}), field) == fraction


@pytest.mark.parametrize("state", ["SKIPPED_BY_RULE", "FAILED_VALIDATION", "PROCESSED_UNCLASSIFIED"])
def test_pipeline_owned_classifications_cannot_be_assigned(state: str) -> None:
    with pytest.raises(TransactionValidationError, match="assigned by the ledger pipeline"):
        resolve_ledger_add_flow(_request(business_classification=state))


@pytest.mark.parametrize("state", ["NOT_YET_PROCESSED", "BUSINESS", "MIXED", "PERSONAL"])
def test_the_import_default_and_every_manual_classification_are_accepted(state: str) -> None:
    classification, direction = resolve_ledger_add_flow(_request(business_classification=state))

    assert classification is BusinessClassification(state)
    assert direction is TransactionDirection.OUTGOING


def test_irpf_category_must_be_declared_by_the_published_taxonomy(operation: PinnedAuthorityOperation) -> None:
    assert (
        resolve_ledger_add_irpf_category(_request(irpf_category=" Actividad_Economica "), operation=operation)
        == "actividad_economica"
    )

    with pytest.raises(TransactionValidationError, match="rental_withholding") as refusal:
        resolve_ledger_add_irpf_category(_request(irpf_category="rental_withholding"), operation=operation)
    assert "arrendamiento_local" in str(refusal.value)


def test_an_absent_or_blank_category_is_no_category(operation: PinnedAuthorityOperation) -> None:
    assert resolve_ledger_add_irpf_category(_request(), operation=operation) is None
    assert resolve_ledger_add_irpf_category(_request(irpf_category="   "), operation=operation) is None


@pytest.mark.usefixtures("operation")
def test_an_added_row_prorrata_reference_must_use_the_reference_grammar() -> None:
    assert (
        _request(prorrata_reference=f"prorrata:{_YEAR}:definitiva:general").prorrata_reference
        == f"prorrata:{_YEAR}:definitiva:general"
    )

    for malformed in ("telefonia_movil", f"prorrata:{_YEAR}:provisional:nonexistent", f"prorrata:{_YEAR}:definitiva"):
        with pytest.raises(ValidationError, match="prorrata_reference"):
            _request(prorrata_reference=malformed)

    with pytest.raises(ValidationError, match="at most 128 characters"):
        _request(prorrata_reference="p" * 129)
