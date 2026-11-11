"""Contracts for Art 20/52, DT12, and SAL governed-fact resolution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...calculations.registry.errors import RegistryValidationError
from ...calculations.registry.tests.authored_editions import filing_year_envelope, manual_edition_matches
from ...calculations.registry.tests.published_authority import PublishedGovernedFactSource
from ..modelo_fact_context import ModeloFactResolutionContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EXERCISE = filing_year_envelope().horizon


def _euros(printed: str) -> Decimal:
    """Read an amount as the AEAT manual prints it: dot thousands, comma decimals."""
    return Decimal(printed.replace(".", "").replace(",", "."))


# The manual edition of the exercise that raised the art. 20 RNT ceiling prints both figures.
((_RAISED_IN, _RAISE),) = manual_edition_matches(
    "renta", r"se eleva de ([\d.]+) euros hasta ([\d.]+(?:,\d+)?) euros"
).items()
_CEILING_BEFORE_RAISE, _CEILING_AFTER_RAISE = (_euros(printed) for printed in _RAISE.groups())


def _context() -> ModeloFactResolutionContext:
    return ModeloFactResolutionContext(
        authority=PublishedGovernedFactSource(),
        filing_period=date(_EXERCISE, 12, 31),
        devengo_date=date(_EXERCISE, 12, 31),
    )


def test_art20_fact_resolves_on_filing_period_with_provenance() -> None:
    resolved = _context().resolved_decimal("lirpf-art-20-trabajo-reduccion-rnt-ceiling")

    assert resolved.payload.value == Decimal("19747.50")
    assert resolved.legal_refs == ("ley-35-2006:art-20",)
    assert resolved.source_refs == ("boe-lirpf-statutory-facts",)


@pytest.mark.parametrize(
    ("filing_year", "ceiling", "source_ref"),
    (
        pytest.param(_RAISED_IN - 1, _CEILING_BEFORE_RAISE, f"aeat-renta-{_RAISED_IN - 1}-manual-parte1", id="before"),
        pytest.param(_RAISED_IN, _CEILING_AFTER_RAISE, f"aeat-renta-{_RAISED_IN}-manual-parte1", id="raised"),
    ),
)
def test_art20_ceiling_resolves_for_the_exercises_around_its_raise(
    filing_year: int, ceiling: Decimal, source_ref: str
) -> None:
    """Ley 31/2022 raised the art. 20 RNT ceiling for the exercise the AEAT manual says it did; the exercise before keeps the old one."""
    context = ModeloFactResolutionContext(
        authority=PublishedGovernedFactSource(),
        filing_period=date(filing_year, 12, 31),
        devengo_date=date(filing_year, 12, 31),
    )

    resolved = context.resolved_decimal("lirpf-art-20-trabajo-reduccion-rnt-ceiling")

    assert resolved.payload.value == ceiling
    assert resolved.legal_refs == ("ley-35-2006:art-20",)
    assert resolved.source_refs == (source_ref,)


def test_context_refuses_unregistered_or_wrongly_typed_fact() -> None:
    context = _context()

    with pytest.raises(RegistryValidationError, match="unregistered modelo governed fact"):
        context.resolved_scalar("not-a-modelo-fact")
    with pytest.raises(RegistryValidationError, match="must resolve to an integer"):
        context.integer("lirpf-dt12-rescate-reduction-rate")
