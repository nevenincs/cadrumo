"""The profile validator holds the provider shape to the channel that carries it."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..bindings import validate_binding_selector_shape
from .binding_family_support import family_binding

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SCALAR = {"kind": "profile", "profile_key": "declarante.nombre"}
_COMPOSITE = {"kind": "profile", "profile_keys": ("declarante.apellido1", "declarante.apellido2"), "format": "join"}
_COLLECTION = {
    "kind": "profile",
    "profile_model": "RentaFamilyProfile",
    "collection": "descendants",
    "field": "tax_id",
    "repeating": True,
}


def test_a_scalar_on_a_scalar_channel_passes() -> None:
    binding = family_binding(_SCALAR, data_type="text", channel="text", aggregation={"op": "copy"})

    assert validate_binding_selector_shape(binding) == []


def test_a_repeating_collection_on_the_row_set_channel_passes() -> None:
    binding = family_binding(_COLLECTION, data_type="text", channel="row_set", aggregation={"op": "rows"})

    assert validate_binding_selector_shape(binding) == []


def test_a_composite_projection_on_the_text_channel_passes() -> None:
    binding = family_binding(_COMPOSITE, data_type="text", channel="text", aggregation={"op": "copy"})

    assert validate_binding_selector_shape(binding) == []


def test_a_repeating_collection_on_a_scalar_channel_is_refused() -> None:
    binding = family_binding(
        _COLLECTION,
        data_type="text",
        channel="text",
        aggregation={"op": "copy"},
        binding_id="test.profile.repeating-scalar",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.profile.repeating-scalar" in failures[0]
    assert "must use the row_set channel" in failures[0]


def test_a_scalar_selector_on_the_row_set_channel_is_refused() -> None:
    binding = family_binding(
        _SCALAR,
        data_type="text",
        channel="row_set",
        aggregation={"op": "rows"},
        binding_id="test.profile.scalar-rows",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.profile.scalar-rows" in failures[0]
    assert "requires a repeating collection" in failures[0]


def test_a_composite_projection_on_the_boolean_channel_is_refused() -> None:
    binding = family_binding(
        _COMPOSITE,
        data_type="boolean",
        channel="boolean",
        aggregation={"op": "copy"},
        binding_id="test.profile.composite-boolean",
    )

    failures = validate_binding_selector_shape(binding)

    assert len(failures) == 1
    assert "test.profile.composite-boolean" in failures[0]
    assert "must use the text channel" in failures[0]


def test_repeating_on_a_scalar_key_is_refused_at_hydration() -> None:
    with pytest.raises(ValidationError, match="repeating=true must declare profile_model"):
        family_binding({**_SCALAR, "repeating": True}, data_type="text", channel="row_set", aggregation={"op": "rows"})
