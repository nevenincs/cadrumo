"""The export slots a counterparty's filing name must fit come from the pinned layouts, judged as the export judges.

Each slot's width is the hydrated layout field's length, and its fit is the
export's own composition run on the stated name: the view says a slot files
exactly when the export would fill it rather than refuse it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.party_name_export_slots import party_name_export_slots
from ....domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ....domain.filing.declared_party_name import (
    DeclaredPartyFilingName,
    DeclaredPartyKind,
    DeclaredPartyNameRendering,
)
from ....domain.filing.declared_party_name_filing import (
    PartyNameSlot,
    compose_declared_party_name,
    party_name_filing_text,
)
from ....domain.filing.errors import FilingExportDeclaredPartyNameTooWideError
from ..counterparty_filing_name_slots import counterparty_filing_name_slots

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _entity(length: int, *, renderings: tuple[DeclaredPartyNameRendering, ...] = ()) -> DeclaredPartyFilingName:
    return DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social="F" * length, renderings=renderings)


def test_every_slot_is_a_layout_field_with_its_width_and_no_name_fills_none(
    *, operation: PinnedAuthorityOperation
) -> None:
    slots, limits = counterparty_filing_name_slots(operation, None)

    assert slots
    assert {slot.modelo for slot in slots} >= {"347", "349"}
    for slot in slots:
        revision = operation.revision_with_export_layouts(slot.modelo, slot.revision_id)
        (field,) = (
            field
            for layout in revision.export_layouts
            if str(layout.id) == slot.layout_id
            for record in layout.records
            if str(record.id) == slot.export_record_id
            for field in record.fields
            if str(field.id) == slot.export_field_id
        )
        assert field.party_name is not None
        assert slot.width == field.length
        assert (slot.fits, slot.refusal, slot.composed_length) == (False, "missing", None)
    assert {limit.part for limit in limits} == {"primer_apellido", "segundo_apellido", "nombre", "razon_social"}


def test_each_part_limit_is_the_longest_part_whose_full_name_the_widest_slot_files_whole(
    *, operation: PinnedAuthorityOperation
) -> None:
    raw_slots = party_name_export_slots(operation)
    _slots, limits = counterparty_filing_name_slots(operation, None)
    widest = max(raw_slots, key=lambda slot: slot.width)
    by_part = {limit.part: limit.max_length for limit in limits}

    def person(surname_length: int) -> DeclaredPartyFilingName:
        return DeclaredPartyFilingName(
            kind=DeclaredPartyKind.NATURAL_PERSON,
            primer_apellido="P" * surname_length,
            segundo_apellido="S",
            nombre="N",
        )

    at_limit = compose_declared_party_name(person(by_part["primer_apellido"]), widest.composition)
    over_limit = compose_declared_party_name(person(by_part["primer_apellido"] + 1), widest.composition)
    assert at_limit is not None
    assert over_limit is not None
    assert len(at_limit) == widest.width
    assert len(over_limit) == widest.width + 1
    assert by_part["razon_social"] == widest.width


@dataclass(frozen=True)
class _NarrowedLayouts:
    """The pinned layouts, with one more copy of a party-name layout whose slot is one character narrower."""

    operation: PinnedAuthorityOperation
    modelo: str
    revision_id: str
    layout_id: str

    def export_layout_ids(self) -> tuple[tuple[str, str, str], ...]:
        return ((self.modelo, self.revision_id, self.layout_id), (self.modelo, self.revision_id, "narrowed"))

    def export_layout(self, modelo_id: str, revision_id: str, layout_id: str) -> ExportLayoutDefinition:
        layout = self.operation.export_layout(modelo_id, revision_id, self.layout_id)
        if layout_id != "narrowed":
            return layout
        return layout.model_copy(
            update={
                "records": tuple(
                    record.model_copy(
                        update={
                            "fields": tuple(
                                field.model_copy(update={"length": field.length - 1})
                                if field.party_name is not None and field.length is not None
                                else field
                                for field in record.fields
                            )
                        }
                    )
                    for record in layout.records
                )
            }
        )


def test_a_name_that_fills_the_wider_slot_overflows_the_narrower_one_as_the_export_refuses_it(
    *, operation: PinnedAuthorityOperation
) -> None:
    pinned = party_name_export_slots(operation)[0]
    source = _NarrowedLayouts(operation, pinned.modelo, pinned.revision_id, pinned.layout_id)
    name = _entity(pinned.width)

    slots, _limits = counterparty_filing_name_slots(source, name)

    wide = [slot for slot in slots if slot.layout_id == pinned.layout_id]
    narrow = [slot for slot in slots if slot.layout_id == "narrowed"]
    assert wide
    assert narrow
    assert all(slot.fits and slot.refusal is None and not slot.uses_rendering for slot in wide)
    assert all((slot.fits, slot.refusal) == (False, "too_wide") for slot in narrow)
    assert all(slot.composed_length == pinned.width for slot in slots)
    narrow_slot = narrow[0]
    with pytest.raises(FilingExportDeclaredPartyNameTooWideError):
        party_name_filing_text(
            name,
            composition=pinned.composition,
            slot=PartyNameSlot(
                modelo=narrow_slot.modelo,
                export_record_id=narrow_slot.export_record_id,
                export_field_id=narrow_slot.export_field_id,
                field_length=narrow_slot.width,
            ),
        )

    rendered = _entity(
        pinned.width, renderings=(DeclaredPartyNameRendering(width=narrow_slot.width, text="R" * narrow_slot.width),)
    )
    slots, _limits = counterparty_filing_name_slots(source, rendered)
    assert all(slot.fits for slot in slots)
    assert {slot.uses_rendering for slot in slots if slot.layout_id == "narrowed"} == {True}
    assert {slot.uses_rendering for slot in slots if slot.layout_id == pinned.layout_id} == {False}


def test_a_natural_person_with_one_surname_fills_no_slot(*, operation: PinnedAuthorityOperation) -> None:
    name = DeclaredPartyFilingName(
        kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="Ejemplo", no_second_surname=True, nombre="Ana"
    )

    slots, _limits = counterparty_filing_name_slots(operation, name)

    assert {(slot.fits, slot.refusal, slot.composed_length) for slot in slots} == {(False, "single_surname", None)}
