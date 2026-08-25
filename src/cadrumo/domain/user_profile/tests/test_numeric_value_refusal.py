"""The rule deciding whether a value satisfies a numeric field's declaration.

`minimum` and `maximum` were inert before this existed. The schema checked
that a declared range was internally coherent -- that the minimum did not
exceed the maximum -- and then never compared a value to it, so a
participation percentage declared `0..100` accepted `999` and carried it
into an attribution calculation with nothing raised. A declaration nothing
enforces is worse than no declaration, because every reader downstream is
entitled to believe it.

Both bounds are INCLUSIVE, and the boundary cases below are the point of
this file rather than filler. A percentage of exactly 0 and exactly 100 are
both ordinary answers -- a socio may hold none of an entity or all of it --
so an exclusive comparison would refuse two legitimate filings while looking
correct on every value in between.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..schema import ProfileFieldDefinition, ProfileFieldType, numeric_value_refusal

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field(
    *,
    key: str = "share_pct",
    field_type: ProfileFieldType = ProfileFieldType.DECIMAL,
    minimum: str | None = "0",
    maximum: str | None = "100",
) -> ProfileFieldDefinition:
    return ProfileFieldDefinition.model_validate(
        {
            "key": key,
            "type": field_type.value,
            "required": True,
            "sensitivity": "financial",
            "description": "Participation percentage.",
            **({"minimum": minimum} if minimum is not None else {}),
            **({"maximum": maximum} if maximum is not None else {}),
        },
    )


# ── the boundaries, which are inclusive ────────────────────────────


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("100")])
def test_a_value_exactly_on_a_bound_is_accepted(value: Decimal) -> None:
    """Holding none of an entity, or all of it, are both ordinary answers.

    An exclusive comparison refuses these two while accepting everything
    between them, which is the failure mode that survives casual testing.
    """
    assert numeric_value_refusal(_field(), value) is None


@pytest.mark.parametrize("value", [Decimal("-0.01"), Decimal("100.01")])
def test_a_value_just_outside_a_bound_is_refused(value: Decimal) -> None:
    """The counterpart: one step beyond either bound must not pass.

    Paired with the case above so neither can be satisfied by a comparison
    that is simply too permissive or simply too strict.
    """
    assert numeric_value_refusal(_field(), value) is not None


# ── what counts as a number ────────────────────────────────────────


def test_a_non_numeric_string_is_refused() -> None:
    """The value that reaches production: a fact carrier keeps `abc` a string.

    Only a canonically-shaped numeric string is restored to `Decimal`, so
    anything else arrives here still text and must be caught by type rather
    than by a failed comparison.
    """
    assert numeric_value_refusal(_field(), "abc") is not None


def test_a_boolean_is_refused_despite_being_an_integer() -> None:
    """`True` is an answer to a different question.

    `bool` subclasses `int` in Python, so a check written as
    `isinstance(value, int)` admits `True` and stores it as the number 1 --
    a plausible value nothing downstream would question.
    """
    assert numeric_value_refusal(_field(), value=True) is not None


def test_a_date_is_refused() -> None:
    """A date-shaped fact reaching a numeric field is not silently ordered."""
    assert numeric_value_refusal(_field(), date(2026, 1, 1)) is not None


@pytest.mark.parametrize("value", [Decimal("50"), 50])
def test_a_decimal_or_integer_within_range_is_accepted(value: object) -> None:
    """Both carriers the fact model preserves for a numeric field."""
    assert numeric_value_refusal(_field(), value) is None


# ── what the rule does not judge ───────────────────────────────────


def test_an_absent_value_is_not_this_rule_s_business() -> None:
    """A cleared field is the required-field check's finding, not this one's.

    Reporting it here too would surface one missing field as two unrelated
    faults, and would refuse the ordinary act of clearing an optional field.
    """
    assert numeric_value_refusal(_field(), None) is None


def test_a_non_numeric_field_is_not_judged() -> None:
    """A string field carries no bounds and must pass through untouched."""
    field = ProfileFieldDefinition.model_validate(
        {
            "key": "name",
            "type": ProfileFieldType.STRING.value,
            "required": True,
            "sensitivity": "identity",
            "description": "Member name.",
        },
    )

    assert numeric_value_refusal(field, "Socio Uno") is None


def test_an_unbounded_numeric_field_still_refuses_a_non_number() -> None:
    """Type is checked even where no range is declared.

    Most numeric fields declare no bounds, so if the type check rode along
    with the range check the rule would cover two fields out of fifty-six.
    """
    unbounded = _field(key="base_imponible_assigned", field_type=ProfileFieldType.MONEY, minimum=None, maximum=None)

    refusal = numeric_value_refusal(unbounded, "abc")
    assert refusal is not None
    assert "base_imponible_assigned" in refusal
    assert numeric_value_refusal(unbounded, Decimal("-999999")) is None


# ── the refusal has to be usable ───────────────────────────────────


def test_the_refusal_names_the_field_and_the_accepted_range() -> None:
    """An operator who is refused must learn what would be accepted.

    A bare "value invalid" leaves them guessing at both the field and the
    bound, which is the refusal shape the CLI boundary rule exists to
    prevent.
    """
    refusal = numeric_value_refusal(_field(), Decimal("999"))

    assert refusal is not None
    assert "share_pct" in refusal
    assert "0" in refusal
    assert "100" in refusal
    assert "999" in refusal


def test_a_one_sided_bound_states_only_the_bound_it_has() -> None:
    """A minimum-only field must not invent an upper limit in its refusal."""
    refusal = numeric_value_refusal(_field(minimum="0", maximum=None), Decimal("-1"))

    assert refusal is not None
    assert "0" in refusal
