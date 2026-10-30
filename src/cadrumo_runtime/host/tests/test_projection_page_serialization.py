"""Paged worker serialization preserves canonical bytes and safe refusal."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError, model_serializer
from pydantic_core import PydanticSerializationError

from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.projection_pages import ProjectionPageRequest, project_document_page

from ..operation_host import _projection_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _NestedProjection(BaseModel):
    label: str
    nested: list[dict[str, int | str]]


class _BadProjection(BaseModel):
    value: str = "ignored"
    replacement: Any

    @model_serializer(mode="plain")
    def _serialize(self) -> Any:
        return self.replacement


def test_paged_projection_has_the_same_canonical_bytes_as_full_validation() -> None:
    result = _NestedProjection(label="ñ" * 40_000, nested=[{"amount": 19, "name": "áé"}])
    full = _projection_document(result, paged=False)
    paged = _projection_document(result, paged=True)
    assert canonical_json_bytes(paged) == canonical_json_bytes(full)
    first = project_document_page(paged, ProjectionPageRequest())
    assert first.decode() == canonical_json_bytes(full)[: len(first.decode())]


@pytest.mark.parametrize("replacement", [[], 7])
def test_paged_projection_refuses_invalid_root(replacement: Any) -> None:
    with pytest.raises(ValidationError):
        _projection_document(_BadProjection(replacement=replacement), paged=True)


def test_paged_projection_refuses_malformed_serializer_output() -> None:
    with pytest.raises(PydanticSerializationError):
        _projection_document(_BadProjection(replacement={"bad": object()}), paged=True)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_paged_projection_refuses_nonfinite_values_at_canonical_encoder(bad: float) -> None:
    with pytest.raises(ProfileAccessRefusedError) as refused:
        project_document_page({"bad": bad}, ProjectionPageRequest())
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_paged_projection_refuses_excessive_nesting_at_canonical_encoder() -> None:
    nested: dict[str, Any] = {}
    for _ in range(10_000):
        nested = {"next": nested}
    with pytest.raises(ProfileAccessRefusedError) as refused:
        project_document_page(nested, ProjectionPageRequest())
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def test_pydantic_serializer_normalizes_nonfinite_and_nonstring_keys_consistently() -> None:
    result = _BadProjection(replacement={1: float("nan")})
    assert _projection_document(result, paged=True) == _projection_document(result, paged=False)
