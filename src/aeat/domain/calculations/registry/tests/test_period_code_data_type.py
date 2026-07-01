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

from .._errors import RegistryValidationError
from .._schema import CasillaDefinition, PeriodCode, _validate_period_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_PERIOD_ADAPTER: TypeAdapter[str] = TypeAdapter(PeriodCode)


def _casilla_with(data_type: str) -> CasillaDefinition:
    return CasillaDefinition.model_validate(
        {
            "id": "period_test_casilla",
            "number": "01",
            "label": "Periodo",
            "section": ("declarante",),
            "data_type": data_type,
            "legal_refs": ("ley-58-2003:art-29",),
            "source_refs": ("aeat-manual-modelo",),
        },
    )


class TestPeriodCodeAccepts:
    """`PeriodCode` accepts every documented period-token form."""

    @pytest.mark.parametrize(
        "code",
        (
            pytest.param("1T", id="quarter-1"),
            pytest.param("2T", id="quarter-2"),
            pytest.param("3T", id="quarter-3"),
            pytest.param("4T", id="quarter-4"),
            pytest.param("1P", id="instalment-1"),
            pytest.param("2P", id="instalment-2"),
            pytest.param("3P", id="instalment-3"),
            pytest.param("4P", id="instalment-4"),
            pytest.param("0A", id="annual"),
            pytest.param("01", id="month-01"),
            pytest.param("02", id="month-02"),
            pytest.param("03", id="month-03"),
            pytest.param("04", id="month-04"),
            pytest.param("05", id="month-05"),
            pytest.param("06", id="month-06"),
            pytest.param("07", id="month-07"),
            pytest.param("08", id="month-08"),
            pytest.param("09", id="month-09"),
            pytest.param("10", id="month-10"),
            pytest.param("11", id="month-11"),
            pytest.param("12", id="month-12"),
            pytest.param("EXT-1T", id="oss-quarter-1"),
            pytest.param("EXT-2T", id="oss-quarter-2"),
            pytest.param("EXT-3T", id="oss-quarter-3"),
            pytest.param("EXT-4T", id="oss-quarter-4"),
            pytest.param("AD-HOC", id="ad-hoc"),
            pytest.param("EVENT-1", id="event-1"),
            pytest.param("EVENT-42", id="event-42"),
            pytest.param("EVENT-9999", id="event-9999"),
        ),
    )
    def test_valid_tokens_accepted(self, code: str) -> None:
        assert _PERIOD_ADAPTER.validate_python(code) == code


class TestPeriodCodeRejects:
    """`PeriodCode` rejects malformed and unsupported period tokens."""

    @pytest.mark.parametrize(
        "raw",
        [
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
        ],
    )
    def test_invalid_inputs_rejected_through_adapter(self, raw: object) -> None:
        with pytest.raises(ValidationError):
            _PERIOD_ADAPTER.validate_python(raw)

    @pytest.mark.parametrize(
        "raw",
        (
            pytest.param("", id="blank"),
            pytest.param(1, id="non-string"),
        ),
    )
    def test_invalid_value_raises_registry_validation_error_at_validator(self, raw: object) -> None:
        with pytest.raises(RegistryValidationError):
            _validate_period_code(raw)


class TestCasillaDefinitionDataType:
    """`CasillaDefinition` accepts the new `period_code` data_type tag."""

    def test_period_code_data_type_round_trips_through_strict_validation(self) -> None:
        casilla = _casilla_with("period_code")
        round_tripped = CasillaDefinition.model_validate(casilla.model_dump())
        assert round_tripped.data_type == "period_code"
        assert round_tripped == casilla
