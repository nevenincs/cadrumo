"""Binding keys are schema paths; gating keys are selector tokens.

The two renderers are not interchangeable, and confusing them fails silently:
a key routed through the wrong lookup resolves to nothing and is passed
through unchanged, so the surface still shows a raw identifier while every
assertion about "not the binding id" keeps passing.

These tests pin the distinction itself rather than either renderer alone.
"""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.preflight import (
    format_profile_path_requirements,
    format_profile_selector_requirements,
)

from ....core.resources import resources
from cadrumo.domain.calculations.registry.profile_grounding import binding_profile_keys
from ....domain.user_profile.loader import load_user_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A field the deadline engine gates on, named by its declared selector token.
_GATING_SELECTOR = "has_employees"
#: The same field's schema path.
_GATING_PATH = "withholding.has_employees"


def _schema():
    return load_user_profile_schema()


def test_a_selector_token_resolves_only_through_the_selector_renderer() -> None:
    schema = _schema()

    by_selector = format_profile_selector_requirements((_GATING_SELECTOR,), schema=schema)
    by_path = format_profile_path_requirements((_GATING_SELECTOR,), schema=schema)

    assert by_selector != (_GATING_SELECTOR,), "the selector renderer failed to resolve a real token"
    assert by_path == (_GATING_SELECTOR,), "a bare token must not resolve through the path renderer"


def test_a_schema_path_resolves_only_through_the_path_renderer() -> None:
    schema = _schema()

    by_path = format_profile_path_requirements((_GATING_PATH,), schema=schema)
    by_selector = format_profile_selector_requirements((_GATING_PATH,), schema=schema)

    assert by_path != (_GATING_PATH,), "the path renderer failed to resolve a real schema path"
    assert by_selector == (_GATING_PATH,), "a path must not resolve through the selector renderer"


def _a_binding_key_naming_a_schema_field() -> str:
    """Return one committed binding's profile key that names a real field."""
    schema = _schema()
    schema_paths = frozenset(schema.field_paths)
    for model in resources().modelos.authority.modelos:
        for revision in model.revisions.values():
            for binding in revision.bindings:
                for key in binding_profile_keys(binding):
                    if key in schema_paths:
                        return key
    pytest.fail("no committed profile binding names a resolvable schema field")


def test_a_real_binding_key_renders_as_a_label_through_the_path_renderer() -> None:
    """The case the modelo requires and calculate guidance surfaces actually hit."""
    schema = _schema()
    key = _a_binding_key_naming_a_schema_field()

    rendered = format_profile_path_requirements((key,), schema=schema)

    assert rendered != (key,), "a binding key naming a real field must not pass through raw"


def test_the_selector_renderer_would_have_left_that_binding_key_raw() -> None:
    """The regression this phase exists to prevent, pinned explicitly.

    Both binding-key surfaces were originally wired to the selector renderer.
    Nothing failed, because the keys simply passed through and the assertions
    in place only checked that the output was not the BINDING ID.
    """
    schema = _schema()
    key = _a_binding_key_naming_a_schema_field()

    assert format_profile_selector_requirements((key,), schema=schema) == (key,)
