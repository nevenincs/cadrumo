"""Lease the published authority with one modelo revision lifted to filing reach.

A test of a filing-grade behaviour (a verification predicate, an export) of an
edition held below filing grade needs that behaviour live. This support lifts
the one revision's declared grade in the leased operation only, never in the
registry: the declared grade is neither read as earned nor changed, and every
other component is the published one. The lease is taken on the process-shared
reader, so profile records opened under the published generation stay readable.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from ...core.authority_grade import RegistryAuthorityGrade
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.authority_artifact import ModeloRevisionComponentQuery
from ...domain.calculations.registry.authority_store import SQLiteAuthorityReader
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .overriding_authority_reader import OverridingComponentReader


@contextmanager
def filing_reach_operation(*, modelo_id: str, filing_year: int, period: str) -> Generator[PinnedAuthorityOperation]:
    """Lease the published generation with the revision selected for one filing coordinate at filing grade."""
    with bundled_indexed_authority().lease_operation() as published:
        revision = published.revision_for_context(modelo_id, filing_year=filing_year, period=period)
        operation = published
        if revision.effective_authority_grade is not RegistryAuthorityGrade.FILING:
            reader = published.reader
            assert isinstance(reader, SQLiteAuthorityReader)
            directory = published.modelo_directory(modelo_id)
            lifted = revision.model_copy(update={"authority_grade": RegistryAuthorityGrade.FILING})
            operation = PinnedAuthorityOperation(
                OverridingComponentReader(
                    reader, {ModeloRevisionComponentQuery(directory.modelo_id, str(revision.id)): lifted}
                ),
                published.generation,
            )
        with validating_governed_facts(operation):
            yield operation
