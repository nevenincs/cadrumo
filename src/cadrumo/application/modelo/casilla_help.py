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
  reaches, or that no formula chain reaches the result at all.

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
from collections.abc import Mapping
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
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
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
from .source_policy import source_policy

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
    casilla = casillas.get(str(casilla_id))
    if casilla is None:
        raise KeyError(f"casilla {casilla_id!r} is not defined by revision {snapshot.revision.id!r}")
    return casilla


def _legal_basis(casilla: CasillaDefinition, operation: PinnedAuthorityOperation) -> tuple[ModeloHelpCitationV1, ...]:
    return tuple(
        ModeloHelpCitationV1(text=legal_citation_text(reference), permalink=str(reference.permalink))
        for reference in (operation.legal_reference(ref_id) for ref_id in casilla.legal_refs)
    )


def _origin_sentences(
    casilla: CasillaDefinition,
    *,
    bindings: Mapping[str, BindingDefinition],
    language: OutputLanguage,
) -> tuple[str, ...]:
    return tuple(
        text
        for text in (_origin_sentence(bindings.get(str(binding_id)), language) for binding_id in _bound_by(casilla))
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
    casillas = {str(item.id): item for item in snapshot.revision.casillas}
    casilla = _require_help_casilla(casilla_id, snapshot=snapshot, casillas=casillas)
    formulas = {str(item.id): item for item in snapshot.revision.formulas}
    parameters = {str(item.id): item for item in snapshot.revision.parameters}
    bindings = {str(item.id): item for item in snapshot.revision.bindings}

    boxes = snapshot_printed_boxes(operation, snapshot)

    def box_text(key: str) -> str:
        number = boxes.number(key)
        return _phrase(language, "formula.working_figure") if number is None else f"[{number}]"

    def box_of(target: CasillaId) -> str:
        return box_text(str(target))

    def binding_name(binding_id: BindingId) -> str:
        binding = bindings.get(str(binding_id))
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
    )


__all__ = [
    "CasillaHelpCatalogueError",
    "ModeloCasillaHelpCardV1",
    "ModeloHelpCitationV1",
    "build_casilla_help_card",
    "legal_citation_text",
]
