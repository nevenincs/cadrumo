"""The boxes an official 0564 sum names that the formula leaves out, per edition and comunidad.

A left-out box is never summed. When the edition's registry declares it as a number,
the formula refuses a value for 0564 while the box holds an amount, so the operator
states 0564 instead; a box the registry does not declare cannot carry an amount on that
edition's return. The inventory records each case with the dictionary rows that show it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.design_sum import NUMERIC_CASILLA_TYPES
from .autonomic_deduction_sum_dictionary import ComunidadOperands, LeftOutBox

__all__ = [
    "NOT_NUMERIC",
    "REFUSES",
    "UNDECLARED",
    "LeftOutEntry",
    "inventory_header",
    "inventory_lines",
    "left_out_entries",
]

_HEADER: Final = "edition\tcomunidad\tfield\tsum_row\tbox\treason\tprinted_at\tregistry\teffect"
REFUSES: Final = "0564 is left without a value while this box holds an amount"
UNDECLARED: Final = "the edition's registry declares no such casilla, so the return cannot carry it"
NOT_NUMERIC: Final = "the edition's registry declares the casilla as {kind}, which holds no amount"


@dataclass(frozen=True, slots=True)
class LeftOutEntry:
    """One left-out box of one comunidad's official sum in one edition."""

    residence: str
    field: str
    sum_line: int
    left_out: LeftOutBox
    declared_as: str | None
    guarded: bool


def _entry(revision: ModeloRevision, comunidad: ComunidadOperands, left_out: LeftOutBox) -> LeftOutEntry:
    casilla = next((item for item in revision.casillas if str(item.id) == left_out.box), None)
    declared_as = None if casilla is None else str(casilla.data_type)
    guarded = casilla is not None and casilla.data_type in NUMERIC_CASILLA_TYPES
    return LeftOutEntry(comunidad.residence, comunidad.row.field, comunidad.row.line, left_out, declared_as, guarded)


def left_out_entries(revision: ModeloRevision, comunidades: Sequence[ComunidadOperands]) -> tuple[LeftOutEntry, ...]:
    """Every left-out box of the edition, in dictionary order, with what the formula does about it."""
    return tuple(_entry(revision, comunidad, left_out) for comunidad in comunidades for left_out in comunidad.left_out)


def _effect(entry: LeftOutEntry) -> str:
    if entry.guarded:
        return REFUSES
    if entry.declared_as is None:
        return UNDECLARED
    return NOT_NUMERIC.format(kind=entry.declared_as)


def _printed_at(source_ref: str, entry: LeftOutEntry) -> str:
    rows = entry.left_out.printed
    if not rows:
        return f"no row of {source_ref} maps box [{entry.left_out.box}]"
    return "; ".join(f"{source_ref}:{row.line} {row.block} {row.field} {row.data_type}" for row in rows)


def inventory_lines(revision_id: str, source_ref: str, entries: Sequence[LeftOutEntry]) -> list[str]:
    """One tab-separated line per left-out box of one edition."""
    return [
        "\t".join(
            (
                revision_id,
                entry.residence,
                entry.field,
                f"{source_ref}:{entry.sum_line}",
                entry.left_out.box,
                entry.left_out.reason,
                _printed_at(source_ref, entry),
                entry.declared_as or "not declared",
                _effect(entry),
            )
        )
        for entry in entries
    ]


def inventory_header() -> str:
    """The column names of the inventory lines."""
    return _HEADER
