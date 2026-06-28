"""Roundtrip tests for the long-tail data_type aliases.

Covers `name`, `nif_iva`, `ccaa_code`, `province_code`,
`postal_code`, `municipality_code`, `bic`, and `date`. Each alias
exercises an accept path, a reject path, and a `CasillaDefinition`
round-trip to confirm the data_type tag is preserved through
strict pydantic validation.
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from .._schema import (
    BicString,
    CalendarDate,
    CasillaDefinition,
    CCAACode,
    MunicipalityCode,
    NifIvaString,
    PersonOrEntityName,
    PostalCode,
    ProvinceCode,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla_with(data_type: str, label: str = "Test casilla") -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "test_casilla",
            "number": "01",
            "label": label,
            "section": ("test",),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual-modelo",),
        },
    )


def test_semantic_role_accepts_long_cross_modelo_domain_identifier() -> None:
    casilla = _casilla_with(
        "decimal",
        label="Rendimiento capital mobiliario general propiedad intelectual no autor",
    )
    rebuilt = CasillaDefinition.model_validate(
        {
            **casilla.model_dump(),
            "semantic_role": "irpf_rendimiento_capital_mobiliario_general_propiedad_intelectual_no_autor",
        },
    )

    assert rebuilt.semantic_role == "irpf_rendimiento_capital_mobiliario_general_propiedad_intelectual_no_autor"


# ---- name ----------------------------------------------------------------

_NAME = TypeAdapter(PersonOrEntityName)


class TestPersonOrEntityName:
    @pytest.mark.parametrize(
        "raw,canonical",
        [
            ("Maria Garcia Lopez", "Maria Garcia Lopez"),
            ("  ACME SA  ", "ACME SA"),
            ("Año Nuevo Holdings", "Año Nuevo Holdings"),
        ],
    )
    def test_accepted(self, raw: str, canonical: str) -> None:
        assert _NAME.validate_python(raw) == canonical

    @pytest.mark.parametrize("raw", ["", "   ", "x" * 201])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _NAME.validate_python(raw)


# ---- nif_iva -------------------------------------------------------------

_NIFIVA = TypeAdapter(NifIvaString)


class TestNifIvaString:
    @pytest.mark.parametrize(
        "raw,canonical",
        [
            ("ESB58818501", "ESB58818501"),
            ("FR12345678901", "FR12345678901"),
            ("DE123456789", "DE123456789"),
            ("  es-b58818501  ", "ESB58818501"),
        ],
    )
    def test_accepted(self, raw: str, canonical: str) -> None:
        assert _NIFIVA.validate_python(raw) == canonical

    @pytest.mark.parametrize("raw", ["", "E", "ES", "ES1", "1234567890", "@@" + "1" * 8])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _NIFIVA.validate_python(raw)


# ---- ccaa_code -----------------------------------------------------------

_CCAA = TypeAdapter(CCAACode)


class TestCCAACode:
    @pytest.mark.parametrize("code", [f"{n:02d}" for n in range(1, 20)])
    def test_supported_accepted(self, code: str) -> None:
        assert _CCAA.validate_python(code) == code

    @pytest.mark.parametrize("raw", ["", "20", "1", "ES", "  01  ", "00"])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _CCAA.validate_python(raw)


# ---- province_code -------------------------------------------------------

_PROV = TypeAdapter(ProvinceCode)


class TestProvinceCode:
    @pytest.mark.parametrize("code", ["01", "28", "50", "52"])
    def test_accepted(self, code: str) -> None:
        assert _PROV.validate_python(code) == code

    @pytest.mark.parametrize("raw", ["", "00", "53", "99", "1", "ES", "AB"])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _PROV.validate_python(raw)


# ---- postal_code ---------------------------------------------------------

_POSTAL = TypeAdapter(PostalCode)


class TestPostalCode:
    @pytest.mark.parametrize("code", ["28013", "08001", "00001", "99999"])
    def test_accepted(self, code: str) -> None:
        assert _POSTAL.validate_python(code) == code

    @pytest.mark.parametrize("raw", ["", "1234", "123456", "ABCDE", "28-13"])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _POSTAL.validate_python(raw)


# ---- municipality_code --------------------------------------------------

_MUNI = TypeAdapter(MunicipalityCode)


class TestMunicipalityCode:
    @pytest.mark.parametrize("code", ["28079", "08019", "00001"])
    def test_accepted(self, code: str) -> None:
        assert _MUNI.validate_python(code) == code

    @pytest.mark.parametrize("raw", ["", "123", "ABCDE", "12-345"])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _MUNI.validate_python(raw)


# ---- bic -----------------------------------------------------------------

_BIC = TypeAdapter(BicString)


class TestBicString:
    @pytest.mark.parametrize(
        "raw,canonical",
        [
            ("CAIXESBBXXX", "CAIXESBBXXX"),
            ("CAIXESBB", "CAIXESBB"),
            ("  caix esbb xxx  ", "CAIXESBBXXX"),
        ],
    )
    def test_accepted(self, raw: str, canonical: str) -> None:
        assert _BIC.validate_python(raw) == canonical

    @pytest.mark.parametrize("raw", ["", "CAIX", "CAIXES", "CAIXESBBXX", "1AIXESBB"])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _BIC.validate_python(raw)


# ---- date ----------------------------------------------------------------

_DATE = TypeAdapter(CalendarDate)


class TestCalendarDate:
    @pytest.mark.parametrize("raw", ["2024-01-15", "2024-12-31", "15012024", "31122024"])
    def test_accepted(self, raw: str) -> None:
        assert _DATE.validate_python(raw) == raw

    @pytest.mark.parametrize("raw", ["", "2024", "2024-13-01", "32012024", "00012024", "2024/01/15"])
    def test_rejected(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            _DATE.validate_python(raw)


# ---- casilla round-trip across all atoms -------------------------------


@pytest.mark.parametrize(
    "tag",
    [
        "name",
        "nif_iva",
        "ccaa_code",
        "province_code",
        "postal_code",
        "municipality_code",
        "bic",
        "date",
    ],
)
def test_casilla_definition_round_trips_with_long_tail_data_types(tag: str) -> None:
    casilla = _casilla_with(tag)
    round_tripped = CasillaDefinition.model_validate(casilla.model_dump())
    assert round_tripped.data_type == tag
    assert round_tripped == casilla
