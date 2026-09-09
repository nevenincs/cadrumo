"""Contracts for Art 20/52, DT12, and SAL governed-fact resolution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...calculations.registry.authority import bundled_authority
from ...calculations.registry.errors import RegistryValidationError
from ..modelo_fact_context import ModeloFactResolutionContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _context() -> ModeloFactResolutionContext:
    return ModeloFactResolutionContext(
        authority=bundled_authority(),
        filing_period=date(2025, 12, 31),
        devengo_date=date(2025, 12, 31),
    )


def test_art20_fact_resolves_on_filing_period_with_provenance() -> None:
    resolved = _context().resolved_decimal("lirpf-art-20-trabajo-reduccion-rnt-ceiling")

    assert resolved.payload.value == Decimal("19747.50")
    assert resolved.legal_refs == ("ley-35-2006:art-20",)
    assert resolved.source_refs == ("boe-lirpf-statutory-facts",)


def test_context_refuses_unregistered_or_wrongly_typed_fact() -> None:
    context = _context()

    with pytest.raises(RegistryValidationError, match="unregistered modelo governed fact"):
        context.resolved_scalar("not-a-modelo-fact")
    with pytest.raises(RegistryValidationError, match="must resolve to an integer"):
        context.integer("lirpf-dt12-rescate-reduction-rate")
