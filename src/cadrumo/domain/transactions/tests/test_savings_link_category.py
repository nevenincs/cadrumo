"""A row linked to a savings position carries the capital-mobiliario category, or none when it is not business."""

from __future__ import annotations

import pytest

from ..enums import BusinessClassification
from ..errors import TransactionValidationError
from ..savings_link import (
    SAVINGS_LINK_CATEGORY_LOCALE_KEY,
    SAVINGS_LINK_IRPF_CATEGORY,
    validate_savings_link_category,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BUSINESS_BEARING = (BusinessClassification.BUSINESS, BusinessClassification.MIXED)


def _validate(
    *,
    classification: BusinessClassification,
    irpf_category: str | None,
    posicion_ref: str | None = "pos-1",
) -> None:
    validate_savings_link_category(
        posicion_ref=posicion_ref,
        classification=classification,
        irpf_category=irpf_category,
    )


@pytest.mark.parametrize("classification", _BUSINESS_BEARING)
def test_a_business_row_linked_with_the_savings_category_is_admitted(classification: BusinessClassification) -> None:
    _validate(classification=classification, irpf_category=SAVINGS_LINK_IRPF_CATEGORY)


@pytest.mark.parametrize("classification", _BUSINESS_BEARING)
@pytest.mark.parametrize("irpf_category", [None, "trabajo", "capital_inmobiliario"])
def test_a_business_row_linked_under_another_category_or_none_is_refused(
    classification: BusinessClassification, irpf_category: str | None
) -> None:
    with pytest.raises(TransactionValidationError) as caught:
        _validate(classification=classification, irpf_category=irpf_category)

    assert caught.value.translated_message == SAVINGS_LINK_CATEGORY_LOCALE_KEY
    assert caught.value.context is not None
    assert caught.value.context["category"] == SAVINGS_LINK_IRPF_CATEGORY
    assert caught.value.context["door"] == "aeat app ledger classify"


def test_a_personal_row_linked_carries_no_category() -> None:
    _validate(classification=BusinessClassification.PERSONAL, irpf_category=None)


def test_a_personal_row_linked_cannot_keep_another_category() -> None:
    with pytest.raises(TransactionValidationError):
        _validate(classification=BusinessClassification.PERSONAL, irpf_category="trabajo")


def test_a_row_not_yet_classified_is_linked_before_its_category() -> None:
    _validate(classification=BusinessClassification.NOT_YET_PROCESSED, irpf_category=None)


def test_the_category_is_read_case_and_space_insensitively() -> None:
    _validate(classification=BusinessClassification.BUSINESS, irpf_category="  Capital_Mobiliario ")


@pytest.mark.parametrize("classification", list(BusinessClassification))
@pytest.mark.parametrize("irpf_category", [None, "trabajo", SAVINGS_LINK_IRPF_CATEGORY])
def test_a_row_without_a_link_is_not_judged(classification: BusinessClassification, irpf_category: str | None) -> None:
    _validate(classification=classification, irpf_category=irpf_category, posicion_ref=None)
