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

from ....deadlines.festivos import CalendarCCAA
from ..schema import (
    BicString,
    CalendarDate,
    CCAACode,
    MunicipalityCode,
    NifIvaString,
    PersonOrEntityName,
    PostalCode,
    ProvinceCode,
)
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "test_casilla",
            "number": "01",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("test",),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual-modelo",),
        },
    )


def test_semantic_role_accepts_long_cross_modelo_domain_identifier() -> None:
    casilla = _casilla_with("decimal")
    rebuilt = CasillaDefinition.model_validate(
        {
            **casilla.model_dump(),
            "localization_keys": casilla.localization_keys,
            "semantic_role": "irpf_rendimiento_capital_mobiliario_general_propiedad_intelectual_no_autor",
        },
    )

    assert rebuilt.semantic_role == "irpf_rendimiento_capital_mobiliario_general_propiedad_intelectual_no_autor"


# ---- name ----------------------------------------------------------------

_NAME = TypeAdapter(PersonOrEntityName)


class TestPersonOrEntityName:
    def test_accepted(self) -> None:
        cases = (
            ("Maria Garcia Lopez", "Maria Garcia Lopez"),
            ("  ACME SA  ", "ACME SA"),
            ("Año Nuevo Holdings", "Año Nuevo Holdings"),
        )

        for raw, canonical in cases:
            assert _NAME.validate_python(raw) == canonical, raw

    def test_rejected(self) -> None:
        for raw in ("", "   ", "x" * 201):
            with pytest.raises(ValidationError):
                _NAME.validate_python(raw)


# ---- nif_iva -------------------------------------------------------------

_NIFIVA = TypeAdapter(NifIvaString)


class TestNifIvaString:
    def test_accepted(self) -> None:
        cases = (
            ("ESB58818501", "ESB58818501"),
            ("FR12345678901", "FR12345678901"),
            ("DE123456789", "DE123456789"),
            ("  es-b58818501  ", "ESB58818501"),
        )

        for raw, canonical in cases:
            assert _NIFIVA.validate_python(raw) == canonical, raw

    def test_rejected(self) -> None:
        for raw in ("", "E", "ES", "ES1", "1234567890", "@@" + "1" * 8):
            with pytest.raises(ValidationError):
                _NIFIVA.validate_python(raw)


# ---- ccaa_code -----------------------------------------------------------

_CCAA = TypeAdapter(CCAACode)


def _accepted_two_digit_codes() -> set[str]:
    """Return the codes the validator actually accepts, by probing every two-digit string.

    Derived from behaviour rather than read from the constant, so the assertions
    below cannot be satisfied by restating the thing they test.
    """
    accepted = set()
    for number in range(100):
        candidate = f"{number:02d}"
        try:
            _CCAA.validate_python(candidate)
        except ValidationError:
            continue
        accepted.add(candidate)
    return accepted


class TestCCAACode:
    def test_accepts_one_code_per_spanish_autonomous_territory(self) -> None:
        """The accepted count matches an independently-authored enumeration.

        :class:`CalendarCCAA` enumerates the same population — the seventeen
        autonomous communities plus Ceuta and Melilla — keyed by ISO 3166-2:ES
        code for holiday calendars. It shares no source with this validator, so
        agreeing on how many Spanish autonomous territories exist is a real
        check rather than a restatement.
        """
        accepted = _accepted_two_digit_codes()

        assert accepted, "the validator accepts nothing; this probe cannot discriminate"
        assert len(accepted) == len(CalendarCCAA), (
            f"the shape check accepts {len(accepted)} codes but Spain has {len(CalendarCCAA)} autonomous territories"
        )

    def test_accepts_a_contiguous_run_of_ordinals_starting_at_one(self) -> None:
        """The accepted set is an ordinal run, asserted as a rule rather than a list.

        A shape check numbers territories consecutively from one; ``00`` is not
        an ordinal, and a gap would mean the set had become some particular
        modelo's numbering, which this deliberately is not.
        """
        accepted = _accepted_two_digit_codes()
        ordinals = sorted(int(code) for code in accepted)

        assert ordinals[0] == 1, "an ordinal run starts at 01, and 00 names no territory"
        assert ordinals == list(range(ordinals[0], ordinals[-1] + 1)), f"the accepted codes have a gap: {ordinals}"
        assert all(len(code) == 2 and code.isdigit() for code in accepted), "every code is two ASCII digits"

    def test_rejected(self) -> None:
        for raw in ("", "20", "1", "ES", "  01  ", "00"):
            with pytest.raises(ValidationError):
                _CCAA.validate_python(raw)


# ---- province_code -------------------------------------------------------

_PROV = TypeAdapter(ProvinceCode)


class TestProvinceCode:
    def test_accepted(self) -> None:
        for code in ("01", "28", "50", "52"):
            assert _PROV.validate_python(code) == code, code

    def test_rejected(self) -> None:
        for raw in ("", "00", "53", "99", "1", "ES", "AB"):
            with pytest.raises(ValidationError):
                _PROV.validate_python(raw)


# ---- postal_code ---------------------------------------------------------

_POSTAL = TypeAdapter(PostalCode)


class TestPostalCode:
    def test_accepted(self) -> None:
        for code in ("28013", "08001", "00001", "99999"):
            assert _POSTAL.validate_python(code) == code, code

    def test_rejected(self) -> None:
        for raw in ("", "1234", "123456", "ABCDE", "28-13"):
            with pytest.raises(ValidationError):
                _POSTAL.validate_python(raw)


# ---- municipality_code --------------------------------------------------

_MUNI = TypeAdapter(MunicipalityCode)


class TestMunicipalityCode:
    def test_accepted(self) -> None:
        for code in ("28079", "08019", "00001"):
            assert _MUNI.validate_python(code) == code, code

    def test_rejected(self) -> None:
        for raw in ("", "123", "ABCDE", "12-345"):
            with pytest.raises(ValidationError):
                _MUNI.validate_python(raw)


# ---- bic -----------------------------------------------------------------

_BIC = TypeAdapter(BicString)


class TestBicString:
    def test_accepted(self) -> None:
        cases = (
            ("CAIXESBBXXX", "CAIXESBBXXX"),
            ("CAIXESBB", "CAIXESBB"),
            ("  caix esbb xxx  ", "CAIXESBBXXX"),
        )

        for raw, canonical in cases:
            assert _BIC.validate_python(raw) == canonical, raw

    def test_rejected(self) -> None:
        for raw in ("", "CAIX", "CAIXES", "CAIXESBBXX", "1AIXESBB"):
            with pytest.raises(ValidationError):
                _BIC.validate_python(raw)


# ---- date ----------------------------------------------------------------

_DATE = TypeAdapter(CalendarDate)


class TestCalendarDate:
    def test_accepted(self) -> None:
        for raw in ("2024-01-15", "2024-12-31", "15012024", "31122024"):
            assert _DATE.validate_python(raw) == raw, raw

    def test_rejected(self) -> None:
        for raw in ("", "2024", "2024-13-01", "32012024", "00012024", "2024/01/15"):
            with pytest.raises(ValidationError):
                _DATE.validate_python(raw)


# ---- casilla round-trip across all atoms -------------------------------


def test_casilla_definition_round_trips_with_long_tail_data_types() -> None:
    tags = (
        "name",
        "nif_iva",
        "ccaa_code",
        "province_code",
        "postal_code",
        "municipality_code",
        "bic",
        "date",
    )

    for tag in tags:
        casilla = _casilla_with(tag)
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == tag, tag
        assert round_tripped == casilla
