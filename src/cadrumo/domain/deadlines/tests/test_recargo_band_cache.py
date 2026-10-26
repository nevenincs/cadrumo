"""The recargo band table is adapted once per authority generation, never across one.

The component reader is the storage boundary: it serves the published
component and counts how often the band table is read. The loader under test
is the real one.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.authority_artifact import (
    AuthorityComponentQuery,
    AuthorityGenerationPin,
    RuntimeCatalogueComponentQuery,
)
from ...calculations.registry.runtime_catalogues import PublishedRecargoBand
from ..recargo import load_recargo_bands

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BANDS_QUERY = RuntimeCatalogueComponentQuery("recargo_bands")


class _CountingReader:
    """Serve one generation's components, replacing the band table when asked."""

    def __init__(
        self,
        operation: PinnedAuthorityOperation,
        pin: AuthorityGenerationPin,
        bands: Mapping[str, PublishedRecargoBand] | None = None,
    ) -> None:
        self._operation = operation
        self._pin = pin
        self._bands = bands
        self.band_reads = 0

    def pin(self) -> AuthorityGenerationPin:
        return self._pin

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        assert pin == self._pin
        if query == _BANDS_QUERY:
            self.band_reads += 1
            if self._bands is not None:
                return self._bands
        return self._operation.load(query, pin=self._operation.generation)

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        return ()


def _pin(marker: str) -> AuthorityGenerationPin:
    return AuthorityGenerationPin(marker * 64, marker * 64)


def _operation(reader: _CountingReader) -> PinnedAuthorityOperation:
    return PinnedAuthorityOperation(reader, reader.pin())


def test_repeated_loads_in_one_generation_read_the_table_once(operation: PinnedAuthorityOperation) -> None:
    reader = _CountingReader(operation, _pin("a"))
    pinned = _operation(reader)

    first = load_recargo_bands(operation=pinned)
    repeated = [load_recargo_bands(operation=pinned) for _ in range(25)]

    assert reader.band_reads == 1, "the band table must be adapted once per generation"
    assert all(bands is first for bands in repeated)
    assert first == load_recargo_bands(operation=operation), "cached bands equal the published ones"


def test_a_new_generation_is_adapted_afresh(operation: PinnedAuthorityOperation) -> None:
    published = operation.runtime_catalogue("recargo_bands")
    assert isinstance(published, Mapping)
    first_band_id, first_band = sorted(published.items(), key=lambda item: item[1].min_completed_months)[0]
    revised = dict(published)
    revised[first_band_id] = first_band.model_copy(update={"surcharge_pct": Decimal("2.5")})

    old_reader = _CountingReader(operation, _pin("b"))
    new_reader = _CountingReader(operation, _pin("c"), bands=revised)
    old_bands = load_recargo_bands(operation=_operation(old_reader))
    new_bands = load_recargo_bands(operation=_operation(new_reader))

    assert new_reader.band_reads == 1, "a new generation must be read, not served from the old one"
    assert new_bands[0].surcharge_pct == Decimal("2.5")
    assert old_bands[0].surcharge_pct != Decimal("2.5")


def test_the_counter_detects_a_table_read_per_call(operation: PinnedAuthorityOperation) -> None:
    """Each distinct generation costs one read, so a per-call read would show as a count per call."""
    readers = [_CountingReader(operation, _pin(marker)) for marker in "def"]
    for reader in readers:
        load_recargo_bands(operation=_operation(reader))

    assert [reader.band_reads for reader in readers] == [1, 1, 1]
