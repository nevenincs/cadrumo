"""Roundtrip and violation tests for text-shape constraints.

`CasillaConstraints` was extended with `pattern`, `min_length`,
`max_length`, and `enum` slots. These tests exercise:

- Self-consistency validation at registry load (`min_length >
  max_length`, empty `enum`, invalid regex `pattern` all fail).
- `violates_text` accept and reject paths for each constraint.
- Anti-tautology: a constraint declaration that drifts on disk
  surfaces a violation when reloaded.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, TypedDict, Unpack

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema_surfaces import CasillaConstraints

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _ConstraintFields(TypedDict, total=False):
    sign: Literal["any", "non_negative", "non_positive"]
    min_value: Decimal | None
    max_value: Decimal | None
    pattern: str | None
    min_length: int | None
    max_length: int | None
    enum: tuple[str, ...] | None


def _make(**fields: Unpack[_ConstraintFields]) -> CasillaConstraints:
    return CasillaConstraints(
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual",),
        **fields,
    )


class TestConstraintsShapeAccepts:
    def test_pattern_alone_accepted(self) -> None:
        c = _make(pattern=r"^[A-Z]{2}$")
        assert c.pattern == "^[A-Z]{2}$"

    def test_min_max_length_pair_accepted(self) -> None:
        c = _make(min_length=2, max_length=10)
        assert (c.min_length, c.max_length) == (2, 10)

    def test_enum_accepted(self) -> None:
        c = _make(enum=("01", "02", "03"))
        assert c.enum == ("01", "02", "03")

    def test_all_text_constraints_combine(self) -> None:
        c = _make(pattern=r"^\d{5}$", min_length=5, max_length=5, enum=("28013", "08001"))
        assert c.min_length == 5
        assert c.enum == ("28013", "08001")


class TestConstraintsShapeRejects:
    def test_min_length_greater_than_max_length_rejected(self) -> None:
        with pytest.raises(ValidationError, match="min_length"):
            _make(min_length=10, max_length=3)

    def test_negative_length_bound_rejected(self) -> None:
        # Test negative min_length
        with pytest.raises(ValidationError):
            _make(min_length=-1)

        # Test negative max_length
        with pytest.raises(ValidationError):
            _make(max_length=-1)

    def test_empty_enum_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            _make(enum=())

    def test_duplicate_enum_values_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            _make(enum=("01", "01", "02"))

    def test_invalid_regex_pattern_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not a valid regex"):
            _make(pattern=r"[")


def _reason(constraints: CasillaConstraints, value: str) -> str:
    """Return the violation reason for `value`, asserting it is non-None.

    `violates_text` returns ``str | None``; the rejection-path tests need a
    plain ``str`` to run an ``in`` substring check against. This helper
    narrows the union once at the assertion site.
    """

    reason = constraints.violates_text(value)
    assert reason is not None, f"expected a violation reason for {value!r}"
    return reason


class TestViolatesText:
    def test_value_within_bounds_passes(self) -> None:
        c = _make(min_length=2, max_length=5)
        assert c.violates_text("abc") is None

    def test_value_outside_length_bounds_rejected(self) -> None:
        # Test value too short
        c = _make(min_length=3)
        assert "min_length" in _reason(c, "ab")

        # Test value too long
        c = _make(max_length=3)
        assert "max_length" in _reason(c, "abcde")

    def test_value_not_matching_pattern_rejected(self) -> None:
        c = _make(pattern=r"^[A-Z]{2}$")
        assert "pattern" in _reason(c, "xy")
        assert c.violates_text("ES") is None

    def test_value_outside_enum_rejected(self) -> None:
        c = _make(enum=("01", "02"))
        assert "enum" in _reason(c, "99")
        assert c.violates_text("01") is None

    def test_constraints_compose_in_order(self) -> None:
        c = _make(min_length=2, max_length=5, pattern=r"^[A-Z]+$", enum=("ES", "FR"))
        # min/max length applied first
        assert "min_length" in _reason(c, "A")
        # Then pattern
        assert "pattern" in _reason(c, "xy")
        # Then enum
        assert "enum" in _reason(c, "DE")
        # All pass
        assert c.violates_text("ES") is None
        assert c.violates_text("FR") is None


class TestAntiTautology:
    """A constraint that catches a deliberate drift survives a round-trip."""

    def test_pattern_constraint_rejects_mutated_value(self) -> None:
        c = _make(pattern=r"^ES\d{2}$")
        # Round-trip through model_dump / model_validate to confirm the
        # pattern survives serialisation.
        rebuilt = CasillaConstraints.model_validate(c.model_dump())
        assert rebuilt.pattern == r"^ES\d{2}$"
        # A drifted value (lowercase) still violates after the round trip.
        assert rebuilt.violates_text("es12") is not None

    def test_enum_constraint_rejects_mutated_value(self) -> None:
        c = _make(enum=("0A", "1T", "2T", "3T", "4T"))
        rebuilt = CasillaConstraints.model_validate(c.model_dump())
        # Drift to a value outside the enum, rejected for the enum reason
        # specifically -- not merely rejected for some unrelated cause.
        reason = rebuilt.violates_text("5T")
        assert reason is not None
        assert "enum" in reason
        assert rebuilt.violates_text("1T") is None


class TestNumericViolatesPreserved:
    """Text-shape constraints are additive; the numeric `violates` contract is untouched."""

    def test_numeric_violates_still_works(self) -> None:
        from decimal import Decimal

        c = _make(sign="non_negative", min_value=Decimal("0"), max_value=Decimal("100"))
        assert c.violates(Decimal("50")) is None
        # Each rejection is pinned to ITS OWN violated axis, not just any
        # truthy reason -- a below-range value must fail for the sign/lower
        # bound, an above-range value for the upper bound.
        below = c.violates(Decimal("-1"))
        assert below is not None
        assert "non_negative" in below
        above = c.violates(Decimal("200"))
        assert above is not None
        assert "max_value" in above
