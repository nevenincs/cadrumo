"""Public period requests reject malformed domain coordinates before dispatch."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ..public_period import PublicPeriod
from ..registry import OperationSchemaBindingV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("code", ["1T", "0A", "03", "EVENT-3"])
def test_public_period_preserves_canonical_domain_meaning(code: str) -> None:
    canonical = Period.from_year_and_code(2026, code)
    projection = PublicPeriod.from_period(canonical)
    restored = PublicPeriod.model_validate_json(projection.model_dump_json())
    assert restored.to_period() == canonical
    binding = OperationSchemaBindingV1.bind(schema_id="test.period", schema_version=1, model_type=PublicPeriod)
    assert binding.model_type is PublicPeriod


@pytest.mark.parametrize("year", [1000, 1979, 2201, 9999])
def test_public_period_takes_any_year_written_with_four_digits(year: int) -> None:
    restored = PublicPeriod.model_validate_json(json.dumps({"filing_year": year, "code": "1T"}))
    assert restored.to_period().start_date.year == year


@pytest.mark.parametrize(
    ("year", "code"),
    [(999, "1T"), (10000, "1T"), (2026, "1t"), (2026, " 1T"), (2026, "Q1"), (2026, "EVENT-N")],
)
def test_public_period_refuses_noncanonical_or_invalid_coordinates(year: int, code: str) -> None:
    with pytest.raises(ValidationError):
        PublicPeriod.model_validate_json(json.dumps({"filing_year": year, "code": code}))
