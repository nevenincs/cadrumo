"""The disability grades a descendant record accepts, read from the governed catalogue."""

from __future__ import annotations

from typing import Final

from .errors import RegistryValidationError
from .form_codes import resolve_form_codes
from .governed_fact_scope import GovernedFactSource

_GRADE_CATALOGUE_FACT: Final = "lirpf-descendant-disability-grade-catalogue"


def accepted_descendant_disability_grades(*, authority: GovernedFactSource | None = None) -> frozenset[int]:
    """Return the statutory grades a descendant may declare, from the pinned catalogue."""
    tokens = resolve_form_codes(_GRADE_CATALOGUE_FACT, authority=authority).codes("accepted_grades")
    try:
        return frozenset(int(token) for token in tokens)
    except ValueError as exc:
        raise RegistryValidationError("descendant disability catalogue has invalid accepted_grades") from exc


__all__ = ["accepted_descendant_disability_grades"]
