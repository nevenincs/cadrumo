"""Unit tests for the contribuyente tax-residence profile models.

Covers strict-frozen guarantees, schema-version handling, residence-
change ledger validation, and accented / foral-alias parsing in
:func:`cadrumo.domain.contribuyente.parse_tax_region`.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ..ccaa import CCAA
from ..errors import ForalRegimeError
from ..tax_residence import ResidenceChange, TaxResidenceProfile, parse_tax_region

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_tax_residence_profile_is_strict_frozen() -> None:
    residence = TaxResidenceProfile(ccaa=CCAA.MADRID)
    with pytest.raises(ValidationError, match=r"frozen"):
        residence.__setattr__("ccaa", CCAA.CATALUNA)
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        TaxResidenceProfile.model_validate({"ccaa": CCAA.MADRID, "extra": "nope"})


def test_tax_residence_profile_round_trips_json_schema_version() -> None:
    residence = TaxResidenceProfile(ccaa=CCAA.CATALUNA, tax_residence_since=date(2025, 1, 1))
    reparsed = TaxResidenceProfile.model_validate_json(residence.model_dump_json())
    assert reparsed == residence
    assert reparsed.schema_version == "1"


def test_tax_residence_profile_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        TaxResidenceProfile.model_validate({"schema_version": "2", "ccaa": "madrid"})


def test_residence_change_validates_closed_ccaa() -> None:
    change = ResidenceChange(
        from_ccaa=None,
        to_ccaa=CCAA.ANDALUCIA,
        effective_from=date(2025, 1, 1),
        reason="move",
    )
    assert change.to_ccaa is CCAA.ANDALUCIA
    assert ResidenceChange.model_validate_json(change.model_dump_json()) == change


def test_parse_tax_region_accepts_accented_display_names() -> None:
    assert parse_tax_region("Aragón") is CCAA.ARAGON
    assert parse_tax_region("Cataluña") is CCAA.CATALUNA
    assert parse_tax_region("Castilla y León") is CCAA.CASTILLA_Y_LEON


def test_parse_tax_region_refuses_accented_foral_alias() -> None:
    with pytest.raises(ForalRegimeError, match=r"País Vasco"):
        parse_tax_region("País Vasco")


def test_ccaa_from_iso_code_maps_all_common_regime_codes() -> None:
    """CCAA.from_iso_code must resolve every 3-letter code used by the former RentaCCAA enum."""
    mapping = {
        "AND": CCAA.ANDALUCIA,
        "ARA": CCAA.ARAGON,
        "AST": CCAA.ASTURIAS,
        "BAL": CCAA.BALEARES,
        "CAN": CCAA.CANARIAS,
        "CAB": CCAA.CANTABRIA,
        "CLM": CCAA.CASTILLA_LA_MANCHA,
        "CYL": CCAA.CASTILLA_Y_LEON,
        "CAT": CCAA.CATALUNA,
        "VAL": CCAA.COMUNIDAD_VALENCIANA,
        "EXT": CCAA.EXTREMADURA,
        "GAL": CCAA.GALICIA,
        "LAR": CCAA.LA_RIOJA,
        "MAD": CCAA.MADRID,
        "MUR": CCAA.MURCIA,
    }
    for code, expected in mapping.items():
        assert CCAA.from_iso_code(code) is expected


def test_ccaa_from_iso_code_is_case_insensitive() -> None:
    assert CCAA.from_iso_code("and") is CCAA.ANDALUCIA
    assert CCAA.from_iso_code("And") is CCAA.ANDALUCIA


def test_ccaa_from_iso_code_raises_key_error_for_unknown_code() -> None:
    with pytest.raises(KeyError, match="XXX"):
        CCAA.from_iso_code("XXX")


def test_ccaa_from_label_accepts_canonical_value() -> None:
    assert CCAA.from_label("andalucia") is CCAA.ANDALUCIA
    assert CCAA.from_label("madrid") is CCAA.MADRID
    assert CCAA.from_label("castilla_la_mancha") is CCAA.CASTILLA_LA_MANCHA


def test_ccaa_from_label_accepts_iso_code() -> None:
    assert CCAA.from_label("AND") is CCAA.ANDALUCIA
    assert CCAA.from_label("and") is CCAA.ANDALUCIA


def test_ccaa_from_label_normalises_hyphens() -> None:
    assert CCAA.from_label("castilla-la-mancha") is CCAA.CASTILLA_LA_MANCHA
    assert CCAA.from_label("comunidad-valenciana") is CCAA.COMUNIDAD_VALENCIANA


def test_ccaa_from_label_raises_value_error_for_unknown_label() -> None:
    with pytest.raises(ValueError, match="unknown CCAA label"):
        CCAA.from_label("pais_vasco")
