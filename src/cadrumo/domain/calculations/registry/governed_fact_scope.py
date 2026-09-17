"""The governed facts a registry validation resolves its vocabulary from.

Runtime resolves a governed fact through the published authority artifact. A
registry *validation* runs before that artifact is available to it: compiling a
candidate revision produces the indexed generation, and decoding its addressed
components is how that generation becomes usable. A validator that reaches for
ambient authority from inside either path would cross the candidate or pinned
generation it is meant to validate.

So a validation scopes the facts it is validating against, the same way a
compilation scopes its legal and source catalogues. Outside that scope nothing
is supplied: a vocabulary check with no scoped facts refuses rather than falling
back to the bundle it must not read.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from threading import RLock
from typing import Final, Protocol
from weakref import ReferenceType, ref

from ....core.errors.hierarchy import InternalInvariantError
from .facts.resolution import GovernedFactQuery, ResolvedGovernedFact, resolve_governed_fact
from .facts.schema import GovernedFactCatalogue
from .schema_references import TemporalSupportEnvelope

UNPUBLISHED_CANDIDATE_DIGEST: Final = "0" * 64
"""The identity a candidate carries while it is being validated.

A candidate has no published identity digest yet -- deriving one is what
publication does -- and a resolution taken from it is consumed by the validator
and discarded, never retained as provenance. The constant makes that state
explicit instead of borrowing the digest of the artifact being replaced.
"""


class GovernedFactSource(Protocol):
    """Anything that can resolve one typed governed-fact query."""

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one typed governed-fact query."""
        ...


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CandidateFactAuthority:
    """Resolve governed facts from the catalogue currently being validated."""

    catalogue: GovernedFactCatalogue
    support: TemporalSupportEnvelope
    authority_digest: str = UNPUBLISHED_CANDIDATE_DIGEST
    _resolutions: dict[GovernedFactQuery, ResolvedGovernedFact] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        """Resolve one query against the candidate, never against the bundle."""
        cached = self._resolutions.get(query)
        if cached is not None:
            return cached
        resolved = resolve_governed_fact(
            self.catalogue,
            query,
            authority_digest=self.authority_digest,
            support=self.support,
        )
        if len(self._resolutions) >= 1024:
            self._resolutions.pop(next(iter(self._resolutions)))
        self._resolutions[query] = resolved
        return resolved


_VALIDATING_GOVERNED_FACTS: ContextVar[GovernedFactSource | None] = ContextVar(
    "validating_governed_facts",
    default=None,
)


@contextmanager
def validating_governed_facts(authority: GovernedFactSource) -> Generator[None]:
    """Scope registry validation to the governed facts it is validating."""
    token = _VALIDATING_GOVERNED_FACTS.set(authority)
    try:
        yield
    finally:
        _VALIDATING_GOVERNED_FACTS.reset(token)


def governed_facts_in_scope() -> GovernedFactSource | None:
    """Return the facts of the validation in progress, or ``None`` outside one."""
    return _VALIDATING_GOVERNED_FACTS.get()


def cache_governed_projection[**P, R](
    *,
    maxsize: int = 64,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Cache a projection by its authority incarnation and hashable arguments.

    Weak ownership prevents the cache from retaining complete old generations.
    Candidate objects with the same unpublished digest remain distinct owners.
    The selected owner stays scoped throughout construction of a cache miss.
    """
    if maxsize < 1:
        raise ValueError("projection cache size must be positive")

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        cache: OrderedDict[tuple[object, ...], tuple[ReferenceType[GovernedFactSource], R]] = OrderedDict()
        lock = RLock()

        @wraps(function)
        def projected(*args: P.args, **kwargs: P.kwargs) -> R:
            owner = governed_facts_in_scope()
            if owner is None:
                raise InternalInvariantError(
                    f"{getattr(function, '__qualname__', type(function).__name__)} requires an explicit "
                    "generation-pinned governed-fact scope"
                )
            key = (id(owner), args, tuple(sorted(kwargs.items())))
            with lock:
                cached = cache.get(key)
                if cached is not None and cached[0]() is owner:
                    cache.move_to_end(key)
                    return cached[1]
                with validating_governed_facts(owner):
                    result = function(*args, **kwargs)
                try:
                    owner_ref = ref(owner)
                except TypeError:
                    return result
                cache[key] = (owner_ref, result)
                cache.move_to_end(key)
                while len(cache) > maxsize:
                    cache.popitem(last=False)
                return result

        return projected

    return decorate


__all__ = [
    "UNPUBLISHED_CANDIDATE_DIGEST",
    "CandidateFactAuthority",
    "GovernedFactSource",
    "cache_governed_projection",
    "governed_facts_in_scope",
    "validating_governed_facts",
]
