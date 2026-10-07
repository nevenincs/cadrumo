"""Saved registry geometry keeps semantic predecessor forms and complete fields."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ....core.hashing import content_hash_hex
from ...calculations.registry.authority import bundled_indexed_authority
from ...calculations.registry.revision_contracts import DeclaredPredecessor, NoPredecessor
from ..calculation_revision_rendering import CalculationRenderingSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    ("modelo_id", "predecessor_type"),
    (("303", DeclaredPredecessor), ("131", NoPredecessor)),
    ids=("declared-predecessor", "grounded-root"),
)
def test_saved_rendering_snapshot_roundtrips_complete_registry_fields(
    modelo_id: str,
    predecessor_type: type[DeclaredPredecessor | NoPredecessor],
) -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot(modelo_id, filing_year=2026, period="1T")
        assert isinstance(snapshot.revision.predecessor, predecessor_type)
        original = CalculationRenderingSnapshot.capture(
            snapshot, authority_generation=operation.pin().logical_generation
        )
        loaded = CalculationRenderingSnapshot.model_validate_json(original.model_dump_json())

    assert loaded == original
    assert loaded.registry_snapshot.revision.localization_key == snapshot.revision.localization_key
    assert loaded.registry_snapshot.revision.predecessor == snapshot.revision.predecessor
    assert loaded.labels == original.labels
    assert loaded.revision_directory_ids == tuple(sorted(snapshot.modelo.directory_revision_ids))


def test_an_existing_valid_rendering_without_directory_context_keeps_its_shape_and_digest() -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("720", filing_year=2026, period="0A")
        original = CalculationRenderingSnapshot.capture(
            snapshot, authority_generation=operation.pin().logical_generation
        )
        payload = original.model_dump(mode="json")
        del payload["revision_directory_ids"]
        payload["rendering_digest"] = content_hash_hex(
            {"registry": payload["registry_snapshot"], "labels": payload["labels"]}
        )
        loaded = CalculationRenderingSnapshot.model_validate_json(json.dumps(payload))

    assert loaded.revision_directory_ids is None
    assert loaded.model_dump(mode="json") == payload


def test_directory_context_is_bound_to_the_saved_rendering_digest() -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("131", filing_year=2026, period="1T")
        original = CalculationRenderingSnapshot.capture(
            snapshot, authority_generation=operation.pin().logical_generation
        )
        payload = original.model_dump(mode="json")
        payload["revision_directory_ids"] = sorted((*payload["revision_directory_ids"], "1900"))

        with pytest.raises(ValidationError, match="saved rendering metadata digest"):
            CalculationRenderingSnapshot.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("missing_context", (False, True), ids=("missing-sibling", "missing-directory"))
def test_a_saved_selected_view_refuses_missing_sibling_authority(missing_context: bool) -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("303", filing_year=2026, period="1T")
        original = CalculationRenderingSnapshot.capture(
            snapshot, authority_generation=operation.pin().logical_generation
        )
        payload = original.model_dump(mode="json")
        if missing_context:
            del payload["revision_directory_ids"]
        else:
            payload["revision_directory_ids"] = [str(snapshot.revision.id)]

        with pytest.raises(ValidationError, match="dangling review reference"):
            CalculationRenderingSnapshot.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("modelo_id", ("303", "131"), ids=("declared-predecessor", "grounded-root"))
def test_saved_rendering_snapshot_refuses_flat_predecessor_objects(modelo_id: str) -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot(modelo_id, filing_year=2026, period="1T")
        original = CalculationRenderingSnapshot.capture(
            snapshot, authority_generation=operation.pin().logical_generation
        )
        payload = original.model_dump(mode="json")
        predecessor = snapshot.revision.predecessor
        assert isinstance(predecessor, DeclaredPredecessor | NoPredecessor)
        payload["registry_snapshot"]["revision"]["predecessor"] = {
            name: getattr(predecessor, name) for name in type(predecessor).model_fields
        }

        with pytest.raises(ValidationError, match="predecessor must be the revision id"):
            CalculationRenderingSnapshot.model_validate_json(json.dumps(payload))
