"""Truthful fail-closed inventory calculation-source readiness tests."""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from .._source_readiness import inventory_source_readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_readiness_acknowledges_persistence_but_refuses_missing_connection() -> None:
    readiness = inventory_source_readiness()

    assert readiness.ready is False
    assert readiness.source_kind is BindingSourceKind.INVENTORY
    assert "encrypted schema-v3 persistence is complete" in readiness.reason
    assert "complete acquisition cost" in readiness.reason
    assert "closing authority" in readiness.reason
    assert "resolver" in readiness.reason
    assert "source-mesh enrollment" in readiness.reason
    assert "registry bindings" in readiness.reason
    assert "calculation orchestration" in readiness.reason
    assert "source-ownership refusal" in readiness.reason
    assert "not persisted" not in readiness.reason
