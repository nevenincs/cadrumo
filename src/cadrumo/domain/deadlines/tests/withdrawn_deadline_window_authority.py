"""A published registry authority with one modelo's deadline windows for one filing year withdrawn.

Whether a consumer borrows another year's deadline can only be shown on a year
the registry declares no window for, and the shipped registry's unauthored
years are exactly the ones authoring closes next. A test that names one of them
as its example starts failing the day that window is authored, for a reason
that has nothing to do with the guard it proves. This support builds the
missing year instead.

It leases the published generation through the runtime reader and substitutes
exactly the components that carry the year's windows: the modelo's directory
metadata, which the deadline projection and the revision selector read, and
each revision that declares a window for that year. Every other component is
served by the published reader unchanged.

The result is served under a generation identity of its own. The deadline
projection is indexed by generation, so an operation sharing the published
identity would read, or leave behind for later tests, a projection of the other
content.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from ....core.hashing import content_hash_hex
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.authority_artifact import (
    AuthorityComponentQuery,
    AuthorityGenerationPin,
    ModeloDirectoryComponentQuery,
    ModeloRevisionComponentQuery,
)
from ...calculations.registry.authority_location import bundled_authority_descriptor_path
from ...calculations.registry.authority_store import SQLiteAuthorityReader
from ...calculations.registry.errors import RegistrySnapshotError
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.schema_deadlines import DeadlineWindowDefinition


class _WithdrawingComponentReader:
    """Serve a published generation under its own identity, with a closed set of components replaced."""

    def __init__(
        self,
        reader: SQLiteAuthorityReader,
        *,
        published: AuthorityGenerationPin,
        generation: AuthorityGenerationPin,
        replacements: Mapping[AuthorityComponentQuery, object],
    ) -> None:
        self._reader = reader
        self._published = published
        self._generation = generation
        self._replacements = dict(replacements)

    def pin(self) -> AuthorityGenerationPin:
        return self._generation

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        if pin != self._generation:
            raise RegistrySnapshotError("authority component query crossed an operation generation boundary")
        if query in self._replacements:
            return self._replacements[query]
        return self._reader.load(query, pin=self._published)

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        return self._reader.component_queries()


def _without_year(
    windows: tuple[DeadlineWindowDefinition, ...],
    filing_year: int,
) -> tuple[DeadlineWindowDefinition, ...]:
    return tuple(window for window in windows if window.filing_year != filing_year)


@contextmanager
def withdrawn_deadline_window_operation(*, modelo_id: str, filing_year: int) -> Iterator[PinnedAuthorityOperation]:
    """Lease the published generation with every window ``modelo_id`` declares for ``filing_year`` withdrawn.

    Raises:
        LookupError: When the published modelo declares no window for the year.
            There is then nothing to withdraw, and a test built on the result
            would prove nothing about a missing window.
    """
    reader = SQLiteAuthorityReader(bundled_authority_descriptor_path())
    try:
        with reader.lease() as published_generation:
            published = PinnedAuthorityOperation(reader, published_generation)
            directory = published.modelo_directory(modelo_id)
            declaring = tuple(
                metadata
                for metadata in directory.revisions
                if any(window.filing_year == filing_year for window in metadata.deadline_windows)
            )
            if not declaring:
                raise LookupError(f"modelo {modelo_id!r} declares no deadline window for {filing_year} to withdraw")
            replacements: dict[AuthorityComponentQuery, object] = {
                ModeloDirectoryComponentQuery(directory.modelo_id): directory.model_copy(
                    update={
                        "revisions": tuple(
                            metadata.model_copy(
                                update={"deadline_windows": _without_year(metadata.deadline_windows, filing_year)},
                            )
                            for metadata in directory.revisions
                        ),
                    },
                ),
            }
            for metadata in declaring:
                revision = published.revision(directory.modelo_id, str(metadata.id))
                replacements[ModeloRevisionComponentQuery(directory.modelo_id, str(metadata.id))] = revision.model_copy(
                    update={"deadline_windows": _without_year(revision.deadline_windows, filing_year)},
                )
            generation = AuthorityGenerationPin(
                logical_generation=content_hash_hex(
                    {
                        "published": published_generation.logical_generation,
                        "withdrawn_deadline_windows": {"modelo": directory.modelo_id, "filing_year": filing_year},
                    },
                ),
                reader_incarnation=published_generation.reader_incarnation,
            )
            operation = PinnedAuthorityOperation(
                _WithdrawingComponentReader(
                    reader,
                    published=published_generation,
                    generation=generation,
                    replacements=replacements,
                ),
                generation,
            )
            with validating_governed_facts(operation):
                yield operation
    finally:
        reader.close()
