"""Printed design sums: the official sum a dictionary row prints, and the formula that restates it.

A declaration dictionary prints some summary boxes as an official sum of other boxes,
for example ``(suma de las casillas [1039] a [1050] + [1115])``. This module reads that
grammar mechanically, and decodes the one formula shape that restates such rows:

- the formula adds one term per printed row;
- a term is selected by a text binding equal to a text literal;
- the selected term is the signed sum of boxes the row names; while any guard box the
  row names but the formula does not add holds an amount, it is a typed refusal instead;
- an unselected term is zero while its sum is zero, and a typed refusal otherwise.

Refusals add no arithmetic: they leave the target without a value. The validator in
:mod:`.validate_design_sum` admits a layout-authority citation only on a formula this
module decodes, and only when each term restates exactly one cited row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from cadrumo.domain.calculations.registry.export_xml_dictionary import decode_dictionary_text
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_formula import FormulaExpression

__all__ = [
    "NUMERIC_CASILLA_TYPES",
    "DesignSumError",
    "DictionaryRow",
    "SelectedTerm",
    "SignedBox",
    "decode_selected_sum",
    "named_boxes",
    "parse_dictionary_row",
    "parse_dictionary_rows",
    "printed_signs",
    "printed_terms",
]

#: The casilla types that hold an amount; a named box of another type cannot carry one.
NUMERIC_CASILLA_TYPES: Final = frozenset({CasillaDataType.MONEY, CasillaDataType.DECIMAL, CasillaDataType.INTEGER})

_ROW_RE: Final = re.compile(
    r"^(?P<field>[A-Za-z0-9_]+)=\[(?P<path>[^\]]*)\]\[(?P<type>[^\]]*)\]\[(?P<box>[^\]]*)\]\[(?P<label>.*)\]\s*$"
)
_SUM_RE: Final = re.compile(
    r"^(?:Total deducciones autonómicas:?\s*)?\(suma de las casillas\s+(?P<expression>.*?)\s*\)$"
)
_TOKEN_RE: Final = re.compile(r"\s*(?:(?P<box>\[\d{4}\])|(?P<range>a)(?=\s)|(?P<sign>[+\-?]))")


class DesignSumError(ValueError):
    """A printed sum or a formula that cannot be read as a design sum without guessing."""


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
    def parent_block(self) -> str:
        """The XML element containing the row's block."""
        parts = self.path.strip("/").split("/")
        return parts[-3] if len(parts) >= 3 else ""


@dataclass(frozen=True, slots=True)
class SignedBox:
    """One operand: a box and whether the sum adds (1) or subtracts (-1) it."""

    sign: int
    box: str


def parse_dictionary_row(text: str, line: int) -> DictionaryRow | None:
    """The row one dictionary line maps, or ``None`` when the line maps no variable to a box."""
    matched = _ROW_RE.match(text)
    if matched is None:
        return None
    return DictionaryRow(
        line=line,
        text=text.rstrip(),
        field=matched["field"],
        path=matched["path"],
        data_type=matched["type"],
        box=matched["box"],
        label=matched["label"],
    )


def parse_dictionary_rows(body: bytes) -> tuple[DictionaryRow, ...]:
    """Decode a published dictionary and return every row that maps a variable to a box."""
    lines = enumerate(decode_dictionary_text(body).splitlines(), start=1)
    return tuple(row for number, text in lines if (row := parse_dictionary_row(text, number)) is not None)


def _tokens(row: DictionaryRow) -> list[tuple[str, str]]:
    summed = _SUM_RE.match(row.label.strip())
    if summed is None:
        raise DesignSumError(f"line {row.line} {row.field}: the description is not an official sum")
    expression = summed["expression"]
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(expression):
        matched = _TOKEN_RE.match(expression, position)
        if matched is None or matched.end() == position:
            raise DesignSumError(f"line {row.line} {row.field}: cannot read the sum at {expression[position:]!r}")
        kind = matched.lastgroup or ""
        tokens.append((kind, matched[kind]))
        position = matched.end()
        while position < len(expression) and expression[position].isspace():
            position += 1
    return tokens


def _term_at(tokens: list[tuple[str, str]], index: int) -> tuple[str, str | None, int]:
    """The box or range starting at ``index``, and the index after it."""
    if index + 2 < len(tokens) and tokens[index + 1][0] == "range" and tokens[index + 2][0] == "box":
        return tokens[index][1][1:-1], tokens[index + 2][1][1:-1], index + 3
    return tokens[index][1][1:-1], None, index + 1


def printed_terms(row: DictionaryRow) -> tuple[tuple[int, str, str | None], ...]:
    """The row's official sum as ``(sign, first box, last box or None)`` terms; sign 0 is an unreadable glyph."""
    tokens = _tokens(row)
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
            raise DesignSumError(f"line {row.line} {row.field}: unexpected {value!r} in the sum")
    if expect_term or not terms:
        raise DesignSumError(f"line {row.line} {row.field}: the sum ends without a box")
    return tuple(terms)


def named_boxes(row: DictionaryRow, first: str, last: str | None) -> tuple[str, ...]:
    """The boxes one term names: the box itself, or every number of a range."""
    if last is None:
        return (first,)
    low, high = int(first), int(last)
    if low > high:
        raise DesignSumError(f"line {row.line} {row.field}: range [{first}] a [{last}] runs backwards")
    return tuple(f"{number:04d}" for number in range(low, high + 1))


def printed_signs(row: DictionaryRow) -> dict[str, int]:
    """Every box the row's official sum names, with the sign printed before it (0 when unreadable)."""
    signs: dict[str, int] = {}
    for sign, first, last in printed_terms(row):
        for box in named_boxes(row, first, last):
            if signs.setdefault(box, sign) != sign:
                raise DesignSumError(f"line {row.line} {row.field}: box [{box}] is named with two signs")
    return signs


@dataclass(frozen=True, slots=True)
class SelectedTerm:
    """One decoded term of a selected design sum."""

    binding: str
    selector: str
    operands: tuple[SignedBox, ...]
    guards: tuple[str, ...]
    guard_reason: str | None
    other_reason: str


def _signed(expression: FormulaExpression) -> SignedBox:
    if expression.casilla_id is not None:
        return SignedBox(1, str(expression.casilla_id))
    if expression.op == "negate" and len(expression.args) == 1 and expression.args[0].casilla_id is not None:
        return SignedBox(-1, str(expression.args[0].casilla_id))
    raise DesignSumError(f"operand {expression!r} is neither a casilla nor its negation")


def _is_zero_test(test: FormulaExpression) -> bool:
    return test.op == "equal" and len(test.args) == 2 and test.args[0].op == "sum" and test.args[1].literal == 0


def _refusal(expression: FormulaExpression) -> str | None:
    """The reason of a typed refusal, or ``None`` when the expression is not one."""
    if expression.op == "unresolved_outcome" and len(expression.args) == 1:
        return expression.args[0].text_literal
    return None


def _other_branch(other: FormulaExpression) -> tuple[tuple[SignedBox, ...], str]:
    """The sum an unselected term tests and the reason it refuses with."""
    if other.op == "if_then_else" and len(other.args) == 3:
        test, zero, refused = other.args
        reason = _refusal(refused)
        if _is_zero_test(test) and zero.literal == 0 and reason is not None:
            return tuple(_signed(arg) for arg in test.args[0].args), reason
    raise DesignSumError("an unselected term is not zero-or-refuse on its own sum")


def _magnitude_box(expression: FormulaExpression) -> str:
    """The box of one ``max(box, -box)`` magnitude."""
    if expression.op == "max" and len(expression.args) == 2:
        box, negated = expression.args
        if box.casilla_id is not None and _signed(negated) == SignedBox(-1, str(box.casilla_id)):
            return str(box.casilla_id)
    raise DesignSumError("a guard is not the magnitude of one box")


def _selected_branch(resident: FormulaExpression) -> tuple[FormulaExpression, tuple[str, ...], str | None]:
    """The selected sum, the guard boxes refusing it, and the guard's reason."""
    if resident.op == "sum":
        return resident, (), None
    if resident.op == "if_then_else" and len(resident.args) == 3:
        test, summed, refused = resident.args
        reason = _refusal(refused)
        if _is_zero_test(test) and summed.op == "sum" and reason is not None:
            return summed, tuple(_magnitude_box(arg) for arg in test.args[0].args), reason
    raise DesignSumError("a selected term is neither a sum nor a guarded sum")


def _selection(predicate: FormulaExpression) -> tuple[str, str]:
    """The binding and the text literal a term's selecting test compares."""
    if predicate.op == "text_equal" and len(predicate.args) == 2:
        binding, literal = predicate.args
        if binding.binding is not None and literal.text_literal is not None:
            return str(binding.binding), literal.text_literal
    raise DesignSumError("a term does not compare a binding with a text literal")


def _decode_term(term: FormulaExpression) -> SelectedTerm:
    if term.op != "if_then_else" or len(term.args) != 3:
        raise DesignSumError("a term is not selected by a text test")
    predicate, resident, other = term.args
    binding, selector = _selection(predicate)
    summed, guards, guard_reason = _selected_branch(resident)
    operands = tuple(_signed(arg) for arg in summed.args)
    other_operands, other_reason = _other_branch(other)
    if other_operands != operands:
        raise DesignSumError(f"the {selector} term does not test its own sum when unselected")
    return SelectedTerm(binding, selector, operands, guards, guard_reason, other_reason)


def decode_selected_sum(expression: FormulaExpression) -> tuple[SelectedTerm, ...]:
    """Decode a formula restating printed sums term by term, refusing any other shape.

    Raises:
        DesignSumError: the formula is not a sum of selected terms on one binding with
            distinct selectors.
    """
    if expression.op != "sum" or not expression.args:
        raise DesignSumError("the formula is not a sum of terms")
    terms = tuple(_decode_term(term) for term in expression.args)
    if len({term.binding for term in terms}) != 1:
        raise DesignSumError("the terms do not select on one binding")
    if len({term.selector for term in terms}) != len(terms):
        raise DesignSumError("two terms select the same value")
    return terms
