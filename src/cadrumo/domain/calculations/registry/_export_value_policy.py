"""Canonical value-policy projection for fixed-width registry export fields."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from fractions import Fraction
from math import isfinite
from typing import Annotated

from pydantic import BeforeValidator

from ._errors import RegistryValidationError


class ExportValuePolicy(StrEnum):
    """Closed runtime transformations from semantic values to AEAT wire tokens."""

    SELECTED_1_UNSELECTED_0 = "selected-1-unselected-0"
    FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS = "four-digit-year-final-two-digits"


def coerce_export_value_policy(value: object) -> object:
    """Hydrate a declared policy token while leaving unknown values to strict validation."""
    if value is None or isinstance(value, ExportValuePolicy):
        return value
    if isinstance(value, str):
        try:
            return ExportValuePolicy(value)
        except ValueError:
            return value
    return value


ExportValuePolicyValue = Annotated[ExportValuePolicy | None, BeforeValidator(coerce_export_value_policy)]

_WIRE_LENGTH_BY_POLICY: dict[ExportValuePolicy, int] = {
    ExportValuePolicy.SELECTED_1_UNSELECTED_0: 1,
    ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS: 2,
}


def export_value_policy_wire_length(policy: ExportValuePolicy) -> int:
    """Return the exact fixed-width slot length authorized by ``policy``."""
    return _WIRE_LENGTH_BY_POLICY[policy]


def project_export_value(policy: ExportValuePolicy | None, value: object) -> object:
    """Project one semantic value to its exact declared wire token.

    ``None`` is deliberately inert: it is not an inference hook and does not
    select a policy from field width, type, identifier, or historical layout.
    """
    if policy is None:
        return value
    if policy is ExportValuePolicy.SELECTED_1_UNSELECTED_0:
        return _project_selected_unselected(value)
    if policy is ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS:
        return _project_four_digit_year(value)
    raise RegistryValidationError(f"unknown export value policy {policy!r}")


def validate_export_wire_value(policy: ExportValuePolicy | None, raw: str) -> None:
    """Refuse a wire token that contradicts its declared value policy."""
    if policy is None:
        return
    if policy is ExportValuePolicy.SELECTED_1_UNSELECTED_0:
        if raw not in {"0", "1"}:
            raise RegistryValidationError("selected/unselected export field must contain exactly ASCII 0 or 1")
        return
    if policy is ExportValuePolicy.FOUR_DIGIT_YEAR_FINAL_TWO_DIGITS:
        if len(raw) != 2 or not raw.isascii() or not raw.isdigit():
            raise RegistryValidationError("short-year export field must contain exactly two ASCII digits")
        return
    raise RegistryValidationError(f"unknown export value policy {policy!r}")


def _project_selected_unselected(value: object) -> str:
    if value is None:
        return "0"
    if isinstance(value, str):
        if value == "":
            return "0"
        if value in {"0", "1"}:
            return value
        raise RegistryValidationError(
            "selected/unselected export string must be empty or exactly ASCII 0 or 1",
        )
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal) and not value.is_finite():
        raise RegistryValidationError("selected/unselected export numeric value must be finite")
    if isinstance(value, float) and not isfinite(value):
        raise RegistryValidationError("selected/unselected export numeric value must be finite")
    if isinstance(value, (int, float, Decimal, Fraction)) and not isinstance(value, bool):
        if value == 0:
            return "0"
        if value == 1:
            return "1"
    raise RegistryValidationError(
        "selected/unselected export value must be absent, empty, False, True, or exact numeric/string 0 or 1",
    )


def _project_four_digit_year(value: object) -> str:
    if isinstance(value, bool):
        raise RegistryValidationError("short-year export value must be a four-digit year, not boolean")
    if isinstance(value, int):
        if 1000 <= value <= 9999:
            return str(value)[-2:]
        raise RegistryValidationError("short-year export integer must contain exactly four digits")
    if isinstance(value, str) and len(value) == 4 and value.isascii() and value.isdigit():
        return value[-2:]
    raise RegistryValidationError("short-year export value must be a four-digit integer or four ASCII-digit string")


__all__ = [
    "ExportValuePolicy",
    "ExportValuePolicyValue",
    "coerce_export_value_policy",
    "export_value_policy_wire_length",
    "project_export_value",
    "validate_export_wire_value",
]
