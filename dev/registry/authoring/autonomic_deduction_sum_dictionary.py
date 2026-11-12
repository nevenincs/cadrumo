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

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from cadrumo.domain.calculations.registry.export_xml_dictionary import decode_dictionary_text

__all__ = [
    "BLOCK_RESIDENCE_TOKENS",
    "NOT_AN_AMOUNT",
    "NOT_PRINTED",
    "PRINTED_ELSEWHERE",
    "UNREADABLE_SIGN",
    "AutonomicSumExtractionError",
    "ComunidadOperands",
    "DictionaryRow",
    "LeftOutBox",
    "SignedBox",
    "extract_comunidad_operands",
    "parse_dictionary_rows",
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


_ROW_RE: Final = re.compile(
    r"^(?P<field>[A-Za-z0-9_]+)=\[(?P<path>[^\]]*)\]\[(?P<type>[^\]]*)\]\[(?P<box>[^\]]*)\]\[(?P<label>.*)\]\s*$"
)
_SUM_RE: Final = re.compile(
    r"^(?:Total deducciones autonómicas:?\s*)?\(suma de las casillas\s+(?P<expression>.*?)\s*\)$"
)
_TOKEN_RE: Final = re.compile(r"\s*(?:(?P<box>\[\d{4}\])|(?P<range>a)(?=\s)|(?P<sign>[+\-?]))")


class AutonomicSumExtractionError(ValueError):
    """A dictionary row the extraction cannot read without guessing."""


@dataclass(frozen=True, slots=True)
class DictionaryRow:
    """One mapped row of a declaration dictionary."""

    line: int
    text: str
    field: str
    path: str
    data_type: str
    box: str
    label: str

    @property
    def block(self) -> str:
        """The XML element directly containing the row's variable."""
        parts = self.path.strip("/").split("/")
        return parts[-2] if len(parts) >= 2 else ""

    @property
    def in_deduction_block(self) -> bool:
        """Whether the row sits in a comunidad block of the autonomic deductions."""
        parts = self.path.strip("/").split("/")
        return len(parts) >= 3 and parts[-3] == _DEDUCTION_BLOCK_PARENT


@dataclass(frozen=True, slots=True)
class SignedBox:
    """One operand: a box and whether the sum adds (1) or subtracts (-1) it."""

    sign: int
    box: str


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


def parse_dictionary_rows(body: bytes) -> tuple[DictionaryRow, ...]:
    """Decode a published dictionary and return every row that maps a variable to a box."""
    rows: list[DictionaryRow] = []
    for number, line in enumerate(decode_dictionary_text(body).splitlines(), start=1):
        matched = _ROW_RE.match(line)
        if matched is None:
            continue
        rows.append(
            DictionaryRow(
                line=number,
                text=line.rstrip(),
                field=matched["field"],
                path=matched["path"],
                data_type=matched["type"],
                box=matched["box"],
                label=matched["label"],
            )
        )
    return tuple(rows)


def _comunidad_rows(rows: Iterable[DictionaryRow]) -> tuple[DictionaryRow, ...]:
    return tuple(row for row in rows if row.box == SUMMARY_BOX and row.in_deduction_block)


def _terms(row: DictionaryRow) -> tuple[tuple[int, str, str | None], ...]:
    """Parse the description into ``(sign, first box, last box or None)`` terms; sign 0 is unreadable."""
    summed = _SUM_RE.match(row.label.strip())
    if summed is None:
        raise AutonomicSumExtractionError(f"line {row.line} {row.field}: the description is not an official sum")
    expression = summed["expression"]
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(expression):
        matched = _TOKEN_RE.match(expression, position)
        if matched is None or matched.end() == position:
            raise AutonomicSumExtractionError(
                f"line {row.line} {row.field}: cannot read the sum at {expression[position:]!r}"
            )
        kind = matched.lastgroup or ""
        tokens.append((kind, matched[kind]))
        position = matched.end()
        while position < len(expression) and expression[position].isspace():
            position += 1
    return _fold_terms(row, tokens)


def _term_at(tokens: list[tuple[str, str]], index: int) -> tuple[str, str | None, int]:
    """The box or range starting at ``index``, and the index after it."""
    if index + 2 < len(tokens) and tokens[index + 1][0] == "range" and tokens[index + 2][0] == "box":
        return tokens[index][1][1:-1], tokens[index + 2][1][1:-1], index + 3
    return tokens[index][1][1:-1], None, index + 1


def _fold_terms(row: DictionaryRow, tokens: list[tuple[str, str]]) -> tuple[tuple[int, str, str | None], ...]:
    terms: list[tuple[int, str, str | None]] = []
    index, sign = 0, 1
    expect_term = True
    while index < len(tokens):
        kind, value = tokens[index]
        if expect_term and kind == "box":
            first, last, index = _term_at(tokens, index)
            terms.append((sign, first, last))
            expect_term = False
        elif not expect_term and kind == "sign":
            sign = {"-": -1, "?": 0}.get(value, 1)
            expect_term = True
            index += 1
        else:
            raise AutonomicSumExtractionError(f"line {row.line} {row.field}: unexpected {value!r} in the sum")
    if expect_term or not terms:
        raise AutonomicSumExtractionError(f"line {row.line} {row.field}: the sum ends without a box")
    return tuple(terms)


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


def _named_boxes(row: DictionaryRow, first: str, last: str | None) -> tuple[str, ...]:
    if last is None:
        return (first,)
    low, high = int(first), int(last)
    if low > high:
        raise AutonomicSumExtractionError(f"line {row.line} {row.field}: range [{first}] a [{last}] runs backwards")
    return tuple(f"{number:04d}" for number in range(low, high + 1))


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
    for sign, first, last in _terms(row):
        found = [_classified(printed, row, sign, box) for box in _named_boxes(row, first, last)]
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
