"""Resolve declared work-form labels and safe box-locator help."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

import re
from typing import Final

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import lookup_translation, tr
from ...domain.calculations.registry.modelo_localization import modelo_localization_source, resolve_modelo_localization
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from .printed_boxes import printed_box_number
from .work_form_models import ModeloFormText, ModeloFormTextDisclosure

_SPANISH: Final[str] = OutputLanguage.ES.value

_UNNAMED_LOCALE_KEY: Final[str] = "application.modelo.work_form.unnamed_box"

"""The label of a box the form gives no name, in the filer's words."""

_FEEDS_BOX_LOCALE_KEY: Final[str] = "application.modelo.work_form.additional_data_for_box"

"""The label of an input no box owns that feeds exactly one numbered box, named after that box."""

_BOX_LOCATOR_HELP_LOCALE_KEYS: Final[tuple[str, ...]] = (
    "application.modelo.work_form.box_locator_help.one_year",
    "application.modelo.work_form.box_locator_help.year_span",
    "application.modelo.work_form.box_locator_help.onwards",
)

"""The catalogue's sentences that only say which box of which modelo and year a casilla is."""

_BOX_SLOT: Final[str] = "\ue000"

_YEARS_SLOT: Final[str] = "\ue001"

"""Placeholders no catalogue text contains, standing where a locator names its box and its year."""

_FIGURES: Final[str] = "[0-9-]+"

"""What fills a locator's box and year: digits and the hyphen of a range, never words."""


def localized_text(keys: tuple[str, ...], language: OutputLanguage) -> ModeloFormText | None:
    """Resolve a modelo catalogue chain and say which language actually served it."""
    source = modelo_localization_source(keys, locale=language.value)
    text = resolve_modelo_localization(keys, locale=language.value)
    if source is None or not text:
        return None
    served_locale = source[1]
    disclosure = (
        ModeloFormTextDisclosure.LOCALIZED
        if served_locale == language.value
        else ModeloFormTextDisclosure.SPANISH_FALLBACK
    )
    return ModeloFormText(text=text, disclosure=disclosure)


def localized_heading(key: str, official: str | None, technical: str, language: OutputLanguage) -> ModeloFormText:
    """Resolve a layout heading: the translation, then Spanish, then the design's words, then a name."""
    translated = lookup_translation(key, locale=language.value)
    if translated:
        return ModeloFormText(text=translated, disclosure=ModeloFormTextDisclosure.LOCALIZED)
    spanish = lookup_translation(key, locale=_SPANISH)
    if spanish:
        disclosure = (
            ModeloFormTextDisclosure.LOCALIZED
            if language is OutputLanguage.ES
            else ModeloFormTextDisclosure.SPANISH_FALLBACK
        )
        return ModeloFormText(text=spanish, disclosure=disclosure)
    if official:
        return ModeloFormText(text=official, disclosure=ModeloFormTextDisclosure.OFFICIAL_SPANISH)
    return ModeloFormText(text=technical, disclosure=ModeloFormTextDisclosure.TECHNICAL)


def unnamed_casilla_label(language: OutputLanguage) -> ModeloFormText:
    """The label of a box the form gives no name: plain words saying so, never its identifier."""
    text = lookup_translation(_UNNAMED_LOCALE_KEY, locale=language.value) or lookup_translation(
        _UNNAMED_LOCALE_KEY, locale=_SPANISH
    )
    if not text:
        raise InternalInvariantError(f"the catalogue has no text for {_UNNAMED_LOCALE_KEY!r}")
    return ModeloFormText(text=text, disclosure=ModeloFormTextDisclosure.UNNAMED)


def fed_box_label(binding_id: str, context: WorkFormContext) -> ModeloFormText | None:
    """Name an input no box owns after the one numbered box it feeds, or ``None`` when it feeds none or several."""
    fed = context.fed_casillas.get(binding_id, set())
    if len(fed) != 1:
        return None
    (casilla_id,) = fed
    box = context.placed_boxes.get(casilla_id) or printed_box_number(context.casillas.get(casilla_id), None)
    if box is None:
        return None
    for locale, disclosure in (
        (context.language.value, ModeloFormTextDisclosure.LOCALIZED),
        (_SPANISH, ModeloFormTextDisclosure.SPANISH_FALLBACK),
    ):
        if lookup_translation(_FEEDS_BOX_LOCALE_KEY, locale=locale):
            return ModeloFormText(text=tr(_FEEDS_BOX_LOCALE_KEY, locale=locale, box=box), disclosure=disclosure)
    raise InternalInvariantError(f"the catalogue has no text for {_FEEDS_BOX_LOCALE_KEY!r}")


def casilla_help(casilla: CasillaDefinition, label: str, context: WorkFormContext) -> str | None:
    """Return the casilla's help unless it only restates the label or names the box."""
    keys = tuple(f"{key.removesuffix('.label')}.help" for key in casilla.localization_keys)
    text = resolve_modelo_localization(keys, locale=context.language.value)
    if not text:
        return None
    if normalized_help_text(text) == normalized_help_text(label) or names_only_its_box(text, context.box_locators):
        return None
    return text


def render_box_locator_patterns(modelo: str) -> tuple[re.Pattern[str], ...]:
    """The sentences that only say which box of ``modelo`` and which year a help is about, in every language.

    Each is the catalogue's own sentence rendered for the modelo, so a reworded
    catalogue is followed rather than missed. The box and the year are taken as
    written, as figures: help an edition inherits names the year of the edition
    that stated it, and some name the box by its record positions.
    """
    locators: list[re.Pattern[str]] = []
    for language in OutputLanguage:
        for key in _BOX_LOCATOR_HELP_LOCALE_KEYS:
            rendered = re.escape(tr(key, locale=language.value, modelo=modelo, box=_BOX_SLOT, years=_YEARS_SLOT))
            figures = rendered.replace(_BOX_SLOT, _FIGURES).replace(_YEARS_SLOT, _FIGURES)
            locators.append(re.compile(figures))
    return tuple(locators)


def names_only_its_box(text: str, locators: tuple[re.Pattern[str], ...]) -> bool:
    """Whether a help text is one of ``locators``' sentences and says nothing else."""
    stated = text.strip()
    return any(locator.fullmatch(stated) for locator in locators)


def normalized_help_text(text: str) -> str:
    """Normalize localized help and label text for duplicate suppression."""
    return re.sub(r"[\W_]+", " ", text).strip().casefold()
