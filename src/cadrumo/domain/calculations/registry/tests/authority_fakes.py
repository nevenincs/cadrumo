"""Reusable strict fakes for generation-pinned authority consumer tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from .....core.hashing import content_hash_hex
from ..authority_artifact import AuthorityComponentQuery, AuthorityGenerationPin


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
            raise LookupError(f"authority component is unavailable for query {query!r}") from exc

    def component_queries(self) -> tuple[AuthorityComponentQuery, ...]:
        """Return the fake's deterministic component addresses."""
        return tuple(self.components)
