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
* where a bound value comes from, and which boxes use this one;
* how a change to the box travels to the declaration's result: the fewest
  formulas from it to the result box, the other printed boxes it also
  reaches, or that no formula chain reaches the result at all;
* the figures its formula reads that the form does not print, each named,
  with the area that owns it, so a box that could not be worked out says what
  it waits on outside the form.

The explanation a person wrote for the casilla is the form's own ``help``; this
card adds what the registry can say mechanically, so a box with no written help
still explains itself.

See Also:
    :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`
        The recorded operand and result trace, read without reevaluating the formula.
    :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
        The pinned registry snapshot supplying the selected modelo revision.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import date
from typing import Final

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import BindingDefinition, FormulaDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_references import LegalReference
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from .casilla_help_formula import (
    ModeloHelpFormulaV1,
    ModeloHelpQuoteV1,
    build_casilla_formula_help,
    constraint_sentences,
)
from .casilla_help_reach import ModeloHelpReachV1, build_casilla_help_reach
from .printed_boxes import snapshot_printed_boxes
from .source_policy import SourceSurface, source_policy
from .work_form_localization import localized_text, unnamed_casilla_label
from .workspace import formula_expression_operand_references
from .workspace_models import (
    ModeloWorkspaceFormulaBindingOperandReferenceV1,
    ModeloWorkspaceFormulaCasillaOperandReferenceV1,
    ModeloWorkspaceFormulaDateBindingOperandReferenceV1,
)

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
    "formula.recorded_values": "application.modelo.help.formula.recorded_values",
    "source_kind.dictionary": "application.modelo.help.source_kind.dictionary",
    "source_kind.form_spec": "application.modelo.help.source_kind.form_spec",
    "source_kind.instructions": "application.modelo.help.source_kind.instructions",
    "source_kind.manual_pdf": "application.modelo.help.source_kind.manual_pdf",
    "source_kind.record_design": "application.modelo.help.source_kind.record_design",
    "source_kind.suppression_notice": "application.modelo.help.source_kind.suppression_notice",
    "source_kind.xsd": "application.modelo.help.source_kind.xsd",
}
"""Every phrase a help card composes, by the name its builders use."""

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
_NO_BREAK_SPACE: Final[str] = "\u00a0"
"""Joins a provision's abbreviation to its number, so "art. 71" never wraps between the two."""


class ModeloHelpCitationV1(BaseModel):
    """One legal basis, cited from its identifier, with its official link."""

    model_config = STRICT_FROZEN_CONFIG

    text: str
    permalink: str


class ModeloHelpOutsideFigureV1(BaseModel):
    """A figure the box's formula reads that the form does not print, and the product area that owns it.

    Exactly one of ``casilla_id`` and ``binding_id`` names the figure: a
    working figure the application computes, or a source the formula reads
    directly. ``surface`` is :attr:`~.source_policy.SourceSurface.NONE` when
    no area owns it, such as a figure calculated from other boxes.
    """

    model_config = STRICT_FROZEN_CONFIG

    label: str
    surface: SourceSurface
    casilla_id: CasillaId | None = None
    binding_id: str | None = None


class ModeloCasillaHelpCardV1(BaseModel):
    """Everything the registry can say mechanically about one casilla.

    ``reach`` is ``None`` when the revision names no result box, and for a
    result box itself, which ``is_result`` says.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    formula: ModeloHelpFormulaV1 | None
    quotes: tuple[ModeloHelpQuoteV1, ...]
    legal_basis: tuple[ModeloHelpCitationV1, ...]
    constraints: tuple[str, ...]
    origins: tuple[str, ...]
    feeds: tuple[str, ...]
    reach: ModeloHelpReachV1 | None = None
    is_result: bool = False
    outside_figures: tuple[ModeloHelpOutsideFigureV1, ...] = ()


class CasillaHelpCatalogueError(InternalInvariantError):
    """The catalogue carries no text for a help phrase the card must show."""


def _phrase(language: OutputLanguage, name: str, /, **values: object) -> str:
    key = _HELP_LOCALE_KEYS[name]
    template = lookup_translation(key, locale=language.value)
    if template is None:
        raise CasillaHelpCatalogueError(f"{key} has no {language.value} text")
    return template.format(**values) if values else template


def legal_citation_text(reference: LegalReference) -> str:
    """Cite one legal reference from its own identifier, falling back to the official document id."""
    document, _, locator = reference.id.partition(":")
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
    number = rest.replace("-", " ").strip()
    return f"{prefix}{_NO_BREAK_SPACE}{number}" if number else prefix


def _bound_by(casilla: CasillaDefinition) -> tuple[BindingId, ...]:
    return tuple(binding_id for binding_id in (casilla.binding, *casilla.alternate_bindings) if binding_id is not None)


def _origin_sentence(binding: BindingDefinition | None, language: OutputLanguage) -> str | None:
    if binding is None:
        return None
    return lookup_translation(source_policy(binding.source).origin_sentence_key, locale=language.value)


def _require_help_casilla(
    casilla_id: CasillaId, *, snapshot: RegistrySnapshot, casillas: Mapping[str, CasillaDefinition]
) -> CasillaDefinition:
    casilla = casillas.get(casilla_id)
    if casilla is None:
        raise KeyError(f"casilla {casilla_id!r} is not defined by revision {snapshot.revision.id!r}")
    return casilla


def _legal_basis(casilla: CasillaDefinition, operation: PinnedAuthorityOperation) -> tuple[ModeloHelpCitationV1, ...]:
    return tuple(
        ModeloHelpCitationV1(text=legal_citation_text(reference), permalink=reference.permalink)
        for reference in (operation.legal_reference(ref_id) for ref_id in casilla.legal_refs)
    )


def _outside_figures(
    casilla: CasillaDefinition,
    *,
    formulas: Mapping[str, FormulaDefinition],
    casillas: Mapping[str, CasillaDefinition],
    bindings: Mapping[str, BindingDefinition],
    is_printed: Callable[[str], bool],
    binding_name: Callable[[BindingId], str],
    language: OutputLanguage,
) -> tuple[ModeloHelpOutsideFigureV1, ...]:
    """The figures the box's formula reads that the form does not print, each once, in formula order."""
    formula = None if casilla.formula is None else formulas.get(casilla.formula)
    if formula is None:
        return ()
    figures: dict[str, ModeloHelpOutsideFigureV1] = {}
    for reference in formula_expression_operand_references(formula.id, formula.expression):
        if isinstance(reference, ModeloWorkspaceFormulaCasillaOperandReferenceV1):
            operand = casillas.get(reference.casilla_id)
            if operand is None or is_printed(operand.id):
                continue
            bound = bindings.get(operand.binding) if operand.binding is not None else None
            label = localized_text(operand.localization_keys, language) or unnamed_casilla_label(language)
            figures.setdefault(
                f"casilla:{operand.id}",
                ModeloHelpOutsideFigureV1(
                    label=label.text,
                    surface=SourceSurface.NONE if bound is None else source_policy(bound.source).surface,
                    casilla_id=operand.id,
                ),
            )
        elif isinstance(
            reference,
            ModeloWorkspaceFormulaBindingOperandReferenceV1 | ModeloWorkspaceFormulaDateBindingOperandReferenceV1,
        ):
            binding = bindings.get(reference.binding_id)
            figures.setdefault(
                f"binding:{reference.binding_id}",
                ModeloHelpOutsideFigureV1(
                    label=binding_name(reference.binding_id),
                    surface=SourceSurface.NONE if binding is None else source_policy(binding.source).surface,
                    binding_id=str(reference.binding_id),
                ),
            )
    return tuple(figures.values())


def _origin_sentences(
    casilla: CasillaDefinition,
    *,
    bindings: Mapping[str, BindingDefinition],
    language: OutputLanguage,
) -> tuple[str, ...]:
    return tuple(
        text
        for text in (_origin_sentence(bindings.get(binding_id), language) for binding_id in _bound_by(casilla))
        if text is not None
    )


def build_casilla_help_card(
    casilla_id: CasillaId,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
    on: date,
    observation: CasillaObservation | None = None,
) -> ModeloCasillaHelpCardV1:
    """Assemble the mechanical help of one casilla of ``snapshot`` in ``language``.

    ``on`` selects the parameter values in force, normally the last day of the
    filing period. A casilla the revision does not define is refused.
    ``observation`` is the current calculation's stored trace for this box;
    its operands and result are formatted without evaluating the formula.
    A missing or mismatched trace leaves the static formula available.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.bindings.CasillaObservation`
            The recorded operand and result trace, read without reevaluating the formula.
        :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`
            The pinned registry snapshot supplying the selected modelo revision.
    """
    casillas = {item.id: item for item in snapshot.revision.casillas}
    casilla = _require_help_casilla(casilla_id, snapshot=snapshot, casillas=casillas)
    formulas = {item.id: item for item in snapshot.revision.formulas}
    parameters = {item.id: item for item in snapshot.revision.parameters}
    bindings = {item.id: item for item in snapshot.revision.bindings}

    boxes = snapshot_printed_boxes(operation, snapshot)

    def box_text(key: str) -> str:
        number = boxes.number(key)
        return _phrase(language, "formula.working_figure") if number is None else f"[{number}]"

    def box_of(target: CasillaId) -> str:
        return box_text(target)

    def binding_name(binding_id: BindingId) -> str:
        binding = bindings.get(binding_id)
        if binding is None:
            return _phrase(language, "formula.table")
        name = lookup_translation(source_policy(binding.source).label_key, locale=language.value)
        return name or _phrase(language, "formula.table")

    formula_card, quotes = build_casilla_formula_help(
        casilla,
        formulas=formulas,
        parameters=parameters,
        casillas=casillas,
        bindings=bindings,
        operation=operation,
        language=language,
        on=on,
        box_of=box_of,
        binding_name=binding_name,
        observation=observation,
        phrase=_phrase,
    )
    legal_basis = _legal_basis(casilla, operation)
    origins = _origin_sentences(casilla, bindings=bindings, language=language)
    feeds, is_result, reach = build_casilla_help_reach(
        casilla, snapshot=snapshot, casillas=casillas, boxes=boxes, box_text=box_text
    )
    outside = _outside_figures(
        casilla,
        formulas=formulas,
        casillas=casillas,
        bindings=bindings,
        is_printed=lambda key: boxes.number(key) is not None,
        binding_name=binding_name,
        language=language,
    )
    return ModeloCasillaHelpCardV1(
        casilla_id=casilla.id,
        formula=formula_card,
        quotes=tuple(quotes),
        legal_basis=legal_basis,
        constraints=constraint_sentences(casilla.constraints, language, phrase=_phrase),
        origins=origins,
        feeds=feeds,
        reach=reach,
        is_result=is_result,
        outside_figures=outside,
    )


__all__ = [
    "CasillaHelpCatalogueError",
    "ModeloCasillaHelpCardV1",
    "ModeloHelpCitationV1",
    "ModeloHelpOutsideFigureV1",
    "build_casilla_help_card",
    "legal_citation_text",
]
