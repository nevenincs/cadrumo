"""Reverse grounding index from profile keys to their consuming registry bindings.

The interactive profile setup flow renders a legal-provenance zone on every
question page: which modelos consume the fact being asked, and under which
legal provisions. That grounding is never hand-authored — it is a projection
over the validated registry: every ``source = "profile"``
:class:`BindingDefinition` names the profile key(s) it consumes in its
selector and carries its own ``legal_refs`` / ``source_refs``, so the index
inverts that relation once per published authority generation and the
flow reads it at flow-compile time.

Only value-consuming selector members contribute (the scalar ``profile_key``
and the composite ``profile_keys``). A ``required_when_profile_key`` gate
names a key to *test*, not to *file*, so counting it would over-claim the
gated key's legal basis; it is deliberately excluded.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, ValidationError

from ....core.aggregation import BindingSourceKind
from ....core.modelo import Modelo
from ....core.models import STRICT_FROZEN_CONFIG
from .authority import PinnedAuthorityOperation
from .binding_selector_utils import provider_member
from .errors import RegistryValidationError
from .profile_bindings import ProfileProvider
from .schema import BindingDefinition


def _runtime_object(value: object) -> object:
    """Capture a provider before retaining its malformed-boundary fallback."""
    return value


class ProfileKeyGrounding(BaseModel):
    """Union grounding for one profile key across every consuming binding.

    ``modelos`` names every modelo with at least one revision whose
    ``source = "profile"`` binding consumes the key; ``legal_refs`` and
    ``source_refs`` are the sorted unions of those bindings' grounding.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_key: str = Field(min_length=1)
    modelos: tuple[Modelo, ...]
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]


_GROUNDING_INDEX_CACHE_MAXSIZE = 4
# How often a deferred warm-up asks again whether it may continue.
_DEFERRED_POLL_SECONDS = 0.05


@dataclass(frozen=True, slots=True)
class _Flight:
    """One walk under way: ``done`` once it ends, ``joined`` once a read waits for it."""

    done: threading.Event = field(default_factory=threading.Event)
    joined: threading.Event = field(default_factory=threading.Event)


_grounding_index_cache: dict[str, Mapping[str, ProfileKeyGrounding]] = {}
# The one walk under way per generation. A flight exists only while its owner
# is computing, so a caller that waits on one waits on work already begun.
_grounding_index_flights: dict[str, _Flight] = {}
_grounding_index_cache_lock = threading.Lock()


def build_profile_grounding_index(
    operation: PinnedAuthorityOperation,
) -> Mapping[str, ProfileKeyGrounding]:
    """Invert every profile-sourced binding into a per-profile-key grounding map.

    Walks every revision the operation's pinned generation publishes and each
    revision's bindings; a key never consumed by any profile binding is simply
    absent (the flow renders no legal zone for it — nothing is invented).

    Memoised per published logical generation: this is a full registry-wide
    walk, and the profile-preflight report path (blocking gate, ``config
    profile preflight``, ``app modelo readiness``) can call it several times
    per operator invocation. Every lease of the same generation yields the same
    index, so the cache keys on the generation's logical identity in a small
    FIFO-bounded dict: at most :data:`_GROUNDING_INDEX_CACHE_MAXSIZE` entries
    are retained, evicting the oldest when a new generation is published into a
    long-running process.

    The walk is single-flight per generation: a caller that finds another
    thread already walking the same generation waits for that walk instead of
    repeating it, and computes the index itself if that walk fails or is
    abandoned.
    """
    cache_key = operation.generation.logical_generation
    while True:
        claim = _claim_grounding_walk(cache_key)
        if isinstance(claim, _CachedGrounding):
            return claim.index
        if isinstance(claim, _WalkUnderWay):
            # A deferred warm-up stops deferring once a read waits for it. The
            # owner ends its flight whether it cached, failed or was abandoned;
            # without a cache entry this caller claims the next walk.
            claim.flight.joined.set()
            claim.flight.done.wait()
            continue
        # This walk polls no abandonment and never defers, so it returns an index or raises.
        index = _walk_and_cache(operation, claim, abandoned=None, deferred=None)
        if index is not None:
            return index


def warm_profile_grounding_index(
    operation: PinnedAuthorityOperation,
    *,
    abandoned: Callable[[], bool],
    deferred: Callable[[], bool] | None = None,
) -> bool:
    """Compute and cache the operation generation's index ahead of the first reader.

    Never waits on another walk: when the index is already cached, or another
    thread is already walking this generation, it returns at once. ``abandoned``
    is polled between revisions; once it answers true the walk stops, nothing is
    cached, and any reader that joined the walk computes the index itself.

    ``deferred`` is also polled between revisions. While it answers true the
    walk pauses before its next revision, so foreground work does not share the
    interpreter with a registry-wide decode it is not waiting for. A read that
    joins the walk ends the pause at once: that read waits for this walk, so
    the walk never defers to the work that needs it.

    Returns:
        Whether this call computed and cached the index.
    """
    claim = _claim_grounding_walk(operation.generation.logical_generation)
    if not isinstance(claim, _OwnedWalk):
        return False
    return _walk_and_cache(operation, claim, abandoned=abandoned, deferred=deferred) is not None


@dataclass(frozen=True, slots=True)
class _CachedGrounding:
    index: Mapping[str, ProfileKeyGrounding]


@dataclass(frozen=True, slots=True)
class _WalkUnderWay:
    flight: _Flight


@dataclass(frozen=True, slots=True)
class _OwnedWalk:
    cache_key: str
    flight: _Flight


def _claim_grounding_walk(cache_key: str) -> _CachedGrounding | _WalkUnderWay | _OwnedWalk:
    """Find the cached index, the walk under way, or claim the walk for the caller."""
    with _grounding_index_cache_lock:
        cached = _grounding_index_cache.get(cache_key)
        if cached is not None:
            return _CachedGrounding(cached)
        flight = _grounding_index_flights.get(cache_key)
        if flight is not None:
            return _WalkUnderWay(flight)
        flight = _Flight()
        _grounding_index_flights[cache_key] = flight
        return _OwnedWalk(cache_key, flight)


def _walk_and_cache(
    operation: PinnedAuthorityOperation,
    claim: _OwnedWalk,
    *,
    abandoned: Callable[[], bool] | None,
    deferred: Callable[[], bool] | None,
) -> Mapping[str, ProfileKeyGrounding] | None:
    """Run the claimed walk, cache a completed index and always release the claim.

    Returns ``None``, caching nothing, when ``abandoned`` stopped the walk.
    """
    try:
        pause = None if deferred is None else _deferral(deferred, claim.flight.joined)
        index = _compute_profile_grounding_index(operation, abandoned=abandoned, pause=pause)
        if index is None:
            return None
        with _grounding_index_cache_lock:
            _grounding_index_cache[claim.cache_key] = index
            while len(_grounding_index_cache) > _GROUNDING_INDEX_CACHE_MAXSIZE:
                oldest_key = next(iter(_grounding_index_cache))
                del _grounding_index_cache[oldest_key]
        return index
    finally:
        with _grounding_index_cache_lock:
            del _grounding_index_flights[claim.cache_key]
        claim.flight.done.set()


def _deferral(deferred: Callable[[], bool], joined: threading.Event) -> Callable[[Callable[[], bool]], None]:
    """Build the between-revision pause of a deferred walk; a joined read ends it."""

    def pause(abandoned: Callable[[], bool]) -> None:
        while not joined.is_set() and not abandoned() and deferred():
            joined.wait(_DEFERRED_POLL_SECONDS)

    return pause


def _never_abandoned() -> bool:
    return False


def _walk_abandoned(
    abandoned: Callable[[], bool] | None,
    pause: Callable[[Callable[[], bool]], None] | None,
) -> bool:
    """Wait at the revision boundary while ``pause`` holds, then report whether the walk was abandoned."""
    if pause is not None:
        pause(abandoned or _never_abandoned)
    return abandoned is not None and abandoned()


def _fold_profile_bindings(
    bindings: Iterable[BindingDefinition],
    modelo_id: str,
    *,
    modelos: dict[str, set[str]],
    legal_refs: dict[str, set[str]],
    source_refs: dict[str, set[str]],
) -> None:
    """Add one revision's profile bindings to the per-key modelo, legal and source sets."""
    for binding in bindings:
        if binding.source is not BindingSourceKind.PROFILE:
            continue
        for key in binding_profile_keys(binding):
            modelos.setdefault(key, set()).add(modelo_id)
            legal_refs.setdefault(key, set()).update(binding.legal_refs)
            source_refs.setdefault(key, set()).update(binding.source_refs)


def _compute_profile_grounding_index(
    operation: PinnedAuthorityOperation,
    *,
    abandoned: Callable[[], bool] | None = None,
    pause: Callable[[Callable[[], bool]], None] | None = None,
) -> Mapping[str, ProfileKeyGrounding] | None:
    """Perform the uncached registry walk :func:`build_profile_grounding_index` memoises.

    Returns ``None`` once ``abandoned`` answers true between revisions.
    ``pause`` runs before each revision and returns once the walk may go on.
    """
    modelos: dict[str, set[str]] = {}
    legal_refs: dict[str, set[str]] = {}
    source_refs: dict[str, set[str]] = {}

    for modelo_id, revision_id in operation.revision_ids():
        if _walk_abandoned(abandoned, pause):
            return None
        _fold_profile_bindings(
            operation.revision(modelo_id, revision_id).bindings,
            modelo_id,
            modelos=modelos,
            legal_refs=legal_refs,
            source_refs=source_refs,
        )

    return {
        key: ProfileKeyGrounding(
            profile_key=key,
            modelos=tuple(Modelo(code) for code in sorted(modelos[key])),
            legal_refs=tuple(sorted(legal_refs[key])),
            source_refs=tuple(sorted(source_refs[key])),
        )
        for key in sorted(modelos)
    }


def binding_profile_keys(binding: BindingDefinition) -> tuple[str, ...]:
    """Return the value-consuming profile keys named by a profile binding's selector.

    Only value-consuming selector members contribute: the scalar
    ``profile_key`` and the composite ``profile_keys``. A
    ``required_when_profile_key`` gate names a key to TEST, not to file, so
    including it would over-claim that key's legal basis.

    Shared with the surfaces that must name the profile fact behind an
    unresolved profile binding, rather than the binding's own identifier - the
    grounding index below inverts the same relation across the whole
    registry, and a per-binding caller needs the same extraction without
    building that index.
    """
    selector = _runtime_object(binding.provider)
    if isinstance(selector, BaseModel) and not isinstance(selector, ProfileProvider):
        # A different binding-source family's selector (manual_input, relation,
        # ...); its shape never carries a profile key, so no read is needed.
        return ()
    if not isinstance(selector, ProfileProvider):
        if binding.source is not BindingSourceKind.PROFILE:
            return ()
        # A ``source = "profile"`` binding whose selector has not been
        # hydrated into the typed model by construction (e.g. built via
        # ``model_construct``). Re-validate through the declared model --
        # ``ProfileProvider`` -- rather than reading the raw mapping with
        # string-literal keys, so a field the model no longer declares fails
        # loud instead of silently under-reporting this key's grounding.
        try:
            selector = provider_member(binding, ProfileProvider)
        except ValidationError as exc:
            raise RegistryValidationError(
                f"binding {binding.id!r} has malformed profile selector: {exc}",
            ) from exc
    scalar = (selector.profile_key,) if selector.profile_key is not None else ()
    return scalar + tuple(selector.profile_keys)


__all__ = [
    "ProfileKeyGrounding",
    "binding_profile_keys",
    "build_profile_grounding_index",
    "warm_profile_grounding_index",
]
