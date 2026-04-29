"""Unit tests for Kent's tax-residence profile models."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from . import CCAA, KentTaxResidence, ResidenceChange

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_kent_tax_residence_is_strict_frozen() -> None:
    residence = KentTaxResidence(ccaa=CCAA.MADRID)
    with pytest.raises(ValidationError):
        residence.__setattr__("ccaa", CCAA.CATALUNA)
    with pytest.raises(ValidationError):
        KentTaxResidence.model_validate({"ccaa": CCAA.MADRID, "extra": "nope"})


def test_kent_tax_residence_round_trips_json_schema_version() -> None:
    residence = KentTaxResidence(ccaa=CCAA.CATALUNA, tax_residence_since=date(2025, 1, 1))
    reparsed = KentTaxResidence.model_validate_json(residence.model_dump_json())
    assert reparsed == residence
    assert reparsed.schema_version == "1"


def test_kent_tax_residence_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        KentTaxResidence.model_validate({"schema_version": "2", "ccaa": "madrid"})


def test_residence_change_validates_closed_ccaa() -> None:
    change = ResidenceChange(
        from_ccaa=None,
        to_ccaa=CCAA.ANDALUCIA,
        effective_from=date(2025, 1, 1),
        reason="move",
    )
    assert change.to_ccaa is CCAA.ANDALUCIA
    assert ResidenceChange.model_validate_json(change.model_dump_json()) == change
