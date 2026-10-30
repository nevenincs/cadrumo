"""The register's closed code sets stay inside what the published type 2 record admits."""

from __future__ import annotations

from datetime import date

import pydantic
import pytest

from ....core.foreign_asset_obligation import M720AssetClassCode
from ...calculations.registry.schema_exports import ExportFieldDefinition
from ...calculations.registry.tests.published_authority import published_revision
from ..register import (
    ForeignAssetRegisterEntry,
    M720AssetIdentifier,
    M720DeclarantCondition,
    M720IdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IDENTIFIER_BY_CLASS = {
    M720AssetClassCode.CUENTA: M720AssetIdentifier(scheme=M720IdentifierScheme.IBAN, value="DE89370400440532013000"),
    M720AssetClassCode.VALOR: M720AssetIdentifier(scheme=M720IdentifierScheme.ISIN, value="US0378331005"),
    M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA: M720AssetIdentifier(
        scheme=M720IdentifierScheme.ISIN, value="US0378331005"
    ),
    M720AssetClassCode.SEGURO: M720AssetIdentifier(scheme=M720IdentifierScheme.NONE),
    M720AssetClassCode.BIEN_INMUEBLE: M720AssetIdentifier(scheme=M720IdentifierScheme.NONE),
}


def _type_2_field(field_id: str) -> ExportFieldDefinition:
    layout = published_revision("720", "2013-y-siguientes").export_layouts[0]
    record = next(record for record in layout.records if record.id == "modelo-720-type-2")
    return next(field for field in record.fields if field.id == field_id)


def _admitted_subclave(asset_class: M720AssetClassCode, subclave: int | None) -> bool:
    try:
        ForeignAssetRegisterEntry(
            asset_ref="m720a_" + "1" * 32,
            asset_class=asset_class,
            subclave=subclave,
            country_code="DE",
            identifier=_IDENTIFIER_BY_CLASS[asset_class],
            description="synthetic asset",
            held_since=date(2015, 1, 1),
        )
    except pydantic.ValidationError:
        return False
    return True


def test_declarant_conditions_are_exactly_the_published_clave_de_condicion_values() -> None:
    field = _type_2_field("modelo-720-type_2-clave-de-condicion-del-declarante")

    assert {condition.value for condition in M720DeclarantCondition} == set(field.allowed_values or ())


def test_class_subclaves_cover_exactly_the_published_subclave_values() -> None:
    field = _type_2_field("modelo-720-type_2-subclave-de-bien-o-derecho")
    declared = {int(value) for value in field.allowed_values or ()}
    admitted = {
        subclave or 0
        for asset_class in M720AssetClassCode
        for subclave in (None, *range(10))
        if _admitted_subclave(asset_class, subclave)
    }

    assert admitted == declared
