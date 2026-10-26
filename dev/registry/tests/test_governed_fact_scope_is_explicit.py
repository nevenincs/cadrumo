"""Registry vocabulary tokens resolve only inside an explicit governed-fact scope."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    governed_facts_in_scope,
    validating_governed_facts,
)
from cadrumo.domain.calculations.registry.iva_category_catalogue import require_iva_category

from ..compiler.authority import compiled_bundled_authority
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EFFECTIVE_DATE = date(2025, 6, 15)


def test_token_construction_without_a_scope_refuses() -> None:
    assert governed_facts_in_scope() is None, "an ambient governed-fact scope would hide the refusal under test"

    with pytest.raises(InternalInvariantError, match="requires an explicit generation-pinned governed-fact scope"):
        require_iva_category("domestic_general", effective_date=_EFFECTIVE_DATE)


def test_the_same_token_resolves_inside_an_explicit_candidate_scope() -> None:
    facts = compiled_bundled_authority().catalogues.facts

    with validating_governed_facts(CandidateFactAuthority(facts, committed_supported_filing_years())):
        category = require_iva_category("domestic_general", effective_date=_EFFECTIVE_DATE)

    assert str(category) == "domestic_general"
    assert governed_facts_in_scope() is None, "the explicit scope must end with its block"
