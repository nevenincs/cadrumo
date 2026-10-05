"""A record's positive gate belongs to the selected revision's casillas."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection

from ..compiler.loader import load_modelo_directory, load_shared_catalogues
from ..pipeline.record_design_intermediate import load_record_design_intermediate
from ..pipeline.semantic_map import load_semantic_map
from ..pipeline.semantic_map_validation import validate_semantic_map

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def source_join_inputs():
    root = Path("src/cadrumo/_data")
    catalogues = load_shared_catalogues(root / "registry/aeat")
    definition = load_modelo_directory(root / "registry/aeat/modelos/347")
    semantic = load_semantic_map(Path("dev/registry/mappings/modelo_347/2025"))
    intermediate = load_record_design_intermediate(
        root,
        catalogues.sources,
        source_ref=semantic.source_ref,
        filing_year=2025,
        design_epoch="2025",
    )
    inspection = RegistryRevisionInspection.from_revision(
        modelo=definition,
        revision=definition.revisions["2025-y-siguientes"],
        source_root=root,
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    return semantic, intermediate, inspection


def test_selected_revision_casilla_can_gate_a_source_record(source_join_inputs) -> None:
    semantic, intermediate, inspection = source_join_inputs
    gate = sorted(inspection.casilla_ids)[0]
    record = semantic.records[0].model_copy(update={"requires_positive_casilla_id": gate})
    selected = semantic.model_copy(update={"records": (record, *semantic.records[1:])})
    validated = validate_semantic_map(selected, intermediate, inspection)
    assert validated.records[0].requires_positive_casilla_id == gate


def test_foreign_casilla_cannot_gate_a_source_record(source_join_inputs) -> None:
    semantic, intermediate, inspection = source_join_inputs
    record = semantic.records[0].model_copy(update={"requires_positive_casilla_id": "foreign-missing-gate"})
    selected = semantic.model_copy(update={"records": (record, *semantic.records[1:])})
    with pytest.raises(RegistryValidationError, match="positive gate references unknown target-revision casilla"):
        validate_semantic_map(selected, intermediate, inspection)
