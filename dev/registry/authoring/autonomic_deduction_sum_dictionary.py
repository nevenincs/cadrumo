"""Read the per-comunidad operand lists of Modelo 100 casilla 0564 from an official dictionary.

Every Modelo 100 declaration dictionary prints one ``DEDAUTx`` row per comunidad
mapped to the summary casilla of the autonomic deductions. Its description is the
official sum, for example ``(suma de las casillas [1039] a [1050] + [1115])``. This
module turns those descriptions into signed operand boxes, mechanically:

- ``[a] a [b]`` is a range: every money box the dictionary prints in the comunidad's
  own block with a number from ``a`` to ``b``. A number in the range that the
  edition prints elsewhere, or not at all, is not that comunidad's deduction.
- ``[n]`` names one box. The edition must print it as a money box in the
  comunidad's own block, or the reviewed placement below must rule on it. A box the
  edition does not print at all cannot hold a value and is reported as dropped.
- ``+`` adds and ``-`` subtracts the next term.

Any row whose description does not follow that grammar, a comunidad block nobody
mapped to a residence token, a box claimed by two comunidades, or a reviewed ruling
that no longer matches the dictionary fails the extraction. Nothing is skipped.

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
    "AutonomicSumExtractionError",
    "ComunidadOperands",
    "DictionaryRow",
    "DroppedOperand",
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


@dataclass(frozen=True, slots=True)
class _ReviewedPlacement:
    """A ruling on one single-box operand that the edition prints outside the comunidad's block."""

    field: str
    casilla_id: str
    printed_in: str
    admitted: bool
    reason: str


#: Single-box operands the official sum names although the dictionary prints the box in
#: another block. Each ruling is keyed by where the box is printed, so a renumbering
#: that moves the box elsewhere fails the extraction instead of inheriting the ruling.
_REVIEWED_PLACEMENTS: Final[tuple[_ReviewedPlacement, ...]] = (
    _ReviewedPlacement(
        field="DEDAUTIB",
        casilla_id="0504",
        printed_in="GravamenesRes",
        admitted=True,
        reason=(
            "the dictionary names the box DEDAUTIB22: the Illes Balears increase of the autonomic cuota "
            "for losing the birth deduction (reintegro del abono anticipado, art. 6 ter DL 1/2014)"
        ),
    ),
    _ReviewedPlacement(
        field="DEDAUTIB",
        casilla_id="1714",
        printed_in="CantabriaRes",
        admitted=False,
        reason=(
            "the box was the Illes Balears deduction for ascendants (IB24); the edition no longer prints "
            "that deduction and prints the number as a Cantabria amount generated in the year"
        ),
    ),
    _ReviewedPlacement(
        field="DEDAUTLR",
        casilla_id="2048",
        printed_in="ExcesosEficienciaEnergeticaRes",
        admitted=False,
        reason=(
            "the edition prints the box as an anexo C energy-efficiency excess pending for future years, "
            "and prints no La Rioja deduction under that number"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class _ReviewedSign:
    """A sign the publisher printed as an unreadable glyph between two named boxes."""

    field: str
    printed: str
    sign: int
    reason: str


#: The Illes Balears row prints ``[1718] ? [1719]`` in some editions: box 1719 is the advance
#: payment of the birth deduction of box 1718, which the edition that prints a dash subtracts.
_REVIEWED_SIGNS: Final[tuple[_ReviewedSign, ...]] = (
    _ReviewedSign(
        field="DEDAUTIB",
        printed="[1718] ? [1719]",
        sign=-1,
        reason=(
            "box 1719 is the advance payment (abono anticipado) of the birth deduction in box 1718, "
            "which the edition that prints the sign subtracts"
        ),
    ),
)

_ROW_RE: Final = re.compile(
    r"^(?P<field>[A-Za-z0-9_]+)=\[(?P<path>[^\]]*)\]\[(?P<type>[^\]]*)\]\[(?P<box>[^\]]*)\]\[(?P<label>.*)\]\s*$"
)
_SUM_RE: Final = re.compile(
    r"^(?:Total deducciones autonómicas:?\s*)?\(suma de las casillas\s+(?P<expression>.*?)\s*\)$"
)
_TOKEN_RE: Final = re.compile(r"\s*(?:(?P<box>\[\d{4}\])|(?P<range>a)(?=\s)|(?P<sign>[+\-?]))")


class AutonomicSumExtractionError(ValueError):
    """A dictionary row or ruling the extraction cannot read without guessing."""


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


@dataclass(frozen=True, slots=True)
class DroppedOperand:
    """A box the official sum names that is not an operand of this edition, and why."""

    box: str
    reason: str


@dataclass(frozen=True, slots=True)
class ComunidadOperands:
    """The official operand list of one comunidad in one edition."""

    residence: str
    row: DictionaryRow
    operands: tuple[SignedBox, ...]
    dropped: tuple[DroppedOperand, ...]


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


def _resolved_glyphs(row: DictionaryRow, expression: str) -> str:
    """Replace each reviewed unreadable sign, refusing any other one."""
    for reviewed in _REVIEWED_SIGNS:
        if reviewed.field == row.field and reviewed.printed in expression:
            symbol = "-" if reviewed.sign < 0 else "+"
            expression = expression.replace(reviewed.printed, reviewed.printed.replace("?", symbol))
    if "?" in expression:
        raise AutonomicSumExtractionError(
            f"line {row.line} {row.field}: the sum prints an unreadable sign and no reviewed ruling reads it"
        )
    return expression


def _terms(row: DictionaryRow) -> tuple[tuple[int, str, str | None], ...]:
    """Parse the description into ``(sign, first box, last box or None)`` terms."""
    summed = _SUM_RE.match(row.label.strip())
    if summed is None:
        raise AutonomicSumExtractionError(f"line {row.line} {row.field}: the description is not an official sum")
    expression = _resolved_glyphs(row, summed["expression"])
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
            sign = -1 if value == "-" else 1
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


def _range_operands(
    printed: _Printed, row: DictionaryRow, sign: int, first: str, last: str
) -> tuple[list[SignedBox], list[DroppedOperand]]:
    low, high = int(first), int(last)
    if low > high:
        raise AutonomicSumExtractionError(f"line {row.line} {row.field}: range [{first}] a [{last}] runs backwards")
    operands: list[SignedBox] = []
    dropped: list[DroppedOperand] = []
    for number in range(low, high + 1):
        box = f"{number:04d}"
        if printed.own_money(box, row.block):
            operands.append(SignedBox(sign, box))
        elif box in printed.by_box:
            dropped.append(DroppedOperand(box, f"in range [{first}] a [{last}] but printed outside {row.block}"))
    if not operands:
        raise AutonomicSumExtractionError(f"line {row.line} {row.field}: range [{first}] a [{last}] holds no box")
    return operands, dropped


def _placement_ruling(printed: _Printed, row: DictionaryRow, box: str) -> _ReviewedPlacement:
    """The one reviewed ruling on a box the edition prints only outside the comunidad's block."""
    rows = printed.by_box[box]
    blocks = {printed_row.block for printed_row in rows}
    rulings = [
        reviewed
        for reviewed in _REVIEWED_PLACEMENTS
        if reviewed.field == row.field and reviewed.casilla_id == box and reviewed.printed_in in blocks
    ]
    money = all(printed_row.data_type == _MONEY_TYPE for printed_row in rows)
    if len(rulings) != 1 or len(blocks) != 1 or not money:
        raise AutonomicSumExtractionError(
            f"line {row.line} {row.field}: box [{box}] is printed in {sorted(blocks)}, not {row.block}, "
            "and no reviewed ruling places it"
        )
    return rulings[0]


def _single_operand(printed: _Printed, row: DictionaryRow, sign: int, box: str) -> SignedBox | DroppedOperand:
    if printed.own_money(box, row.block):
        return SignedBox(sign, box)
    if box not in printed.by_box:
        return DroppedOperand(box, "the edition prints no box with this number")
    ruling = _placement_ruling(printed, row, box)
    return SignedBox(sign, box) if ruling.admitted else DroppedOperand(box, ruling.reason)


def _operands(printed: _Printed, row: DictionaryRow) -> tuple[tuple[SignedBox, ...], tuple[DroppedOperand, ...]]:
    operands: list[SignedBox] = []
    dropped: list[DroppedOperand] = []
    for sign, first, last in _terms(row):
        if last is not None:
            found, missed = _range_operands(printed, row, sign, first, last)
            operands.extend(found)
            dropped.extend(missed)
            continue
        single = _single_operand(printed, row, sign, first)
        if isinstance(single, SignedBox):
            operands.append(single)
        else:
            dropped.append(single)
    seen: dict[str, int] = {}
    unique: list[SignedBox] = []
    for operand in operands:
        if operand.box in seen:
            if seen[operand.box] != operand.sign:
                raise AutonomicSumExtractionError(
                    f"line {row.line} {row.field}: box [{operand.box}] is both added and subtracted"
                )
            continue
        seen[operand.box] = operand.sign
        unique.append(operand)
    return tuple(unique), tuple(dropped)


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
        operands, dropped = _operands(printed, row)
        for operand in operands:
            if operand.box in owner:
                raise AutonomicSumExtractionError(
                    f"line {row.line} {row.field}: box [{operand.box}] is also an operand of {owner[operand.box]}"
                )
            owner[operand.box] = row.field
        extracted.append(ComunidadOperands(residence, row, operands, dropped))
    if not extracted:
        raise AutonomicSumExtractionError(f"the dictionary prints no comunidad row for box {SUMMARY_BOX}")
    residences = [item.residence for item in extracted]
    if len(set(residences)) != len(residences):
        raise AutonomicSumExtractionError("a comunidad prints more than one row for the summary box")
    return tuple(extracted)
