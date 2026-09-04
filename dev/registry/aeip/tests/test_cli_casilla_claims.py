"""Tests for the AEIP inventory's casilla-claim analysis.

`dev.quality.module_test_reach` listed `dev/registry/aeip/cli.py` as unreached.
Its inventory verb reports id reuse across the anexo-A continuity family, and
that report was answering two different questions with one number.

Pooling every revision under a bare casilla id counts a programme that INHERITED
an id in a later year as colliding with the programme that held it earlier. That
is ordinary AEAT reassignment. The finding that matters is two programmes
claiming one casilla WITHIN a revision, because only there is the id ambiguous.

Measured on the live modelo 100 family before the change: the pooled number
reported thirty, and the same-revision number was zero. Every reported collision
was expected behaviour, and a real one appearing would have moved thirty to
thirty-one with nothing to tell it apart - which is the "a repeated box number
is candidate evidence, not identity" distinction this campaign exists to keep.

The live case at the end asserts the RELATIONSHIP between the two numbers rather
than either value, so it stays true as the registry grows.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ..cli import _load, casilla_claims

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@dataclass(frozen=True)
class _Occurrence:
    revision_id: str
    casilla_id: str


@dataclass(frozen=True)
class _Event:
    slug: str
    occurrences: tuple[_Occurrence, ...]


@dataclass(frozen=True)
class _Inventory:
    events: tuple[_Event, ...]


def _inventory(*events: _Event) -> _Inventory:
    return _Inventory(events=events)


def test_two_programmes_sharing_a_casilla_in_one_revision_collide() -> None:
    """The real ambiguity: within one revision an id can name only one programme."""
    inventory = _inventory(
        _Event("alpha", (_Occurrence("2024", "0100"),)),
        _Event("bravo", (_Occurrence("2024", "0100"),)),
    )

    within_revision, _ = casilla_claims(inventory)  # type: ignore[arg-type]

    assert within_revision[("2024", "0100")] == {"alpha", "bravo"}


def test_an_id_reassigned_in_a_later_revision_is_not_a_collision() -> None:
    """The thirty findings that were not findings.

    Each revision is a separate legal document; an id freed in one year and
    given to another programme the next is the registry working as intended.
    """
    inventory = _inventory(
        _Event("alpha", (_Occurrence("2023", "0100"),)),
        _Event("bravo", (_Occurrence("2024", "0100"),)),
    )

    within_revision, pooled = casilla_claims(inventory)  # type: ignore[arg-type]

    assert not [key for key, slugs in within_revision.items() if len(slugs) > 1]
    assert pooled["0100"] == {"alpha", "bravo"}


def test_one_programme_keeping_its_casilla_across_revisions_is_neither() -> None:
    """Continuity is the family's normal shape and must register as nothing."""
    inventory = _inventory(
        _Event("alpha", (_Occurrence("2023", "0100"), _Occurrence("2024", "0100"))),
    )

    within_revision, pooled = casilla_claims(inventory)  # type: ignore[arg-type]

    assert not [key for key, slugs in within_revision.items() if len(slugs) > 1]
    assert pooled["0100"] == {"alpha"}


def test_a_collision_is_reported_against_its_own_revision() -> None:
    """A finding naming no revision sends a reader through every year to find it."""
    inventory = _inventory(
        _Event("alpha", (_Occurrence("2023", "0100"), _Occurrence("2024", "0200"))),
        _Event("bravo", (_Occurrence("2024", "0200"),)),
    )

    within_revision, _ = casilla_claims(inventory)  # type: ignore[arg-type]
    collisions = [key for key, slugs in within_revision.items() if len(slugs) > 1]

    assert collisions == [("2024", "0200")]


def test_an_empty_family_yields_no_claims() -> None:
    """Nothing declared is not the same as nothing colliding, but both are empty here."""
    within_revision, pooled = casilla_claims(_inventory())  # type: ignore[arg-type]

    assert within_revision == {}
    assert pooled == {}


def test_the_live_family_separates_the_two_counts() -> None:
    """Driven over the real modelo 100 declarations, not a constructed shape.

    The relationship is asserted rather than either count: every same-revision
    collision is necessarily also pooled reuse, so the sharp number can never
    exceed the broad one. A run where they were equal would mean the pooled
    number had been telling the truth all along; a run where the sharp one was
    larger would mean the analysis was inconsistent.
    """
    inventory, _ = _load("100", None)

    within_revision, pooled = casilla_claims(inventory)
    collisions = {key for key, slugs in within_revision.items() if len(slugs) > 1}
    reassigned = {casilla for casilla, slugs in pooled.items() if len(slugs) > 1}

    assert pooled, "the live family produced no casilla claims at all"
    assert len(collisions) <= len(reassigned)
    assert {casilla for _, casilla in collisions} <= reassigned
