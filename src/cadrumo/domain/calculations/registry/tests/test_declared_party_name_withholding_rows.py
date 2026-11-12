"""A perceptor-name slot files the name the person declared, composed by its record design's rule.

The Modelo 190 and 193 perceptor records fill their name "el primer apellido, un
espacio, el segundo apellido, un espacio y el nombre completo, necesariamente en
este mismo orden" for a natural person and the entity's complete denomination
otherwise. The rule and the width come from the published layout field, and every
scenario runs through the real withholding row resolver. A name the retention
source printed never reaches the slot, and a perceptor with no declared name
leaves the slot without content and is reported with the door that states it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import RetencionClave
from ....filing.declared_party_name import DeclaredPartyFilingName, DeclaredPartyKind
from ....filing.declared_party_name_filing import DECLARED_PARTY_NAME_DOOR_ACTION_ID, PartyNameRefusals
from ....filing.errors import FilingExportDeclaredPartyNameMissingError, FilingExportDeclaredPartyNameTooWideError
from ..authority import bundled_indexed_authority
from ..party_name_composition import PartyNameComponent
from ..schema import ModeloRevision
from ..schema_exports import ExportFieldDefinition
from ..withholding_bindings import WithholdingObservation, resolve_withholding_binding_row_values
from ..withholding_party_rows import (
    PENDING_PERCEPTOR_NAME,
    PENDING_PERCEPTOR_NIF,
    DeclaredWithholdingParty,
    withholding_party,
)
from .authored_editions import authored_revisions, filing_year_envelope
from .published_authority import published_revision
from .withholding_observation_defaults import zero_incapacity_and_foral_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M190_NAME_BINDING = "modelo-190-perceptor-row-name"
_M193_NAME_BINDING = "modelo-193-perceptor-row-name"
_PERCEPTOR = "12345678Z"
_PRINTED = "NOMBRE IMPRESO POR LA FUENTE"
_HANDLE = "a1b2c3d4e5f6"

_NATURAL = DeclaredPartyFilingName(
    kind=DeclaredPartyKind.NATURAL_PERSON, primer_apellido="GARCIA", segundo_apellido="LOPEZ", nombre="ANA MARIA"
)


@pytest.fixture(autouse=True)
def _generation_pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _exercise(revision: ModeloRevision) -> int:
    """An exercise the revision governs inside the support envelope: its last, or the horizon when open-ended."""
    return filing_year_envelope().horizon if revision.valid_to is None else revision.valid_to.year


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


def _observation(
    revision: ModeloRevision, *, tax_id: str = _PERCEPTOR, country: str | None = None
) -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"source-{tax_id}",
        perceptor_tax_id=tax_id,
        perceptor_legal_name=_PRINTED,
        country_code=country,
        transaction_date=date(_exercise(revision), 6, 1),
        clave=RetencionClave.from_registry("G"),
        subclave="01",
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("150"),
        province_code="28",
        territorial_deduction_clave=0,
        **zero_incapacity_and_foral_fields(),
    )


def _party(observation: WithholdingObservation, name: DeclaredPartyFilingName | None) -> DeclaredWithholdingParty:
    country, tax_id = withholding_party(observation)
    return DeclaredWithholdingParty(
        country_code=country, party_tax_id=tax_id, party_handle=_HANDLE, party_filing_name=name
    )


def _name_cells(
    revision: ModeloRevision,
    binding_id: str,
    observations: tuple[WithholdingObservation, ...],
    parties: tuple[DeclaredWithholdingParty, ...],
    refusals: PartyNameRefusals | None = None,
) -> dict[int, object]:
    rows = resolve_withholding_binding_row_values(revision, observations, parties=parties, party_name_refusals=refusals)
    return {index: value for (binding, index), value in rows.items() if binding == binding_id}


@pytest.mark.parametrize("revision_id", [str(item.id) for item in authored_revisions("190")])
def test_each_190_edition_carries_the_design_order_and_composes_a_natural_person_in_it(revision_id: str) -> None:
    revision = published_revision("190", revision_id)
    field = _name_field(revision, _M190_NAME_BINDING)
    assert field.party_name is not None
    assert field.party_name.natural_person == (
        PartyNameComponent.PRIMER_APELLIDO,
        PartyNameComponent.SEGUNDO_APELLIDO,
        PartyNameComponent.NOMBRE,
    )
    observation = _observation(revision)

    cells = _name_cells(revision, _M190_NAME_BINDING, (observation,), (_party(observation, _NATURAL),))

    assert cells == {1: "GARCIA LOPEZ ANA MARIA"}


@pytest.mark.parametrize("revision_id", [str(item.id) for item in authored_revisions("193")])
def test_each_193_edition_files_an_entity_perceptor_by_its_razon_social_and_never_the_printed_name(
    revision_id: str,
) -> None:
    revision = published_revision("193", revision_id)
    observation = _observation(revision, tax_id="B11111112")
    entity = DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social="INVERSIONES OLMO SL")

    cells = _name_cells(revision, _M193_NAME_BINDING, (observation,), (_party(observation, entity),))

    assert cells == {1: "INVERSIONES OLMO SL"}


def test_a_perceptor_with_no_declared_name_leaves_the_slot_empty_and_is_reported_with_its_door() -> None:
    revision = published_revision("190", str(authored_revisions("190")[-1].id))
    field = _name_field(revision, _M190_NAME_BINDING)
    observation = _observation(revision)
    refusals = PartyNameRefusals(modelo="190")

    cells = _name_cells(revision, _M190_NAME_BINDING, (observation,), (_party(observation, None),), refusals)

    assert cells == {}
    (refusal,) = refusals.refusals
    assert isinstance(refusal, FilingExportDeclaredPartyNameMissingError)
    assert refusal.context == {
        "reason": "missing",
        "modelo": "190",
        "export_record_id": refusal.export_record_id,
        "export_field_id": str(field.id),
        "field_length": field.length,
        "door_action_id": DECLARED_PARTY_NAME_DOOR_ACTION_ID,
        "party_handle": _HANDLE,
        "row_index": 1,
    }
    assert _PRINTED not in str(refusal)
    assert _PERCEPTOR not in str(refusal.context)


def test_a_perceptor_the_caller_declared_nothing_for_is_refused_exactly_as_one_stated_without_a_name() -> None:
    revision = published_revision("190", str(authored_revisions("190")[-1].id))
    refusals = PartyNameRefusals(modelo="190")

    cells = _name_cells(revision, _M190_NAME_BINDING, (_observation(revision),), (), refusals)

    assert cells == {}
    assert [type(item) for item in refusals.refusals] == [FilingExportDeclaredPartyNameMissingError]


def test_a_name_wider_than_the_slot_is_refused_not_truncated() -> None:
    revision = published_revision("190", str(authored_revisions("190")[-1].id))
    width = _name_field(revision, _M190_NAME_BINDING).length
    assert width is not None
    full = "A" * (width + 1)
    observation = _observation(revision)
    refusals = PartyNameRefusals(modelo="190")

    cells = _name_cells(
        revision,
        _M190_NAME_BINDING,
        (observation,),
        (_party(observation, DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social=full)),),
        refusals,
    )

    assert cells == {}
    (refusal,) = refusals.refusals
    assert isinstance(refusal, FilingExportDeclaredPartyNameTooWideError)
    assert (refusal.field_length, refusal.composed_length) == (width, width + 1)


def test_each_perceptor_row_files_the_name_declared_for_that_perceptor() -> None:
    revision = published_revision("190", str(authored_revisions("190")[-1].id))
    first = _observation(revision)
    second = _observation(revision, tax_id="B11111112")
    entity = DeclaredPartyFilingName(kind=DeclaredPartyKind.ENTITY, razon_social="OLMO SL")
    refusals = PartyNameRefusals(modelo="190")

    cells = _name_cells(
        revision,
        _M190_NAME_BINDING,
        (first, second),
        (_party(first, _NATURAL), _party(second, entity)),
        refusals,
    )

    assert sorted(map(str, cells.values())) == ["GARCIA LOPEZ ANA MARIA", "OLMO SL"]
    assert refusals.refusals == []


def test_a_stated_country_distinguishes_a_perceptor_from_one_whose_source_stated_none() -> None:
    revision = published_revision("190", str(authored_revisions("190")[-1].id))
    stated = _observation(revision, country="ES")
    unstated = _observation(revision, tax_id="B11111112")
    stated_party = _party(stated, _NATURAL)
    refusals = PartyNameRefusals(modelo="190")

    cells = _name_cells(revision, _M190_NAME_BINDING, (stated, unstated), (stated_party,), refusals)

    assert list(cells.values()) == ["GARCIA LOPEZ ANA MARIA"]
    assert len(refusals.refusals) == 1


def test_the_193_pending_collection_record_files_the_name_its_design_fixes_without_a_declared_name() -> None:
    revision = published_revision("193", str(authored_revisions("193")[-1].id))
    observation = _observation(revision, tax_id=PENDING_PERCEPTOR_NIF).model_copy(
        update={"perceptor_legal_name": PENDING_PERCEPTOR_NAME, "pendiente_flag": "X"}
    )
    refusals = PartyNameRefusals(modelo="193")

    cells = _name_cells(revision, _M193_NAME_BINDING, (observation,), (), refusals)

    assert cells == {1: PENDING_PERCEPTOR_NAME}
    assert refusals.refusals == []


def test_a_pending_flag_alone_does_not_exempt_a_named_perceptor_from_the_declared_name() -> None:
    revision = published_revision("193", str(authored_revisions("193")[-1].id))
    observation = _observation(revision).model_copy(update={"pendiente_flag": "X"})
    refusals = PartyNameRefusals(modelo="193")

    cells = _name_cells(revision, _M193_NAME_BINDING, (observation,), (), refusals)

    assert cells == {}
    assert len(refusals.refusals) == 1
