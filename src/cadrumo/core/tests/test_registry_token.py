"""Contract tests for the registry-projected token bases."""

from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from ..errors.hierarchy import CoreValidationError
from ..registry_token import StrictRegistryToken, TextProjectedRegistryToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Strict(StrictRegistryToken):
    __slots__ = ()


class _StrictFromRegistry(StrictRegistryToken):
    __slots__ = ()

    _projection_source = "registry"


class _Labelled(StrictRegistryToken):
    __slots__ = ()

    _vocabulary_label = "demo income-category"
    _refusal_error = ValueError


class _Text(TextProjectedRegistryToken):
    __slots__ = ()

    _empty_value_message = "demo letter must be a non-empty string"
    _boundary_subject = "demo letter"


def test_a_projected_token_is_its_text_and_carries_no_instance_dict() -> None:
    projected = _Strict.from_registry("general")

    assert projected == "general"
    assert projected.value == "general"
    assert projected.name == "general"
    assert not hasattr(projected, "__dict__")


def test_unprojected_construction_names_the_class_and_its_authority() -> None:
    with pytest.raises(TypeError, match=r"^_Strict tokens must be projected from the facts registry$"):
        _Strict("general")
    with pytest.raises(TypeError, match=r"^_StrictFromRegistry tokens must be projected from the registry$"):
        _StrictFromRegistry("general")


def test_an_empty_token_is_refused_with_the_default_or_declared_wording() -> None:
    with pytest.raises(ValueError, match=r"^_Strict token must be a non-empty string$"):
        _Strict.from_registry("")
    with pytest.raises(ValueError, match=r"^demo letter must be a non-empty string$"):
        _Text.from_registry("")


def test_a_strict_model_boundary_admits_only_projected_tokens_and_serializes_text() -> None:
    adapter = TypeAdapter(_Strict)
    projected = _Strict.from_registry("general")

    assert adapter.validate_python(projected) is projected
    assert adapter.dump_python(projected) == "general"
    with pytest.raises(ValidationError, match="_Strict must be a registry-projected token") as refused:
        adapter.validate_python("general")
    registered = refused.value.errors()[0]["ctx"]["error"].__cause__
    assert isinstance(registered, CoreValidationError)


def test_a_text_model_boundary_projects_stripped_text_and_refuses_blank_input() -> None:
    adapter = TypeAdapter(_Text)

    projected = adapter.validate_python(" g ")
    assert type(projected) is _Text
    assert projected == "g"
    with pytest.raises(ValidationError, match="demo letter must be a non-empty structural token"):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python(5)


def test_a_declared_label_and_refusal_error_word_every_diagnostic() -> None:
    with pytest.raises(TypeError, match=r"^demo income-category tokens must be projected from the facts registry$"):
        _Labelled("x")
    with pytest.raises(ValueError, match=r"^demo income-category token must be a non-empty string$"):
        _Labelled.from_registry("")
    with pytest.raises(ValidationError, match="demo income-category must be a registry-projected token"):
        TypeAdapter(_Labelled).validate_python("x")
