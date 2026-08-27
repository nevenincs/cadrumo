"""The data-inventory checklist resolves unresolved bindings to profile keys.

A registry binding id names the registry's internal consumer of a profile
fact. The operator-facing surfaces need the FACT, and only this layer holds the
binding definitions that name it, so the mapping belongs here rather than at
the entrypoint that renders it.
"""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.profile_grounding import binding_profile_keys
from ...aggregation import AtribucionMemberSourceResolver
from .._data_inventory import _LIVE_OBSERVATION_SOURCE_KINDS, _profile_keys_for_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _a_committed_profile_binding():
    """Return one real committed ``(binding, revision, keys)`` triple."""
    for model in bundled_authority().modelos:
        for revision in model.revisions.values():
            for binding in revision.bindings:
                keys = binding_profile_keys(binding)
                if keys:
                    return binding, revision, keys
    pytest.fail("no committed profile binding names a profile key")


def test_the_registry_declares_a_profile_binding_that_names_profile_keys() -> None:
    """Anchor: the tests below are vacuous if no such binding is committed."""
    binding, _revision, keys = _a_committed_profile_binding()

    assert keys
    assert str(binding.id)


def test_unresolved_binding_ids_map_to_the_profile_keys_they_consume() -> None:
    binding, revision, keys = _a_committed_profile_binding()

    assert _profile_keys_for_bindings(revision, (binding.id,)) == keys


def test_an_empty_binding_set_maps_to_no_keys() -> None:
    """The positive control.

    A mapping that ignored its binding-id filter and returned every profile
    key in the revision would satisfy the test above and fail this one.
    """
    _binding, revision, _keys = _a_committed_profile_binding()

    assert _profile_keys_for_bindings(revision, ()) == ()


def test_profile_backed_atribucion_resolver_is_not_a_live_observation_source() -> None:
    """The real M184 resolver ownership must stay out of the local-observation bucket."""
    assert AtribucionMemberSourceResolver.owned_sources == (BindingSourceKind.ATRIBUCION_MEMBER,)
    assert set(AtribucionMemberSourceResolver.owned_sources).isdisjoint(_LIVE_OBSERVATION_SOURCE_KINDS)
