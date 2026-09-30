"""The help card of one casilla: how it is calculated, what the official text says, and the law behind it.

Help a filer can trust is assembled from what the registry already declares,
each part labelled with where it comes from, and nothing about tax law is
written at runtime:

* the registry formula, rendered as box arithmetic in the filer's language
  ("[04] = max(0; 20 % of [03])"), and marked incomplete where a modelo-specific
  rule cannot be spelled out;
* the verbatim fragments of official instructions the formula is grounded in,
  attributed to their source and retrieval date;
* the legal basis, cited mechanically from each legal reference's own
  identifier ("Ley 35/2006, art. 99") with its official link;
* the declared constraints in words, or a plain statement that none are
  declared, which is different from saying the box is unconstrained;
* where a bound value comes from, and which boxes use this one.

The explanation a person wrote for the casilla is the form's own ``help``; this
card adds what the registry can say mechanically, so a box with no written help
still explains itself.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date
from decimal import Decimal
from typing import Final

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import BindingId, ParameterId
from ...domain.calculations.registry.schema import BindingDefinition, FormulaDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_base import CasillaSignConstraint
from ...domain.calculations.registry.schema_formula import FormulaExpression, ParameterDefinition
from ...domain.calculations.registry.schema_references import LegalReference
from ...domain.calculations.registry.schema_surfaces import CasillaConstraints, CasillaDefinition
from .source_policy import source_policy
from .value_presentation import LOCALE_NUMBER_FORMATS, SCREEN_MINUS_SIGN, group_decimal_text

_HELP_LOCALE_KEYS: Final[Mapping[str, str]] = {
    "constraint.at_least": "application.modelo.help.constraint.at_least",
    "constraint.at_most": "application.modelo.help.constraint.at_most",
    "constraint.choices": "application.modelo.help.constraint.choices",
    "constraint.exact_length": "application.modelo.help.constraint.exact_length",
    "constraint.format": "application.modelo.help.constraint.format",
    "constraint.length": "application.modelo.help.constraint.length",
    "constraint.max_length": "application.modelo.help.constraint.max_length",
    "constraint.min_length": "application.modelo.help.constraint.min_length",
    "constraint.non_negative": "application.modelo.help.constraint.non_negative",
    "constraint.none_declared": "application.modelo.help.constraint.none_declared",
    "constraint.range": "application.modelo.help.constraint.range",
    "formula.clamp": "application.modelo.help.formula.clamp",
    "formula.if_then_else": "application.modelo.help.formula.if_then_else",
    "formula.max": "application.modelo.help.formula.max",
    "formula.min": "application.modelo.help.formula.min",
    "formula.other_modelos": "application.modelo.help.formula.other_modelos",
    "formula.percent_of": "application.modelo.help.formula.percent_of",
    "formula.previous_period": "application.modelo.help.formula.previous_period",
    "formula.rule": "application.modelo.help.formula.rule",
    "formula.table": "application.modelo.help.formula.table",
    "formula.working_figure": "application.modelo.help.formula.working_figure",
    "source_kind.dictionary": "application.modelo.help.source_kind.dictionary",
    "source_kind.form_spec": "application.modelo.help.source_kind.form_spec",
    "source_kind.instructions": "application.modelo.help.source_kind.instructions",
    "source_kind.manual_pdf": "application.modelo.help.source_kind.manual_pdf",
    "source_kind.record_design": "application.modelo.help.source_kind.record_design",
    "source_kind.suppression_notice": "application.modelo.help.source_kind.suppression_notice",
    "source_kind.xsd": "application.modelo.help.source_kind.xsd",
}
"""Every phrase a help card composes, by the name its builders use."""

_INFIX: Final[Mapping[str, str]] = {
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
_LAW_TYPES: Final[Mapping[str, str]] = {
    "ley": "Ley",
    "lo": "Ley Orgánica",
    "rd": "Real Decreto",
    "rdl": "Real Decreto-ley",
    "real-decreto-ley": "Real Decreto-ley",
    "rdleg": "Real Decreto Legislativo",
    "dl": "Decreto Legislativo",
    "decreto": "Decreto",
}
_LAW_ID: Final[re.Pattern[str]] = re.compile(
    r"^(?P<type>ley|lo|rd|rdl|real-decreto-ley|rdleg|dl|decreto)-(?P<number>\d+)-(?P<year>\d{4})$"
)
_ORDER_ID: Final[re.Pattern[str]] = re.compile(r"^orden-(?P<department>[a-z]+)-(?P<number>\d+)-(?P<year>\d{4})$")
_ARTICLE_PREFIXES: Final[Mapping[str, str]] = {"art": "art.", "da": "DA", "df": "DF", "dt": "DT", "dd": "DD"}


class ModeloHelpFormulaV1(BaseModel):
    """A casilla's registry formula as box arithmetic; ``complete`` is false where a rule is not spelled out."""

    model_config = STRICT_FROZEN_CONFIG

    text: str
    complete: bool


class ModeloHelpQuoteV1(BaseModel):
    """Verbatim fragments of one official source, with its attribution."""

    model_config = STRICT_FROZEN_CONFIG

    fragments: tuple[str, ...]
    source: str
    source_url: str
    retrieved_at: date


class ModeloHelpCitationV1(BaseModel):
    """One legal basis, cited from its identifier, with its official link."""

    model_config = STRICT_FROZEN_CONFIG

    text: str
    permalink: str


class ModeloCasillaHelpCardV1(BaseModel):
    """Everything the registry can say mechanically about one casilla."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    formula: ModeloHelpFormulaV1 | None
    quotes: tuple[ModeloHelpQuoteV1, ...]
    legal_basis: tuple[ModeloHelpCitationV1, ...]
    constraints: tuple[str, ...]
    origins: tuple[str, ...]
    feeds: tuple[str, ...]


class CasillaHelpCatalogueError(InternalInvariantError):
    """The catalogue carries no text for a help phrase the card must show."""


def _phrase(language: OutputLanguage, name: str, /, **values: object) -> str:
    key = _HELP_LOCALE_KEYS[name]
    template = lookup_translation(key, locale=language.value)
    if template is None:
        raise CasillaHelpCatalogueError(f"{key} has no {language.value} text")
    return template.format(**values) if values else template


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
    ) -> None:
        self.box_of = box_of
        self.binding_name = binding_name
        self.parameter_value = parameter_value
        self.language = language
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
        separator = _argument_separator(self.language)
        if op == "percent":
            return _phrase(self.language, "formula.percent_of", rate=args[1], amount=args[0])
        if op in {"max", "min"}:
            return _phrase(self.language, f"formula.{op}", items=separator.join(args))
        if op == "negate":
            return f"{SCREEN_MINUS_SIGN}{args[0]}"
        if op == "copy":
            return args[0]
        if op == "clamp":
            return _phrase(self.language, "formula.clamp", value=args[0], minimum=args[1], maximum=args[2])
        if op == "if_then_else":
            return _phrase(self.language, "formula.if_then_else", condition=args[0], then=args[1], otherwise=args[2])
        if op in {"previous_period_value", "previous_period_sum"}:
            return _phrase(self.language, "formula.previous_period", value=" + ".join(args))
        if op == "cross_model_sum":
            return _phrase(self.language, "formula.other_modelos")
        if op.startswith("lookup_"):
            return _phrase(self.language, "formula.table")
        self.complete = False
        return _phrase(self.language, "formula.rule")

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
                return _phrase(self.language, "formula.table")
            return _number(value, self.language)
        return _phrase(self.language, "formula.table")


def _parameter_value(parameter: ParameterDefinition | None, on: date) -> Decimal | None:
    """Return a scalar parameter's value in force on ``on``, or ``None`` for tables and gaps."""
    if parameter is None or not parameter.values:
        return None
    in_force = [
        dated
        for dated in parameter.values
        if dated.valid_from <= on and (dated.valid_to is None or on <= dated.valid_to)
    ]
    return in_force[-1].value if len(in_force) == 1 else None


def legal_citation_text(reference: LegalReference) -> str:
    """Cite one legal reference from its own identifier, falling back to the official document id."""
    document, _, locator = str(reference.id).partition(":")
    title = reference.document_id
    law = _LAW_ID.match(document)
    order = _ORDER_ID.match(document)
    if law is not None:
        title = f"{_LAW_TYPES[law['type']]} {law['number']}/{law['year']}"
    elif order is not None:
        title = f"Orden {order['department'].upper()}/{order['number']}/{order['year']}"
    article = _article_text(locator) if locator else None
    return title if article is None else f"{title}, {article}"


def _article_text(locator: str) -> str:
    head, _, rest = locator.partition("-")
    prefix = _ARTICLE_PREFIXES.get(head)
    if prefix is None:
        return locator.replace("-", " ")
    return f"{prefix} {rest.replace('-', ' ')}".strip()


def _constraint_sentences(constraints: CasillaConstraints | None, language: OutputLanguage) -> tuple[str, ...]:
    if constraints is None:
        return (_phrase(language, "constraint.none_declared"),)
    sentences: list[str] = []
    if constraints.sign is CasillaSignConstraint.NON_NEGATIVE:
        sentences.append(_phrase(language, "constraint.non_negative"))
    low, high = constraints.min_value, constraints.max_value
    if low is not None and high is not None:
        sentences.append(
            _phrase(language, "constraint.range", minimum=_number(low, language), maximum=_number(high, language))
        )
    elif low is not None:
        sentences.append(_phrase(language, "constraint.at_least", minimum=_number(low, language)))
    elif high is not None:
        sentences.append(_phrase(language, "constraint.at_most", maximum=_number(high, language)))
    shortest, longest = constraints.min_length, constraints.max_length
    if shortest is not None and shortest == longest:
        sentences.append(_phrase(language, "constraint.exact_length", length=shortest))
    elif shortest is not None and longest is not None:
        sentences.append(_phrase(language, "constraint.length", minimum=shortest, maximum=longest))
    elif shortest is not None:
        sentences.append(_phrase(language, "constraint.min_length", minimum=shortest))
    elif longest is not None:
        sentences.append(_phrase(language, "constraint.max_length", maximum=longest))
    if constraints.enum:
        sentences.append(_phrase(language, "constraint.choices", choices=", ".join(constraints.enum)))
    if constraints.pattern is not None:
        sentences.append(_phrase(language, "constraint.format"))
    return tuple(sentences) or (_phrase(language, "constraint.none_declared"),)


def _bound_by(casilla: CasillaDefinition) -> tuple[BindingId, ...]:
    return tuple(binding_id for binding_id in (casilla.binding, *casilla.alternate_bindings) if binding_id is not None)


def _origin_sentence(binding: BindingDefinition | None, language: OutputLanguage) -> str | None:
    if binding is None:
        return None
    return lookup_translation(source_policy(binding.source).origin_sentence_key, locale=language.value)


def _uses(formula: FormulaDefinition) -> set[str]:
    found: set[str] = set()
    pending = [formula.expression]
    while pending:
        node = pending.pop()
        if node.casilla_id is not None:
            found.add(str(node.casilla_id))
        pending.extend(node.args)
    return found


def build_casilla_help_card(
    casilla_id: CasillaId,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
    on: date,
) -> ModeloCasillaHelpCardV1:
    """Assemble the mechanical help of one casilla of ``snapshot`` in ``language``.

    ``on`` selects the parameter values in force, normally the last day of the
    filing period. A casilla the revision does not define is refused.
    """
    casillas = {str(item.id): item for item in snapshot.revision.casillas}
    casilla = casillas.get(str(casilla_id))
    if casilla is None:
        raise KeyError(f"casilla {casilla_id!r} is not defined by revision {snapshot.revision.id!r}")
    formulas = {str(item.id): item for item in snapshot.revision.formulas}
    parameters = {str(item.id): item for item in snapshot.revision.parameters}
    bindings = {str(item.id): item for item in snapshot.revision.bindings}

    def box_of(target: CasillaId) -> str:
        other = casillas.get(str(target))
        if other is not None and other.number.isdigit():
            return f"[{other.number}]"
        if other is not None and other.form_number is not None:
            return f"[{other.form_number}]"
        return _phrase(language, "formula.working_figure")

    def binding_name(binding_id: BindingId) -> str:
        binding = bindings.get(str(binding_id))
        if binding is None:
            return _phrase(language, "formula.table")
        name = lookup_translation(source_policy(binding.source).label_key, locale=language.value)
        return name or _phrase(language, "formula.table")

    formula_card: ModeloHelpFormulaV1 | None = None
    quotes: list[ModeloHelpQuoteV1] = []
    formula = None if casilla.formula is None else formulas.get(str(casilla.formula))
    if formula is not None:
        renderer = _FormulaRenderer(
            box_of=box_of,
            binding_name=binding_name,
            parameter_value=lambda parameter_id: _parameter_value(parameters.get(str(parameter_id)), on),
            language=language,
        )
        text = f"{box_of(casilla.id)} = {renderer.render(formula.expression)}"
        formula_card = ModeloHelpFormulaV1(text=text, complete=renderer.complete)
        for citation in formula.source_citations:
            source = operation.source_reference(citation.source_ref)
            quotes.append(
                ModeloHelpQuoteV1(
                    fragments=tuple(citation.required_text),
                    source=_phrase(language, f"source_kind.{source.kind.value}"),
                    source_url=str(source.source_url),
                    retrieved_at=source.retrieved_at,
                )
            )
    legal_basis = tuple(
        ModeloHelpCitationV1(text=legal_citation_text(reference), permalink=str(reference.permalink))
        for reference in (operation.legal_reference(ref_id) for ref_id in casilla.legal_refs)
    )
    origins = tuple(
        text
        for text in (_origin_sentence(bindings.get(str(binding_id)), language) for binding_id in _bound_by(casilla))
        if text is not None
    )
    feeds = tuple(
        sorted(
            {
                box_of(item.target_casilla_id)
                for item in snapshot.revision.formulas
                if str(casilla.id) in _uses(item) and str(item.target_casilla_id) != str(casilla.id)
            }
        )
    )
    return ModeloCasillaHelpCardV1(
        casilla_id=casilla.id,
        formula=formula_card,
        quotes=tuple(quotes),
        legal_basis=legal_basis,
        constraints=_constraint_sentences(casilla.constraints, language),
        origins=origins,
        feeds=feeds,
    )


__all__ = [
    "CasillaHelpCatalogueError",
    "ModeloCasillaHelpCardV1",
    "ModeloHelpCitationV1",
    "ModeloHelpFormulaV1",
    "ModeloHelpQuoteV1",
    "build_casilla_help_card",
    "legal_citation_text",
]
