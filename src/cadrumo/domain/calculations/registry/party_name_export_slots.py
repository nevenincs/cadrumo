"""The party-name slots the pinned authority's export layouts declare.

A party-name slot is a binding-filled export field whose design states how a
party's name is composed into it (:class:`PartyNameComposition`) and how wide it
is. The export fills exactly these fields from a party's declared filing name and
refuses one the name cannot fill, so this inventory is what a counterparty's
filing name has to fit. Every slot is read from the hydrated layouts of the
pinned generation; nothing here names a modelo, a year or a width.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..export_field_kind import CasillaFieldKind
from .party_name_composition import PartyNameComposition
from .schema_exports import ExportFieldDefinition, ExportLayoutDefinition


class ExportLayoutSource(Protocol):
    """The export layouts of one pinned generation, as :class:`PinnedAuthorityOperation` serves them."""

    def export_layout_ids(self) -> tuple[tuple[str, str, str], ...]:
        """Every modelo/revision/layout identity the generation holds."""
        ...

    def export_layout(self, modelo_id: str, revision_id: str, layout_id: str) -> ExportLayoutDefinition:
        """One hydrated export layout."""
        ...


@dataclass(frozen=True, slots=True)
class PartyNameExportSlot:
    """One export field a party's filing name is filed into, with its design rule and width."""

    modelo: str
    revision_id: str
    layout_id: str
    export_record_id: str
    export_field_id: str
    width: int
    composition: PartyNameComposition


def is_party_name_slot(field: ExportFieldDefinition) -> bool:
    """Whether the field is a binding-filled party-name slot."""
    return field.party_name is not None and field.kind == CasillaFieldKind.BINDING and field.binding is not None


def party_name_export_slots(operation: ExportLayoutSource) -> tuple[PartyNameExportSlot, ...]:
    """Every party-name slot the pinned generation's export layouts declare, in layout order."""
    slots: dict[tuple[str, str, str, str, str], PartyNameExportSlot] = {}
    for modelo, revision_id, layout_id in operation.export_layout_ids():
        layout = operation.export_layout(modelo, revision_id, layout_id)
        for record in layout.records:
            for field in record.fields:
                if not is_party_name_slot(field) or field.length is None or field.party_name is None:
                    continue
                identity = (modelo, revision_id, layout_id, str(record.id), str(field.id))
                slots.setdefault(
                    identity,
                    PartyNameExportSlot(
                        modelo=modelo,
                        revision_id=revision_id,
                        layout_id=layout_id,
                        export_record_id=str(record.id),
                        export_field_id=str(field.id),
                        width=field.length,
                        composition=field.party_name,
                    ),
                )
    return tuple(slots.values())


__all__ = ["ExportLayoutSource", "PartyNameExportSlot", "is_party_name_slot", "party_name_export_slots"]
