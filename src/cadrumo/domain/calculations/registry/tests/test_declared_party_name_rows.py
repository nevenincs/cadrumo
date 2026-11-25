"""A party-name slot files the name the person declared, composed by its record design's rule.

Both Modelo 347 designs fill the declarado and arrendatario name "el primer
apellido, un espacio, el segundo apellido, un espacio y el nombre completo,
necesariamente en este mismo orden" for a natural person and "la razón social o
la denominación completa de la entidad, sin anagramas" for an entity; the Modelo
349 operador name is filled "con el mismo criterio que el especificado para el
declarante". The rule and the width come from the published layout field, and
every scenario runs through the real row resolver. An invoice's printed name
never reaches the slot, and a name the slot cannot take leaves it without
content and is reported with the door that states the name.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from ....filing.declared_party_name import DeclaredPartyFilingName, DeclaredPartyKind, DeclaredPartyNameRendering
from ....filing.declared_party_name_filing import DECLARED_PARTY_NAME_DOOR_ACTION_ID, PartyNameRefusals
from ....filing.errors import (
    FilingExportDeclaredPartyNameMissingError,
    FilingExportDeclaredPartyNameSingleSurnameError,
    FilingExportDeclaredPartyNameTooWideError,
)
from ..authority import bundled_indexed_authority
from ..invoice_bindings import InvoiceObservation, resolve_invoice_binding_row_values
from ..party_name_composition import PartyNameComponent
from ..schema import ModeloRevision
from ..schema_exports import ExportFieldDefinition
from .authored_editions import authored_revisions, filing_year_envelope
from .published_authority import published_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M347_NAME_BINDING = "modelo-347-contraparte-row-nombre"
_M349_NAME_BINDING = "iva-349-operador-row-apellidos"
_PARTY = "B11111112"
_PRINTED = "NOMBRE IMPRESO EN LA FACTURA SL"


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _name_field(revision: ModeloRevision, binding_id: str) -> ExportFieldDefinition:
    fields = [
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.binding == binding_id and field.party_name is not None
    ]
    assert fields, f"no layout field files {binding_id} with a composition rule"
    return fields[0]


def _m347(revision_id: str) -> ModeloRevision:
    return published_revision("347", revision_id)


def _m347_year(revision: ModeloRevision) -> int:
    return _exercise(revision)


def _exercise(revision: ModeloRevision) -> int:
    """An exercise the revision governs inside the support envelope: its last, or the horizon when open-ended."""
    return filing_year_envelope().horizon if revision.valid_to is None else revision.valid_to.year


def _m347_observation(
    revision: ModeloRevision,
    *,
    name: DeclaredPartyFilingName | None,
    handle: str | None = "a1b2c3d4e5f6",
) -> InvoiceObservation:
    return InvoiceObservation(
        invoice_id="inv-347-1",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id=_PARTY,
        country_code="ES",
        transaction_date=date(_m347_year(revision), 3, 10),
        base_amount=Decimal("8000"),
        invoice_total_amount=Decimal("9680"),
        operation_clave="B",
        party_legal_name=_PRINTED,
        party_filing_name=name,
        party_handle=handle,
    )


def _m347_name_cells(
    revision: ModeloRevision,
    name: DeclaredPartyFilingName | None,
    refusals: PartyNameRefusals | None = None,
) -> dict[int, object]:
    rows = resolve_invoice_binding_row_values(
        revision,
        (_m347_observation(revision, name=name),),
        effective_date=date(_m347_year(revision), 12, 31),
        party_name_refusals=refusals,
    )
    return {index: value for (binding, index), value in rows.items() if binding == _M347_NAME_BINDING}


_NATURAL = DeclaredPartyFilingName(
    kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="GARCIA", segundo_apellido="LOPEZ", nombre="ANA MARIA"
)


@pytest.mark.parametrize("revision_id", [str(item.id) for item in authored_revisions("347")])
def test_each_347_edition_carries_the_design_order_and_composes_a_natural_person_in_it(revision_id: str) -> None:
    revision = _m347(revision_id)
    field = _name_field(revision, _M347_NAME_BINDING)
    assert field.party_name is not None
    assert field.party_name.natural_person == (
        PartyNameComponent.PRIMER_APELLIDO,
        PartyNameComponent.SEGUNDO_APELLIDO,
        PartyNameComponent.NOMBRE,
    )

    assert _m347_name_cells(revision, _NATURAL) == {1: "GARCIA LOPEZ ANA MARIA"}


def test_an_entity_files_its_razon_social_and_never_the_printed_name() -> None:
    revision = _m347(str(authored_revisions("347")[-1].id))
    entity = DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social="CONSTRUCCIONES OLMO SL")

    assert _m347_name_cells(revision, entity) == {1: "CONSTRUCCIONES OLMO SL"}


def test_a_party_with_no_declared_name_leaves_the_slot_empty_and_is_reported_with_its_door() -> None:
    revision = _m347(str(authored_revisions("347")[-1].id))
    field = _name_field(revision, _M347_NAME_BINDING)
    refusals = PartyNameRefusals(modelo="347")

    cells = _m347_name_cells(revision, None, refusals)

    assert cells == {}
    assert len(refusals.refusals) == 1
    refusal = refusals.refusals[0]
    assert isinstance(refusal, FilingExportDeclaredPartyNameMissingError)
    assert refusal.context == {
        "reason": "missing",
        "modelo": "347",
        "export_record_id": refusal.export_record_id,
        "export_field_id": str(field.id),
        "field_length": field.length,
        "door_action_id": DECLARED_PARTY_NAME_DOOR_ACTION_ID,
        "party_handle": "a1b2c3d4e5f6",
        "row_index": 1,
    }
    assert _PRINTED not in str(refusal)
    assert _PARTY not in str(refusal.context)


def test_a_natural_person_stated_with_one_surname_is_refused_not_composed() -> None:
    revision = _m347(str(authored_revisions("347")[-1].id))
    single = DeclaredPartyFilingName(
        kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="GARCIA", no_second_surname=True, nombre="ANA"
    )
    refusals = PartyNameRefusals(modelo="347")

    assert _m347_name_cells(revision, single, refusals) == {}
    assert [type(item) for item in refusals.refusals] == [FilingExportDeclaredPartyNameSingleSurnameError]


def test_a_name_wider_than_its_slot_files_only_a_rendering_stated_for_that_width() -> None:
    revision = _m347(str(authored_revisions("347")[-1].id))
    width = _name_field(revision, _M347_NAME_BINDING).length
    assert width is not None
    full = "COMUNIDAD DE PROPIETARIOS CALLE OLMO " + "X" * (width - 36)
    assert len(full) == width + 1
    unrendered = DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social=full)
    refusals = PartyNameRefusals(modelo="347")

    assert _m347_name_cells(revision, unrendered, refusals) == {}
    (refusal,) = refusals.refusals
    assert isinstance(refusal, FilingExportDeclaredPartyNameTooWideError)
    assert (refusal.field_length, refusal.composed_length) == (width, width + 1)
    assert full not in str(refusal.context)

    stated_short = "C.P. CALLE OLMO " + "X" * (width - 36)
    rendered = unrendered.model_copy(
        update={"renderings": (DeclaredPartyNameRendering(width=width, text=stated_short),)},
    )
    assert _m347_name_cells(revision, rendered) == {1: stated_short}

    other_width = unrendered.model_copy(
        update={"renderings": (DeclaredPartyNameRendering(width=width + 5, text=full[: width + 5]),)},
    )
    assert _m347_name_cells(revision, other_width) == {}


def test_a_349_operador_files_its_declared_name_by_the_declarante_rule() -> None:
    revision = published_revision("349", str(authored_revisions("349")[-1].id))
    field = _name_field(revision, _M349_NAME_BINDING)
    assert field.party_name is not None
    year = _exercise(revision)
    observation = InvoiceObservation(
        invoice_id="inv-349-1",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        party_tax_id="DE123456789",
        country_code="DE",
        transaction_date=date(year, 2, 10),
        base_amount=Decimal("7000"),
        intracommunity_clave="E",
        party_legal_name=_PRINTED,
        party_filing_name=DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social="BEISPIEL GMBH"),
    )
    unnamed = observation.model_copy(
        update={
            "invoice_id": "inv-349-2",
            "party_tax_id": "FR12345678901",
            "country_code": "FR",
            "party_filing_name": None,
        }
    )
    refusals = PartyNameRefusals(modelo="349")

    rows = resolve_invoice_binding_row_values(
        revision, (observation, unnamed), effective_date=date(year, 3, 31), party_name_refusals=refusals
    )

    names = {index: value for (binding, index), value in rows.items() if binding == _M349_NAME_BINDING}
    assert names == {1: "BEISPIEL GMBH"}
    assert [(type(item), item.row_index) for item in refusals.refusals] == [
        (FilingExportDeclaredPartyNameMissingError, 2)
    ]
