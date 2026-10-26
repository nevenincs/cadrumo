"""Unit proof for the shared ``ValidationError`` rendering helper.

:func:`~dev.registry.pipeline.pydantic_error_detail.validation_error_detail`
is the one place three pipeline modules (``export_fragment_provenance.py``,
``render_profile.py``, ``semantic_map.py``) build a message from a
caught :exc:`~pydantic.ValidationError`. These tests pin its contract
directly, independent of any one caller's schema: it never reaches
``str(exc)``'s truncated payload dump, and it still names the failing field
and message.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError, model_validator

from ..pipeline.pydantic_error_detail import validation_error_detail

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _FieldModel(BaseModel):
    name: str
    count: int


class _CoherenceModel(BaseModel):
    identity: str
    flag: bool

    @model_validator(mode="after")
    def _require_flag(self) -> _CoherenceModel:
        if not self.flag:
            raise ValueError("flag must be set")
        return self


def _raised(model: type[BaseModel], payload: object) -> ValidationError:
    with pytest.raises(ValidationError) as excinfo:
        model.model_validate(payload)
    return excinfo.value


def test_field_level_error_names_its_location_and_message() -> None:
    exc = _raised(_FieldModel, {"name": "x", "count": "not-a-number"})

    assert (
        validation_error_detail(exc) == "count: Input should be a valid integer, unable to parse string as an integer"
    )


def test_missing_field_error_names_its_location() -> None:
    exc = _raised(_FieldModel, {"count": 1})

    assert validation_error_detail(exc) == "name: Field required"


def test_multiple_errors_are_joined_in_order() -> None:
    exc = _raised(_FieldModel, {})

    assert validation_error_detail(exc) == "name: Field required; count: Field required"


def test_model_level_coherence_error_never_carries_a_sibling_fields_value() -> None:
    """The mechanism the three real call sites rely on, pinned directly.

    ``identity`` is a value the failing ``_require_flag`` validator never
    inspects. ``str(exc)`` embeds it anyway (via pydantic's truncated
    ``input_value=`` dump of the whole model); :func:`validation_error_detail`
    must not.
    """
    probe_value = "nif-Z"
    exc = _raised(_CoherenceModel, {"identity": probe_value, "flag": False})

    assert probe_value in str(exc), "premise: the raw ValidationError must actually carry the value"
    assert validation_error_detail(exc) == "Value error, flag must be set"
    assert probe_value not in validation_error_detail(exc)


def test_detail_never_carries_pydantics_own_added_framing() -> None:
    """Pin the absence of pydantic's own framing, not just of any one secret.

    ``ValidationError.__str__`` appends ``[type=..., input_value=...,
    input_type=...]`` and a documentation URL after the validator's own
    message.
    """
    exc = _raised(_CoherenceModel, {"identity": "irrelevant", "flag": False})

    detail = validation_error_detail(exc)
    assert "input_value" not in detail
    assert "input_type" not in detail
    assert "errors.pydantic.dev" not in detail
