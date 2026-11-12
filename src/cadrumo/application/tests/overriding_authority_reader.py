"""Serve a published authority generation with a closed set of substituted components.

Test support for consumers that must be exercised against an authority shape
the published generation does not carry: every component outside the
substitution set is served by the published reader unchanged, under the same
generation pin.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.calculations.registry.authority_artifact import AuthorityComponentQuery, AuthorityGenerationPin
from ...domain.calculations.registry.authority_store import SQLiteAuthorityReader
from ...domain.calculations.registry.errors import RegistrySnapshotError


class OverridingComponentReader:
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
