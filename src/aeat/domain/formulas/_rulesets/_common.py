"""Shared helpers for concise ruleset authoring.

Every concrete ruleset module under :mod:`aeat.domain.formulas._rulesets`
imports from here. The helpers keep the ruleset files short and
declarative: ``casilla("03", label=...)`` is easier to review than
manually instantiating :class:`CasillaDefinition`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ....core.i18n import Translatable
from ...casillas import CasillaDataType
from ...modelos import LegalCitation, LegalCitationSource
from .._casilla import CasillaDefinition
from .._formula import (
    AddFormula,
    Bracket,
    BracketsFormula,
    CasillaRef,
    ClampPositiveFormula,
    DivFormula,
    FormulaDefinition,
    Literal,
    MaxFormula,
    MinFormula,
    MulFormula,
    Operand,
    ParamRef,
    PercentFormula,
    RoundFormula,
    SubFormula,
)

__all__ = [
    "Bracket",
    "Translatable",
    "add_op",
    "brackets",
    "casilla",
    "clamp_pos",
    "currency_casilla",
    "div_op",
    "formula",
    "lit",
    "make_citation",
    "max_op",
    "min_op",
    "mul_op",
    "param",
    "percent",
    "percent_from_whole",
    "ref",
    "round2",
    "sub_op",
]


def currency_casilla(
    *,
    casilla_id: str,
    label: Translatable,
    computed: bool,
    legal_basis: tuple[LegalCitation, ...] = (),
    notes_es: str | None = None,
) -> CasillaDefinition:
    """Shorthand for a EUR casilla."""
    return CasillaDefinition(
        casilla_id=casilla_id,
        label=label,
        computed=computed,
        data_type=CasillaDataType.CURRENCY_EUR,
        legal_basis=legal_basis,
        notes_es=notes_es,
    )


casilla = currency_casilla


def formula(*, casilla_id: str, formula_id: str, body: Operand) -> FormulaDefinition:
    """Build a :class:`FormulaDefinition` with a trailing :class:`RoundFormula`.

    Wraps ``body`` in :class:`RoundFormula` to apply the terminal
    presentation-step rounding (2 decimal places, ROUND_HALF_UP) per
    the single-rounding invariant.
    """
    return FormulaDefinition(
        casilla_id=casilla_id,
        formula_id=formula_id,
        formula=RoundFormula(operands=(body,), digits=2),  # type: ignore[arg-type]
    )


def ref(casilla_id: str) -> CasillaRef:
    """Build a :class:`CasillaRef`."""
    return CasillaRef(casilla_id=casilla_id)


def lit(value: str | int) -> Literal:
    """Build a :class:`Literal` from a string or int."""
    if isinstance(value, int):
        return Literal(value=Decimal(value))
    return Literal(value=Decimal(value))


def param(param_id: str) -> ParamRef:
    """Build a :class:`ParamRef`."""
    return ParamRef(param_id=param_id)


def add_op(*operands: Operand) -> AddFormula:
    """Build an :class:`AddFormula`."""
    return AddFormula(operands=operands)


def sub_op(lhs: Operand, rhs: Operand) -> SubFormula:
    """Build a :class:`SubFormula`."""
    return SubFormula(operands=(lhs, rhs))


def mul_op(*operands: Operand) -> MulFormula:
    """Build a :class:`MulFormula`."""
    return MulFormula(operands=operands)


def div_op(lhs: Operand, rhs: Operand, *, quantize: str = "0.0001") -> DivFormula:
    """Build a :class:`DivFormula`."""
    return DivFormula(operands=(lhs, rhs), quantize=Decimal(quantize))


def min_op(*operands: Operand) -> MinFormula:
    """Build a :class:`MinFormula`."""
    return MinFormula(operands=operands)


def max_op(*operands: Operand) -> MaxFormula:
    """Build a :class:`MaxFormula`."""
    return MaxFormula(operands=operands)


def clamp_pos(operand: Operand) -> ClampPositiveFormula:
    """Build a :class:`ClampPositiveFormula`."""
    return ClampPositiveFormula(operands=(operand,))


def percent(rate: Operand, base: Operand) -> PercentFormula:
    """Build a :class:`PercentFormula`."""
    return PercentFormula(operands=(rate, base))


def percent_from_whole(rate_ref: Operand, base: Operand) -> PercentFormula:
    """Apply a whole-percent rate (e.g. ``17,00`` for 17%) to a base.

    AEAT forms print the rate as a whole-percent value (``Decimal("17.00")``
    ⇒ 17%); this helper normalises it to a fraction via ``rate / 100`` and
    applies ``rate * base``. Use this when the rate is read from an
    extracted casilla rather than stored in a :class:`ParameterTable`.

    Consistent quantisation ``Decimal("0.0001")`` keeps post-division
    precision at four decimals — exactly enough for any 2-decimal
    whole-percent rate (``17,00`` ⇒ 0.1700, ``24,50`` ⇒ 0.2450).
    AEAT never prints rates below 2 decimal places, so truncation
    does not arise in practice.
    """
    return PercentFormula(operands=(div_op(rate_ref, Literal(value=Decimal("100")), quantize="0.0001"), base))


def brackets(operand: Operand, *, steps: tuple[Bracket, ...]) -> BracketsFormula:
    """Build a :class:`BracketsFormula`."""
    return BracketsFormula(operands=(operand,), brackets=steps)


def round2(operand: Operand) -> RoundFormula:
    """Build a terminal :class:`RoundFormula` (2dp, ROUND_HALF_UP)."""
    return RoundFormula(operands=(operand,), digits=2)


def make_citation(
    source: LegalCitationSource,
    article: str,
    quoted_text_es: str,
    *,
    url: str | None = None,
    retrieval_date: date = date(2026, 4, 17),
    is_curated_summary: bool = True,
) -> LegalCitation:
    """Build a :class:`LegalCitation` for a ruleset's legal basis."""
    payload: dict[str, object] = {
        "source": source,
        "article": article,
        "quoted_text_es": quoted_text_es,
        "retrieval_date": retrieval_date,
        "is_curated_summary": is_curated_summary,
    }
    if url is not None:
        payload["url"] = url
    return LegalCitation.model_validate(payload)
