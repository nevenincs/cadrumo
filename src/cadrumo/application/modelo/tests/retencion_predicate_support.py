"""Look up a verification predicate the registry declares on a Modelo 100 revision."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.tests.published_authority import published_authored_revision


def declared_m100_predicate(predicate_id: str, year: int):
    """Return the registry's own declared predicate, not a hand-written expression."""
    revision = published_authored_revision("100", year=year)
    for predicate in revision.verification_predicates or ():
        if predicate.predicate_id == predicate_id:
            return predicate
    pytest.fail(f"{predicate_id} is not declared on the M100/{year} revision")
