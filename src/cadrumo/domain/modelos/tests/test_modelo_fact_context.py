"""Contracts for Art 52, DT12, and SAL governed-fact resolution."""

from __future__ import annotations

from datetime import date

import pytest

from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ..modelo_fact_context import ModeloFactResolutionContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _context() -> ModeloFactResolutionContext:
    return ModeloFactResolutionContext(
        authority=PublishedGovernedFactSource(),
        filing_period=date(2025, 12, 31),
        devengo_date=date(2025, 12, 31),
    )


def test_context_refuses_unregistered_or_wrongly_typed_fact() -> None:
    context = _context()

    with pytest.raises(RegistryValidationError, match="unregistered modelo governed fact"):
        context.resolved_scalar("not-a-modelo-fact")
    with pytest.raises(RegistryValidationError, match="must resolve to an integer"):
        context.integer("lirpf-dt12-rescate-reduction-rate")
