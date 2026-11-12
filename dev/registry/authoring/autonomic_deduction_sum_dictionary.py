"""Read the per-comunidad operand lists of Modelo 100 casilla 0564 from an official dictionary.

Every Modelo 100 declaration dictionary prints one ``DEDAUTx`` row per comunidad
mapped to the summary casilla of the autonomic deductions. Its description is the
official sum, for example ``(suma de las casillas [1039] a [1050] + [1115])``. This
module turns those descriptions into signed operand boxes, mechanically, and never
guesses:

- ``[a] a [b]`` is a range and ``[n]`` names one box.
- A named box is an operand only when the edition prints it as a money box in the
  comunidad's own block. Every other named box is left out, with the reason and the
  dictionary rows that show it: the edition prints no box with that number, prints it
  outside the comunidad's block, or prints it in the block but not as an amount.
- ``+`` adds and ``-`` subtracts the next term. A sign the publisher printed as an
  unreadable glyph (``?``) is not read as either: the term after it is left out.

No list of exceptions exists. A left-out box is reported, never summed, and the
writer makes the formula refuse a value while such a box holds an amount.

Any row whose description does not follow that grammar, a comunidad block nobody
mapped to a residence token, or a box summed by two comunidades fails the extraction.

The runtime never reads these files: the extraction feeds the registry formula
that :mod:`.autonomic_deduction_sum` writes and checks.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from ..compiler.design_sum import (
    DesignSumError,
    DictionaryRow,
    SignedBox,
    named_boxes,
    parse_dictionary_rows,
    printed_terms,
)

__all__ = [
    "BLOCK_RESIDENCE_TOKENS",
    "NOT_AN_AMOUNT",
    "NOT_PRINTED",
    "PRINTED_ELSEWHERE",
    "UNREADABLE_SIGN",
    "AutonomicSumExtractionError",
    "ComunidadOperands",
    "LeftOutBox",
    "extract_comunidad_operands",
]

SUMMARY_BOX: Final = "0564"
_MONEY_TYPE: Final = "P102"
_DEDUCTION_BLOCK_PARENT: Final = "DeduccionAutonomicaRes"

#: The residence token of the registry's CCAA catalogue that each dictionary block belongs to.
#: These are names, not operands; a block missing here fails the extraction.
BLOCK_RESIDENCE_TOKENS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "AndaluciaRes": "andalucia",
        "AragonRes": "aragon",
        "AsturiasRes": "asturias",
        "IBalearesRes": "baleares",
        "CanariasRes": "canarias",
        "CantabriaRes": "cantabria",
        "CastillaLaManchaRes": "castilla_la_mancha",
        "CastillaYLeonRes": "castilla_y_leon",
        "CatalunyaRes": "cataluna",
        "ExtremaduraRes": "extremadura",
        "GaliciaRes": "galicia",
        "MadridRes": "madrid",
        "MurciaRes": "murcia",
        "LaRiojaRes": "la_rioja",
        "CValencianaRes": "comunidad_valenciana",
    }
)


class AutonomicSumExtractionError(DesignSumError):
    """A dictionary or registry state the extraction cannot read without guessing."""


#: Why a box the official sum names is not an operand of the edition.
NOT_PRINTED: Final = "the edition prints no box with this number"
PRINTED_ELSEWHERE: Final = "the edition prints the box outside the comunidad's block"
NOT_AN_AMOUNT: Final = "the edition prints the box in the comunidad's block, but not as an amount"
UNREADABLE_SIGN: Final = "the sum prints an unreadable sign before the box"


@dataclass(frozen=True, slots=True)
class LeftOutBox:
    """A box the official sum names that is not an operand of this edition, why, and where it is printed."""

    box: str
    reason: str
    printed: tuple[DictionaryRow, ...]


@dataclass(frozen=True, slots=True)
class ComunidadOperands:
    """The official operand list of one comunidad in one edition."""

    residence: str
    row: DictionaryRow
    operands: tuple[SignedBox, ...]
    left_out: tuple[LeftOutBox, ...]


def _comunidad_rows(rows: Iterable[DictionaryRow]) -> tuple[DictionaryRow, ...]:
    return tuple(row for row in rows if row.box == SUMMARY_BOX and row.parent_block == _DEDUCTION_BLOCK_PARENT)


@dataclass(frozen=True, slots=True)
class _Printed:
    by_box: Mapping[str, tuple[DictionaryRow, ...]]

    def own_money(self, box: str, block: str) -> bool:
        return any(row.block == block and row.data_type == _MONEY_TYPE for row in self.by_box.get(box, ()))


def _classified(printed: _Printed, row: DictionaryRow, sign: int, box: str) -> SignedBox | LeftOutBox:
    """The operand a named box is, or why it is left out."""
    rows = printed.by_box.get(box, ())
    if sign == 0:
        return LeftOutBox(box, UNREADABLE_SIGN, rows)
    if printed.own_money(box, row.block):
        return SignedBox(sign, box)
    if not rows:
        return LeftOutBox(box, NOT_PRINTED, ())
    if any(printed_row.block == row.block for printed_row in rows):
        return LeftOutBox(box, NOT_AN_AMOUNT, rows)
    return LeftOutBox(box, PRINTED_ELSEWHERE, rows)


def _merge(
    row: DictionaryRow,
    found: list[SignedBox | LeftOutBox],
    operands: dict[str, SignedBox],
    left_out: dict[str, LeftOutBox],
) -> None:
    """Add one term's boxes, refusing a box the sum both adds and subtracts."""
    for item in found:
        if isinstance(item, LeftOutBox):
            left_out.setdefault(item.box, item)
        elif operands.setdefault(item.box, item).sign != item.sign:
            raise AutonomicSumExtractionError(
                f"line {row.line} {row.field}: box [{item.box}] is both added and subtracted"
            )


def _operands(printed: _Printed, row: DictionaryRow) -> tuple[tuple[SignedBox, ...], tuple[LeftOutBox, ...]]:
    operands: dict[str, SignedBox] = {}
    left_out: dict[str, LeftOutBox] = {}
    for sign, first, last in printed_terms(row):
        found = [_classified(printed, row, sign, box) for box in named_boxes(row, first, last)]
        if last is not None and sign != 0 and not any(isinstance(item, SignedBox) for item in found):
            raise AutonomicSumExtractionError(f"line {row.line} {row.field}: range [{first}] a [{last}] holds no box")
        _merge(row, found, operands, left_out)
    return tuple(operands.values()), tuple(item for box, item in left_out.items() if box not in operands)


def extract_comunidad_operands(body: bytes) -> tuple[ComunidadOperands, ...]:
    """Extract every comunidad's operand list from one published declaration dictionary.

    Raises:
        AutonomicSumExtractionError: a row cannot be read, a block has no residence token,
            a box belongs to two comunidades, or the dictionary prints no comunidad row.
    """
    rows = parse_dictionary_rows(body)
    by_box: dict[str, list[DictionaryRow]] = {}
    for row in rows:
        by_box.setdefault(row.box, []).append(row)
    printed = _Printed({box: tuple(found) for box, found in by_box.items()})
    extracted: list[ComunidadOperands] = []
    owner: dict[str, str] = {}
    for row in _comunidad_rows(rows):
        residence = BLOCK_RESIDENCE_TOKENS.get(row.block)
        if residence is None:
            raise AutonomicSumExtractionError(f"line {row.line} {row.field}: block {row.block} has no residence token")
        operands, left_out = _operands(printed, row)
        for operand in operands:
            if operand.box in owner:
                raise AutonomicSumExtractionError(
                    f"line {row.line} {row.field}: box [{operand.box}] is also an operand of {owner[operand.box]}"
                )
            owner[operand.box] = row.field
        extracted.append(ComunidadOperands(residence, row, operands, left_out))
    if not extracted:
        raise AutonomicSumExtractionError(f"the dictionary prints no comunidad row for box {SUMMARY_BOX}")
    residences = [item.residence for item in extracted]
    if len(set(residences)) != len(residences):
        raise AutonomicSumExtractionError("a comunidad prints more than one row for the summary box")
    return tuple(extracted)
