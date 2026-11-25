"""Gates for the registry-backed RIRPF art. 100 urban rent retención rates.

The expected rates are read out of the bundled BOE excerpt of RD 439/2007
art. 100, not recomputed from the loader: the general percentage and the
Ceuta/Melilla reduction are parsed from the text, and the reduced rate is the
excerpt's own arithmetic on them.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest

from ....core.resources.bundled_data import bundled_path
from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..retencion_facts import urban_rent_retencion_rates

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Load the rent rates inside one generation-pinned authority operation."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _excerpt_percentages() -> tuple[Decimal, Decimal]:
    path = bundled_path("corpus", "normatives", "html") / "rd-439-2007-art-100.html"
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8")))
    general = re.search(r"aplicar el porcentaje del (\d+) por ciento sobre todos los conceptos", text)
    reduction = re.search(r"Este porcentaje se reducirá en el (\d+) por ciento cuando el inmueble urbano", text)
    assert general is not None
    assert reduction is not None
    return Decimal(general.group(1)) / Decimal("100"), Decimal(reduction.group(1)) / Decimal("100")


@pytest.mark.parametrize("year", tuple(filing_year_envelope().years))
def test_the_rent_rates_are_the_general_and_ceuta_melilla_rates_the_excerpt_states(year: int) -> None:
    general, reduction = _excerpt_percentages()

    rates = urban_rent_retencion_rates(effective_date=date(year, 1, 1))

    assert rates == frozenset({general, general - general * reduction})
