"""Stated values keyed by a casilla's registry identity, resolved in the return's own edition.

A persona may state an amount under ``roles`` keyed by a casilla's
``continuidad_id`` or ``semantic_role`` instead of its casilla id, so the
figure follows the legal concept across editions. The key resolves only
through the registry: in the edition the law selects for the return (or the
one the calculation used), the casillas whose ``continuidad_id`` equals the key
are the candidates, else those whose ``semantic_role`` equals it. Exactly one
candidate resolves; none or several leave the value unresolved, and the table
then lists it as unchecked rather than comparing it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import cache

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.tests.personas import ExpectedValue


@dataclass(frozen=True, slots=True)
class CasillaIdentity:
    """The identities a role key may name, of one casilla of an edition."""

    casilla_id: str
    continuidad_id: str | None
    semantic_role: str | None


@dataclass(frozen=True, slots=True)
class StatedCasilla:
    """One stated amount and the casilla it is compared at; ``casilla`` is ``None`` for an unresolved role."""

    label: str
    casilla: str | None
    amount: str
    role: str | None = None


def identities(revision: ModeloRevision) -> tuple[CasillaIdentity, ...]:
    """The casillas of ``revision`` with the identities a role key may name."""
    return tuple(
        CasillaIdentity(str(casilla.id), casilla.continuidad_id, casilla.semantic_role) for casilla in revision.casillas
    )


def resolve(casillas: Iterable[CasillaIdentity], key: str) -> str | None:
    """The one casilla ``key`` names by ``continuidad_id``, else by ``semantic_role``; ``None`` for none or several."""
    held = tuple(casillas)
    matches = [item.casilla_id for item in held if item.continuidad_id == key] or [
        item.casilla_id for item in held if item.semantic_role == key
    ]
    return matches[0] if len(matches) == 1 else None


@cache
def edition_identities(modelo: str, year: int, period: str) -> tuple[CasillaIdentity, ...]:
    """The casillas of the edition the law selects for the return; none when the registry selects no edition."""
    with bundled_indexed_authority().operation() as operation:
        try:
            return identities(operation.revision_for_context(modelo, filing_year=year, period=period))
        except RegistryError:
            return ()


@cache
def revision_identities(modelo: str, revision_id: str) -> tuple[CasillaIdentity, ...]:
    """The casillas of the named edition, as a calculation reports the edition it used."""
    with bundled_indexed_authority().operation() as operation:
        return identities(operation.revision(modelo, revision_id))


def unresolved_roles(value: ExpectedValue, year: int) -> set[str]:
    """The ``role:<key>`` items of ``value`` that name no single casilla of the return's edition."""
    if not value.roles:
        return set()
    casillas = edition_identities(value.modelo, year, value.period)
    return {f"role:{key}" for key, _ in value.roles if resolve(casillas, key) is None}


def stated_casillas(values: Iterable[ExpectedValue], casillas: tuple[CasillaIdentity, ...]) -> list[StatedCasilla]:
    """Every stated amount with its casilla: a casilla as stated, a role as ``casillas`` resolve it."""
    stated: list[StatedCasilla] = []
    for value in values:
        stated += [StatedCasilla(f"c{casilla}", casilla, amount) for casilla, amount in value.casillas]
        stated += [_role(key, amount, casillas) for key, amount in value.roles]
    return stated


def compared(
    values: Iterable[ExpectedValue], casillas: tuple[CasillaIdentity, ...], unchecked: Iterable[str]
) -> list[StatedCasilla]:
    """The stated amounts the calculation is compared with: all but an unresolved role the row lists as unchecked.

    A role that names no single casilla of the calculation's edition but is not listed unchecked stays compared,
    against no value, so it can never pass silently.
    """
    listed = set(unchecked)
    return [
        item
        for item in stated_casillas(values, casillas)
        if item.casilla is not None or f"role:{item.role}" not in listed
    ]


def differing(stated: Iterable[StatedCasilla], got: Mapping[str, object]) -> list[tuple[StatedCasilla, object]]:
    """Each stated amount the calculation does not equal, with the value it gave (``None`` for none)."""
    pairs = [(item, got.get(item.casilla) if item.casilla is not None else None) for item in stated]
    return [(item, found) for item, found in pairs if _decimal(found) != _decimal(item.amount)]


def mismatch_text(item: StatedCasilla, found: object) -> str:
    """The reason text of one differing amount, as ``<label> exp <amount> got <value>``."""
    return f"{item.label} exp {item.amount} got {found}"


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _role(key: str, amount: str, casillas: tuple[CasillaIdentity, ...]) -> StatedCasilla:
    casilla = resolve(casillas, key)
    label = f"role {key} (casilla {casilla})" if casilla is not None else f"role {key}"
    return StatedCasilla(label, casilla, amount, role=key)


__all__ = [
    "CasillaIdentity",
    "StatedCasilla",
    "compared",
    "differing",
    "edition_identities",
    "identities",
    "mismatch_text",
    "resolve",
    "revision_identities",
    "stated_casillas",
    "unresolved_roles",
]
