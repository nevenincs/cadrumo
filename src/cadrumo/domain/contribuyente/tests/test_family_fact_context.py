"""Contract tests for governed family-fact resolution."""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.schema_base import DateAxis
from ..family_fact_context import FamilyFactResolutionContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _context() -> FamilyFactResolutionContext:
    coordinate = date(2024, 12, 31)
    return FamilyFactResolutionContext(
        authority=bundled_authority(),
        filing_period=coordinate,
        devengo_date=coordinate,
    )


def test_family_context_resolves_the_under_three_age_with_typed_provenance() -> None:
    resolved = _context().resolved_scalar("lirpf-art-58-under-three-maximum-age")

    assert resolved.payload.value == 3
    assert resolved.date_axis is DateAxis.FILING_PERIOD
    assert resolved.effective_date == date(2024, 12, 31)
    assert resolved.legal_refs == ("ley-35-2006:art-58",)
    assert resolved.source_refs == ("boe-lirpf-statutory-facts",)
    assert resolved.authority_digest


def test_family_context_refuses_a_fact_not_declared_for_family_resolution() -> None:
    with pytest.raises(RegistryValidationError, match="unregistered family governed fact"):
        _context().integer("not-a-family-fact")
