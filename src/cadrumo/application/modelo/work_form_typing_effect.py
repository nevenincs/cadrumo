"""What typing a value over a box does, said in words, for every frontend.

A value typed into a box is new when the box held nothing anyone gave it,
replaces what a source or the calculation produced, or changes the filer's own
value. A replaced source is named by the kind of place it came from, and by the
declaration when it was carried from exactly one. Removing the filer's value and
giving a box back to its source each have one fixed sentence.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, Field

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language, tr
from ...core.models import STRICT_FROZEN_CONFIG
from .source_policy import SourceFamily
from .work_form_models import (
    ModeloFormAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloFormOrigin,
    ModeloWorkForm,
    address_key,
)
from .work_form_wording import period_words

#: Editabilities under which the filer may type a value on the field itself.
TYPED_EDITABILITIES: Final[frozenset[ModeloFormEditability]] = frozenset(
    {
        ModeloFormEditability.EDITABLE_VALUE,
        ModeloFormEditability.EDITABLE_OVERRIDE,
        ModeloFormEditability.OVERRIDABLE_SOURCE,
    }
)


class ModeloFormDisplacement(StrEnum):
    """What a value typed over a box replaces."""

    NOTHING = "nothing"
    SOURCE = "source"
    CALCULATION = "calculation"
    FILER = "filer"


_NAMED_FILING: Final = "named_filing"
CLEAR_EFFECT_LOCALE_KEY: Final = "workspace.modelo.review.effect.clear"
RESTORE_EFFECT_LOCALE_KEY: Final = "workspace.modelo.review.effect.restore"
TYPING_EFFECTS: Final[tuple[str, ...]] = (
    "clear",
    "restore",
    *(f"set_{item.value}" for item in ModeloFormDisplacement),
    *(f"replaces_{family.value}" for family in SourceFamily),
    f"replaces_{_NAMED_FILING}",
)
"""Every effect a change can state; a replaced source is named by its family."""


def _effect_key(effect: str) -> str:
    return f"workspace.modelo.review.effect.{effect}"


def field_displacement(field: ModeloFormField) -> ModeloFormDisplacement:
    """What a value typed over ``field`` replaces, from where its value comes from."""
    if field.origin in {ModeloFormOrigin.IMPORTED, ModeloFormOrigin.OVERRIDES_SOURCE}:
        return ModeloFormDisplacement.SOURCE
    if field.origin is ModeloFormOrigin.CALCULATED:
        return ModeloFormDisplacement.CALCULATION
    if field.origin is ModeloFormOrigin.ENTERED:
        return ModeloFormDisplacement.FILER
    return ModeloFormDisplacement.NOTHING


def typing_effect_key(field: ModeloFormField) -> str:
    """The catalogue key saying what typing a value over ``field`` does.

    The key for one earlier declaration takes ``{modelo}`` and ``{period}``.
    """
    displaces = field_displacement(field)
    source = field.source
    if displaces is ModeloFormDisplacement.SOURCE and source is not None:
        if source.family is SourceFamily.EARLIER_FILINGS and len(source.earlier_filings) == 1:
            return _effect_key(f"replaces_{_NAMED_FILING}")
        return _effect_key(f"replaces_{source.family.value}")
    return _effect_key(f"set_{displaces.value}")


def typing_effect_words(field: ModeloFormField, language: OutputLanguage | None = None) -> str:
    """Say what typing a value over ``field`` does, naming the declaration a replaced value came from."""
    key = typing_effect_key(field)
    locale = language.value if language is not None else output_language()
    source = field.source
    if key == _effect_key(f"replaces_{_NAMED_FILING}") and source is not None:
        filing = source.earlier_filings[0]
        return tr(key, modelo=filing.modelo, period=period_words(filing.period, language), locale=locale)
    return tr(key, locale=locale)


def field_typing_effect_words(field: ModeloFormField, language: OutputLanguage) -> str | None:
    """What typing over ``field`` does, or ``None`` when the filer cannot type a value on it."""
    if field.editability not in TYPED_EDITABILITIES:
        return None
    return typing_effect_words(field, language)


class ModeloFormTypingEffect(BaseModel):
    """What typing a value over one box does, in the form's language, keyed by the box's address.

    ``displaces`` says what the typed value replaces, so a review can count the
    changes that replace an imported or calculated value without reading words.
    """

    model_config = STRICT_FROZEN_CONFIG

    address: ModeloFormAddressV1
    displaces: ModeloFormDisplacement
    words: str = Field(min_length=1)


def form_typing_effects(form: ModeloWorkForm, language: OutputLanguage) -> tuple[ModeloFormTypingEffect, ...]:
    """What typing over each box the filer can type a value on does, in reading order, once per box."""
    effects: dict[tuple[str, str], ModeloFormTypingEffect] = {}
    for field in form.fields():
        words = field_typing_effect_words(field, language)
        if words is not None:
            effects.setdefault(
                address_key(field.address),
                ModeloFormTypingEffect(address=field.address, displaces=field_displacement(field), words=words),
            )
    return tuple(effects.values())


__all__ = [
    "CLEAR_EFFECT_LOCALE_KEY",
    "RESTORE_EFFECT_LOCALE_KEY",
    "TYPED_EDITABILITIES",
    "TYPING_EFFECTS",
    "ModeloFormDisplacement",
    "ModeloFormTypingEffect",
    "field_displacement",
    "field_typing_effect_words",
    "form_typing_effects",
    "typing_effect_key",
    "typing_effect_words",
]
