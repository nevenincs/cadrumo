"""The register's conditions and subclaves are the ones the published fact declares."""

from __future__ import annotations

from datetime import date

import pydantic
import pytest

from ....core.foreign_asset_obligation import M720AssetClassCode
from ..register import (
    ForeignAssetRegisterEntry,
    M720AssetIdentifier,
    M720DeclarantCondition,
    M720IdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_IDENTIFIER_BY_CLASS = {
    M720AssetClassCode.CUENTA: M720AssetIdentifier(scheme=M720IdentifierScheme.IBAN, value="DE89370400440532013000"),
    M720AssetClassCode.VALOR: M720AssetIdentifier(scheme=M720IdentifierScheme.ISIN, value="US0378331005"),
    M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA: M720AssetIdentifier(
        scheme=M720IdentifierScheme.ISIN, value="US0378331005"
    ),
    M720AssetClassCode.SEGURO: M720AssetIdentifier(scheme=M720IdentifierScheme.NONE),
    M720AssetClassCode.BIEN_INMUEBLE: M720AssetIdentifier(scheme=M720IdentifierScheme.NONE),
}


def _admitted(asset_class: M720AssetClassCode, subclave: int | None) -> bool:
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


def test_each_class_admits_the_subclaves_the_published_record_design_lists() -> None:
    # Read from the AEAT Modelo 720 type 2 record, position 103: C one to five, V one to
    # three, S one and two, B one to five, and I written as zero.
    expected = {
        M720AssetClassCode.CUENTA: {1, 2, 3, 4, 5},
        M720AssetClassCode.VALOR: {1, 2, 3},
        M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA: set(),
        M720AssetClassCode.SEGURO: {1, 2},
        M720AssetClassCode.BIEN_INMUEBLE: {1, 2, 3, 4, 5},
    }

    for asset_class, subclaves in expected.items():
        assert {value for value in range(10) if _admitted(asset_class, value)} == subclaves
        assert _admitted(asset_class, None) is (not subclaves)


def test_conditions_are_the_published_clave_de_condicion_values() -> None:
    # Read from the same record, position 76.
    assert M720DeclarantCondition.TITULAR.code == "1"
    assert M720DeclarantCondition.OTRAS_TITULARIDAD_REAL.code == "8"
    assert sorted(M720DeclarantCondition.form_codes().values()) == [str(number) for number in range(1, 9)]
