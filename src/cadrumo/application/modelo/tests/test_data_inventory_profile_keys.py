"""The data-inventory checklist resolves unresolved bindings to profile keys.

A registry binding id names the registry's internal consumer of a profile
fact. The operator-facing surfaces need the FACT, and only this layer holds the
binding definitions that name it, so the mapping belongs here rather than at
the entrypoint that renders it.
"""

from __future__ import annotations

import pytest

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.profile_grounding import binding_profile_keys
from ....domain.calculations.registry.tests.published_authority import (
    published_profile_schema,
    published_revision_definitions,
)
from ....domain.user_profile.schema import derived_selector_for_path
from ...aggregation.atribucion_member import AtribucionMemberSourceResolver
from ..data_inventory import LIVE_OBSERVATION_SOURCE_KINDS, profile_keys_for_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _a_committed_profile_binding():
    """Return one real committed ``(binding, revision, keys)`` triple naming only declared fields."""
    derived_selectors = published_profile_schema().derived_selectors
    for model in published_revision_definitions():
        for revision in model.revisions.values():
            for binding in revision.bindings:
                keys = binding_profile_keys(binding)
                if keys and all(derived_selector_for_path(key, derived_selectors) is None for key in keys):
                    return binding, revision, keys
    pytest.fail("no committed profile binding names a declared profile key")


def _a_committed_derived_binding():
    """Return one real committed binding whose profile key is an engine-derived path."""
    derived_selectors = published_profile_schema().derived_selectors
    for model in published_revision_definitions():
        for revision in model.revisions.values():
            for binding in revision.bindings:
                for key in binding_profile_keys(binding):
                    derived = derived_selector_for_path(key, derived_selectors)
                    if derived is not None:
                        return binding, revision, key, derived
    pytest.fail("no committed profile binding names a derived profile path")


def test_the_registry_declares_a_profile_binding_that_names_profile_keys() -> None:
    """Anchor: the tests below are vacuous if no such binding is committed."""
    binding, _revision, keys = _a_committed_profile_binding()

    assert keys
    assert str(binding.id)


def test_unresolved_binding_ids_map_to_the_profile_keys_they_consume() -> None:
    binding, revision, keys = _a_committed_profile_binding()

    derived_selectors = published_profile_schema().derived_selectors

    assert profile_keys_for_bindings(revision, (binding.id,), derived_selectors) == keys


def test_a_derived_path_is_named_by_the_facts_it_derives_from() -> None:
    """An operator cannot set a derived path, so the checklist names its source facts."""
    binding, revision, derived_key, derived = _a_committed_derived_binding()

    keys = profile_keys_for_bindings(revision, (binding.id,), published_profile_schema().derived_selectors)

    assert derived_key not in keys
    assert set(derived.derived_from) <= set(keys)


def test_an_empty_binding_set_maps_to_no_keys() -> None:
    """The positive control.

    A mapping that ignored its binding-id filter and returned every profile
    key in the revision would satisfy the test above and fail this one.
    """
    _binding, revision, _keys = _a_committed_profile_binding()

    assert profile_keys_for_bindings(revision, (), published_profile_schema().derived_selectors) == ()


def test_profile_backed_atribucion_resolver_is_not_a_live_observation_source() -> None:
    """The real M184 resolver ownership must stay out of the local-observation bucket."""
    assert AtribucionMemberSourceResolver.owned_sources == (BindingSourceKind.ATRIBUCION_MEMBER,)
    assert set(AtribucionMemberSourceResolver.owned_sources).isdisjoint(LIVE_OBSERVATION_SOURCE_KINDS)
