"""Authority serialization preserves factory-resolved values without recomputing them."""

from __future__ import annotations

import json
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from ..actividad_asset_disposal_bindings import ActivityAssetDisposalProvider
from ..authority_artifact import ModeloRevisionComponentQuery
from ..authority_component_codec import encode_authority_component
from .authored_editions import newest_authored_edition, revision_covering

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REVISION_ID = str(revision_covering("100", newest_authored_edition("100")).id)


def test_factory_backed_values_are_encoded_without_calling_the_factory() -> None:
    calls = 0

    def unavailable_factory() -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError("the original construction context is gone")

    class Component(BaseModel):
        kind: Literal["example"] = "example"
        resolved: str = Field(default_factory=unavailable_factory)
        items: list[str] = Field(default_factory=list)
        unchanged: str = "default"

    component = Component.model_construct(resolved="100", items=[])
    query = ModeloRevisionComponentQuery("100", _REVISION_ID)
    encoded = encode_authority_component(query, component)
    payload = json.loads(encoded)["payload"]
    assert payload == {"kind": "example", "resolved": "100", "items": []}
    assert Component.model_validate(payload) == component
    assert encode_authority_component(query, component) == encoded
    assert calls == 0


def test_governed_role_default_is_not_recomputed_during_publication() -> None:
    # The compiler has already materialized this value under its fact scope;
    # publishing the component does not itself borrow that scope.
    provider = ActivityAssetDisposalProvider.model_construct(modelo="100", target_casilla_id="0224")
    encoded = encode_authority_component(ModeloRevisionComponentQuery("100", _REVISION_ID), provider)
    assert json.loads(encoded)["payload"]["modelo"] == "100"
