"""Reusable strict fakes for generation-pinned authority consumer tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from .....core.filing_year import FILING_YEAR_MAX, FILING_YEAR_MIN
from .....core.hashing import content_hash_hex
from ..authority_artifact import AuthorityComponentQuery, AuthorityGenerationPin, SnapshotGlobalsComponentQuery
from ..schema import SnapshotGlobalCatalogues, SupportedFilingYearsCatalogue

FIXTURE_SNAPSHOT_GLOBALS = SnapshotGlobalCatalogues(
    supported_filing_years=SupportedFilingYearsCatalogue(floor=FILING_YEAR_MIN, horizon=FILING_YEAR_MAX),
)
"""Registry globals admitting every representable filing year.

A fixture that declares no snapshot globals still needs the single support
envelope governed-fact resolution reads; this one neither gates nor projects
any coordinate the fixture chooses.
"""


@dataclass(slots=True)
class FakeAuthorityComponentReader:
    """Small in-memory reader that preserves the production pinning contract."""

    components: dict[AuthorityComponentQuery, object]
    logical_generation: str = field(default_factory=lambda: content_hash_hex({"generation": "fixture"}))
    reader_incarnation: str = field(default_factory=lambda: content_hash_hex({"reader": "fixture"}))
    loads: list[AuthorityComponentQuery] = field(default_factory=list)

    def pin(self) -> AuthorityGenerationPin:
        return AuthorityGenerationPin(self.logical_generation, self.reader_incarnation)

    def load(self, query: AuthorityComponentQuery, *, pin: AuthorityGenerationPin) -> object:
        if pin != self.pin():
            raise RuntimeError("authority component query used a stale or foreign generation pin")
        self.loads.append(query)
        try:
            return self.components[query]
        except KeyError as exc:
            if isinstance(query, SnapshotGlobalsComponentQuery):
                return FIXTURE_SNAPSHOT_GLOBALS
            raise LookupError(f"authority component is unavailable for query {query!r}") from exc

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        """Return the fake's deterministic component addresses."""
        return tuple(self.components)
