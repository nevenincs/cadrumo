"""``app modelo requires`` names the missing profile fact, not the binding id.

A registry binding id names the registry's internal consumer of a profile
fact. The operator has to supply the FACT, so the unresolved-coefficient
warning must name the profile field by its operator label with whatever legal
grounding the registry carries, while the binding ids remain available on the
machine-readable notice context.
"""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.profile_grounding import binding_profile_keys, build_profile_grounding_index

from ....application.user_profile.preflight import format_profile_selector_requirements
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.user_profile.loader import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _profile_bindings_with_keys():
    """Return committed profile bindings that name at least one profile key."""
    authority = bundled_authority()
    found = []
    for definition in authority.modelos:
        for revision in definition.revisions.values():
            for binding in revision.bindings:
                keys = binding_profile_keys(binding)
                if keys:
                    found.append((binding, keys))
    return found


def test_the_registry_declares_profile_bindings_that_name_profile_keys() -> None:
    """Anchor: every assertion below is vacuous over an empty binding set."""
    assert _profile_bindings_with_keys(), "no committed profile binding names a profile key"


def test_a_profile_binding_key_renders_as_a_label_rather_than_the_binding_id() -> None:
    """The rendered warning text names the fact, and never the binding id.

    Run over every committed profile binding that names a key, so a single
    unlabelled field anywhere in the registry fails this rather than only the
    one example a hand-picked fixture would cover.
    """
    schema = load_user_profile_schema()
    grounding_index = build_profile_grounding_index(bundled_authority())

    for binding, keys in _profile_bindings_with_keys():
        rendered = format_profile_selector_requirements(
            keys,
            schema=schema,
            grounding_index=grounding_index,
        )
        assert len(rendered) == len(keys)
        for text in rendered:
            assert str(binding.id) not in text
