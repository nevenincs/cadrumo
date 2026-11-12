"""The export slots a counterparty's filing name must fit, and whether its stated name fits each.

A view serves these so a surface can ask for a rendering per width before an
export refuses. Every slot, width and composition rule is read from the pinned
authority's export layouts, and the fit is the export's own composition run on
the stated name, so the view and the export cannot disagree.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.modelo_localization import revision_locale_key
from ...domain.calculations.registry.party_name_composition import PartyNameComponent
from ...domain.calculations.registry.party_name_export_slots import (
    ExportLayoutSource,
    PartyNameExportSlot,
    party_name_export_slots,
)
from ...domain.filing.declared_party_name import DeclaredPartyFilingName
from ...domain.filing.declared_party_name_filing import PartyNameSlot, party_name_slot_fit
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH, served_words_language

_ID_MAX = 128
"""The longest registry identity a slot projection carries."""

FilingNameSlotRefusal = Literal["missing", "single_surname", "too_wide"]
FilingNamePart = Literal["primer_apellido", "segundo_apellido", "nombre", "razon_social"]


class CounterpartyFilingNameSlot(BaseModel):
    """One export field the counterparty's filing name is filed into, and whether the stated name fills it.

    ``fits`` and ``refusal`` are the export's answer for this slot: ``refusal``
    names why the export would refuse it and is ``None`` exactly when ``fits``.
    With no name stated every slot refuses as ``missing``. ``composed_length`` is
    the length of the full name the slot's design composes, ``None`` when it
    composes none; ``uses_rendering`` says the slot files the rendering stated for
    its width because the full name is wider. ``edition_words`` name the slot's
    edition as the registry words it, in ``edition_words_language``, so a surface
    tells editions apart without reading a revision identity.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    modelo: str = Field(min_length=1, max_length=_ID_MAX)
    revision_id: str = Field(min_length=1, max_length=_ID_MAX)
    edition_words: str = Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    edition_words_language: OutputLanguage
    layout_id: str = Field(min_length=1, max_length=_ID_MAX)
    export_record_id: str = Field(min_length=1, max_length=_ID_MAX)
    export_field_id: str = Field(min_length=1, max_length=_ID_MAX)
    width: int = Field(gt=0)
    fits: bool
    refusal: FilingNameSlotRefusal | None = None
    composed_length: int | None = Field(default=None, gt=0)
    uses_rendering: bool = False


class CounterpartyFilingNamePartLimit(BaseModel):
    """The longest a stated name part can be and still compose a full name some slot files whole.

    For each slot the part composes into, the bound is the slot's width less
    the design's separators and one character for each other part the design
    composes with it (a stated part is never empty); the limit is the widest
    such bound. A longer part can be stated, but every slot then needs a
    rendering of its own.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    part: FilingNamePart
    max_length: int = Field(gt=0)


def _refusal(reason: str | None) -> FilingNameSlotRefusal | None:
    if reason is None:
        return None
    if reason == "missing":
        return "missing"
    if reason == "single_surname":
        return "single_surname"
    if reason == "too_wide":
        return "too_wide"
    raise ValueError(f"unknown party-name refusal {reason!r}")


def _slot_projection(
    slot: PartyNameExportSlot, name: DeclaredPartyFilingName | None, language: OutputLanguage
) -> CounterpartyFilingNameSlot:
    fit = party_name_slot_fit(
        name,
        composition=slot.composition,
        slot=PartyNameSlot(
            modelo=slot.modelo,
            export_record_id=slot.export_record_id,
            export_field_id=slot.export_field_id,
            field_length=slot.width,
        ),
    )
    return CounterpartyFilingNameSlot(
        modelo=slot.modelo,
        revision_id=slot.revision_id,
        edition_words=tr(revision_locale_key(slot.modelo, slot.revision_id), locale=language.value),
        edition_words_language=language,
        layout_id=slot.layout_id,
        export_record_id=slot.export_record_id,
        export_field_id=slot.export_field_id,
        width=slot.width,
        fits=fit.fits,
        refusal=_refusal(fit.refusal),
        composed_length=fit.composed_length,
        uses_rendering=fit.uses_rendering,
    )


def _part_limits(slots: tuple[PartyNameExportSlot, ...]) -> tuple[CounterpartyFilingNamePartLimit, ...]:
    limits: dict[PartyNameComponent, int] = {}
    for slot in slots:
        composition = slot.composition
        for branch in (composition.natural_person, composition.entity):
            others = len(branch) - 1
            bound = slot.width - others * (len(composition.separator) + 1)
            for part in branch:
                if bound > limits.get(part, 0):
                    limits[part] = bound
    return tuple(
        CounterpartyFilingNamePartLimit(part=_part(component), max_length=limits[component])
        for component in PartyNameComponent
        if component in limits
    )


def _part(component: PartyNameComponent) -> FilingNamePart:
    if component is PartyNameComponent.PRIMER_APELLIDO:
        return "primer_apellido"
    if component is PartyNameComponent.SEGUNDO_APELLIDO:
        return "segundo_apellido"
    if component is PartyNameComponent.NOMBRE:
        return "nombre"
    return "razon_social"


def counterparty_filing_name_slots(
    operation: ExportLayoutSource, name: DeclaredPartyFilingName | None
) -> tuple[tuple[CounterpartyFilingNameSlot, ...], tuple[CounterpartyFilingNamePartLimit, ...]]:
    """Every party-name slot of the pinned authority with the stated name's fit, and the per-part limits."""
    slots = party_name_export_slots(operation)
    language = served_words_language()
    return tuple(_slot_projection(slot, name, language) for slot in slots), _part_limits(slots)


__all__ = [
    "CounterpartyFilingNamePartLimit",
    "CounterpartyFilingNameSlot",
    "FilingNamePart",
    "FilingNameSlotRefusal",
    "counterparty_filing_name_slots",
]
