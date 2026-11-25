"""What a ledger row's savings-position link demands of its income category.

A row linked to a savings position is a capital-mobiliario row. The Renta
aggregation that reads it selects rows by that income category, so a linked row
that is read as business, or may still be, must carry that category: a row
linked this way and filed under another category would be read by neither.
"""

from __future__ import annotations

from typing import Final

from .enums import BusinessClassification, carries_business_figures
from .errors import TransactionValidationError

SAVINGS_LINK_IRPF_CATEGORY: Final = "capital_mobiliario"
"""The ledger IRPF category id of a row linked to a savings position."""

SAVINGS_LINK_CATEGORY_LOCALE_KEY: Final = "errors.transaction.savings_link_category"
SAVINGS_LINK_CATEGORY_DOOR: Final = "aeat app ledger classify"


def has_savings_link(*, posicion_ref: str | None) -> bool:
    """Report whether a row names a savings position."""
    return posicion_ref is not None


def validate_savings_link_category(
    *,
    posicion_ref: str | None,
    classification: BusinessClassification,
    irpf_category: str | None,
) -> None:
    """Refuse a linked row whose income category is not the capital-mobiliario one.

    A business-bearing row must carry the capital-mobiliario category. A row
    without a business component carries no category at all, which is allowed;
    one that still carries another category is refused.

    Raises:
        TransactionValidationError: When the row is linked and its category disagrees.
    """
    if not has_savings_link(posicion_ref=posicion_ref):
        return
    stated = None if irpf_category is None else irpf_category.strip().casefold()
    if stated == SAVINGS_LINK_IRPF_CATEGORY:
        return
    if stated is None and not carries_business_figures(classification):
        return
    raise TransactionValidationError(
        "a row linked to a savings position must carry the capital-mobiliario income category",
        translated_message=SAVINGS_LINK_CATEGORY_LOCALE_KEY,
        context={
            "category": SAVINGS_LINK_IRPF_CATEGORY,
            "stated": stated or "",
            "door": SAVINGS_LINK_CATEGORY_DOOR,
        },
    )


__all__ = [
    "SAVINGS_LINK_CATEGORY_DOOR",
    "SAVINGS_LINK_CATEGORY_LOCALE_KEY",
    "SAVINGS_LINK_IRPF_CATEGORY",
    "has_savings_link",
    "validate_savings_link_category",
]
