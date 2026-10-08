"""An optional generated-record gate is attested only when authored."""

from __future__ import annotations

from pathlib import Path

import pytest

from ..export_fragment_provenance_projection import _normalise_semantic_map_record
from ..semantic_map import load_semantic_map_for_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_positive_casilla_gate_changes_only_its_present_record_projection() -> None:
    root = Path(__file__).resolve().parents[2] / "mappings" / "modelo_131" / "2024"
    semantic_map = load_semantic_map_for_revision(root, "2024")
    did = next(record for record in semantic_map.records if record.record_identity == "DID")
    payload = did.model_dump(mode="json")
    assert payload["requires_positive_casilla_id"] == "15"
    with_gate = _normalise_semantic_map_record(payload)
    assert with_gate["requires_positive_casilla_id"] == "15"
    without_gate = _normalise_semantic_map_record({**payload, "requires_positive_casilla_id": None})
    assert "requires_positive_casilla_id" not in without_gate
    assert with_gate != without_gate
    assert _normalise_semantic_map_record({**payload, "requires_positive_casilla_id": "16"}) != with_gate
