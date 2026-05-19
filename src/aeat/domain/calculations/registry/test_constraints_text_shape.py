"""Roundtrip and violation tests for the Plan B text-shape constraints.

`CasillaConstraints` was extended with `pattern`, `min_length`,
`max_length`, and `enum` slots. These tests exercise:

- Self-consistency validation at registry load (`min_length >
  max_length`, empty `enum`, invalid regex `pattern` all fail).
- `violates_text` accept and reject paths for each constraint.
- Anti-tautology: a constraint declaration that drifts on disk
  surfaces a violation when reloaded.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ._errors import RegistryValidationError
from ._schema import CasillaConstraints


pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _make(**fields: object) -> CasillaConstraints:
    base: dict[str, object] = {
        "legal_refs": ("ley-58-2003:art-29",),
        "source_refs": ("aeat-manual",),
    }
    base.update(fields)
    return CasillaConstraints(**base)  # type: ignore[arg-type]


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

    def test_negative_min_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _make(min_length=-1)

    def test_negative_max_length_rejected(self) -> None:
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


class TestViolatesText:
    def test_value_within_bounds_passes(self) -> None:
        c = _make(min_length=2, max_length=5)
        assert c.violates_text("abc") is None

    def test_value_below_min_length_rejected(self) -> None:
        c = _make(min_length=3)
        assert c.violates_text("ab") is not None
        assert "min_length" in c.violates_text("ab")  # type: ignore[operator]

    def test_value_above_max_length_rejected(self) -> None:
        c = _make(max_length=3)
        assert "max_length" in c.violates_text("abcde")  # type: ignore[operator]

    def test_value_not_matching_pattern_rejected(self) -> None:
        c = _make(pattern=r"^[A-Z]{2}$")
        assert "pattern" in c.violates_text("xy")  # type: ignore[operator]
        assert c.violates_text("ES") is None

    def test_value_outside_enum_rejected(self) -> None:
        c = _make(enum=("01", "02"))
        assert "enum" in c.violates_text("99")  # type: ignore[operator]
        assert c.violates_text("01") is None

    def test_constraints_compose_in_order(self) -> None:
        c = _make(min_length=2, max_length=5, pattern=r"^[A-Z]+$", enum=("ES", "FR"))
        # min/max length applied first
        assert "min_length" in c.violates_text("A")  # type: ignore[operator]
        # Then pattern
        assert "pattern" in c.violates_text("xy")  # type: ignore[operator]
        # Then enum
        assert "enum" in c.violates_text("DE")  # type: ignore[operator]
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
        # Drift to a value outside the enum.
        assert rebuilt.violates_text("5T") is not None
        assert rebuilt.violates_text("1T") is None


class TestNumericViolatesPreserved:
    """Plan B is additive; the existing numeric `violates` contract is untouched."""

    def test_numeric_violates_still_works(self) -> None:
        from decimal import Decimal
        c = _make(sign="non_negative", min_value=Decimal("0"), max_value=Decimal("100"))
        assert c.violates(Decimal("50")) is None
        assert c.violates(Decimal("-1")) is not None
        assert c.violates(Decimal("200")) is not None
