"""Modelo 720 foreign-asset register invariants (Orden HAP/72/2013 Anexo, type 2).

Each refusal is checked through the registered cause the validator raises, not
only through Pydantic's wrapper, so a validator that started refusing for a
different reason would fail here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pydantic
import pytest

from ....core.foreign_asset_obligation import M720AssetClassCode
from ..register import (
    ForeignAssetDeclarationEntry,
    ForeignAssetRegister,
    ForeignAssetRegisterEntry,
    ForeignAssetRegisterError,
    ForeignAssetRegisterValidationError,
    M720AssetIdentifier,
    M720DeclarantCondition,
    M720IdentifierScheme,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_IBAN = "DE89370400440532013000"
_OTHER_IBAN = "ES9121000418450200051332"
_ISIN = "US0378331005"


def _ref(digit: str) -> str:
    return "m720a_" + digit * 32


def _entry(
    ref: str,
    asset_class: M720AssetClassCode,
    identifier: M720AssetIdentifier,
    *,
    subclave: int | None = 1,
    country: str = "DE",
) -> ForeignAssetRegisterEntry:
    return ForeignAssetRegisterEntry(
        asset_ref=ref,
        asset_class=asset_class,
        subclave=subclave,
        country_code=country,
        identifier=identifier,
        description="synthetic asset",
        held_since=date(2015, 1, 1),
    )


def _account(ref: str, iban: str = _IBAN) -> ForeignAssetRegisterEntry:
    return _entry(ref, M720AssetClassCode.CUENTA, M720AssetIdentifier(scheme=M720IdentifierScheme.IBAN, value=iban))


def _real_estate(ref: str) -> ForeignAssetRegisterEntry:
    return _entry(ref, M720AssetClassCode.BIEN_INMUEBLE, M720AssetIdentifier(scheme=M720IdentifierScheme.NONE))


def _declaration(
    ref: str,
    condition: M720DeclarantCondition = M720DeclarantCondition.TITULAR,
    *,
    titularidad: str | None = None,
    pct: str = "100.00",
) -> ForeignAssetDeclarationEntry:
    return ForeignAssetDeclarationEntry(
        asset_ref=ref,
        condition=condition,
        titularidad_detail=titularidad,
        participation_pct=Decimal(pct),
    )


def _assert_refused(build: Callable[[], object], match: str) -> None:
    with pytest.raises(pydantic.ValidationError) as excinfo:
        build()
    error = excinfo.value.errors()[0]["ctx"]["error"]
    assert isinstance(error.__cause__, ForeignAssetRegisterValidationError), error
    assert match in str(error)


def test_a_register_with_every_class_round_trips_through_json() -> None:
    register = ForeignAssetRegister(
        assets=(
            _account(_ref("1")),
            _entry(
                _ref("2"),
                M720AssetClassCode.VALOR,
                M720AssetIdentifier(scheme=M720IdentifierScheme.ISIN, value=_ISIN),
                country="US",
            ),
            _entry(
                _ref("3"),
                M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA,
                M720AssetIdentifier(scheme=M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY, value="ZLU"),
                subclave=None,
                country="LU",
            ),
            _entry(
                _ref("4"),
                M720AssetClassCode.SEGURO,
                M720AssetIdentifier(scheme=M720IdentifierScheme.NONE),
                subclave=2,
                country="FR",
            ),
            _real_estate(_ref("5")),
            # B carries no identifier, so a second real-estate asset is not a collision.
            _real_estate(_ref("6")),
        ),
        declarations=(
            _declaration(_ref("1")),
            _declaration(_ref("1"), M720DeclarantCondition.AUTORIZADO, pct="50.00"),
            _declaration(_ref("5"), M720DeclarantCondition.OTRAS_TITULARIDAD_REAL, titularidad="nuda propiedad"),
        ),
    )

    restored = ForeignAssetRegister.model_validate_json(register.model_dump_json())

    assert restored == register
    assert restored.asset(_ref("2")).identifier.value == _ISIN


@pytest.mark.parametrize("asset_ref", ("a" * 32, "m720a_" + "A" * 32, "m720a_" + "a" * 31, "m720a_" + "g" * 32))
def test_an_asset_reference_outside_the_persisted_identity_contract_is_refused(asset_ref: str) -> None:
    with pytest.raises(pydantic.ValidationError) as excinfo:
        _account(asset_ref)
    error = excinfo.value.errors()[0]
    assert error["loc"] == ("asset_ref",)
    assert error["type"] == "string_pattern_mismatch"


@pytest.mark.parametrize(
    ("scheme", "value", "match"),
    [
        (M720IdentifierScheme.IBAN, "DE89370400440532013001", "check digits"),
        (M720IdentifierScheme.IBAN, "de89 3704 0044 0532 0130 00", "canonical"),
        (M720IdentifierScheme.ISIN, "US0378331006", "ISIN"),
        (M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY, "LU", "Z plus the issuer country"),
        (M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY, "Zlu", "uppercase"),
        (M720IdentifierScheme.NONE, "anything", "carries no value"),
        (M720IdentifierScheme.ISIN, "", "requires a value"),
    ],
)
def test_an_identifier_that_does_not_fit_its_scheme_is_refused(
    scheme: M720IdentifierScheme, value: str, match: str
) -> None:
    _assert_refused(lambda: M720AssetIdentifier(scheme=scheme, value=value), match)


def test_a_scheme_the_class_does_not_admit_is_refused() -> None:
    isin = M720AssetIdentifier(scheme=M720IdentifierScheme.ISIN, value=_ISIN)
    _assert_refused(lambda: _entry(_ref("1"), M720AssetClassCode.CUENTA, isin), "not admitted")


def test_a_subclave_outside_the_class_vocabulary_is_refused() -> None:
    isin = M720AssetIdentifier(scheme=M720IdentifierScheme.ISIN, value=_ISIN)
    _assert_refused(lambda: _entry(_ref("1"), M720AssetClassCode.VALOR, isin, subclave=5), "not defined")
    _assert_refused(
        lambda: _entry(_ref("1"), M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA, isin, subclave=1),
        "no subclave",
    )


def test_a_repeated_asset_ref_is_refused() -> None:
    _assert_refused(
        lambda: ForeignAssetRegister(assets=(_account(_ref("1")), _account(_ref("1"), _OTHER_IBAN))),
        "repeated asset_ref",
    )


def test_two_assets_with_one_unique_official_identifier_are_refused() -> None:
    _assert_refused(
        lambda: ForeignAssetRegister(assets=(_account(_ref("1")), _account(_ref("2")))),
        "same official identifier",
    )


def test_a_declaration_for_an_unregistered_asset_is_refused() -> None:
    _assert_refused(
        lambda: ForeignAssetRegister(assets=(_account(_ref("1")),), declarations=(_declaration(_ref("9")),)),
        "unregistered assets",
    )


def test_two_declarations_for_one_asset_and_condition_are_refused() -> None:
    register = ForeignAssetRegister(assets=(_account(_ref("1")),), declarations=(_declaration(_ref("1")),))
    _assert_refused(lambda: register.with_declaration(_declaration(_ref("1"))), "one asset and condition")


@pytest.mark.parametrize(
    ("condition", "titularidad", "pct", "match"),
    [
        (M720DeclarantCondition.OTRAS_TITULARIDAD_REAL, None, "100.00", "requires the tipo de titularidad"),
        (M720DeclarantCondition.TITULAR, "nuda propiedad", "100.00", "only for condition 8"),
        (M720DeclarantCondition.TITULAR, None, "0", "positive"),
        (M720DeclarantCondition.TITULAR, None, "33.333", "two decimals"),
    ],
)
def test_a_declaration_breaking_the_record_design_is_refused(
    condition: M720DeclarantCondition, titularidad: str | None, pct: str, match: str
) -> None:
    _assert_refused(lambda: _declaration(_ref("1"), condition, titularidad=titularidad, pct=pct), match)


def test_an_unsupported_schema_version_is_refused() -> None:
    _assert_refused(lambda: ForeignAssetRegister(schema_version="0"), "schema_version")


def test_looking_up_an_unregistered_asset_refuses() -> None:
    with pytest.raises(ForeignAssetRegisterError, match="not registered"):
        ForeignAssetRegister().asset(_ref("1"))


@pytest.mark.parametrize(
    ("held_since", "ceased_on", "held_in_2025", "ceased_in_2025"),
    [
        (date(2015, 1, 1), None, True, False),
        (date(2025, 12, 31), None, True, False),
        (date(2026, 1, 1), None, False, False),
        (date(2015, 1, 1), date(2025, 1, 1), True, True),
        (date(2015, 1, 1), date(2024, 12, 31), False, False),
    ],
)
def test_the_holding_period_decides_which_ejercicios_reach_the_asset(
    held_since: date, ceased_on: date | None, held_in_2025: bool, ceased_in_2025: bool
) -> None:
    entry = _account(_ref("a")).model_copy(update={"held_since": held_since, "ceased_on": ceased_on})

    assert entry.held_in(2025) is held_in_2025
    assert entry.ceased_in(2025) is ceased_in_2025


def test_an_asset_cannot_cease_before_it_was_first_held() -> None:
    payload = _account(_ref("a")).model_dump()
    payload["ceased_on"] = date(2014, 12, 31)

    with pytest.raises(pydantic.ValidationError, match="cannot cease before it was first held"):
        ForeignAssetRegisterEntry.model_validate(payload)
