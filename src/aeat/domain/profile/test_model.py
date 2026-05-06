"""Unit tests for the contribuyente tax-residence profile models.

Covers strict-frozen guarantees, schema-version handling, residence-
change ledger validation, and accented / foral-alias parsing in
:func:`aeat.domain.profile.parse_tax_region`.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from . import CCAA, ForalRegimeError, ResidenceChange, TaxResidenceProfile, parse_tax_region

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_tax_residence_profile_is_strict_frozen() -> None:
    residence = TaxResidenceProfile(ccaa=CCAA.MADRID)
    with pytest.raises(ValidationError):
        residence.__setattr__("ccaa", CCAA.CATALUNA)
    with pytest.raises(ValidationError):
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
    with pytest.raises(ForalRegimeError):
        parse_tax_region("País Vasco")
