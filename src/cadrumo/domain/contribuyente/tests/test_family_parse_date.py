"""Real-behavior tests for the consolidated coerce_iso_date_field helper.

Verifies that each of the three pydantic models that use _parse_date
(@field_validator) share identical input/output contracts:
- None passthrough (optional fields)
- ISO string parse (str -> date)
- ValidationError on bad format (non-ISO string)
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core import DescendantRelacion
from ..descendant import DescendantInfo
from ..family_types import RentaAscendantProfile, RentaDescendantProfile, coerce_iso_date_field

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ── coerce_iso_date_field unit contract ──────────────────────────────────────


def test_coerce_iso_date_field_none_passthrough() -> None:
    result = coerce_iso_date_field(None)
    assert result is None


def test_coerce_iso_date_field_parses_iso_string() -> None:
    result = coerce_iso_date_field("2024-03-15")
    assert result == date(2024, 3, 15)


def test_coerce_iso_date_field_passes_through_date_object() -> None:
    d = date(2023, 1, 1)
    result = coerce_iso_date_field(d)
    assert result is d


def test_coerce_iso_date_field_raises_on_bad_format() -> None:
    with pytest.raises(ValueError, match="not a valid ISO-8601 date"):
        coerce_iso_date_field("15/03/2024")


# ── DescendantInfo: birth_date and entry-event date fields ────────────────────


def test_descendant_info_birth_date_from_iso_string() -> None:
    info = DescendantInfo.model_validate({"birth_date": "2020-06-01"})
    assert info.birth_date == date(2020, 6, 1)


def test_descendant_info_entry_event_dates_none_passthrough() -> None:
    info = DescendantInfo(
        birth_date=date(2020, 1, 1),
        inscripcion_registro_civil_date=None,
        acogimiento_resolucion_date=None,
    )
    assert info.inscripcion_registro_civil_date is None
    assert info.acogimiento_resolucion_date is None


def test_descendant_info_inscripcion_date_from_iso_string() -> None:
    info = DescendantInfo.model_validate(
        {"birth_date": date(2020, 1, 1), "inscripcion_registro_civil_date": "2021-05-10"},
    )
    assert info.inscripcion_registro_civil_date == date(2021, 5, 10)


def test_descendant_info_acogimiento_date_from_iso_string() -> None:
    info = DescendantInfo.model_validate(
        {
            "birth_date": date(2020, 1, 1),
            "relacion": DescendantRelacion.ACOGIMIENTO_PREADOPTIVO_O_PERMANENTE,
            "acogimiento_resolucion_date": "2021-05-10",
        },
    )
    assert info.acogimiento_resolucion_date == date(2021, 5, 10)


def test_descendant_info_entry_date_bad_format_raises() -> None:
    """The ISO coercion covers both new date fields, not only birth_date."""
    for field in ("inscripcion_registro_civil_date", "acogimiento_resolucion_date"):
        with pytest.raises(ValidationError):
            DescendantInfo.model_validate({"birth_date": date(2020, 1, 1), field: "10-05-2021"})


def test_descendant_info_birth_date_bad_format_raises() -> None:
    with pytest.raises(ValidationError):
        DescendantInfo.model_validate({"birth_date": "01-06-2020"})


# ── RentaDescendantProfile: birth_date and death_date fields ─────────────────


def test_renta_descendant_birth_date_from_iso_string() -> None:
    p = RentaDescendantProfile.model_validate({"birth_date": "1990-11-22"})
    assert p.birth_date == date(1990, 11, 22)


def test_renta_descendant_death_date_none_passthrough() -> None:
    p = RentaDescendantProfile(birth_date=date(1990, 1, 1), death_date=None)
    assert p.death_date is None


def test_renta_descendant_death_date_from_iso_string() -> None:
    p = RentaDescendantProfile.model_validate({"birth_date": date(1990, 1, 1), "death_date": "2023-07-04"})
    assert p.death_date == date(2023, 7, 4)


def test_renta_descendant_birth_date_bad_format_raises() -> None:
    with pytest.raises(ValidationError):
        RentaDescendantProfile.model_validate({"birth_date": "22/11/1990"})


# ── RentaAscendantProfile: birth_date and death_date fields ──────────────────


def test_renta_ascendant_birth_date_from_iso_string() -> None:
    p = RentaAscendantProfile.model_validate({"birth_date": "1955-03-08"})
    assert p.birth_date == date(1955, 3, 8)


def test_renta_ascendant_death_date_none_passthrough() -> None:
    p = RentaAscendantProfile(birth_date=date(1955, 1, 1), death_date=None)
    assert p.death_date is None


def test_renta_ascendant_death_date_from_iso_string() -> None:
    p = RentaAscendantProfile.model_validate({"birth_date": date(1955, 1, 1), "death_date": "2022-12-31"})
    assert p.death_date == date(2022, 12, 31)


def test_renta_ascendant_birth_date_bad_format_raises() -> None:
    with pytest.raises(ValidationError):
        RentaAscendantProfile.model_validate({"birth_date": "not-a-date"})
