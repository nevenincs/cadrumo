"""Tests for period-code validation and typing."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from .._period import (
    Period,
    PeriodError,
    PeriodKind,
    RegistryPeriodCode,
    StandardPeriodCode,
    accepted_period_codes,
    accepted_period_patterns,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class TestStandardPeriodCode:
    """Verify StandardPeriodCode enum covers expected members."""

    def test_quarterly_codes(self) -> None:
        assert StandardPeriodCode.Q1 == "1T"
        assert StandardPeriodCode.Q2 == "2T"
        assert StandardPeriodCode.Q3 == "3T"
        assert StandardPeriodCode.Q4 == "4T"

    def test_instalment_codes(self) -> None:
        assert StandardPeriodCode.P1 == "1P"
        assert StandardPeriodCode.P2 == "2P"
        assert StandardPeriodCode.P3 == "3P"
        assert StandardPeriodCode.P4 == "4P"

    def test_annual_code(self) -> None:
        assert StandardPeriodCode.ANNUAL == "0A"

    def test_monthly_codes(self) -> None:
        assert StandardPeriodCode.JAN == "01"
        assert StandardPeriodCode.DEC == "12"

    def test_strenumed_members(self) -> None:
        assert len(StandardPeriodCode) == 21


class TestRegistryPeriodCodeValidator:
    """Verify RegistryPeriodCode validator accepts all valid forms."""

    def test_accepts_standard_period_codes(self) -> None:
        for code in StandardPeriodCode:
            result = _validate_test_model(code.value)
            assert result == code.value

    def test_accepts_extended_oss_codes(self) -> None:
        for code in ("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T"):
            result = _validate_test_model(code)
            assert result == code

    def test_accepts_ad_hoc_literal(self) -> None:
        result = _validate_test_model("AD-HOC")
        assert result == "AD-HOC"

    def test_accepts_event_period_patterns(self) -> None:
        for event_num in (1, 2, 27, 142):
            event_code = f"EVENT-{event_num}"
            result = _validate_test_model(event_code)
            assert result == event_code

    def test_normalizes_case(self) -> None:
        result = _validate_test_model("1t")
        assert result == "1T"

        result = _validate_test_model("ad-hoc")
        assert result == "AD-HOC"

    def test_strips_whitespace(self) -> None:
        result = _validate_test_model("  1T  ")
        assert result == "1T"

    def test_rejects_invalid_code(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _validate_test_model("BOGUS")
        assert "invalid period code" in str(exc_info.value).lower()

    def test_rejects_invalid_event_pattern(self) -> None:
        with pytest.raises(ValidationError):
            _validate_test_model("EVENT-abc")

    def test_rejects_invalid_extended_pattern(self) -> None:
        with pytest.raises(ValidationError):
            _validate_test_model("EXT-5T")

    def test_error_message_lists_accepted_set(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _validate_test_model("INVALID")
        error_str = str(exc_info.value).lower()
        assert "standardperiodcode" in error_str or "1t" in error_str
        assert "event-n" in error_str or "event" in error_str


class TestRegistryPeriodCodeAccessors:
    """Verify accessor functions for period-code discovery."""

    def test_accepted_period_codes_returns_tuple(self) -> None:
        codes = accepted_period_codes()
        assert isinstance(codes, tuple)

    def test_accepted_period_codes_includes_standard(self) -> None:
        codes = accepted_period_codes()
        assert "1T" in codes
        assert "0A" in codes
        assert "12" in codes

    def test_accepted_period_codes_includes_extended(self) -> None:
        codes = accepted_period_codes()
        assert "EXT-1T" in codes
        assert "EXT-4T" in codes

    def test_accepted_period_codes_includes_ad_hoc(self) -> None:
        codes = accepted_period_codes()
        assert "AD-HOC" in codes

    def test_accepted_period_patterns_returns_tuple(self) -> None:
        patterns = accepted_period_patterns()
        assert isinstance(patterns, tuple)
        assert len(patterns) >= 3

    def test_accepted_period_patterns_describes_event_regex(self) -> None:
        patterns = accepted_period_patterns()
        pattern_str = " ".join(patterns).lower()
        assert "event" in pattern_str
        assert "integer" in pattern_str


class TestRegistryPeriodCodeRoundtrip:
    """Verify RegistryPeriodCode persists through JSON roundtrip."""

    def test_json_roundtrip_standard_period(self) -> None:
        class Envelope(BaseModel):
            period: RegistryPeriodCode

        original = Envelope(period="1T")
        json_str = original.model_dump_json()
        restored = Envelope.model_validate_json(json_str)
        assert restored.period == "1T"
        assert restored == original

    def test_json_roundtrip_extended_period(self) -> None:
        class Envelope(BaseModel):
            period: RegistryPeriodCode

        original = Envelope(period="EXT-1T")
        json_str = original.model_dump_json()
        restored = Envelope.model_validate_json(json_str)
        assert restored.period == "EXT-1T"
        assert restored == original

    def test_json_roundtrip_event_period(self) -> None:
        class Envelope(BaseModel):
            period: RegistryPeriodCode

        original = Envelope(period="EVENT-27")
        json_str = original.model_dump_json()
        restored = Envelope.model_validate_json(json_str)
        assert restored.period == "EVENT-27"
        assert restored == original

    def test_roundtrip_rejects_invalid_after_deserialise(self) -> None:
        class Envelope(BaseModel):
            period: RegistryPeriodCode

        original = Envelope(period="1T")
        json_str = original.model_dump_json()
        tampered = json_str.replace('"1T"', '"INVALID"')
        with pytest.raises(ValidationError):
            Envelope.model_validate_json(tampered)


class TestRegistryPeriodCodeAntiTautology:
    """Prevent tautological testing by mutating fixtures and asserting rejection."""

    def test_mutation_of_fixture_refuses_invalid_period(self) -> None:
        class CalculationRevision(BaseModel):
            period: RegistryPeriodCode

        fixture = CalculationRevision(period="1T")
        assert fixture.period == "1T"

        mutated_json = fixture.model_dump_json().replace('"1T"', '"MUTATED"')
        with pytest.raises(ValidationError) as exc_info:
            CalculationRevision.model_validate_json(mutated_json)

        assert "invalid period code" in str(exc_info.value).lower()


def _validate_test_model(period: str) -> str:
    """Helper to validate a period code through pydantic."""

    class TestModel(BaseModel):
        period: RegistryPeriodCode

    model = TestModel(period=period)
    return model.period


class TestPeriodConstruction:
    """Verify Period construction, refusal, and token coverage."""

    @pytest.mark.parametrize(
        ("code", "kind"),
        [
            ("1T", PeriodKind.QUARTERLY),
            ("4T", PeriodKind.QUARTERLY),
            ("0A", PeriodKind.ANNUAL),
            ("01", PeriodKind.MONTHLY),
            ("12", PeriodKind.MONTHLY),
            ("1P", PeriodKind.INSTALMENT),
            ("4P", PeriodKind.INSTALMENT),
            ("EXT-1T", PeriodKind.EXTENDED),
            ("AD-HOC", PeriodKind.EXTENDED),
            ("EVENT-3", PeriodKind.EXTENDED),
        ],
    )
    def test_from_year_and_code_covers_every_token_kind(self, code: str, kind: PeriodKind) -> None:
        period = Period.from_year_and_code(2026, code)
        assert period.filing_year == 2026
        assert period.registry_token == code
        assert period.kind is kind

    @pytest.mark.parametrize("combined", ["2026Q1", "2026-1T", "2026", "2026-03", "2026A"])
    def test_combined_calendar_strings_refuse(self, combined: str) -> None:
        with pytest.raises(PeriodError):
            Period.from_year_and_code(2026, combined)

    @pytest.mark.parametrize("bad", ["13", "00", "5T", "0T", "5P", "not-a-period", ""])
    def test_malformed_codes_refuse(self, bad: str) -> None:
        with pytest.raises(PeriodError):
            Period.from_year_and_code(2026, bad)

    @pytest.mark.parametrize("year", [1979, 2201])
    def test_out_of_range_year_refuses(self, year: int) -> None:
        with pytest.raises(PeriodError):
            Period.from_year_and_code(year, "1T")

    def test_lowercase_token_normalises(self) -> None:
        assert str(Period.from_year_and_code(2026, "ext-2t")) == "2026 EXT-2T"


class TestPeriodAccessors:
    """Verify the read-only accessors and the date-span semantics."""

    def test_quarterly_span(self) -> None:
        period = Period.from_year_and_code(2026, "1T")
        assert period.has_date_span() is True
        assert period.start_date == date(2026, 1, 1)
        assert period.end_date == date(2026, 3, 31)
        assert period.contains(date(2026, 2, 15)) is True
        assert period.contains(date(2026, 4, 1)) is False

    def test_annual_span(self) -> None:
        period = Period.from_year_and_code(2026, "0A")
        assert period.start_date == date(2026, 1, 1)
        assert period.end_date == date(2026, 12, 31)

    def test_monthly_span_february_leap_year(self) -> None:
        period = Period.from_year_and_code(2024, "02")
        assert period.start_date == date(2024, 2, 1)
        assert period.end_date == date(2024, 2, 29)

    def test_year_alias(self) -> None:
        assert Period.from_year_and_code(2026, "1T").year == 2026

    def test_standard_code_for_standard_token(self) -> None:
        assert Period.from_year_and_code(2026, "3T").standard_code is StandardPeriodCode.Q3

    def test_standard_code_none_for_extended(self) -> None:
        assert Period.from_year_and_code(2026, "EXT-1T").standard_code is None

    @pytest.mark.parametrize("code", ["1P", "EXT-1T", "AD-HOC", "EVENT-1"])
    def test_non_span_periods_refuse_date_access(self, code: str) -> None:
        period = Period.from_year_and_code(2026, code)
        assert period.has_date_span() is False
        with pytest.raises(PeriodError):
            _ = period.start_date
        with pytest.raises(PeriodError):
            _ = period.end_date


class TestPeriodValueSemantics:
    """Verify equality, hashing, string projection, and serialisation."""

    def test_equality_by_year_and_code(self) -> None:
        assert Period.from_year_and_code(2026, "1T") == Period.from_year_and_code(2026, "1T")
        assert Period.from_year_and_code(2026, "1T") != Period.from_year_and_code(2026, "2T")
        assert Period.from_year_and_code(2026, "1T") != Period.from_year_and_code(2025, "1T")

    def test_hashable_as_dict_key_and_set_member(self) -> None:
        a = Period.from_year_and_code(2026, "1T")
        b = Period.from_year_and_code(2026, "1T")
        assert len({a, b}) == 1
        mapping = {a: "value"}
        assert mapping[b] == "value"

    def test_frozen(self) -> None:
        period = Period.from_year_and_code(2026, "1T")
        with pytest.raises(ValidationError):
            period.filing_year = 2025  # type: ignore[misc]

    def test_str_is_the_separated_form_not_combined(self) -> None:
        assert str(Period.from_year_and_code(2026, "1T")) == "2026 1T"
        assert str(Period.from_year_and_code(2026, "0A")) == "2026 0A"
        # The killed combined form must never be the display projection.
        assert "Q" not in str(Period.from_year_and_code(2026, "1T"))

    def test_repr_round_trips_through_constructor(self) -> None:
        period = Period.from_year_and_code(2026, "03")
        assert repr(period) == "Period(filing_year=2026, code='03')"

    def test_json_serialises_to_structured_pair_not_combined_string(self) -> None:
        period = Period.from_year_and_code(2026, "1T")
        assert period.model_dump() == {"filing_year": 2026, "code": "1T"}
        assert period.model_dump_json() == '{"filing_year":2026,"code":"1T"}'

    def test_json_round_trip_equality(self) -> None:
        period = Period.from_year_and_code(2026, "2T")
        restored = Period.model_validate_json(period.model_dump_json())
        assert restored == period
