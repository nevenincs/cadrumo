"""Which Modelo 303 record design admits a rectificativa motive, by the date it is presented.

The motive fields entered the 303 record design with the edition from
September 2024 (DR303 "Motivo de la rectificación"). A return presented before
that edition has no motive field in any design, so asking for the admitted
design answers "none" instead of failing the return's export.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

import pytest

from ....core.time.clock import frozen_clock
from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ...calculations.registry.tests.published_authority import published_snapshot
from ..calculation_revision_amendment import m303_rectificativa_record_design_from_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FACT_ID = "modelo-303-rectificativa-record-design-mapping"


def _first_motive_edition() -> datetime:
    with bundled_indexed_authority().operation() as operation:
        fact = operation.governed_fact(_FACT_ID)
    first = min(variant.valid_from for variant in fact.variants if variant.valid_from is not None)
    return datetime.combine(first, time(12), tzinfo=UTC)


def _admitted_design_presented_at(instant: datetime) -> object:
    snapshot = published_snapshot("303", filing_year=filing_year_envelope().horizon, period="1T")
    with frozen_clock(instant):
        return m303_rectificativa_record_design_from_snapshot(snapshot)


def test_a_return_presented_before_the_motive_edition_has_no_admitted_design() -> None:
    assert _admitted_design_presented_at(_first_motive_edition() - timedelta(days=1)) is None


def test_a_return_presented_from_the_motive_edition_reads_the_admitted_design() -> None:
    assert _admitted_design_presented_at(_first_motive_edition()) is not None
