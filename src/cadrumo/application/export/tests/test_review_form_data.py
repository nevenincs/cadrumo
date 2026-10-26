"""Saved forms retain scalar channels without executing current-source resolution."""

from datetime import UTC, datetime

import pytest

from ....domain.calculations.registry.bindings import CasillaObservation, CasillaObservationValueKind
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.calculation_revision_rendering import CalculationRenderingSnapshot
from ...storage.calc_sheets.tests.test_form_context_fields import snapshot_with_binding_context
from ...storage.calc_sheets.tests.test_form_workbook import form_source as form_source
from ..review_form_data import capture_review_form

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("saved_binding", [None, "-125.37"])
def test_binding_context_preserves_saved_whole_scalar_or_unknown(form_source, saved_binding):
    snapshot, _ = form_source
    snapshot, block, binding = snapshot_with_binding_context(snapshot, unused=True)
    overrides = {} if saved_binding is None else {binding.id: saved_binding}
    rendering = CalculationRenderingSnapshot.capture(snapshot, authority_generation="e" * 64)
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides=overrides,
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
            rendering_snapshot=rendering,
        ),
        work_unit_id="a" * 64,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        binding_overrides=overrides,
        rendering_snapshot=rendering,
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=datetime(2026, 10, 7, tzinfo=UTC),
        updated_at=datetime(2026, 10, 7, tzinfo=UTC),
    )
    saved = capture_review_form(revision)
    assert saved is not None
    assert next(item.value for item in saved.contexts if item.id == block.id) == saved_binding


def test_source_text_observation_is_retained_even_without_numeric_or_manual_map(form_source):
    snapshot, _ = form_source
    first = snapshot.revision.casillas[0]
    snapshot = snapshot.model_copy(
        update={
            "revision": snapshot.revision.model_copy(
                update={
                    "casillas": (
                        first.model_copy(update={"data_type": CasillaDataType.TEXT}),
                        *snapshot.revision.casillas[1:],
                    ),
                }
            )
        }
    )
    rendering = CalculationRenderingSnapshot.capture(snapshot, authority_generation="e" * 64)
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id="a" * 64,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=None,
            source_provenance=(),
            rendering_snapshot=rendering,
        ),
        work_unit_id="a" * 64,
        registry_snapshot_ref=snapshot.snapshot_ref,
        state=CalculationRevisionState.BORRADOR,
        rendering_snapshot=rendering,
        observations=(
            CasillaObservation(
                casilla_id=first.id,
                value="28001",
                value_kind=CasillaObservationValueKind.TEXT,
                legal_refs=("test-law",),
                source_refs=("test-source",),
            ),
        ),
        filing_instance_evidence=None,
        source_provenance=(),
        created_at=datetime(2026, 10, 7, tzinfo=UTC),
        updated_at=datetime(2026, 10, 7, tzinfo=UTC),
    )
    saved = capture_review_form(revision)
    assert saved is not None
    assert next(item.value for item in saved.scalars if item.id == first.id) == "28001"
    assert not revision.input_values_by_casilla_id and not revision.casilla_values
