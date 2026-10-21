"""Single classification refuses the same bad input whichever frontend submits it."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import TransactionCatalogue
from .. import classify_requests as requests
from ..classify_patch import build_manual_classification_patch
from ..models import ManualLedgerTransactionPatch
from .ledger_input_rule_support import PROFILE, current_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("field", ["taxable_base", "iva_amount"])
@pytest.mark.parametrize("amount", ["10.1234", "0.123", "1234.567"])
def test_amounts_carry_at_most_euro_cent_precision(field: str, amount: str) -> None:
    with pytest.raises(ValidationError, match="canonical decimal text"):
        requests.LedgerClassifyPatch.model_validate({"business_classification": "BUSINESS", field: amount})

    accepted = requests.LedgerClassifyPatch.model_validate({"business_classification": "BUSINESS", field: "10.12"})
    assert getattr(accepted, field) == "10.12"


@pytest.mark.parametrize("share", ["0.333", "0.1234", "0.005"])
def test_a_business_share_keeps_the_fraction_digits_it_has(share: str) -> None:
    assert requests.LedgerClassifyPatch(business_classification="MIXED", business_pct=share).business_pct == share


@pytest.mark.parametrize("rate", ["0.052", "0.075", "0.014", "0.005", "0.0175", "0.21"])
def test_an_iva_rate_keeps_the_fraction_digits_the_governed_rates_have(rate: str) -> None:
    assert requests.LedgerClassifyPatch(business_classification="BUSINESS", iva_rate=rate).iva_rate == rate


@pytest.mark.parametrize(
    ("fraction", "refusal"),
    [("-0.1", "canonical decimal text"), ("1.01", r"within 0\.\.1"), ("21", r"within 0\.\.1")],
)
@pytest.mark.parametrize(("field", "classification"), [("iva_rate", "BUSINESS"), ("business_pct", "MIXED")])
def test_a_rate_or_share_outside_the_unit_interval_is_refused(
    field: str, classification: str, fraction: str, refusal: str
) -> None:
    with pytest.raises(ValidationError, match=refusal):
        requests.LedgerClassifyPatch.model_validate({"business_classification": classification, field: fraction})


def test_a_rate_above_one_names_the_fraction_convention() -> None:
    with pytest.raises(ValidationError, match=r"within 0\.\.1; a percentage is a fraction, so 21% is 0\.21"):
        requests.LedgerClassifyPatch(business_classification="BUSINESS", iva_rate="21")


@pytest.mark.parametrize("amount", ["0.1234", "0.123", "1234.567"])
def test_the_explicit_m210_gross_income_carries_euro_cent_precision(amount: str) -> None:
    with pytest.raises(ValidationError, match="canonical decimal text"):
        requests.LedgerClassifyM210Options(gross_income_amount=amount)

    assert requests.LedgerClassifyM210Options(gross_income_amount="0.12").gross_income_amount == "0.12"


def test_the_explicit_m210_rate_is_a_fraction_of_one() -> None:
    assert requests.LedgerClassifyM210Options(applicable_rate="0.195").applicable_rate == "0.195"
    with pytest.raises(ValidationError, match=r"within 0\.\.1"):
        requests.LedgerClassifyM210Options(applicable_rate="1.01")


def test_business_share_must_lie_within_the_unit_interval_at_both_boundaries() -> None:
    for share in ("0", "1"):
        assert requests.LedgerClassifyPatch(business_classification="MIXED", business_pct=share).business_pct == share
    with pytest.raises(ValidationError, match=r"within 0\.\.1"):
        requests.LedgerClassifyPatch(business_classification="MIXED", business_pct="1.01")


@pytest.mark.parametrize("state", ["SKIPPED_BY_RULE", "FAILED_VALIDATION", "PROCESSED_UNCLASSIFIED"])
def test_pipeline_owned_dispositions_cannot_be_assigned(state: str) -> None:
    with pytest.raises(ValidationError, match="pipeline-owned"):
        requests.LedgerClassifyPatch(business_classification=state)

    assert requests.LedgerClassifyPatch(business_classification="PERSONAL").business_classification == "PERSONAL"


def test_a_share_belongs_to_a_mixed_classification_only() -> None:
    with pytest.raises(ValidationError, match="mixed classification requires exactly one business percentage"):
        requests.LedgerClassifyRequest(
            profile_id=PROFILE,
            transaction_id="b" * 12,
            patch=requests.LedgerClassifyPatch(business_classification="BUSINESS", business_pct="0.5"),
            patch_fields=("business_classification", "business_pct"),
        )

    mixed = requests.LedgerClassifyRequest(
        profile_id=PROFILE,
        transaction_id="b" * 12,
        patch=requests.LedgerClassifyPatch(business_classification="MIXED", business_pct="0.5"),
        patch_fields=("business_classification", "business_pct"),
    )
    assert mixed.patch.business_pct == "0.5"


def test_a_reason_must_say_something_and_an_omitted_reason_is_still_allowed() -> None:
    for blank in ("", "   "):
        with pytest.raises(ValidationError, match="must record why"):
            requests.LedgerClassifyPatch(business_classification="PERSONAL", notes=blank)

    with_reason = requests.LedgerClassifyPatch(business_classification="PERSONAL", notes="private subscription")
    assert with_reason.notes == "private subscription"
    assert requests.LedgerClassifyPatch(business_classification="PERSONAL").notes is None


def _classify_with(irpf_category: str) -> requests.LedgerClassifyRequest:
    return requests.LedgerClassifyRequest(
        profile_id=PROFILE,
        transaction_id="b" * 12,
        patch=requests.LedgerClassifyPatch(business_classification="BUSINESS", irpf_category=irpf_category),
        patch_fields=("business_classification", "irpf_category"),
    )


def _build_patch(
    payload: requests.LedgerClassifyRequest, operation: PinnedAuthorityOperation
) -> ManualLedgerTransactionPatch:
    current = current_transaction()
    return build_manual_classification_patch(
        payload,
        bucket_id=str(PROFILE),
        transaction_id=current.transaction_id,
        current=current,
        operation=operation,
        catalogue=TransactionCatalogue.model_validate({"transactions": {current.transaction_id: current}}),
    )


def test_irpf_category_must_be_declared_by_the_published_taxonomy(operation: PinnedAuthorityOperation) -> None:
    accepted = _build_patch(_classify_with(" Actividad_Economica "), operation)
    assert accepted.irpf_category == "actividad_economica"

    with pytest.raises(TransactionValidationError, match="rental_withholding") as refusal:
        _build_patch(_classify_with("rental_withholding"), operation)
    assert "arrendamiento_local" in str(refusal.value)


def test_a_blank_category_selects_no_irpf_category(operation: PinnedAuthorityOperation) -> None:
    patch = _build_patch(_classify_with("  "), operation)

    assert "irpf_category" in patch.model_fields_set
    assert patch.irpf_category is None
