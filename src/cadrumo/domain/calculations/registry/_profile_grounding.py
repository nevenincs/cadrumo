"""Reverse grounding index from profile keys to their consuming registry bindings.

The interactive profile setup flow renders a legal-provenance zone on every
question page: which modelos consume the fact being asked, and under which
legal provisions. That grounding is never hand-authored — it is a projection
over the validated registry: every ``source = "profile"``
:class:`DataBindingDefinition` names the profile key(s) it consumes in its
selector and carries its own ``legal_refs`` / ``source_refs``, so the index
inverts that relation once per :class:`ValidatedRegistryAuthority` and the
flow reads it at flow-compile time.

Only value-consuming selector members contribute (the scalar ``profile_key``
and the composite ``profile_keys``). A ``required_when_profile_key`` gate
names a key to *test*, not to *file*, so counting it would over-claim the
gated key's legal basis; it is deliberately excluded.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG, Modelo
from ....core.aggregation import BindingSourceKind
from ._authority import ValidatedRegistryAuthority
from ._binding_selector_utils import selector_as_dict
from ._bindings import ProfileSelector
from ._schema import DataBindingDefinition


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
_grounding_index_cache: dict[int, Mapping[str, ProfileKeyGrounding]] = {}
_grounding_index_cache_lock = threading.Lock()


def build_profile_grounding_index(
    authority: ValidatedRegistryAuthority,
) -> Mapping[str, ProfileKeyGrounding]:
    """Invert every profile-sourced binding into a per-profile-key grounding map.

    Walks every :class:`ModeloDefinition` registered on the supplied
    :class:`ValidatedRegistryAuthority` and every revision's bindings; a key
    never consumed by any profile binding is simply absent (the flow renders
    no legal zone for it — nothing is invented).

    Memoised per *authority* instance: this is a full registry-wide walk, and
    the profile-preflight report path (blocking gate, ``config profile
    preflight``, ``app modelo readiness``) can call it several times per
    operator invocation. :class:`ValidatedRegistryAuthority` is an unhashable
    ``@dataclass(slots=True)`` with no ``__weakref__`` slot (its default
    ``eq``-driven ``__hash__ = None`` rules out ``functools.lru_cache``, and
    its ``slots=True`` rules out :func:`weakref.finalize`-based eviction), so
    the cache keys on ``id(authority)`` in a small FIFO-bounded dict instead:
    at most :data:`_GROUNDING_INDEX_CACHE_MAXSIZE` entries are retained,
    evicting the oldest when a new authority instance is seen. In practice at
    most one or two distinct authority instances are ever live in a process
    (a fresh instance appears only on an explicit registry reload), so the
    bound is never exercised in production and exists purely so a long-running
    process or test session cannot grow this cache unbounded.
    """
    cache_key = id(authority)
    with _grounding_index_cache_lock:
        cached = _grounding_index_cache.get(cache_key)
        if cached is not None:
            return cached
    index = _compute_profile_grounding_index(authority)
    with _grounding_index_cache_lock:
        _grounding_index_cache[cache_key] = index
        while len(_grounding_index_cache) > _GROUNDING_INDEX_CACHE_MAXSIZE:
            oldest_key = next(iter(_grounding_index_cache))
            del _grounding_index_cache[oldest_key]
    return index


def _compute_profile_grounding_index(
    authority: ValidatedRegistryAuthority,
) -> Mapping[str, ProfileKeyGrounding]:
    """Perform the uncached registry walk :func:`build_profile_grounding_index` memoises."""
    modelos: dict[str, set[str]] = {}
    legal_refs: dict[str, set[str]] = {}
    source_refs: dict[str, set[str]] = {}

    for definition in authority.modelos:
        for revision in definition.revisions.values():
            for binding in revision.bindings:
                if binding.source is not BindingSourceKind.PROFILE:
                    continue
                for key in binding_profile_keys(binding):
                    modelos.setdefault(key, set()).add(definition.id)
                    legal_refs.setdefault(key, set()).update(binding.legal_refs)
                    source_refs.setdefault(key, set()).update(binding.source_refs)

    return {
        key: ProfileKeyGrounding(
            profile_key=key,
            modelos=tuple(Modelo(code) for code in sorted(modelos[key])),
            legal_refs=tuple(sorted(legal_refs[key])),
            source_refs=tuple(sorted(source_refs[key])),
        )
        for key in sorted(modelos)
    }


def binding_profile_keys(binding: DataBindingDefinition) -> tuple[str, ...]:
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
    selector = binding.selector
    if isinstance(selector, ProfileSelector):
        scalar = (selector.profile_key,) if selector.profile_key is not None else ()
        return scalar + tuple(selector.profile_keys)
    mapping = selector_as_dict(binding)
    scalar_raw = mapping.get("profile_key")
    composite_raw = mapping.get("profile_keys")
    keys: list[str] = []
    if isinstance(scalar_raw, str) and scalar_raw:
        keys.append(scalar_raw)
    if isinstance(composite_raw, (list, tuple)):
        # CAST-RATIONALE-PROFILE-GROUNDING-COMPOSITE-KEYS: isinstance narrows to
        # list/tuple but not the element type; each item is coerced via str()
        # below regardless of its actual type.
        # nosemgrep: no-cast-in-domain-application
        keys.extend(str(item) for item in cast(list[object] | tuple[object, ...], composite_raw) if item)
    return tuple(keys)


__all__ = ["ProfileKeyGrounding", "binding_profile_keys", "build_profile_grounding_index"]
