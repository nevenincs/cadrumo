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


def build_profile_grounding_index(
    authority: ValidatedRegistryAuthority,
) -> Mapping[str, ProfileKeyGrounding]:
    """Invert every profile-sourced binding into a per-profile-key grounding map.

    Walks every :class:`ModeloDefinition` registered on the supplied
    :class:`ValidatedRegistryAuthority` and every revision's bindings; a key
    never consumed by any profile binding is simply absent (the flow renders
    no legal zone for it — nothing is invented).
    """
    modelos: dict[str, set[str]] = {}
    legal_refs: dict[str, set[str]] = {}
    source_refs: dict[str, set[str]] = {}

    for definition in authority.modelos:
        for revision in definition.revisions.values():
            for binding in revision.bindings:
                if binding.source is not BindingSourceKind.PROFILE:
                    continue
                for key in _selector_profile_keys(binding):
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


def _selector_profile_keys(binding: DataBindingDefinition) -> tuple[str, ...]:
    """Return the value-consuming profile keys named by a profile binding's selector."""
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
        keys.extend(str(item) for item in cast(list[object] | tuple[object, ...], composite_raw) if item)
    return tuple(keys)


__all__ = ["ProfileKeyGrounding", "build_profile_grounding_index"]
