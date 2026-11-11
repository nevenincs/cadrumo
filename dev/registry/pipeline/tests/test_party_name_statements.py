"""A party-name rule is held to the design sentence that states it."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.export_field_kind import CasillaFieldKind
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.party_name_composition import PartyNameComponent, PartyNameComposition

from ..party_name_statements import verify_party_name_statements
from ..record_design_intermediate import (
    RecordDesignIntermediate,
    RecordDesignIntermediateField,
    RecordDesignIntermediateSheet,
    RecordDesignIntermediateSource,
    RecordDesignWorkbookFormat,
)
from ..semantic_map import SemanticMap, SemanticMapAnchor, SemanticMapEntry, SemanticMapPartyName, SemanticMapRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SHEET = "Tipo2"
_IDENTITY = "tipo-2"
_SOURCE_REF = "aeat-dr-347-fixture"
_EPOCH = "fixture-epoch"
_NATURAL = (
    "Si es persona fisica: el primer apellido, un espacio, el segundo apellido, un espacio y el nombre completo, "
    "necesariamente en este mismo orden."
)
_ENTITY = "Si es persona juridica o entidad: la razón social o la denominación completa de la entidad."
_REFERRAL = "Se cumplimentara con el mismo criterio que el especificado para el declarante."
_ORDER = (PartyNameComponent.PRIMER_APELLIDO, PartyNameComponent.SEGUNDO_APELLIDO, PartyNameComponent.NOMBRE)


def _field(row: int, content: str) -> RecordDesignIntermediateField:
    return RecordDesignIntermediateField(
        sheet=_SHEET,
        record_identity=_IDENTITY,
        source_row=row,
        source_cell=f"F{row}",
        ordinal=str(row),
        offset=row,
        length=40,
        aeat_type="Alfanumerico",
        normalized_description="NOMBRE",
        content=content,
    )


def _anchor(row: int) -> SemanticMapAnchor:
    return SemanticMapAnchor(
        sheet=_SHEET, source_row=row, source_cell=f"F{row}", ordinal=str(row), record_identity=_IDENTITY
    )


def _intermediate(*fields: RecordDesignIntermediateField) -> RecordDesignIntermediate:
    return RecordDesignIntermediate(
        source=RecordDesignIntermediateSource(
            source_ref=_SOURCE_REF,
            source_sha256="0" * 64,
            workbook_format=RecordDesignWorkbookFormat.XLSX,
            design_epoch=_EPOCH,
        ),
        sheets=(RecordDesignIntermediateSheet(sheet=_SHEET, record_identity=_IDENTITY, fields=fields),),
    )


def _rule(
    *,
    order: tuple[PartyNameComponent, ...] = _ORDER,
    separator: str = " ",
    natural: str = _NATURAL,
    stated_at: int | None = None,
) -> SemanticMapPartyName:
    return SemanticMapPartyName(
        composition=PartyNameComposition(
            natural_person=order, separator=separator, entity=(PartyNameComponent.RAZON_SOCIAL,)
        ),
        natural_person_statement=natural,
        entity_statement=_ENTITY,
        stated_at=None if stated_at is None else _anchor(stated_at),
        referral_statement=None if stated_at is None else _REFERRAL,
    )


def _semantic_map(rule: SemanticMapPartyName, *, row: int = 1) -> SemanticMap:
    return SemanticMap(
        modelo="347",
        design_epoch=_EPOCH,
        source_ref=_SOURCE_REF,
        source_sha256="0" * 64,
        records=(
            SemanticMapRecord(sheet=_SHEET, record_identity=_IDENTITY, export_record_id="m347-test", record_type="2"),
        ),
        entries=(
            SemanticMapEntry(
                anchor=_anchor(row),
                export_field_id="modelo-347-test-nombre",
                kind=CasillaFieldKind.BINDING,
                binding="modelo-347-contraparte-row-nombre",
                legal_refs=("rd-1065-2007:art-34",),
                source_refs=(_SOURCE_REF,),
                party_name=rule,
            ),
        ),
    )


def test_a_rule_the_slot_text_states_is_accepted() -> None:
    slot = _field(1, f"{_NATURAL}\n  {_ENTITY}")
    verify_party_name_statements(_semantic_map(_rule()), _intermediate(slot))


def test_a_rule_stated_by_reference_is_found_at_the_referred_slot() -> None:
    own = _field(1, _REFERRAL)
    stated = _field(2, f"{_NATURAL} {_ENTITY}")
    verify_party_name_statements(_semantic_map(_rule(stated_at=2)), _intermediate(own, stated))


def test_a_quotation_absent_from_the_slot_is_refused() -> None:
    slot = _field(1, _ENTITY)
    with pytest.raises(RegistryValidationError, match="natural-person statement its design slot does not contain"):
        verify_party_name_statements(_semantic_map(_rule()), _intermediate(slot))


def test_a_referred_slot_the_design_lacks_is_refused() -> None:
    own = _field(1, _REFERRAL)
    with pytest.raises(RegistryValidationError, match="slot the design does not have"):
        verify_party_name_statements(_semantic_map(_rule(stated_at=9)), _intermediate(own))


def test_a_composition_order_the_sentence_does_not_state_is_refused() -> None:
    slot = _field(1, f"{_NATURAL} {_ENTITY}")
    swapped = (PartyNameComponent.NOMBRE, PartyNameComponent.PRIMER_APELLIDO, PartyNameComponent.SEGUNDO_APELLIDO)
    with pytest.raises(RegistryValidationError, match="does not name it in that order"):
        verify_party_name_statements(_semantic_map(_rule(order=swapped)), _intermediate(slot))


def test_a_separator_the_sentence_does_not_state_is_refused() -> None:
    slot = _field(1, f"{_NATURAL} {_ENTITY}")
    with pytest.raises(RegistryValidationError, match="separates parts with"):
        verify_party_name_statements(_semantic_map(_rule(separator="-")), _intermediate(slot))
