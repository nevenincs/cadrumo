"""Admitting a property or a lease row before it reaches the profile write door.

The profile write door judges each fact's shape; it cannot judge what a row means
together with the rest of the profile. This module does: a row must cohere as a
record, a lease must name a property the profile holds, a tenant identifier must
hold its control letter unless it is declared foreign, and a property that a
lease references cannot be removed.

The canonical form returned is the one stored: the same grammar a round trip
through the record gives, so a value typed in any accepted spelling is stored in
exactly one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Final

from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.identity.documents import IdentityError
from ...core.identity.tax_id import validate_spanish_tax_id
from ...domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ...domain.contribuyente.arrendamiento_record import ArrendamientoRecord
from ...domain.contribuyente.inmueble_facts import (
    arrendamiento_from_row,
    arrendamiento_row_values,
    inmueble_from_row,
    inmueble_row_values,
)
from ...domain.contribuyente.inmueble_record import InmuebleRecord
from ...domain.user_profile.errors import UserProfileValidationError

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_ROW_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.rental_row_invalid"
_LEASE_PROPERTY_MISSING_LOCALE_KEY: Final = "application.user_profile.errors.rental_lease_property_missing"
_PROPERTY_HAS_LEASES_LOCALE_KEY: Final = "application.user_profile.errors.rental_property_has_leases"
_TENANT_ID_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.rental_tenant_id_invalid"
_NEW_ROW_KEY: Final = 0


def _refusing_incoherent[RecordT](build: Callable[[], RecordT]) -> RecordT:
    """Run a record build, serving its refusal as the localised sentence that names the leaf."""
    try:
        return build()
    except ProfileAnswerTypeError as error:
        leaf = (error.context or {}).get("key", "row")
        raise UserProfileValidationError(
            translated_message=_ROW_INVALID_LOCALE_KEY, context={"leaf": str(leaf)}
        ) from error


def canonical_inmueble_values(values: Mapping[str, str], *, clave: int = _NEW_ROW_KEY) -> dict[str, str]:
    """Return the stored form of a property row, refusing a row that does not cohere as a record."""
    record = _refusing_incoherent(lambda: inmueble_from_row(clave, values))
    return inmueble_row_values(record)


def canonical_arrendamiento_values(
    values: Mapping[str, str],
    *,
    inmuebles: tuple[InmuebleRecord, ...],
    operation: PinnedAuthorityOperation,
    clave: int = _NEW_ROW_KEY,
) -> dict[str, str]:
    """Return the stored form of a lease row.

    The lease must name a property the profile holds, and every tenant whose
    identifier is not declared foreign must hold a valid Spanish identifier.
    """
    record = _refusing_incoherent(lambda: arrendamiento_from_row(clave, values))
    if record.inmueble not in {inmueble.clave for inmueble in inmuebles}:
        raise UserProfileValidationError(
            translated_message=_LEASE_PROPERTY_MISSING_LOCALE_KEY, context={"inmueble": record.inmueble}
        )
    tax_id_format = runtime_tax_id_format(authority=operation)
    for inquilino in record.inquilinos:
        if inquilino.extranjero:
            continue
        try:
            validate_spanish_tax_id(inquilino.nif, tax_id_format)
        except IdentityError as error:
            raise UserProfileValidationError(translated_message=_TENANT_ID_INVALID_LOCALE_KEY) from error
    return arrendamiento_row_values(record)


def require_inmueble_removable(clave: int, arrendamientos: tuple[ArrendamientoRecord, ...]) -> None:
    """Refuse removing a property that a lease of the profile still names."""
    leases = sorted(lease.clave for lease in arrendamientos if lease.inmueble == clave)
    if leases:
        raise UserProfileValidationError(
            translated_message=_PROPERTY_HAS_LEASES_LOCALE_KEY,
            context={"inmueble": clave, "leases": ", ".join(str(lease) for lease in leases)},
        )


__all__ = [
    "canonical_arrendamiento_values",
    "canonical_inmueble_values",
    "require_inmueble_removable",
]
