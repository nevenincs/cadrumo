"""Roundtrip tests for the `period_code` data_type and `PeriodCode` alias.

The `period_code` variant on `CasillaDefinition.data_type` plus the
`PeriodCode` `Annotated` alias on the schema module form the
canonical filing-period validation surface for the registry
boundary. Period tokens span six concrete forms documented in the
schema-hardening fiscal-period inventory: quarterly (`1T`-`4T`),
IS-instalment (`1P`-`4P`), annual (`0A`), monthly (`01`-`12`),
OSS-quarter (`EXT-1T`-`EXT-4T`), and ad-hoc (`AD-HOC`,
`EVENT-N`).
"""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..errors import RegistryValidationError
from .._schema import CasillaDefinition, PeriodCode, _validate_period_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_PERIOD_ADAPTER: TypeAdapter[str] = TypeAdapter(PeriodCode)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "period_test_casilla",
            "number": "01",
            "localization_keys": ("test.schema.casilla.label",),
            "section": ("declarante",),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual-modelo",),
        },
    )


class TestPeriodCodeAccepts:
    """`PeriodCode` accepts every documented period-token form."""

    def test_valid_tokens_accepted(self) -> None:
        cases = (
            "1T",
            "2T",
            "3T",
            "4T",
            "1P",
            "2P",
            "3P",
            "4P",
            "0A",
            "01",
            "02",
            "03",
            "04",
            "05",
            "06",
            "07",
            "08",
            "09",
            "10",
            "11",
            "12",
            "EXT-1T",
            "EXT-2T",
            "EXT-3T",
            "EXT-4T",
            "AD-HOC",
            "EVENT-1",
            "EVENT-42",
            "EVENT-9999",
        )

        for code in cases:
            assert _PERIOD_ADAPTER.validate_python(code) == code, code


class TestPeriodCodeRejects:
    """`PeriodCode` rejects malformed and unsupported period tokens."""

    def test_invalid_inputs_rejected_through_adapter(self) -> None:
        cases: tuple[object, ...] = (
            "",
            "T1",  # reversed-letter quarter
            "5T",  # quarter out of range
            "0T",  # quarter out of range
            "13",  # month out of range
            "00",  # month out of range
            "1Q",  # wrong letter
            "ext-1t",  # lowercase not accepted
            "EXT-5T",  # OSS quarter out of range
            "EXT-1Q",  # wrong OSS letter
            "Q1",  # wrong letter
            "FY2024",  # year-style
            "EVENT-",  # event needs number
            "AD HOC",  # space variant rejected
            "^AD-HOC$",  # the raw regex literal must NOT pass — a previous
            # bug compared values against this string instead
            # of regex-matching against the AD-HOC pattern;
            # this anti-tautology guard pins the fix and would
            # accept the literal back if the regression returns
            1,
        )

        for raw in cases:
            with pytest.raises(ValidationError):
                _PERIOD_ADAPTER.validate_python(raw)

    def test_invalid_value_raises_registry_validation_error_at_validator(self) -> None:
        for raw in ("", 1):
            with pytest.raises(RegistryValidationError):
                _validate_period_code(raw)


class TestCasillaDefinitionDataType:
    """`CasillaDefinition` accepts the new `period_code` data_type tag."""

    def test_period_code_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("period_code")
        round_tripped = CasillaDefinition.model_validate(
            {**casilla.model_dump(), "localization_keys": casilla.localization_keys},
        )
        assert round_tripped.data_type == "period_code"
        assert round_tripped == casilla
