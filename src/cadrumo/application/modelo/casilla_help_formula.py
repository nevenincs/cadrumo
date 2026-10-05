"""Canonical formula arithmetic and declared-constraint help rendering."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from typing import Protocol, override

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.ids import BindingId, ParameterId
from ...domain.calculations.registry.schema import BindingDefinition, FormulaDefinition
from ...domain.calculations.registry.schema_base import CasillaSignConstraint
from ...domain.calculations.registry.schema_formula import FormulaExpression, ParameterDefinition
from ...domain.calculations.registry.schema_surfaces import CasillaConstraints, CasillaDefinition
from .edit_value_grammar import ratio_unit
from .value_presentation import (
    LOCALE_NUMBER_FORMATS,
    SCREEN_MINUS_SIGN,
    VALUE_ABSENT_LOCALE_KEY,
    format_casilla_value,
    group_decimal_text,
)


class _HelpPhrase(Protocol):
    """Phrase lookup contract supplied by the owning catalogue module."""

    def __call__(self, language: OutputLanguage, name: str, /, **values: object) -> str: ...


class ModeloHelpFormulaV1(BaseModel):
    """A casilla's registry formula as box arithmetic; ``complete`` is false where a rule is not spelled out."""

    model_config = STRICT_FROZEN_CONFIG

    text: str
    complete: bool
    #: The same arithmetic with recorded operands and result; never a new calculation.
    values_text: str | None = None


class ModeloHelpQuoteV1(BaseModel):
    """Verbatim fragments of one official source, with its attribution."""

    model_config = STRICT_FROZEN_CONFIG

    fragments: tuple[str, ...]
    source: str
    source_url: str
    retrieved_at: date


_INFIX: Mapping[str, str] = {
    "add": " + ",
    "sum": " + ",
    "subtract": f" {SCREEN_MINUS_SIGN} ",
    "multiply": " × ",
    "divide": " ÷ ",
    "less_than": " < ",
    "less_equal": " ≤ ",
    "greater_than": " > ",
    "greater_equal": " ≥ ",
    "equal": " = ",
}


def _number(value: Decimal, language: OutputLanguage) -> str:
    text = format(value.normalize(), "f") if value == value.to_integral_value() else format(value, "f")
    return group_decimal_text(text, language, minus=SCREEN_MINUS_SIGN) or text


def _argument_separator(language: OutputLanguage) -> str:
    return "; " if LOCALE_NUMBER_FORMATS[language].decimal_separator == "," else ", "


class _FormulaRenderer:
    """Render one expression tree as box arithmetic, noting what it could not spell out."""

    def __init__(
        self,
        *,
        box_of: Callable[[CasillaId], str],
        binding_name: Callable[[BindingId], str],
        parameter_value: Callable[[ParameterId], Decimal | None],
        language: OutputLanguage,
        phrase: _HelpPhrase,
    ) -> None:
        self.box_of = box_of
        self.binding_name = binding_name
        self.parameter_value = parameter_value
        self.language = language
        self.phrase = phrase
        self.complete = True

    def render(self, node: FormulaExpression, *, nested: bool = False) -> str:
        if node.op is None:
            return self.leaf(node)
        op = str(node.op)
        args = [self.render(arg, nested=True) for arg in node.args]
        infix = _INFIX.get(op)
        if infix is not None:
            text = infix.join(args)
            return f"({text})" if nested and len(args) > 1 else text
        rendered = self._render_named_operation(op, args)
        if rendered is not None:
            return rendered
        self.complete = False
        return self.phrase(self.language, "formula.rule")

    def _render_named_operation(self, op: str, args: list[str]) -> str | None:
        rendered = self._render_aggregate_operation(op, args)
        if rendered is not None:
            return rendered
        return self._render_control_operation(op, args)

    def _render_aggregate_operation(self, op: str, args: list[str]) -> str | None:
        separator = _argument_separator(self.language)
        if op == "percent":
            return self.phrase(self.language, "formula.percent_of", rate=args[1], amount=args[0])
        if op in {"max", "min"}:
            return self.phrase(self.language, f"formula.{op}", items=separator.join(args))
        if op in {"previous_period_value", "previous_period_sum"}:
            return self.phrase(self.language, "formula.previous_period", value=" + ".join(args))
        if op.startswith("lookup_"):
            return self.phrase(self.language, "formula.table")
        return None

    def _render_control_operation(self, op: str, args: list[str]) -> str | None:
        if op == "negate":
            return f"{SCREEN_MINUS_SIGN}{args[0]}"
        if op == "copy":
            return args[0]
        if op == "clamp":
            return self.phrase(self.language, "formula.clamp", value=args[0], minimum=args[1], maximum=args[2])
        if op == "if_then_else":
            return self.phrase(
                self.language, "formula.if_then_else", condition=args[0], then=args[1], otherwise=args[2]
            )
        if op == "cross_model_sum":
            return self.phrase(self.language, "formula.other_modelos")
        return None

    def leaf(self, node: FormulaExpression) -> str:
        if node.casilla_id is not None:
            return self.box_of(node.casilla_id)
        if node.binding is not None:
            return self.binding_name(node.binding)
        if node.date_binding is not None:
            return self.binding_name(node.date_binding)
        if node.literal is not None:
            return _number(node.literal, self.language)
        if node.parameter is not None:
            value = self.parameter_value(node.parameter)
            if value is None:
                return self.phrase(self.language, "formula.table")
            return _number(value, self.language)
        return self.phrase(self.language, "formula.table")


def _parameter_value(parameter: ParameterDefinition | None, on: date) -> Decimal | None:
    if parameter is None or not parameter.values:
        return None
    in_force = [
        dated
        for dated in parameter.values
        if dated.valid_from <= on and (dated.valid_to is None or on <= dated.valid_to)
    ]
    return in_force[-1].value if len(in_force) == 1 else None


class _RecordedValuesRenderer(_FormulaRenderer):
    """Keep declared arithmetic and substitute only values from the stored trace."""

    def __init__(
        self,
        *,
        values: Mapping[str, Decimal],
        casillas: Mapping[str, CasillaDefinition],
        bindings: Mapping[str, BindingDefinition],
        box_of: Callable[[CasillaId], str],
        binding_name: Callable[[BindingId], str],
        language: OutputLanguage,
        phrase: _HelpPhrase,
    ) -> None:
        super().__init__(
            box_of=box_of,
            binding_name=binding_name,
            # A parameter not captured by this calculation stays absent, even if
            # the authority could supply one now.
            parameter_value=lambda _key: None,
            language=language,
            phrase=phrase,
        )
        self.values = values
        self.casillas = casillas
        self.bindings = bindings

    @override
    def render(self, node: FormulaExpression, *, nested: bool = False) -> str:
        if node.op is not None and (str(node.op).startswith("lookup_") or node.op == "cross_model_sum"):
            self.complete = False
        if node.op == "percent":
            amount, rate = (self.render(arg, nested=True) for arg in node.args)
            return self.phrase(self.language, "formula.percent_of", rate=rate.removesuffix("\u00a0%"), amount=amount)
        return super().render(node, nested=nested)

    @override
    def leaf(self, node: FormulaExpression) -> str:
        if node.casilla_id is not None:
            casilla = self.casillas[str(node.casilla_id)]
            maximum = None if casilla.constraints is None else casilla.constraints.max_value
            value = _format_recorded_value(
                self.values, str(node.casilla_id), str(casilla.data_type), self.language, maximum
            )
            return f"{self.box_of(node.casilla_id)} {value}"
        if node.binding is not None:
            binding = self.bindings[str(node.binding)]
            value = _format_recorded_value(self.values, str(node.binding), str(binding.value.data_type), self.language)
            return f"{self.binding_name(node.binding)} {value}"
        if node.parameter is not None:
            value = self.values.get(str(node.parameter))
            return super().leaf(node) if value is None else _number(value, self.language)
        return super().leaf(node)


def _recorded_operand_values(observation: CasillaObservation) -> dict[str, Decimal] | None:
    if len(observation.operand_refs) != len(observation.operand_values):
        return None
    values: dict[str, Decimal] = {}
    for key, value in zip(observation.operand_refs, observation.operand_values, strict=True):
        if key in values and values[key] != value:
            return None
        values[key] = value
    return values


def _format_recorded_value(
    values: Mapping[str, Decimal], key: str, data_type: str, language: OutputLanguage, maximum: Decimal | None = None
) -> str:
    value = values.get(key)
    if value is None:
        return lookup_translation(VALUE_ABSENT_LOCALE_KEY, locale=language.value) or "?"
    return format_casilla_value(
        value, data_type=data_type, language=language, ratio_unit=ratio_unit(data_type, maximum)
    )


def _recorded_operand_labels(
    values: Mapping[str, Decimal],
    *,
    renderer: _RecordedValuesRenderer,
    casillas: Mapping[str, CasillaDefinition],
    bindings: Mapping[str, BindingDefinition],
    language: OutputLanguage,
) -> list[str]:
    operands: list[str] = []
    for key in values:
        if key in casillas:
            operands.append(renderer.leaf(FormulaExpression(casilla_id=casillas[key].id)))
        elif key in bindings:
            operands.append(renderer.leaf(FormulaExpression(binding=bindings[key].id)))
        else:
            operands.append(_number(values[key], language))
    return operands


def _formula_values_text(
    formula: FormulaDefinition,
    observation: CasillaObservation,
    *,
    casillas: Mapping[str, CasillaDefinition],
    bindings: Mapping[str, BindingDefinition],
    box_of: Callable[[CasillaId], str],
    binding_name: Callable[[BindingId], str],
    language: OutputLanguage,
    phrase: _HelpPhrase,
) -> str | None:
    values = _recorded_operand_values(observation)
    if values is None:
        return None
    renderer = _RecordedValuesRenderer(
        values=values,
        casillas=casillas,
        bindings=bindings,
        box_of=box_of,
        binding_name=binding_name,
        language=language,
        phrase=phrase,
    )
    expression = renderer.render(formula.expression)
    target = casillas[str(observation.casilla_id)]
    maximum = None if target.constraints is None else target.constraints.max_value
    result = format_casilla_value(
        observation.value,
        data_type=str(target.data_type),
        language=language,
        ratio_unit=ratio_unit(str(target.data_type), maximum),
    )
    if not renderer.complete:
        operands = _recorded_operand_labels(
            values, renderer=renderer, casillas=casillas, bindings=bindings, language=language
        )
        return (
            phrase(language, "formula.recorded_values", values=" · ".join(operands), result=result)
            if operands
            else None
        )
    return f"{expression} = {result}"


def _format_constraint_value(value: Decimal, language: OutputLanguage) -> str:
    return _number(value, language)


def constraint_sentences(
    constraints: CasillaConstraints | None, language: OutputLanguage, *, phrase: _HelpPhrase
) -> tuple[str, ...]:
    """Render declared sign, value, length, and format constraints in stable order."""
    if constraints is None:
        return ()
    return (
        *_sign_constraint_sentences(constraints, language, phrase=phrase),
        *_value_constraint_sentences(constraints, language, phrase=phrase),
        *_length_constraint_sentences(constraints, language, phrase=phrase),
        *_format_constraint_sentences(constraints, language, phrase=phrase),
    )


def _sign_constraint_sentences(
    constraints: CasillaConstraints, language: OutputLanguage, *, phrase: _HelpPhrase
) -> tuple[str, ...]:
    if constraints.sign is CasillaSignConstraint.NON_NEGATIVE:
        return (phrase(language, "constraint.non_negative"),)
    return ()


def _value_constraint_sentences(
    constraints: CasillaConstraints, language: OutputLanguage, *, phrase: _HelpPhrase
) -> tuple[str, ...]:
    low, high = constraints.min_value, constraints.max_value
    if low is not None and high is not None:
        return (
            phrase(
                language,
                "constraint.range",
                minimum=_format_constraint_value(low, language),
                maximum=_format_constraint_value(high, language),
            ),
        )
    if low is not None:
        return (phrase(language, "constraint.at_least", minimum=_format_constraint_value(low, language)),)
    if high is not None:
        return (phrase(language, "constraint.at_most", maximum=_format_constraint_value(high, language)),)
    return ()


def _length_constraint_sentences(
    constraints: CasillaConstraints, language: OutputLanguage, *, phrase: _HelpPhrase
) -> tuple[str, ...]:
    shortest, longest = constraints.min_length, constraints.max_length
    if shortest is not None and shortest == longest:
        return (phrase(language, "constraint.exact_length", length=shortest),)
    if shortest is not None and longest is not None:
        return (phrase(language, "constraint.length", minimum=shortest, maximum=longest),)
    if shortest is not None:
        return (phrase(language, "constraint.min_length", minimum=shortest),)
    if longest is not None:
        return (phrase(language, "constraint.max_length", maximum=longest),)
    return ()


def _format_constraint_sentences(
    constraints: CasillaConstraints, language: OutputLanguage, *, phrase: _HelpPhrase
) -> tuple[str, ...]:
    sentences: list[str] = []
    if constraints.enum:
        sentences.append(phrase(language, "constraint.choices", choices=", ".join(constraints.enum)))
    if constraints.pattern is not None:
        sentences.append(phrase(language, "constraint.format"))
    return tuple(sentences)


def build_casilla_formula_help(
    casilla: CasillaDefinition,
    *,
    formulas: Mapping[str, FormulaDefinition],
    parameters: Mapping[str, ParameterDefinition],
    casillas: Mapping[str, CasillaDefinition],
    bindings: Mapping[str, BindingDefinition],
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
    on: date,
    box_of: Callable[[CasillaId], str],
    binding_name: Callable[[BindingId], str],
    observation: CasillaObservation | None,
    phrase: _HelpPhrase,
) -> tuple[ModeloHelpFormulaV1 | None, list[ModeloHelpQuoteV1]]:
    """Render one declared formula and its cited sources without evaluating it.

    A matching observation contributes its stored operands and result; a missing
    or mismatched observation leaves the static formula arithmetic available.

    Parameter types: ``observation`` (:class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`).
    """
    formula = None if casilla.formula is None else formulas.get(str(casilla.formula))
    if formula is None:
        return None, []
    renderer = _FormulaRenderer(
        box_of=box_of,
        binding_name=binding_name,
        parameter_value=lambda parameter_id: _parameter_value(parameters.get(str(parameter_id)), on),
        language=language,
        phrase=phrase,
    )
    text = f"{box_of(casilla.id)} = {renderer.render(formula.expression)}"
    values_text = _matching_observation_text(
        formula,
        casilla,
        observation=observation,
        casillas=casillas,
        bindings=bindings,
        box_of=box_of,
        binding_name=binding_name,
        language=language,
        phrase=phrase,
    )
    formula_card = ModeloHelpFormulaV1(text=text, complete=renderer.complete, values_text=values_text)
    quotes = _formula_quotes(formula, operation=operation, language=language, phrase=phrase)
    return formula_card, quotes


def _matching_observation_text(
    formula: FormulaDefinition,
    casilla: CasillaDefinition,
    *,
    observation: CasillaObservation | None,
    casillas: Mapping[str, CasillaDefinition],
    bindings: Mapping[str, BindingDefinition],
    box_of: Callable[[CasillaId], str],
    binding_name: Callable[[BindingId], str],
    language: OutputLanguage,
    phrase: _HelpPhrase,
) -> str | None:
    if observation is None or observation.casilla_id != casilla.id or observation.formula_id != formula.id:
        return None
    return _formula_values_text(
        formula,
        observation,
        casillas=casillas,
        bindings=bindings,
        box_of=box_of,
        binding_name=binding_name,
        language=language,
        phrase=phrase,
    )


def _formula_quotes(
    formula: FormulaDefinition,
    *,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
    phrase: _HelpPhrase,
) -> list[ModeloHelpQuoteV1]:
    quotes: list[ModeloHelpQuoteV1] = []
    for citation in formula.source_citations:
        source = operation.source_reference(citation.source_ref)
        quotes.append(
            ModeloHelpQuoteV1(
                fragments=tuple(citation.required_text),
                source=phrase(language, f"source_kind.{source.kind.value}"),
                source_url=str(source.source_url),
                retrieved_at=source.retrieved_at,
            )
        )
    return quotes


__all__ = [
    "ModeloHelpFormulaV1",
    "ModeloHelpQuoteV1",
    "build_casilla_formula_help",
    "constraint_sentences",
]
