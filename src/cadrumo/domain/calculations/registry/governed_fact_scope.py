"""The governed facts a registry validation resolves its vocabulary from.

Runtime resolves a governed fact through the published authority artifact. A
registry *validation* runs before that artifact is available to it: compiling a
candidate revision produces the artifact, and decoding the published artifact is
how the artifact becomes an authority in the first place. A validator that
reaches for the bundle from inside either path deadlocks the reader --
:func:`~cadrumo.domain.calculations.registry.authority_artifact.read_shared_authority_artifact`
holds the shared-artifact lock while it validates the decoded document, so a
validator calling ``bundled_authority`` asks a non-reentrant lock for the very
artifact it is in the middle of producing.

So a validation scopes the facts it is validating against, the same way a
compilation scopes its legal and source catalogues. Outside that scope nothing
is supplied: a vocabulary check with no scoped facts refuses rather than falling
back to the bundle it must not read.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Final, Protocol

from .facts.resolution import GovernedFactQuery, ResolvedGovernedFact, resolve_governed_fact
from .facts.schema import GovernedFactCatalogue

UNPUBLISHED_CANDIDATE_DIGEST: Final = "0" * 64
"""The identity a candidate carries while it is being validated.

A candidate has no published identity digest yet -- deriving one is what
publication does -- and a resolution taken from it is consumed by the validator
and discarded, never retained as provenance. The constant makes that state
explicit instead of borrowing the digest of the artifact being replaced.
"""


class GovernedFactSource(Protocol):
    """Anything that can resolve one typed governed-fact query."""

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact: ...


@dataclass(frozen=True, slots=True)
class CandidateFactAuthority:
    """Resolve governed facts from the catalogue currently being validated."""

    catalogue: GovernedFactCatalogue
    authority_digest: str = UNPUBLISHED_CANDIDATE_DIGEST

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one query against the candidate, never against the bundle."""
        return resolve_governed_fact(self.catalogue, query, authority_digest=self.authority_digest)


_VALIDATING_GOVERNED_FACTS: ContextVar[GovernedFactSource | None] = ContextVar(
    "validating_governed_facts",
    default=None,
)


@contextmanager
def validating_governed_facts(authority: GovernedFactSource) -> Iterator[None]:
    """Scope registry validation to the governed facts it is validating."""
    token = _VALIDATING_GOVERNED_FACTS.set(authority)
    try:
        yield
    finally:
        _VALIDATING_GOVERNED_FACTS.reset(token)


def governed_facts_in_scope() -> GovernedFactSource | None:
    """Return the facts of the validation in progress, or ``None`` outside one."""
    return _VALIDATING_GOVERNED_FACTS.get()


__all__ = [
    "UNPUBLISHED_CANDIDATE_DIGEST",
    "CandidateFactAuthority",
    "GovernedFactSource",
    "governed_facts_in_scope",
    "validating_governed_facts",
]
