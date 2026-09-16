"""A published registry authority whose one modelo revision overrides a filing year's periods.

No shipped revision declares ``period_overrides`` yet, so the consumers that
must honour one cannot be exercised against the published generation alone.
This support leases the published generation through the runtime reader and
substitutes exactly two components: ONE revision whose selector overrides a
covered year and drops the leading flat token, and that modelo's directory
metadata carrying the same selector. Every other component is served by the
published reader unchanged. A consumer reading the flat tuple therefore picks
``1T``, a period the override says the edition does not file that year; a
consumer reading the override surface picks ``2T``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Final

from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_authority_descriptor_path
from ...domain.calculations.registry.authority_artifact import (
    AuthorityComponentQuery,
    AuthorityGenerationPin,
    ModeloDirectoryComponentQuery,
    ModeloRevisionComponentQuery,
)
from ...domain.calculations.registry.authority_store import SQLiteAuthorityReader
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.schema_references import PeriodOverride, PeriodSelector

OVERRIDE_MODELO: Final = "216"
"""The modelo whose revision the fixture overrides; every other component is published verbatim."""

OVERRIDE_REVISION: Final = "2024-y-siguientes"
"""The overridden revision -- the modelo's current provider, and open-ended."""

OVERRIDE_YEAR: Final = 2024
"""The filing year whose surface the override replaces."""

DROPPED_PERIOD: Final = "1T"
"""The first flat token the override removes -- what a flat read still returns."""

OVERRIDE_PERIODS: Final = ("2T", "3T", "4T")
"""The surface the overridden year actually serves."""


class _OverridingComponentReader:
    """Serve a published generation with a closed set of substituted components."""

    def __init__(self, reader: SQLiteAuthorityReader, overrides: Mapping[AuthorityComponentQuery, object]) -> None:
        self._reader = reader
        self._overrides = dict(overrides)

    def pin(self) -> AuthorityGenerationPin:
        return self._reader.pin()

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        if query in self._overrides:
            if pin != self._reader.pin():
                raise RegistrySnapshotError("authority component query crossed an operation generation boundary")
            return self._overrides[query]
        return self._reader.load(query, pin=pin)

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        return self._reader.component_queries()


@contextmanager
def period_override_operation(
    *,
    modelo_id: str,
    revision_id: str,
    year: int,
    periods: tuple[str, ...],
) -> Iterator[PinnedAuthorityOperation]:
    """Lease the published generation with one revision's year surface overridden.

    The selector is rebuilt through the typed constructor, so the override is
    validated exactly as an authored one would be. The revision's declared
    years and flat tuple are carried over unchanged, and the modelo directory
    the temporal selector reads carries the same selector.
    """
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        with reader.lease() as generation:
            published = PinnedAuthorityOperation(reader, generation)
            revision = published.revision(modelo_id, revision_id)
            declared = revision.period_selector
            selector = PeriodSelector(
                years=declared.years,
                year_from=declared.year_from,
                year_to=declared.year_to,
                periods=declared.periods,
                period_overrides=(PeriodOverride(year=year, periods=periods),),
            )
            directory = published.modelo_directory(modelo_id)
            overrides: dict[AuthorityComponentQuery, object] = {
                ModeloRevisionComponentQuery(directory.modelo_id, revision_id): revision.model_copy(
                    update={"period_selector": selector},
                ),
                ModeloDirectoryComponentQuery(directory.modelo_id): directory.model_copy(
                    update={
                        "revisions": tuple(
                            metadata.model_copy(update={"period_selector": selector})
                            if str(metadata.id) == revision_id
                            else metadata
                            for metadata in directory.revisions
                        ),
                    },
                ),
            }
            operation = PinnedAuthorityOperation(_OverridingComponentReader(reader, overrides), generation)
            with validating_governed_facts(operation):
                yield operation
    finally:
        reader.close()


@contextmanager
def override_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease the generation whose :data:`OVERRIDE_MODELO` overrides :data:`OVERRIDE_YEAR`."""
    with period_override_operation(
        modelo_id=OVERRIDE_MODELO,
        revision_id=OVERRIDE_REVISION,
        year=OVERRIDE_YEAR,
        periods=OVERRIDE_PERIODS,
    ) as operation:
        yield operation
