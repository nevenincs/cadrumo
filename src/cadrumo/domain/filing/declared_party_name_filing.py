"""The text a party-name slot files, composed from the party's declared filing name.

The composition rule (order of the parts, separator) is the record design's,
read from the hydrated export field; the width is that field's ``length``. The
operator's words are never split, reordered, abbreviated or truncated: when the
full name does not fit, only a rendering the operator stated for exactly that
width can stand in for it, and otherwise the slot refuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from ..calculations.registry.party_name_composition import PartyNameComponent, PartyNameComposition
from .declared_party_name import DeclaredPartyFilingName, DeclaredPartyKind
from .errors import (
    FilingExportDeclaredPartyNameError,
    FilingExportDeclaredPartyNameMissingError,
    FilingExportDeclaredPartyNameSingleSurnameError,
    FilingExportDeclaredPartyNameTooWideError,
)

#: The operator action that states or restates a party's filing name: the door
#: every declared-party-name refusal names.
DECLARED_PARTY_NAME_DOOR_ACTION_ID: Final[str] = "operator.ledger.counterparty.filing_name"


@dataclass(frozen=True, slots=True)
class PartyNameSlot:
    """Where a party name is filed, named without identifying the party.

    ``party_handle`` is a non-identifying handle (a prefix of the party's record
    key digest), never a tax identifier or a name.
    """

    modelo: str
    export_record_id: str
    export_field_id: str
    field_length: int
    party_handle: str | None = None
    row_index: int | None = None


@dataclass(slots=True)
class PartyNameRefusals:
    """Collects the party-name slots a calculation could not fill, for one modelo.

    A calculation leaves such a slot without content and reports it; the
    export refuses the slot again if it is still without content then.
    """

    modelo: str
    refusals: list[FilingExportDeclaredPartyNameError] = field(default_factory=list)


def compose_declared_party_name(name: DeclaredPartyFilingName, composition: PartyNameComposition) -> str | None:
    """Return the full name the design composes from the stated parts, or ``None`` when it states no rule for them.

    A natural person declared with no second surname has no composition in any
    design, so ``None``; a blank is never put in its place.
    """
    if name.kind is DeclaredPartyKind.ENTITY:
        parts = composition.entity
    else:
        if name.no_second_surname:
            return None
        parts = composition.natural_person
    texts = tuple(_component_text(name, part) for part in parts)
    if any(text is None for text in texts):
        return None
    return composition.separator.join(text for text in texts if text is not None)


def party_name_filing_text(
    name: DeclaredPartyFilingName | None,
    *,
    composition: PartyNameComposition,
    slot: PartyNameSlot,
) -> str:
    """Return the text ``slot`` files for a party, or refuse with the door that states its name.

    Raises:
        FilingExportDeclaredPartyNameMissingError: No filing name is stated.
        FilingExportDeclaredPartyNameSingleSurnameError: A natural person stated
            with one surname, which no design composes.
        FilingExportDeclaredPartyNameTooWideError: The composed name is wider
            than the slot and no stated rendering for that width exists.
    """
    if name is None:
        raise _refusal(FilingExportDeclaredPartyNameMissingError, slot)
    composed = compose_declared_party_name(name, composition)
    if composed is None:
        raise _refusal(FilingExportDeclaredPartyNameSingleSurnameError, slot)
    if len(composed) <= slot.field_length:
        return composed
    rendering = next((item for item in name.renderings if item.width == slot.field_length), None)
    if rendering is not None:
        return rendering.text
    raise _refusal(FilingExportDeclaredPartyNameTooWideError, slot, composed_length=len(composed))


def _component_text(name: DeclaredPartyFilingName, component: PartyNameComponent) -> str | None:
    if component is PartyNameComponent.PRIMER_APELLIDO:
        return name.primer_apellido
    if component is PartyNameComponent.SEGUNDO_APELLIDO:
        return name.segundo_apellido
    if component is PartyNameComponent.NOMBRE:
        return name.nombre
    return name.razon_social


def _refusal(
    error_type: type[FilingExportDeclaredPartyNameError],
    slot: PartyNameSlot,
    *,
    composed_length: int | None = None,
) -> FilingExportDeclaredPartyNameError:
    return error_type(
        modelo=slot.modelo,
        export_record_id=slot.export_record_id,
        export_field_id=slot.export_field_id,
        field_length=slot.field_length,
        door_action_id=DECLARED_PARTY_NAME_DOOR_ACTION_ID,
        party_handle=slot.party_handle,
        row_index=slot.row_index,
        composed_length=composed_length,
    )


__all__ = [
    "DECLARED_PARTY_NAME_DOOR_ACTION_ID",
    "PartyNameRefusals",
    "PartyNameSlot",
    "compose_declared_party_name",
    "party_name_filing_text",
]
