"""The month-level guardería entry surface: one grammar, one stored shape.

The domain half of Art. 81.2 month-level spend landed first and deliberately
alone: nothing could WRITE the field, so no profile changed behaviour. These
tests cover the half that makes it writable — the shared grammar, the
``--descendiente`` flag key, and the ``renta_family.descendiente.{n}.*`` fact
round-trip — and they exist because a half-landed entry surface is worse than
the gap it closes. An operator who can store a value that reaches nothing has
been given work to do and nothing for it.

Assertions are structural throughout: which shapes the grammar admits, which it
refuses, and whether a stored map reloads identical. No euro figure here is an
expected TAX outcome, so nothing re-derives a registry formula against itself.
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from ....core.errors import ProfileAnswerTypeError
from ..descendant import DescendantInfo
from ..descendant_facts import (
    descendant_facts_from_list,
    descendant_list_from_facts,
    parse_descendiente_flag,
)
from ..family_types import GuarderiaMonthSpend
from ..guarderia_mensual import parse_guarderia_mensual, serialise_guarderia_mensual

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FIELD = "probe"


def _months(raw: str) -> tuple[tuple[int, int], ...]:
    """The parsed map as plain (month, amount) pairs, for readable assertions."""
    return tuple((entry.month, entry.amount_euros) for entry in parse_guarderia_mensual(raw, field=_FIELD))


class TestGrammar:
    """What the one shared grammar admits."""

    def test_a_bare_month_binds_its_amount(self) -> None:
        assert _months("9:210") == ((9, 210),)

    def test_entries_separate_on_semicolon_not_comma(self) -> None:
        """``,`` already separates the flag's own keys, so the map cannot use it.

        This is not a style choice: a comma here would end the ``--descendiente``
        value mid-map and the remainder would be read as further flag keys, so
        the separator is load-bearing on the door the map most has to survive.
        """
        assert _months("1:180;2:180") == ((1, 180), (2, 180))
        with pytest.raises(ProfileAnswerTypeError):
            parse_guarderia_mensual("1:180,2:180", field=_FIELD)

    def test_a_range_expands_to_every_month_it_names(self) -> None:
        """The shape a taxpayer reads off a certificate: one fee, one span."""
        assert _months("9-12:210") == ((9, 210), (10, 210), (11, 210), (12, 210))

    def test_a_map_sorts_by_month_however_it_was_typed(self) -> None:
        assert _months("12:100;3:100;7:100") == ((3, 100), (7, 100), (12, 100))

    def test_a_blank_map_is_undeclared_not_zero(self) -> None:
        """Absent and "declared as nothing" are different answers.

        An empty tuple means no monthly breakdown was given, which in the
        turning-three period leaves the annual figure unusable rather than
        asserting the child had no childcare.
        """
        assert parse_guarderia_mensual("", field=_FIELD) == ()
        assert parse_guarderia_mensual("   ", field=_FIELD) == ()

    def test_a_zero_month_is_a_real_declaration(self) -> None:
        """Distinct from the month being absent: this states the fee was nil."""
        assert _months("8:0") == ((8, 0),)

    @pytest.mark.parametrize(
        ("raw", "reason"),
        [
            ("0:100", "month below January"),
            ("13:100", "month above December"),
            ("9-13:100", "range end above December"),
            ("12-9:100", "range running backwards"),
            ("x:100", "month that is not a number"),
            ("9", "entry with no amount"),
            ("9:", "entry with an empty amount"),
            ("9:-100", "negative amount"),
            ("9:10.50", "fractional amount"),
            ("9:1e3", "exponent notation"),
            ("9:100;9:200", "the same month twice"),
            ("9-11:100;10:200", "a month covered by a range and again alone"),
            ("9:100;;10:200", "a doubled separator"),
            # The isdigit-is-not-int family. Every one of these satisfied the
            # original gate and then raised a bare ValueError from int, which is
            # untranslated, names neither field nor accepted form, and escapes
            # the wizard's answer validator because that catches only the typed
            # refusal. The superscript is the reachable one: an operator pastes a
            # footnote marker out of a formatted certificate.
            ("9:²", "a superscript amount, which isdigit accepts and int does not"),
            ("²:100", "a superscript month"),
            ("9:1_0", "an amount using int's own underscore tolerance"),
            ("٩:100", "a non-ASCII digit month"),
            ("9:٩", "a non-ASCII digit amount"),
        ],
    )
    def test_a_malformed_map_refuses_rather_than_dropping_the_entry(self, raw: str, reason: str) -> None:
        """Every bad shape refuses; none is silently skipped.

        Dropping the offending entry would under-grant, which is the safe
        direction on amount — but silently. The whole purpose of this map is to
        carry months a taxpayer can evidence from a certificate they hold, so a
        month that vanished between typing and storage is exactly what nobody
        would catch.
        """
        with pytest.raises(ProfileAnswerTypeError):
            parse_guarderia_mensual(raw, field=_FIELD)

    def test_the_refusal_names_the_field_it_was_given(self) -> None:
        """The operator is told which descendant and which door, not just "invalid"."""
        with pytest.raises(ProfileAnswerTypeError, match=re.escape("renta_family.descendiente.3")):
            parse_guarderia_mensual("13:100", field="renta_family.descendiente.3.gastos_guarderia_mensuales")


class TestCanonicalSerialisation:
    """One stored representation, whichever form was typed."""

    def test_a_range_and_its_months_serialise_identically(self) -> None:
        """The stored bytes cannot record HOW the operator typed the map.

        If they could, the same map entered two ways would produce two stored
        values, and a resume walk seeding one of them back would no longer match
        the leg that saved it.
        """
        assert serialise_guarderia_mensual(parse_guarderia_mensual("9-11:210", field=_FIELD)) == (
            serialise_guarderia_mensual(parse_guarderia_mensual("11:210;9:210;10:210", field=_FIELD))
        )

    def test_the_canonical_form_reparses_to_itself(self) -> None:
        canonical = serialise_guarderia_mensual(parse_guarderia_mensual("9-12:210;1:180", field=_FIELD))
        assert canonical == "01:180;09:210;10:210;11:210;12:210"
        assert parse_guarderia_mensual(canonical, field=_FIELD) == parse_guarderia_mensual(
            "9-12:210;1:180",
            field=_FIELD,
        )

    def test_an_empty_map_serialises_to_nothing_at_all(self) -> None:
        """So the fact emitter can drop it, like every other absent optional."""
        assert serialise_guarderia_mensual(()) == ""


class TestFlagDoor:
    """The ``--descendiente GASTOS_GUARDERIA_MENSUAL=`` key."""

    def test_the_flag_carries_the_map_onto_the_record(self) -> None:
        parsed = parse_descendiente_flag("NACIMIENTO=2021-04-15,GASTOS_GUARDERIA_MENSUAL=9-12:210;1:180")
        assert parsed.gastos_guarderia_mensuales == (
            GuarderiaMonthSpend(month=1, amount_euros=180),
            GuarderiaMonthSpend(month=9, amount_euros=210),
            GuarderiaMonthSpend(month=10, amount_euros=210),
            GuarderiaMonthSpend(month=11, amount_euros=210),
            GuarderiaMonthSpend(month=12, amount_euros=210),
        )

    def test_declaring_both_spend_shapes_refuses_at_the_flag_door(self) -> None:
        """And refuses as the flag door's own error, not the record's.

        The record refuses too, but through pydantic — which this verb's handler
        does not translate, so the operator would meet a raw traceback instead of
        a sentence naming the two keys and which one to drop.
        """
        with pytest.raises(ProfileAnswerTypeError, match="GASTOS_GUARDERIA_MENSUAL"):
            parse_descendiente_flag(
                "NACIMIENTO=2021-04-15,GASTOS_GUARDERIA=900,GASTOS_GUARDERIA_MENSUAL=1:100",
            )

    def test_a_zero_annual_figure_does_not_collide_with_a_map(self) -> None:
        """Zero states no annual spend, so it contradicts nothing."""
        parsed = parse_descendiente_flag(
            "NACIMIENTO=2021-04-15,GASTOS_GUARDERIA=0,GASTOS_GUARDERIA_MENSUAL=1:100",
        )
        assert parsed.gastos_guarderia_euros == 0
        assert parsed.gastos_guarderia_mensuales == (GuarderiaMonthSpend(month=1, amount_euros=100),)

    def test_an_unknown_neighbouring_key_is_still_refused(self) -> None:
        """The new key must not have widened the accepted set by accident."""
        with pytest.raises(ProfileAnswerTypeError, match="GASTOS_GUARDERIA_MENSUALES"):
            parse_descendiente_flag("NACIMIENTO=2021-04-15,GASTOS_GUARDERIA_MENSUALES=1:100")


class TestFactRoundTrip:
    """The ``renta_family.descendiente.{n}.*`` persistence boundary."""

    def _child(
        self,
        *,
        gastos_guarderia_euros: int = 0,
        gastos_guarderia_mensuales: tuple[GuarderiaMonthSpend, ...] = (),
    ) -> DescendantInfo:
        """Typed rather than ``**kwargs: object``, so the checker sees the real fields."""
        return DescendantInfo(
            birth_date=date(2021, 4, 15),
            gastos_guarderia_euros=gastos_guarderia_euros,
            gastos_guarderia_mensuales=gastos_guarderia_mensuales,
        )

    def test_a_declared_map_survives_the_fact_boundary_identically(self) -> None:
        child = self._child(
            gastos_guarderia_mensuales=parse_guarderia_mensual("9-12:210;1:180", field=_FIELD),
        )

        reloaded = descendant_list_from_facts(dict(descendant_facts_from_list([child])))

        assert reloaded == (child,)

    def test_the_stored_fact_carries_the_canonical_form(self) -> None:
        child = self._child(gastos_guarderia_mensuales=parse_guarderia_mensual("11:210;9:210", field=_FIELD))

        facts = dict(descendant_facts_from_list([child]))

        assert facts["renta_family.descendiente.0.gastos_guarderia_mensuales"] == "09:210;11:210"

    def test_an_undeclared_map_emits_no_fact(self) -> None:
        """An absent optional stays absent, so no profile looks re-declared."""
        facts = dict(descendant_facts_from_list([self._child()]))

        assert "renta_family.descendiente.0.gastos_guarderia_mensuales" not in facts

    def test_the_annual_figure_still_round_trips_beside_the_new_path(self) -> None:
        """The map is additive: the shape every existing profile uses is untouched."""
        child = self._child(gastos_guarderia_euros=1200)

        reloaded = descendant_list_from_facts(dict(descendant_facts_from_list([child])))

        assert reloaded == (child,)

    def test_a_second_descendant_keeps_its_own_map(self) -> None:
        """Indexed paths must not bleed between rows.

        The new path is the longest sibling under the same prefix, so a regex
        alternation ordered wrongly would match the shorter ``gastos_guarderia``
        branch, fail its anchor, and drop the map from every row at once.
        """
        first = self._child(gastos_guarderia_mensuales=parse_guarderia_mensual("1:100", field=_FIELD))
        second = DescendantInfo(
            birth_date=date(2019, 2, 2),
            gastos_guarderia_mensuales=parse_guarderia_mensual("6:300;7:300", field=_FIELD),
        )

        reloaded = descendant_list_from_facts(dict(descendant_facts_from_list([first, second])))

        assert reloaded == (first, second)


class TestStoredValueAntiTautology:
    """Proof the boundary would CATCH a corrupted stored map rather than coerce it.

    The round-trips above assert equality across the fact boundary. Their risk is
    that a load side which silently resolved a bad value to the empty map would
    still satisfy every one of them whose fixture happens to be empty. These
    cases corrupt the stored value directly and require a refusal.

    Empty is the dangerous fallback specifically: it means "no monthly breakdown
    declared", which in the turning-three period makes the spend contribute
    nothing — so a corrupted map resolving to empty would withhold the whole
    Art. 81.2 increase from the household the extension exists for, with nothing
    said.
    """

    @pytest.mark.parametrize(
        ("corrupted", "reason"),
        [
            ("13:100", "a month outside the calendar"),
            ("9:100;9:200", "the same month stored twice"),
            ("9:abc", "an amount that is not a number"),
            ("garbage", "a value with no structure at all"),
            ("9:²", "a superscript int cannot read"),
        ],
    )
    def test_a_corrupted_stored_map_refuses_instead_of_reading_as_undeclared(
        self,
        corrupted: str,
        reason: str,
    ) -> None:
        facts = dict(
            descendant_facts_from_list(
                [DescendantInfo(birth_date=date(2021, 4, 15), gastos_guarderia_mensuales=())],
            ),
        )
        facts["renta_family.descendiente.0.gastos_guarderia_mensuales"] = corrupted

        with pytest.raises(ProfileAnswerTypeError):
            descendant_list_from_facts(facts)

    @pytest.mark.parametrize(
        ("corrupted", "reason"),
        [
            ("nine hundred", "a value with no digits at all"),
            ("--5", "a DOUBLE sign, which a dash-stripping guard let reach int"),
            ("-5", "a single negative sign"),
            ("-0", "a signed zero, refused so the sign is never sometimes readable"),
            ("+5", "an explicit positive sign"),
            ("1_0", "int's own underscore tolerance"),
            ("²", "a superscript isdigit accepts and int does not"),
            ("9.5", "a fractional figure"),
        ],
    )
    def test_a_corrupted_annual_figure_refuses_by_shape(self, corrupted: str, reason: str) -> None:
        """Every non-plain-integer shape refuses as the TYPED error, never as ValueError.

        The double sign is the case that got through. The guard stripped every
        leading dash before testing for digits, so a second dash survived into
        ``int`` and raised exactly the bare, untranslated ``ValueError`` this
        function exists to replace — the failure class its own docstring names,
        surviving one shape outside the case the test below covers.

        That is the shape where an almost-right guard is worse than none: the
        test proving it works passes, so nothing signals the hole.
        """
        facts = dict(
            descendant_facts_from_list([DescendantInfo(birth_date=date(2021, 4, 15), gastos_guarderia_euros=900)]),
        )
        facts["renta_family.descendiente.0.gastos_guarderia"] = corrupted

        with pytest.raises(ProfileAnswerTypeError):
            descendant_list_from_facts(facts)

    def test_a_corrupted_annual_figure_refuses_by_index(self) -> None:
        """The calculate path folded onto this reader, so its diagnostic must survive.

        The derived-facts injector used to carry its own tolerant coercion and
        its own refusal naming the row. Delegating to the canonical record was
        the right move — it was a second aggregation path — but it would have
        traded that diagnostic for an untranslated ``ValueError`` naming nothing.
        """
        facts = dict(
            descendant_facts_from_list([DescendantInfo(birth_date=date(2021, 4, 15), gastos_guarderia_euros=900)]),
        )
        facts["renta_family.descendiente.0.gastos_guarderia"] = "nine hundred"

        with pytest.raises(ProfileAnswerTypeError, match=re.escape("renta_family.descendiente.0.gastos_guarderia")):
            descendant_list_from_facts(facts)
