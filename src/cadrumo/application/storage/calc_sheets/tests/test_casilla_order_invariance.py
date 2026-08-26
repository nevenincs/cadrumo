"""Compiled casilla order decides presentation, never the calculation surface.

The loader compiles ``revision.casillas`` in ``sorted(rglob("*.toml"))`` order over
the fragment directory, so a casilla's *filename* is its merge position. Any
renaming convention that drops the merge ordinal in favour of a purely
content-derived stem permutes that order across the corpus. This gate pins what
such a permutation is allowed to move.

The workbook layout is the one consumer that genuinely reads the sequence:
:func:`plan_layout` assigns Entradas/Cálculos rows by iteration, so a permutation
relocates every cell. That is presentation, and it is self-consistent — the
emitted formulas reference the permuted layout's own addresses. Everything that
decides *what the taxpayer declares* is keyed by ``casilla.id``: the emitted
casilla set, the formula attached to each casilla, each casilla's number format,
and the filing schema collection (which sorts by canonical id). Those must be
byte-identical under permutation, or a corpus-wide rename would silently change a
declaration.

The stale-workbook hazard the permutation creates is closed by an existing guard
rather than by order stability: a pulled workbook is bound to its snapshot through
``registry_sha``, which hashes the ordered snapshot JSON. A reorder therefore
changes the SHA and the pull refuses the stale sheet instead of reading a
neighbour's cell. The final assertions pin that guard, and are the anti-tautology
control for the whole gate: if a permutation stopped moving the addresses and the
SHA, the invariance assertions above would hold vacuously.

The permutation is built in memory with ``model_copy``; the bundled corpus is
never written.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from .....domain.calculations.registry.authority import bundled_authority
from ....filing.runtime import collection_from_snapshot
from .. import build_export_plan
from .._engine import registry_sha

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# (modelo, filing_year, period, on) — export-capable modelos whose workbook plan
# builds, spanning a small revision (M130, 20 casillas) through the largest
# corpus member (M200, 3250) so the invariant is proven at both ends of the size
# range the rename would touch.
_COVERED = [
    ("130", 2025, "1T", date(2025, 4, 1)),
    ("111", 2025, "1T", date(2025, 4, 1)),
    ("303", 2025, "1T", date(2025, 4, 1)),
    ("200", 2025, "0A", date(2026, 7, 1)),
]


def _snapshot(modelo: str, year: int, period: str, on: date) -> RegistrySnapshot:
    return bundled_authority().snapshot(modelo, filing_year=year, period=period, on=on)


def _reordered(snapshot: RegistrySnapshot) -> RegistrySnapshot:
    """Return ``snapshot`` with its casilla sequence reversed and nothing else changed.

    Reversal is the maximal permutation: every casilla whose position could move
    does move, so an order dependency anywhere in the compile path is exposed.
    """
    revision = snapshot.revision
    permuted = revision.model_copy(update={"casillas": tuple(reversed(revision.casillas))})
    return snapshot.model_copy(update={"revision": permuted})


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_declaration_order_does_not_change_the_calculation_surface(
    modelo: str, year: int, period: str, on: date
) -> None:
    baseline = _snapshot(modelo, year, period, on)
    permuted = _reordered(baseline)

    assert [c.id for c in baseline.revision.casillas] != [c.id for c in permuted.revision.casillas], (
        f"modelo {modelo}: the reversal did not reorder anything, so this gate would pass vacuously"
    )
    assert {c.id for c in baseline.revision.casillas} == {c.id for c in permuted.revision.casillas}

    base_plan = build_export_plan(baseline)
    perm_plan = build_export_plan(permuted)

    # Which casillas the workbook emits at all.
    base_emitted = {cell.casilla_id for cell in base_plan.value_cells if cell.casilla_id is not None}
    perm_emitted = {cell.casilla_id for cell in perm_plan.value_cells if cell.casilla_id is not None}
    assert base_emitted == perm_emitted, (
        f"modelo {modelo}: reordering the casilla fragments changed which casillas the workbook emits "
        f"(added {sorted(perm_emitted - base_emitted)[:5]}, dropped {sorted(base_emitted - perm_emitted)[:5]})"
    )

    # Which casillas carry a live formula.
    assert {cell.casilla_id for cell in base_plan.formula_cells} == {
        cell.casilla_id for cell in perm_plan.formula_cells
    }, f"modelo {modelo}: reordering changed which casillas carry a live spreadsheet formula"

    # The number format each casilla renders with.
    assert {item.casilla_id: item.pattern for item in base_plan.number_formats} == {
        item.casilla_id: item.pattern for item in perm_plan.number_formats
    }, f"modelo {modelo}: reordering changed a casilla's number format"

    # The filing schema collection build_draft projects (sorted by canonical id).
    assert [schema.casilla_id for schema in collection_from_snapshot(baseline).all()] == [
        schema.casilla_id for schema in collection_from_snapshot(permuted).all()
    ], f"modelo {modelo}: reordering changed the filing schema collection"


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_reordering_moves_cells_and_invalidates_a_pulled_workbook(
    modelo: str, year: int, period: str, on: date
) -> None:
    """Anti-tautology: the permutation must really move the presentation surface.

    A pulled workbook resolves each casilla by the A1 address the *live* layout
    plans, so a reorder that moved cells while leaving ``registry_sha`` stable
    would let the pull read a neighbouring casilla's value. Both halves are
    asserted together because it is their pairing that makes the reorder safe.
    """
    baseline = _snapshot(modelo, year, period, on)
    permuted = _reordered(baseline)

    base_addresses = {
        cell.casilla_id: str(cell.address) for cell in build_export_plan(baseline).value_cells if cell.casilla_id
    }
    perm_addresses = {
        cell.casilla_id: str(cell.address) for cell in build_export_plan(permuted).value_cells if cell.casilla_id
    }
    assert base_addresses != perm_addresses, (
        f"modelo {modelo}: reordering left every cell address unchanged, so the invariance gate above proves nothing"
    )

    assert registry_sha(baseline) != registry_sha(permuted), (
        f"modelo {modelo}: reordering moved the cell addresses but left registry_sha unchanged, so a "
        f"workbook exported before the reorder would still bind to the new layout and the pull would "
        f"read the wrong cell for every moved casilla"
    )
