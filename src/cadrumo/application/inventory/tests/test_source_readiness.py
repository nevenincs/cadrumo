"""Truthful fail-closed inventory calculation-source readiness tests."""

from __future__ import annotations

import pytest

from ....core import BindingSourceKind
from .._source_readiness import inventory_source_readiness

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_readiness_acknowledges_connected_source_but_refuses_missing_filing_rows() -> None:
    readiness = inventory_source_readiness()

    assert readiness.ready is False
    assert readiness.source_kind is BindingSourceKind.INVENTORY
    assert "encrypted schema-v3 persistence" in readiness.reason
    assert "canonical resolution" in readiness.reason
    assert "source-mesh enrollment" in readiness.reason
    assert "registry row bindings" in readiness.reason
    assert "calculation orchestration" in readiness.reason
    assert "source identity" in readiness.reason
    assert "caller-override refusal" in readiness.reason
    assert "filing readiness remains false" in readiness.reason
    assert "repeated M100 activity-row casillas" in readiness.reason
    assert "materialized, rendered, and verified" in readiness.reason
    assert "until the canonical inventory resolver" not in readiness.reason
    assert "not persisted" not in readiness.reason
