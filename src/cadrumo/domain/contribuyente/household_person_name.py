"""The surnames and name a household member row states.

The Renta declaration names every descendant and ascendant it counts by surnames and
name, in that order, as one text. The official type collapses whitespace, so a stored
name keeps exactly the collapsed text and a name that collapses to nothing is no name.
How long it may be is a form datum the registry declares, never a number held here.
Letter case is left as typed: the export capitalizes a value only where the official
type requires it.
"""

from __future__ import annotations

from typing import Final

from ...core.errors.hierarchy import CoreValidationError
from ..calculations.registry.form_codes import form_codes_in_scope, resolve_form_codes
from ..calculations.registry.governed_fact_scope import GovernedFactSource
from .errors import ProfileValidationError

_FORM_ROW_CODES_FACT: Final = "form-row-codes"
_NAME_BOUND_KEY: Final = "m100.household_person_name_max"


def collapsed_person_name(raw: str) -> str | None:
    """Return the name with its whitespace collapsed, or ``None`` when nothing is left."""
    collapsed = " ".join(raw.split())
    return collapsed or None


def household_person_name_limit(*, authority: GovernedFactSource) -> int:
    """Return the most characters the declaration's design admits for a household member's name."""
    return resolve_form_codes(_FORM_ROW_CODES_FACT, authority=authority).integer(_NAME_BOUND_KEY)


def household_person_name_limit_in_scope() -> int | None:
    """Return the design's name length in the current authority scope, or ``None`` outside every scope.

    Only a validator may use this reader; code that needs the bound itself resolves it
    with :func:`household_person_name_limit`.
    """
    codes = form_codes_in_scope(_FORM_ROW_CODES_FACT)
    return None if codes is None else codes.integer(_NAME_BOUND_KEY)


def admitted_household_person_name(raw: str, *, authority: GovernedFactSource) -> str | None:
    """Return the collapsed name a row may store, or ``None`` when it is blank or longer than the design admits."""
    collapsed = collapsed_person_name(raw)
    if collapsed is None or len(collapsed) > household_person_name_limit(authority=authority):
        return None
    return collapsed


def require_household_person_name(value: str | None) -> str | None:
    """Return a stated name in its collapsed form, for a model validator.

    Inside an authority scope the name is also held to the design's length; a client
    reading a runtime result holds no scope and keeps only the blank check.

    Raises:
        ProfileValidationError: The name is blank once its whitespace is collapsed.
        CoreValidationError: The name is longer than the design admits.
    """
    if value is None:
        return None
    collapsed = collapsed_person_name(value)
    if collapsed is None:
        raise ProfileValidationError("apellidos_nombre must not be blank when provided")
    limit = household_person_name_limit_in_scope()
    if limit is not None and len(collapsed) > limit:
        raise CoreValidationError("apellidos_nombre is longer than the form declares")
    return collapsed


__all__ = [
    "admitted_household_person_name",
    "collapsed_person_name",
    "household_person_name_limit",
    "household_person_name_limit_in_scope",
    "require_household_person_name",
]
