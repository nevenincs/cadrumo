"""Tests for period-code validation and typing."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from .. import aggregation, period as _period
from ..period import (
    FilingPeriodCode,
    Period,
    PeriodError,
    PeriodKind,
    RegistryPeriodCode,
    StandardPeriodCode,
    accepted_filing_period_codes,
    accepted_filing_period_patterns,
    accepted_period_codes,
)
from ..period import accepted_period_patterns

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


#: The tokens a registry ``period_selector`` declares to address a censo or
#: comunicación revision (Modelo 036 declares the first three, Modelo 145 the
#: last two). They name a registration event, never a period a taxpayer files in.
ADMINISTRATIVE_TOKENS = ("ALTA", "MODIFICACION", "BAJA", "COMUNICACION", "VARIACION")

#: The symbolic token Modelo 210's 2025 ``period_selector`` declares. The
#: registry's revision matcher treats it as COVERING the concrete ``EVENT-1`` /
#: ``EVENT-2`` operator scopes, so it stands for a set of periods, not one.
SYMBOLIC_EVENT_SELECTOR = "EVENT-N"


def test_period_kind_has_one_core_definition_without_aggregation_shadow() -> None:
    """The public classifier is the core-period type, never an aggregation subset."""
    assert PeriodKind is _period.PeriodKind
    assert "PeriodKind" not in vars(aggregation)


class TestStandardPeriodCode:
    """Verify StandardPeriodCode enum covers expected members."""

    def test_canonical_member_values(self) -> None:
        expected_values = {
            StandardPeriodCode.Q1: "1T",
            StandardPeriodCode.Q2: "2T",
            StandardPeriodCode.Q3: "3T",
            StandardPeriodCode.Q4: "4T",
            StandardPeriodCode.P1: "1P",
            StandardPeriodCode.P2: "2P",
            StandardPeriodCode.P3: "3P",
            StandardPeriodCode.P4: "4P",
            StandardPeriodCode.ANNUAL: "0A",
            StandardPeriodCode.JAN: "01",
            StandardPeriodCode.DEC: "12",
        }
        for member, expected in expected_values.items():
            assert member == expected
        assert len(StandardPeriodCode) == 21


class TestRegistryPeriodCodeValidator:
    """Verify RegistryPeriodCode validator accepts all valid forms."""

    def test_accepts_every_standard_period_code(self) -> None:
        for code in StandardPeriodCode:
            result = _validate_test_model(code.value)
            assert result == code.value

    def test_accepts_extended_normalized_period_codes(self) -> None:
        for raw, expected in (
            ("EXT-1T", "EXT-1T"),
            ("EXT-2T", "EXT-2T"),
            ("EXT-3T", "EXT-3T"),
            ("EXT-4T", "EXT-4T"),
            ("AD-HOC", "AD-HOC"),
            ("alta", "ALTA"),
            ("modificacion", "MODIFICACION"),
            ("baja", "BAJA"),
            ("comunicacion", "COMUNICACION"),
            ("variacion", "VARIACION"),
            ("EVENT-N", "EVENT-N"),
            ("EVENT-1", "EVENT-1"),
            ("EVENT-2", "EVENT-2"),
            ("EVENT-27", "EVENT-27"),
            ("EVENT-142", "EVENT-142"),
            ("1t", "1T"),
            ("ad-hoc", "AD-HOC"),
            ("  1T  ", "1T"),
        ):
            assert _validate_test_model(raw) == expected, raw

    def test_rejects_invalid_period_codes(self) -> None:
        for bad in ("BOGUS", "EVENT-abc", "EXT-5T"):
            with pytest.raises(ValidationError):
                _validate_test_model(bad)

    def test_error_message_lists_accepted_set(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _validate_test_model("INVALID")
        error_str = str(exc_info.value).lower()
        assert "standardperiodcode" in error_str or "1t" in error_str
        assert "event-n" in error_str or "event" in error_str


class TestRegistryPeriodCodeAccessors:
    """Verify accessor functions for period-code discovery."""

    def test_accepted_period_codes_surface_expected_families(self) -> None:
        codes = accepted_period_codes()
        assert isinstance(codes, tuple)
        for expected in (
            "1T",
            "0A",
            "12",
            "EXT-1T",
            "EXT-4T",
            "AD-HOC",
            "ALTA",
            "MODIFICACION",
            "BAJA",
            "COMUNICACION",
            "VARIACION",
        ):
            assert expected in codes

    def test_accepted_period_patterns_describe_event_regex(self) -> None:
        patterns = accepted_period_patterns()
        assert isinstance(patterns, tuple)
        assert len(patterns) >= 3
        pattern_str = " ".join(patterns).lower()
        assert "event" in pattern_str
        assert "integer" in pattern_str

    def test_registry_patterns_report_every_administrative_token(self) -> None:
        """The pattern listing and the code listing describe the same set."""
        pattern_str = " ".join(accepted_period_patterns())
        for token in ADMINISTRATIVE_TOKENS:
            assert token in pattern_str, token
            assert token in accepted_period_codes(), token

    def test_filing_accessors_exclude_the_administrative_vocabulary(self) -> None:
        codes = accepted_filing_period_codes()
        patterns = " ".join(accepted_filing_period_patterns())
        for token in ADMINISTRATIVE_TOKENS:
            assert token not in codes, token
            assert token not in patterns, token
        for expected in ("1T", "0A", "12", "EXT-1T", "AD-HOC"):
            assert expected in codes, expected
        assert set(codes) < set(accepted_period_codes())


class TestRegistryPeriodCodeRoundtrip:
    """Verify RegistryPeriodCode persists through JSON roundtrip."""

    def test_json_roundtrip_period(self) -> None:
        class Envelope(BaseModel):
            period: RegistryPeriodCode

        for period in ("1T", "EXT-1T", "EVENT-27"):
            original = Envelope(period=period)
            json_str = original.model_dump_json()
            restored = Envelope.model_validate_json(json_str)
            assert restored.period == period, period
            assert restored == original, period

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


def _validate_filing_test_model(period: str) -> str:
    """Helper to validate a period code through the narrow filing annotation."""

    class TestModel(BaseModel):
        period: FilingPeriodCode

    model = TestModel(period=period)
    return model.period


class TestPeriodTypeBoundarySplit:
    """Pin BOTH halves of the registry/filing period-vocabulary split, adjacently.

    The registry coordinate and the typed filing period have genuinely different
    value spaces, and for a while one validator served both. Widening it so the
    registry could address a Modelo 036 censo revision silently widened
    :class:`Period`, so ``--period alta`` built a filing period out of a
    registration event and the instructive parse-boundary refusal that named the
    modelo's declared tokens was replaced by a late generic error.

    A test pinning only the refusal direction would let the next well-intentioned
    widening re-merge the validators to fix a registry-load failure; a test
    pinning only the registry direction is what existed when this arrived. Both
    directions belong here, together, so the trade-off is visible at the point
    where either one would be changed.
    """

    @pytest.mark.parametrize("token", ADMINISTRATIVE_TOKENS)
    def test_administrative_tokens_are_not_filing_periods(self, token: str) -> None:
        for spelling in (token, token.lower()):
            with pytest.raises(PeriodError):
                Period.from_year_and_code(2025, spelling)
            with pytest.raises(ValidationError):
                _validate_filing_test_model(spelling)

    def test_symbolic_event_selector_is_not_a_filing_period(self) -> None:
        with pytest.raises(PeriodError):
            Period.from_year_and_code(2025, SYMBOLIC_EVENT_SELECTOR)
        with pytest.raises(ValidationError):
            _validate_filing_test_model(SYMBOLIC_EVENT_SELECTOR)

    @pytest.mark.parametrize("token", ("EVENT-3", "EVENT-27", "EVENT-142"))
    def test_concrete_event_numbers_remain_filing_periods(self, token: str) -> None:
        """The positive control: narrowing must not have taken the event family with it."""
        assert Period.from_year_and_code(2025, token).registry_token == token

    def test_filing_refusal_names_the_accepted_filing_set(self) -> None:
        with pytest.raises(PeriodError) as exc_info:
            Period.from_year_and_code(2025, "ALTA")
        message = str(exc_info.value)
        assert "accepted forms" in message
        assert "AD-HOC" in message
        # The filing-scoped listing must not advertise the vocabulary it refuses.
        assert "Administrative" not in message

    @pytest.mark.parametrize("token", (*ADMINISTRATIVE_TOKENS, SYMBOLIC_EVENT_SELECTOR))
    def test_registry_coordinate_still_admits_the_administrative_vocabulary(self, token: str) -> None:
        """The other direction: the registry must keep loading."""
        from ...domain.calculations.registry.schema_references import RegistrySnapshotRef

        assert _validate_test_model(token) == token
        ref = RegistrySnapshotRef(
            modelo="036",
            revision_id="2025-02-03-y-siguientes",
            modelo_year=2025,
            period=token,
        )
        assert ref.period == token

    @pytest.mark.parametrize(
        "declared",
        (
            pytest.param(("alta", "modificacion", "baja"), id="modelo-036-censo-events"),
            pytest.param(("comunicacion", "variacion"), id="modelo-145-comunicacion-events"),
            pytest.param(("EVENT-N", "0A"), id="modelo-210-event-placeholder-plus-annual"),
        ),
    )
    def test_declared_period_selectors_still_validate(self, declared: tuple[str, ...]) -> None:
        """The shipped declarations that made the widening necessary in the first place."""
        from ...domain.calculations.registry.schema_references import PeriodSelector

        selector = PeriodSelector(year_from=2012, periods=declared)

        assert selector.periods == declared


class TestPeriodConstruction:
    """Verify Period construction, refusal, and token coverage."""

    def test_from_year_and_code_covers_every_token_kind(self) -> None:
        for code, kind in (
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
        ):
            period = Period.from_year_and_code(2026, code)
            assert period.filing_year == 2026, code
            assert period.registry_token == code, code
            assert period.kind is kind, code

    def test_combined_calendar_strings_refuse(self) -> None:
        for combined in ("2026Q1", "2026-1T", "2026", "2026-03", "2026A"):
            with pytest.raises(PeriodError):
                Period.from_year_and_code(2026, combined)

    def test_malformed_codes_refuse(self) -> None:
        for bad in ("13", "00", "5T", "0T", "5P", "not-a-period", ""):
            with pytest.raises(PeriodError):
                Period.from_year_and_code(2026, bad)

    def test_out_of_range_year_refuses(self) -> None:
        for year in (1979, 2201):
            with pytest.raises(PeriodError):
                Period.from_year_and_code(year, "1T")

    def test_lowercase_token_normalises(self) -> None:
        assert str(Period.from_year_and_code(2026, "ext-2t")) == "2026 EXT-2T"

    def test_from_string_round_trips_canonical_display_projection(self) -> None:
        period = Period.from_year_and_code(2026, "1T")

        assert Period.from_string(str(period)) == period

    def test_from_string_accepts_current_display_forms(self) -> None:
        for display, expected in (
            ("2026 1T", Period.from_year_and_code(2026, "1T")),
            ("2026 03", Period.from_year_and_code(2026, "03")),
            ("2026 1P", Period.from_year_and_code(2026, "1P")),
            ("2026 EXT-1T", Period.from_year_and_code(2026, "EXT-1T")),
            ("2026 AD-HOC", Period.from_year_and_code(2026, "AD-HOC")),
            ("2026 EVENT-1", Period.from_year_and_code(2026, "EVENT-1")),
        ):
            assert Period.from_string(display) == expected, display

    def test_from_string_refuses_combined_calendar_strings(self) -> None:
        for combined in ("2026Q1", "2026-1T", "2026", "2026-03", "2026A"):
            with pytest.raises(PeriodError, match="expected 'YYYY <period-code>'"):
                Period.from_string(combined)


class TestPeriodAccessors:
    """Verify the read-only accessors and the date-span semantics."""

    @pytest.mark.parametrize(
        ("code", "expected_quarter_ordinal"),
        (
            pytest.param("1T", 1, id="first-standard-quarter"),
            pytest.param("4T", 4, id="fourth-standard-quarter"),
            pytest.param("0A", None, id="annual-period-is-not-a-quarter"),
            pytest.param("03", None, id="monthly-period-is-not-a-quarter"),
            pytest.param("1P", None, id="first-instalment-is-not-a-quarter"),
            pytest.param("3P", None, id="third-instalment-is-not-a-quarter"),
            pytest.param("4P", None, id="fourth-instalment-is-not-a-quarter"),
            pytest.param("EXT-1T", None, id="extended-token-is-not-a-quarter"),
            pytest.param("AD-HOC", None, id="ad-hoc-token-is-not-a-quarter"),
            pytest.param("EVENT-1", None, id="event-token-is-not-a-quarter"),
        ),
    )
    def test_typed_period_classification_and_quarter_projection(
        self,
        code: str,
        expected_quarter_ordinal: int | None,
    ) -> None:
        period = Period.from_year_and_code(2026, code)

        assert period.quarter_ordinal == expected_quarter_ordinal
        assert period.is_quarterly is (expected_quarter_ordinal is not None)

    def test_period_date_span(self) -> None:
        for year, code, expected_start, expected_end, inside, outside in (
            (2026, "1T", date(2026, 1, 1), date(2026, 3, 31), date(2026, 2, 15), date(2026, 4, 1)),
            (2026, "0A", date(2026, 1, 1), date(2026, 12, 31), None, None),
            (2024, "02", date(2024, 2, 1), date(2024, 2, 29), None, None),
        ):
            period = Period.from_year_and_code(year, code)
            assert period.has_date_span() is True, code
            assert period.start_date == expected_start, code
            assert period.end_date == expected_end, code
            if inside is not None:
                assert period.contains(inside) is True, code
            if outside is not None:
                assert period.contains(outside) is False, code

    def test_filing_year_is_the_only_year_field(self) -> None:
        period = Period.from_year_and_code(2026, "1T")

        assert period.filing_year == 2026
        assert not hasattr(period, "year")

    def test_standard_code_for_standard_token(self) -> None:
        assert Period.from_year_and_code(2026, "3T").standard_code is StandardPeriodCode.Q3

    def test_standard_code_none_for_extended(self) -> None:
        assert Period.from_year_and_code(2026, "EXT-1T").standard_code is None

    def test_non_span_periods_refuse_date_access(self) -> None:
        for code in ("1P", "EXT-1T", "AD-HOC", "EVENT-1"):
            period = Period.from_year_and_code(2026, code)
            assert period.has_date_span() is False, code
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
            period.__setattr__("filing_year", 2025)

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
