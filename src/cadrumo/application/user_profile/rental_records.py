"""Admitting a property or a lease row before it reaches the profile write door.

The profile write door judges each fact's shape; it cannot judge what a row means
together with the rest of the profile. This module does, for the two rental
sections, and the repeatable-row operation runs it inside add, update and remove
so every door -- the generic row command, the specific property and lease
commands, the manager and the window -- gives one acceptance and one refusal:

* a row must cohere as a record;
* a lease must name a property row the profile holds;
* a property's principal must be another property row the profile holds;
* a tenant identifier must hold its control letter unless it is declared foreign;
* a property that a lease or an accessory names cannot be removed.

The canonical form returned is the one stored: the same grammar a round trip
through the record gives, so a value typed in any accepted spelling is stored in
exactly one. Every refusal names the command that resolves it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.identity.documents import IdentityError
from ...core.identity.tax_id import validate_spanish_tax_id
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.contribuyente.inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    arrendamiento_from_row,
    arrendamiento_row_values,
    arrendamientos_from_facts,
    inmueble_from_row,
    inmueble_row_values,
    inmuebles_from_facts,
    rows_from_facts,
)
from ...domain.user_profile.errors import UserProfileValidationError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

RENTAL_SECTIONS: Final = frozenset({INMUEBLE_SECTION, ARRENDAMIENTO_SECTION})

_ROW_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.rental_row_invalid"
_LEASE_PROPERTY_MISSING_LOCALE_KEY: Final = "application.user_profile.errors.rental_lease_property_missing"
_PRINCIPAL_MISSING_LOCALE_KEY: Final = "application.user_profile.errors.rental_principal_missing"
_PROPERTY_HAS_LEASES_LOCALE_KEY: Final = "application.user_profile.errors.rental_property_has_leases"
_PROPERTY_HAS_ACCESSORIES_LOCALE_KEY: Final = "application.user_profile.errors.rental_property_has_accessories"
_TENANT_ID_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.rental_tenant_id_invalid"
_DOOR_FAMILY: Final = {INMUEBLE_SECTION: "inmueble", ARRENDAMIENTO_SECTION: "arrendamiento"}


class RentalRowMutation(StrEnum):
    """The row mutation an admission judges; it names the door command in a refusal."""

    ADD = "add"
    EDIT = "edit"
    REMOVE = "remove"


def _door(section_key: str, mutation: RentalRowMutation) -> str:
    return f"aeat config profile {_DOOR_FAMILY[section_key]} {mutation.value}"


def _refusing_incoherent[RecordT](build: Callable[[], RecordT], *, door: str) -> RecordT:
    """Run a record build, serving its refusal as the localised sentence that names the leaf and the door."""
    try:
        return build()
    except ProfileAnswerTypeError as error:
        leaf = (error.context or {}).get("key", "row")
        raise UserProfileValidationError(
            translated_message=_ROW_INVALID_LOCALE_KEY, context={"leaf": str(leaf), "door": door}
        ) from error


def is_rental_section(section_key: str) -> bool:
    """Report whether a repeatable section is one of the two rental record sections."""
    return section_key in RENTAL_SECTIONS


def admit_rental_row(
    section_key: str,
    *,
    row_key: int,
    row: Mapping[str, str],
    path_values: Mapping[str, object],
    authority: PinnedAuthorityOperation,
    mutation: RentalRowMutation,
) -> dict[str, str]:
    """Return the stored form of a rental row, refusing a row the profile cannot hold.

    ``path_values`` are the facts of the profile the row is written into; ``row``
    is the complete row as it will stand after the mutation.
    """
    if section_key == INMUEBLE_SECTION:
        return _admit_inmueble(row_key, row, path_values, mutation)
    if section_key == ARRENDAMIENTO_SECTION:
        return _admit_arrendamiento(row_key, row, path_values, authority, mutation)
    raise UserProfileValidationError(f"section {section_key!r} is not a rental record section")


def _admit_inmueble(
    row_key: int, row: Mapping[str, str], path_values: Mapping[str, object], mutation: RentalRowMutation
) -> dict[str, str]:
    record = _refusing_incoherent(lambda: inmueble_from_row(row_key, row), door=_door(INMUEBLE_SECTION, mutation))
    principal = record.inmueble_principal
    if principal is not None and principal not in {
        clave for clave in rows_from_facts(INMUEBLE_SECTION, path_values) if clave != row_key
    }:
        raise UserProfileValidationError(
            translated_message=_PRINCIPAL_MISSING_LOCALE_KEY,
            context={"principal": principal, "door": _door(INMUEBLE_SECTION, RentalRowMutation.ADD)},
        )
    return inmueble_row_values(record)


def _admit_arrendamiento(
    row_key: int,
    row: Mapping[str, str],
    path_values: Mapping[str, object],
    authority: PinnedAuthorityOperation,
    mutation: RentalRowMutation,
) -> dict[str, str]:
    record = _refusing_incoherent(
        lambda: arrendamiento_from_row(row_key, row), door=_door(ARRENDAMIENTO_SECTION, mutation)
    )
    if record.inmueble not in {inmueble.clave for inmueble in inmuebles_from_facts(path_values)}:
        raise UserProfileValidationError(
            translated_message=_LEASE_PROPERTY_MISSING_LOCALE_KEY,
            context={"inmueble": record.inmueble, "door": _door(INMUEBLE_SECTION, RentalRowMutation.ADD)},
        )
    tax_id_format = runtime_tax_id_format(authority=authority)
    for inquilino in record.inquilinos:
        if inquilino.extranjero:
            continue
        try:
            validate_spanish_tax_id(inquilino.nif, tax_id_format)
        except IdentityError as error:
            raise UserProfileValidationError(
                translated_message=_TENANT_ID_INVALID_LOCALE_KEY,
                context={"door": _door(ARRENDAMIENTO_SECTION, mutation)},
            ) from error
    return arrendamiento_row_values(record)


def require_rental_row_removable(section_key: str, *, row_key: int, path_values: Mapping[str, object]) -> None:
    """Refuse removing a property that a lease or an accessory of the profile still names."""
    if section_key != INMUEBLE_SECTION:
        return
    leases = sorted(lease.clave for lease in arrendamientos_from_facts(path_values) if lease.inmueble == row_key)
    if leases:
        raise UserProfileValidationError(
            translated_message=_PROPERTY_HAS_LEASES_LOCALE_KEY,
            context={
                "inmueble": row_key,
                "leases": ", ".join(str(lease) for lease in leases),
                "door": _door(ARRENDAMIENTO_SECTION, RentalRowMutation.REMOVE),
            },
        )
    accessories = sorted(
        property_.clave for property_ in inmuebles_from_facts(path_values) if property_.inmueble_principal == row_key
    )
    if accessories:
        raise UserProfileValidationError(
            translated_message=_PROPERTY_HAS_ACCESSORIES_LOCALE_KEY,
            context={
                "inmueble": row_key,
                "accessories": ", ".join(str(clave) for clave in accessories),
                "door": _door(INMUEBLE_SECTION, RentalRowMutation.EDIT),
            },
        )


__all__ = [
    "RENTAL_SECTIONS",
    "RentalRowMutation",
    "admit_rental_row",
    "is_rental_section",
    "require_rental_row_removable",
]
