"""The Art. 81.1 worked-months grammar: months in, canonical months out.

The set exists because Art. 81.2 prorates by an INTERSECTION of two month sets,
which a count cannot express. These tests cover the grammar itself; the
intersection it feeds is covered where the increment is computed.
"""

from __future__ import annotations

import pytest

from ....core.errors.hierarchy import ProfileAnswerTypeError
from ..meses_trabajo import parse_meses_trabajo, serialise_meses_trabajo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class TestAcceptedForms:
    def test_a_range_expands_inclusively(self) -> None:
        """The manual's own case: a mother entitled May to August."""
        assert parse_meses_trabajo("5-8", field="f") == (5, 6, 7, 8)

    def test_separate_months_are_read_in_order(self) -> None:
        assert parse_meses_trabajo("1;2;11;12", field="f") == (1, 2, 11, 12)

    def test_ranges_and_singles_mix(self) -> None:
        assert parse_meses_trabajo("1;3-5;12", field="f") == (1, 3, 4, 5, 12)

    def test_input_order_does_not_survive(self) -> None:
        """Ascending is canonical, so two orderings of one set store identically."""
        assert parse_meses_trabajo("12;3;7", field="f") == parse_meses_trabajo("3;7;12", field="f")

    def test_blank_means_no_months_declared(self) -> None:
        """Distinct from a declared set that happens to be empty of qualifying months."""
        assert parse_meses_trabajo("", field="f") == ()
        assert parse_meses_trabajo("   ", field="f") == ()

    def test_surrounding_whitespace_is_tolerated(self) -> None:
        assert parse_meses_trabajo(" 5 ; 6 ", field="f") == (5, 6)


class TestRefusals:
    """Every malformed input refuses; none is silently dropped."""

    @pytest.mark.parametrize(
        ("raw", "reason"),
        [
            ("13", "outside"),
            ("0", "outside"),
            ("8-5", "back to month"),
            ("x", "not a number"),
            ("5;5", "more than once"),
            ("3-5;4", "more than once"),
            ("5;;6", "empty entry"),
            ("1_0", "not a number"),
            ("²", "not a number"),
        ],
    )
    def test_malformed_input_refuses(self, raw: str, reason: str) -> None:
        """A dropped month would silently change the proration basis."""
        with pytest.raises(ProfileAnswerTypeError, match=reason):
            parse_meses_trabajo(raw, field="f")

    def test_the_refusal_names_the_field_and_the_accepted_form(self) -> None:
        """The operator is told which door the bad value came through, and what to write."""
        with pytest.raises(ProfileAnswerTypeError, match=r"descendiente\.0\.meses_madre_trabajo") as caught:
            parse_meses_trabajo("nope", field="descendiente.0.meses_madre_trabajo")

        assert "MM or MM-MM" in str(caught.value)


class TestSerialisationIsCanonical:
    def test_ranges_are_never_emitted(self) -> None:
        assert serialise_meses_trabajo((5, 6, 7, 8)) == "05;06;07;08"

    def test_emission_is_month_sorted_and_zero_padded(self) -> None:
        assert serialise_meses_trabajo((12, 1, 3)) == "01;03;12"

    def test_an_empty_set_serialises_to_the_empty_string(self) -> None:
        assert serialise_meses_trabajo(()) == ""

    @pytest.mark.parametrize("raw", ["5-8", "1;2;11;12", "1;3-5;12", "12;3;7", ""])
    def test_parse_then_serialise_then_parse_is_stable(self, raw: str) -> None:
        """Whichever form was typed, the stored fact has exactly one representation."""
        once = parse_meses_trabajo(raw, field="f")
        rendered = serialise_meses_trabajo(once)

        assert parse_meses_trabajo(rendered, field="f") == once
        assert serialise_meses_trabajo(parse_meses_trabajo(rendered, field="f")) == rendered
