"""Admitting a position row before it reaches the profile write door.

The profile write door judges each fact's shape; it cannot judge what a row means
with the pinned authority. This module does, for the position section, and the
repeatable-row operation runs it inside add and update so every door -- the
generic row command, the specific position command, the manager and the window --
gives one acceptance and one refusal:

* a row must cohere as a record;
* the source state must be a state the pinned country catalogue holds;
* a Spanish payer's identifier must hold its control character, because it is
  the key that joins the position to the payer's suffered-withholding record.

A foreign payer's identifier keeps only its shape check: it is not a Spanish tax
identifier and the payer record never names it.

The canonical form returned is the one stored, so a value typed in any accepted
spelling is stored in exactly one. Every refusal names the command that resolves it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.identity.documents import IdentityError
from ...core.identity.tax_id import validate_spanish_tax_id
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.contribuyente.posicion_facts import POSICION_SECTION, posicion_from_row, posicion_row_values
from ...domain.iva.establishment import SPAIN_COUNTRY_CODE, catalogued_country_codes
from ...domain.user_profile.errors import UserProfileValidationError
from .rental_records import ProfileRecordRowMutation

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.contribuyente.posicion_record import PosicionRecord

_ROW_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.posicion_row_invalid"
_COUNTRY_UNKNOWN_LOCALE_KEY: Final = "application.user_profile.errors.posicion_country_unknown"
_PAYER_ID_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.posicion_payer_id_invalid"


def _door(mutation: ProfileRecordRowMutation) -> str:
    return f"aeat config profile posicion {mutation.value}"


def is_posicion_section(section_key: str) -> bool:
    """Report whether a repeatable section is the position record section."""
    return section_key == POSICION_SECTION


def admit_posicion_row(
    *,
    row_key: int,
    row: Mapping[str, str],
    authority: PinnedAuthorityOperation,
    mutation: ProfileRecordRowMutation,
) -> dict[str, str]:
    """Return the stored form of a position row, refusing a row the profile cannot hold.

    ``row`` is the complete row as it will stand after the mutation.
    """
    try:
        record = posicion_from_row(row_key, row)
    except ProfileAnswerTypeError as error:
        leaf = (error.context or {}).get("key", "row")
        raise UserProfileValidationError(
            translated_message=_ROW_INVALID_LOCALE_KEY, context={"leaf": str(leaf), "door": _door(mutation)}
        ) from error
    if record.pais_origen not in catalogued_country_codes(operation=authority):
        raise UserProfileValidationError(
            translated_message=_COUNTRY_UNKNOWN_LOCALE_KEY,
            context={"pais": record.pais_origen, "door": _door(mutation)},
        )
    _require_spanish_payer_identifier(record, authority, mutation)
    return posicion_row_values(record)


def _require_spanish_payer_identifier(
    record: PosicionRecord, authority: PinnedAuthorityOperation, mutation: ProfileRecordRowMutation
) -> None:
    if record.pais_origen != SPAIN_COUNTRY_CODE:
        return
    try:
        validate_spanish_tax_id(record.pagador_nif, runtime_tax_id_format(authority=authority))
    except IdentityError as error:
        raise UserProfileValidationError(
            translated_message=_PAYER_ID_INVALID_LOCALE_KEY, context={"door": _door(mutation)}
        ) from error


__all__ = ["admit_posicion_row", "is_posicion_section"]
