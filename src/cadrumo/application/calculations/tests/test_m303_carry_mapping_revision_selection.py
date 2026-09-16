"""Modelo 303 carry mapping resolves for the revision selected at each filing scope."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..m303_carry_ingress import m303_declaration_type_header_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


@pytest.mark.parametrize(
    ("filing_year", "period"),
    (
        pytest.param(2025, "4T", id="2025-design"),
        pytest.param(2026, "1T", id="2026-design-first-quarter"),
        pytest.param(2026, "4T", id="2026-design-terminal-quarter"),
        pytest.param(2026, "12", id="2026-design-monthly"),
    ),
)
def test_carry_mapping_matches_the_selected_modelo_303_revision(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
    period: str,
) -> None:
    header_key = m303_declaration_type_header_key(
        filing_year=filing_year,
        period=period,
        operation=authority_operation,
    )

    assert header_key == "declaration_type"
