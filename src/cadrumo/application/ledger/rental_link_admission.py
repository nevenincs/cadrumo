"""Admitting the lease or property a ledger row names against the rows the profile holds.

A ledger row names a rental row of the profile by its stable row key. The ledger
and the profile are separate stores, so nothing but this check stops a row from
naming a lease or a property that was never stored, and the profile's removal
guard (which reads the ledger through :func:`rental_ledger_references`) is what
stops a stored one from being removed while a row names it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Final, Protocol

from ...domain.contribuyente.inmueble_facts import ARRENDAMIENTO_SECTION, INMUEBLE_SECTION
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.models import Transaction
from ..user_profile.rental_records import RentalLedgerReferences, canonical_rental_ref, rental_row_keys

_LEASE_UNKNOWN_LOCALE_KEY: Final = "errors.transaction.rental_lease_unknown"
_PROPERTY_UNKNOWN_LOCALE_KEY: Final = "errors.transaction.rental_property_unknown"
LEASE_LIST_DOOR: Final = "aeat config profile arrendamiento list"
PROPERTY_LIST_DOOR: Final = "aeat config profile inmueble list"


class RentalProfileFactsLoader(Protocol):
    """Read the path-keyed facts of the one profile a ledger action is bound to."""

    def __call__(self) -> Mapping[str, str] | None:
        """Return the profile's facts, or ``None`` when the profile holds none."""
        ...


def _held_refs(section_key: str, loader: RentalProfileFactsLoader | None) -> frozenset[str]:
    facts = loader() if loader is not None else None
    if facts is None:
        return frozenset[str]()
    return frozenset(canonical_rental_ref(key) for key in rental_row_keys(section_key, facts))


def _require_held(
    ref: str,
    *,
    section_key: str,
    loader: RentalProfileFactsLoader | None,
    locale_key: str,
    door: str,
) -> None:
    if ref not in _held_refs(section_key, loader):
        raise TransactionValidationError(
            f"rental reference {ref!r} names no stored row of the profile",
            translated_message=locale_key,
            context={"ref": ref, "door": door},
        )


def verify_rental_link_references(
    *,
    arrendamiento_ref: str | None,
    inmueble_ref: str | None,
    stored_arrendamiento_ref: str | None,
    stored_inmueble_ref: str | None,
    loader: RentalProfileFactsLoader | None,
) -> None:
    """Refuse a lease or property reference the row newly names that the profile does not hold.

    A reference the stored row already carried is not asked again: removing the
    row it names is refused while any ledger row names it, so it stays held.

    Raises:
        TransactionValidationError: Naming the command that lists the profile's rows.
    """
    if arrendamiento_ref is not None and arrendamiento_ref != stored_arrendamiento_ref:
        _require_held(
            arrendamiento_ref,
            section_key=ARRENDAMIENTO_SECTION,
            loader=loader,
            locale_key=_LEASE_UNKNOWN_LOCALE_KEY,
            door=LEASE_LIST_DOOR,
        )
    if inmueble_ref is not None and inmueble_ref != stored_inmueble_ref:
        _require_held(
            inmueble_ref,
            section_key=INMUEBLE_SECTION,
            loader=loader,
            locale_key=_PROPERTY_UNKNOWN_LOCALE_KEY,
            door=PROPERTY_LIST_DOOR,
        )


def rental_references_of(transactions: Iterable[Transaction]) -> RentalLedgerReferences:
    """Count the ledger rows that carry each lease, property and position reference, in every lifecycle state."""
    leases: dict[str, int] = {}
    properties: dict[str, int] = {}
    positions: dict[str, int] = {}
    for transaction in transactions:
        if transaction.arrendamiento_ref is not None:
            leases[transaction.arrendamiento_ref] = leases.get(transaction.arrendamiento_ref, 0) + 1
        if transaction.inmueble_ref is not None:
            properties[transaction.inmueble_ref] = properties.get(transaction.inmueble_ref, 0) + 1
        if transaction.posicion_ref is not None:
            positions[transaction.posicion_ref] = positions.get(transaction.posicion_ref, 0) + 1
    return RentalLedgerReferences(leases=leases, properties=properties, positions=positions)


type TransactionRowsLoader = Callable[[str], Iterable[Transaction]]
"""Load every ledger row of one profile bucket, in any lifecycle state."""


def rental_ledger_references(load_rows: TransactionRowsLoader) -> Callable[..., RentalLedgerReferences]:
    """Bind the profile's removal guard to a read of the ledger rows of the profile it is removing from."""

    def read(*, profile_id: str) -> RentalLedgerReferences:
        return rental_references_of(load_rows(profile_id))

    return read


__all__ = [
    "LEASE_LIST_DOOR",
    "PROPERTY_LIST_DOOR",
    "RentalProfileFactsLoader",
    "TransactionRowsLoader",
    "rental_ledger_references",
    "rental_references_of",
    "verify_rental_link_references",
]
