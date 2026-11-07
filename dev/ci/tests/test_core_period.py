"""Tests for period-code validation and typing."""

from __future__ import annotations

import calendar
from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from cadrumo.core import aggregation
from cadrumo.core import period as core_period
from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from cadrumo.core.period import (
    FilingPeriodCode,
    Period,
    PeriodError,
    PeriodKind,
    RegistryPeriodCode,
    StandardPeriodCode,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    open_ended_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


FILING_YEAR = filing_year_envelope().horizon
#: A leap year inside the support envelope, so the February span has its 29th day.
LEAP_YEAR = max(year for year in filing_year_envelope().years if calendar.isleap(year))
#: Combined calendar spellings of the filing year that ``Period`` refuses to split.
_COMBINED_CALENDAR_STRINGS = (
    f"{FILING_YEAR}Q1",
    f"{FILING_YEAR}-1T",
    f"{FILING_YEAR}",
    f"{FILING_YEAR}-03",
    f"{FILING_YEAR}A",
)

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
    assert PeriodKind is core_period.PeriodKind
    assert "PeriodKind" not in vars(aggregation)


class TestStandardPeriodCode:
    """Verify StandardPeriodCode enum covers expected members."""

    def test_canonical_member_values(self) -> None:
        """Every member's value, compared as one mapping rather than sampled.

        This replaces a loop over eleven of the twenty-one members followed by
        ``assert len(StandardPeriodCode) == 21``. The count made the case read
        as exhaustive while eight members -- APR through NOV -- had their value
        pinned by nothing in this file, so ``MAY = "5"`` passed. A whole-mapping
        comparison catches an added member, a removed one and a changed value
        in one assertion, and cannot drift back to a sample.

        The sibling case below does NOT cover this: ``_STANDARD_PERIOD_SET`` is
        built from this enum, so feeding ``code.value`` to the validator and
        asserting the same value returns is true whatever the value is.
        """
        assert {member.name: member.value for member in StandardPeriodCode} == {
            "Q1": "1T",
            "Q2": "2T",
            "Q3": "3T",
            "Q4": "4T",
            "P1": "1P",
            "P2": "2P",
            "P3": "3P",
            "P4": "4P",
            "ANNUAL": "0A",
            "JAN": "01",
            "FEB": "02",
            "MAR": "03",
            "APR": "04",
            "MAY": "05",
            "JUN": "06",
            "JUL": "07",
            "AUG": "08",
            "SEP": "09",
            "OCT": "10",
            "NOV": "11",
            "DEC": "12",
        }


class TestRegistryPeriodCodeValidator:
    """Verify RegistryPeriodCode validator accepts all valid forms."""

    def test_accepts_every_standard_period_code(self) -> None:
        """The validator admits the whole enum, not a subset of it.

        Deliberately narrow, and kept rather than deleted for that reason:
        ``_STANDARD_PERIOD_SET`` is derived from the enum, so this says
        nothing about whether any member's VALUE is correct -- the case
        above owns that. What it does catch is the set being narrowed to a
        hand-written subset, which no other case here would see.
        """
        for code in StandardPeriodCode:
            result = _validate_test_model(code.value)
            assert result == code.value

    def test_accepts_extended_normalized_period_codes(self) -> None:
        for raw, expected in (
            ("EXT-1T", "EXT-1T"),
            ("EXT-2T", "EXT-2T"),
            ("EXT-3T", "EXT-3T"),
            ("EXT-4T", "EXT-4T"),
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
            ("  1T  ", "1T"),
        ):
            assert _validate_test_model(raw) == expected, raw

    def test_rejects_invalid_period_codes(self) -> None:
        for bad in ("BOGUS", "EVENT-abc", "EXT-5T", "AD-HOC"):
            with pytest.raises(ValidationError):
                _validate_test_model(bad)

    def test_error_message_lists_accepted_set(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _validate_test_model("INVALID")
        error_str = str(exc_info.value).lower()
        assert "standardperiodcode" in error_str or "1t" in error_str
        # The EVENT-n family, named as the accepted set spells it. Accepting
        # bare "event" accepted the word wherever it fell -- and it is a
        # substring of "event-n", so the specific token was never required.
        assert "event-n" in error_str


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
                Period.from_year_and_code(FILING_YEAR, spelling)
            with pytest.raises(ValidationError):
                _validate_filing_test_model(spelling)

    def test_symbolic_event_selector_is_not_a_filing_period(self) -> None:
        with pytest.raises(PeriodError):
            Period.from_year_and_code(FILING_YEAR, SYMBOLIC_EVENT_SELECTOR)
        with pytest.raises(ValidationError):
            _validate_filing_test_model(SYMBOLIC_EVENT_SELECTOR)

    @pytest.mark.parametrize("token", ("EVENT-3", "EVENT-27", "EVENT-142"))
    def test_concrete_event_numbers_remain_filing_periods(self, token: str) -> None:
        """The positive control: narrowing must not have taken the event family with it."""
        assert Period.from_year_and_code(FILING_YEAR, token).registry_token == token

    def test_filing_refusal_names_the_accepted_filing_set(self) -> None:
        with pytest.raises(PeriodError) as exc_info:
            Period.from_year_and_code(FILING_YEAR, "ALTA")
        message = str(exc_info.value)
        assert "accepted forms" in message
        assert "EXT-1T" in message
        # The filing-scoped listing must not advertise the vocabulary it refuses.
        assert "Administrative" not in message

    @pytest.mark.parametrize("token", (*ADMINISTRATIVE_TOKENS, SYMBOLIC_EVENT_SELECTOR))
    def test_registry_coordinate_still_admits_the_administrative_vocabulary(self, token: str) -> None:
        """The other direction: the registry must keep loading."""
        from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef

        assert _validate_test_model(token) == token
        ref = RegistrySnapshotRef(
            modelo="036",
            revision_id=open_ended_revision("036").id,
            modelo_year=FILING_YEAR,
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
        from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

        selector = PeriodSelector(year_from=filing_year_envelope().floor, periods=declared)

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
            ("EVENT-3", PeriodKind.EXTENDED),
        ):
            period = Period.from_year_and_code(FILING_YEAR, code)
            assert period.filing_year == FILING_YEAR, code
            assert period.registry_token == code, code
            assert period.kind is kind, code

    def test_combined_calendar_strings_refuse(self) -> None:
        for combined in _COMBINED_CALENDAR_STRINGS:
            with pytest.raises(PeriodError):
                Period.from_year_and_code(FILING_YEAR, combined)

    def test_malformed_codes_refuse(self) -> None:
        for bad in ("13", "00", "5T", "0T", "5P", "not-a-period", ""):
            with pytest.raises(PeriodError):
                Period.from_year_and_code(FILING_YEAR, bad)

    def test_out_of_range_year_refuses(self) -> None:
        for year in (FOUR_DIGIT_YEAR_FIRST - 1, FOUR_DIGIT_YEAR_LAST + 1):
            with pytest.raises(PeriodError):
                Period.from_year_and_code(year, "1T")

    def test_lowercase_token_normalises(self) -> None:
        assert str(Period.from_year_and_code(FILING_YEAR, "ext-2t")) == f"{FILING_YEAR} EXT-2T"

    def test_from_string_round_trips_canonical_display_projection(self) -> None:
        period = Period.from_year_and_code(FILING_YEAR, "1T")

        assert Period.from_string(str(period)) == period

    def test_from_string_accepts_current_display_forms(self) -> None:
        for display, expected in (
            (f"{FILING_YEAR} 1T", Period.from_year_and_code(FILING_YEAR, "1T")),
            (f"{FILING_YEAR} 03", Period.from_year_and_code(FILING_YEAR, "03")),
            (f"{FILING_YEAR} 1P", Period.from_year_and_code(FILING_YEAR, "1P")),
            (f"{FILING_YEAR} EXT-1T", Period.from_year_and_code(FILING_YEAR, "EXT-1T")),
            (f"{FILING_YEAR} EVENT-1", Period.from_year_and_code(FILING_YEAR, "EVENT-1")),
        ):
            assert Period.from_string(display) == expected, display

    def test_from_string_refuses_combined_calendar_strings(self) -> None:
        for combined in _COMBINED_CALENDAR_STRINGS:
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
            pytest.param("EVENT-1", None, id="event-token-is-not-a-quarter"),
        ),
    )
    def test_typed_period_classification_and_quarter_projection(
        self,
        code: str,
        expected_quarter_ordinal: int | None,
    ) -> None:
        period = Period.from_year_and_code(FILING_YEAR, code)

        assert period.quarter_ordinal == expected_quarter_ordinal
        assert period.is_quarterly is (expected_quarter_ordinal is not None)

    def test_period_date_span(self) -> None:
        for year, code, expected_start, expected_end, inside, outside in (
            (
                FILING_YEAR,
                "1T",
                date(FILING_YEAR, 1, 1),
                date(FILING_YEAR, 3, 31),
                date(FILING_YEAR, 2, 15),
                date(FILING_YEAR, 4, 1),
            ),
            (FILING_YEAR, "0A", date(FILING_YEAR, 1, 1), date(FILING_YEAR, 12, 31), None, None),
            (LEAP_YEAR, "02", date(LEAP_YEAR, 2, 1), date(LEAP_YEAR, 2, 29), None, None),
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
        period = Period.from_year_and_code(FILING_YEAR, "1T")

        assert period.filing_year == FILING_YEAR
        assert not hasattr(period, "year")

    def test_standard_code_for_standard_token(self) -> None:
        assert Period.from_year_and_code(FILING_YEAR, "3T").standard_code is StandardPeriodCode.Q3

    def test_standard_code_none_for_extended(self) -> None:
        assert Period.from_year_and_code(FILING_YEAR, "EXT-1T").standard_code is None

    def test_non_span_periods_refuse_date_access(self) -> None:
        for code in ("1P", "EXT-1T", "EVENT-1"):
            period = Period.from_year_and_code(FILING_YEAR, code)
            assert period.has_date_span() is False, code
            with pytest.raises(PeriodError):
                _ = period.start_date
            with pytest.raises(PeriodError):
                _ = period.end_date


class TestPeriodValueSemantics:
    """Verify equality, hashing, string projection, and serialisation."""

    def test_equality_by_year_and_code(self) -> None:
        assert Period.from_year_and_code(FILING_YEAR, "1T") == Period.from_year_and_code(FILING_YEAR, "1T")
        assert Period.from_year_and_code(FILING_YEAR, "1T") != Period.from_year_and_code(FILING_YEAR, "2T")
        assert Period.from_year_and_code(FILING_YEAR, "1T") != Period.from_year_and_code(FILING_YEAR - 1, "1T")

    def test_hashable_as_dict_key_and_set_member(self) -> None:
        a = Period.from_year_and_code(FILING_YEAR, "1T")
        b = Period.from_year_and_code(FILING_YEAR, "1T")
        assert len({a, b}) == 1
        mapping = {a: "value"}
        assert mapping[b] == "value"

    def test_frozen(self) -> None:
        period = Period.from_year_and_code(FILING_YEAR, "1T")
        with pytest.raises(ValidationError):
            period.__setattr__("filing_year", FILING_YEAR - 1)

    def test_str_is_the_separated_form_not_combined(self) -> None:
        assert str(Period.from_year_and_code(FILING_YEAR, "1T")) == f"{FILING_YEAR} 1T"
        assert str(Period.from_year_and_code(FILING_YEAR, "0A")) == f"{FILING_YEAR} 0A"
        # The killed combined form must never be the display projection.
        assert "Q" not in str(Period.from_year_and_code(FILING_YEAR, "1T"))

    def test_repr_round_trips_through_constructor(self) -> None:
        period = Period.from_year_and_code(FILING_YEAR, "03")
        assert repr(period) == f"Period(filing_year={FILING_YEAR}, code='03')"

    def test_json_serialises_to_structured_pair_not_combined_string(self) -> None:
        period = Period.from_year_and_code(FILING_YEAR, "1T")
        assert period.model_dump() == {"filing_year": FILING_YEAR, "code": "1T"}
        assert period.model_dump_json() == f'{{"filing_year":{FILING_YEAR},"code":"1T"}}'

    def test_json_round_trip_equality(self) -> None:
        period = Period.from_year_and_code(FILING_YEAR, "2T")
        restored = Period.model_validate_json(period.model_dump_json())
        assert restored == period
