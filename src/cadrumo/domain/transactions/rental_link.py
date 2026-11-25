"""What a ledger row's rental link demands of its income category.

A row linked to a lease or a property is a rental row. The Renta aggregation
that reads it selects rows by the rental income category, so a linked row that
is read as business, or may still be, must carry that category: a row linked
this way and filed under another category would be read by neither.
"""

from __future__ import annotations

from typing import Final

from .enums import BusinessClassification, carries_business_figures
from .errors import TransactionValidationError

RENTAL_LINK_IRPF_CATEGORY: Final = "capital_inmobiliario"
"""The ledger IRPF category id of a row linked to a lease or a property."""

RENTAL_LINK_CATEGORY_LOCALE_KEY: Final = "errors.transaction.rental_link_category"
RENTAL_LINK_CATEGORY_DOOR: Final = "aeat app ledger classify"


def has_rental_link(*, arrendamiento_ref: str | None, inmueble_ref: str | None) -> bool:
    """Report whether a row names a lease or a property."""
    return arrendamiento_ref is not None or inmueble_ref is not None


def validate_rental_link_category(
    *,
    arrendamiento_ref: str | None,
    inmueble_ref: str | None,
    classification: BusinessClassification,
    irpf_category: str | None,
) -> None:
    """Refuse a linked row whose income category is not the rental one.

    A business-bearing row must carry the rental category. A row without a
    business component carries no category at all, which is allowed; one that
    still carries another category is refused.

    Raises:
        TransactionValidationError: When the row is linked and its category disagrees.
    """
    if not has_rental_link(arrendamiento_ref=arrendamiento_ref, inmueble_ref=inmueble_ref):
        return
    stated = None if irpf_category is None else irpf_category.strip().casefold()
    if stated == RENTAL_LINK_IRPF_CATEGORY:
        return
    if stated is None and not carries_business_figures(classification):
        return
    raise TransactionValidationError(
        "a row linked to a lease or a property must carry the rental income category",
        translated_message=RENTAL_LINK_CATEGORY_LOCALE_KEY,
        context={
            "category": RENTAL_LINK_IRPF_CATEGORY,
            "stated": stated or "",
            "door": RENTAL_LINK_CATEGORY_DOOR,
        },
    )


__all__ = [
    "RENTAL_LINK_CATEGORY_DOOR",
    "RENTAL_LINK_CATEGORY_LOCALE_KEY",
    "RENTAL_LINK_IRPF_CATEGORY",
    "has_rental_link",
    "validate_rental_link_category",
]
