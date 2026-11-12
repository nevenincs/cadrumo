"""Admitting the savings position a ledger row names against the rows the profile holds.

A ledger row names a position row of the profile by its stable row key, together
with the capital-mobiliario concept the income belongs to. The ledger and the
profile are separate stores, so nothing but this check stops a row from naming a
position that was never stored, or a concept the position's kind cannot carry. The
profile's removal guard reads the ledger through the same reference reader the
rental rows use, and stops a stored position from being removed while a row names it.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Final

from ...domain.calculations.registry.capital_mobiliario_facts import resolve_capital_mobiliario_concept_vocabulary
from ...domain.contribuyente.inmueble_facts import rows_from_facts
from ...domain.contribuyente.posicion_facts import POSICION_SECTION
from ...domain.transactions.errors import TransactionValidationError
from ..user_profile.rental_records import canonical_rental_ref

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from .rental_link_admission import RentalProfileFactsLoader

_POSITION_UNKNOWN_LOCALE_KEY: Final = "errors.transaction.savings_position_unknown"
_CONCEPT_KIND_LOCALE_KEY: Final = "errors.transaction.savings_concept_kind"
POSITION_LIST_DOOR: Final = "aeat config profile posicion list"
CONCEPT_DOOR: Final = "aeat app ledger classify"


def _held_kinds(loader: RentalProfileFactsLoader | None) -> Mapping[str, str]:
    facts = loader() if loader is not None else None
    if facts is None:
        return dict[str, str]()
    return {
        canonical_rental_ref(clave): row.get("tipo", "")
        for clave, row in rows_from_facts(POSICION_SECTION, facts).items()
    }


def verify_savings_link_references(
    *,
    posicion_ref: str | None,
    concepto: str | None,
    stored_posicion_ref: str | None,
    stored_concepto: str | None,
    booked_date: date,
    operation: PinnedAuthorityOperation,
    loader: RentalProfileFactsLoader | None,
) -> None:
    """Refuse a position the row newly names that the profile does not hold, or a concept its kind cannot carry.

    A pair the stored row already carried is not asked again: removing the
    position it names is refused while any ledger row names it, so it stays held.

    Raises:
        TransactionValidationError: Naming the command that lists the profile's positions
            or the one that sets the concept.
    """
    if posicion_ref is None:
        return
    if posicion_ref == stored_posicion_ref and concepto == stored_concepto:
        return
    kinds = _held_kinds(loader)
    if posicion_ref not in kinds:
        raise TransactionValidationError(
            f"savings position reference {posicion_ref!r} names no stored row of the profile",
            translated_message=_POSITION_UNKNOWN_LOCALE_KEY,
            context={"ref": posicion_ref, "door": POSITION_LIST_DOOR},
        )
    if concepto is None:
        return
    required = (
        resolve_capital_mobiliario_concept_vocabulary(effective_date=booked_date, authority=operation)
        .require(concepto)
        .requires_position_kind
    )
    if required is not None and kinds[posicion_ref] != required:
        raise TransactionValidationError(
            f"concept {concepto!r} is admitted only on a {required!r} position",
            translated_message=_CONCEPT_KIND_LOCALE_KEY,
            context={"concepto": concepto, "kind": required, "ref": posicion_ref, "door": CONCEPT_DOOR},
        )


__all__ = ["CONCEPT_DOOR", "POSITION_LIST_DOOR", "verify_savings_link_references"]
