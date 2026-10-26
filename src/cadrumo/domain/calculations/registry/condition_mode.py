"""How a registry declaration combines the conditions it carries.

One vocabulary, one definition. Deadline windows, modelo schedules, verification
declarations and the parity audit surface all ask the same question of a condition
list -- must every condition hold, or is one enough -- and each previously spelled
the answer out at its own field. A member added to one spelling would have left the
others validating the old set.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BeforeValidator

from .schema_base import coerce_enum_member


class ConditionMode(StrEnum):
    """Whether a declaration's conditions are conjunctive or disjunctive."""

    ALL = "all"
    """Every declared condition must hold. The default where a field is silent."""

    ANY = "any"
    """One holding condition is enough, so the list must not be empty."""


ConditionModeField = Annotated[ConditionMode, BeforeValidator(coerce_enum_member(ConditionMode))]
"""Registry condition-mode token hydrated into a member.

Registry schema models validate strictly, which refuses a bare TOML string for an
enum-typed field, so the token is coerced at the boundary.
"""


__all__ = ["ConditionMode", "ConditionModeField"]
