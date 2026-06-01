"""Tests for period-code validation and typing."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from aeat.core._period import (
    RegistryPeriodCode,
    StandardPeriodCode,
    accepted_period_codes,
    accepted_period_patterns,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


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
