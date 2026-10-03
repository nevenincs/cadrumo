"""A calculated encrypted revision crosses the public snapshot without loss."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.calculation_projection import ModeloCalculationSnapshot
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.entrypoints.cli._modelo_rendering import calculation_revision_lines, calculation_revision_payload
from cadrumo.entrypoints.cli.runtime_modelo_calculation import calculation_snapshot_lines, calculation_snapshot_payload
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import (
    DEFAULT_130_BASELINE_INPUTS,
    DEFAULT_130_BINDING_VALUES,
    T1,
    Repos,
    calculation_ports_for_test,
    seed_work_unit,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_real_encrypted_calculation_snapshot_preserves_existing_result_facts(repos: Repos) -> None:
    """The public JSON round-trip retains the current CLI projection's facts."""
    work_units, revisions, _, _, events = repos
    unit = seed_work_unit(work_units)
    with calculation_ports_for_test(
        bucket_id=unit.bucket_id,
        work_unit_repository=work_units,
        calculation_repository=revisions,
        bucket_event_repository=events,
    ) as ports:
        revision = calculate_modelo_revision(
            unit.work_unit_id,
            actor="operator-A",
            casilla_inputs=DEFAULT_130_BASELINE_INPUTS,
            binding_values=DEFAULT_130_BINDING_VALUES,
            ports=ports,
            clock=T1,
        )
        stored = revisions.load().get(revision.calculation_revision_id)
        assert stored is not None
        assert stored == revision
        selected = work_units.load().get(unit.work_unit_id)
        assert selected is not None
        with override_settings(cadrumo_output_language="es"):
            snapshot = ModeloCalculationSnapshot.from_revision(stored, work_unit=selected, operation=ports.operation)
            current = calculation_revision_payload(stored, operation=ports.operation, work_unit=selected)
            current_lines = calculation_revision_lines(stored, operation=ports.operation, work_unit=selected)
        with override_settings(cadrumo_output_language="ca"):
            another_language = ModeloCalculationSnapshot.from_revision(
                stored, work_unit=selected, operation=ports.operation
            )

    parsed = ModeloCalculationSnapshot.model_validate_json(canonical_json_bytes(snapshot.model_dump(mode="json")))
    assert parsed == snapshot == another_language
    with override_settings(cadrumo_output_language="es"):
        assert calculation_snapshot_payload(parsed, language=OutputLanguage.ES).model_dump(mode="json") == (
            current.model_dump(mode="json")
        )
        assert calculation_snapshot_lines(parsed, language=OutputLanguage.ES) == current_lines
    assert snapshot.bucket_id == unit.bucket_id
    assert snapshot.work_unit_id == current.work_unit_id
    assert snapshot.calculation_revision_id == current.calculation_revision_id
    assert snapshot.registry_snapshot_ref.model_dump(mode="json") == current.registry_snapshot_ref.model_dump(
        mode="json"
    )
    assert {
        item.key: item.value.decimal for item in snapshot.casilla_values if isinstance(item.value, PublicDecimal)
    } == (current.casilla_values)
    assert {item.key: item.value for item in snapshot.binding_overrides} == current.binding_overrides
    assert {item.key: item.value for item in snapshot.relation_overrides} == current.relation_overrides
    assert {item.key: item.value for item in snapshot.input_values_by_casilla_id} == (
        current.input_values_by_casilla_id
    )
    assert tuple(
        (
            item.casilla_id,
            item.value.decimal if isinstance(item.value, PublicDecimal) else item.value,
            item.formula_id,
            item.op,
            item.operand_refs,
            item.operand_casilla_refs,
            tuple(value.decimal for value in item.operand_values),
            item.legal_refs,
            item.source_refs,
            item.absent_by_design,
        )
        for item in snapshot.observations
    ) == tuple(
        (
            item.casilla_id,
            item.value,
            item.formula_id,
            item.op,
            item.operand_refs,
            item.operand_casilla_refs,
            item.operand_values,
            item.legal_refs,
            item.source_refs,
            item.absent_by_design,
        )
        for item in current.observations
    )
    assert tuple((item.role, item.casilla_id, item.value.decimal) for item in snapshot.result_summary) == tuple(
        (item.role, item.casilla_id, item.value) for item in current.result_summary
    )
    assert all(item.label_keys for item in snapshot.result_summary)
    assert tuple(
        (item.index, item.row_type, {field.key: field.value for field in item.fields}) for item in snapshot.detail_rows
    ) == tuple((item.index, item.row_type, item.fields) for item in current.detail_rows)
    assert tuple(item.model_dump(mode="json") for item in snapshot.source_provenance) == tuple(
        item.model_dump(mode="json") for item in current.source_provenance
    )
    assert snapshot.created_at.isoformat() == current.created_at
    assert snapshot.updated_at.isoformat() == current.updated_at
    assert snapshot.casilla_values
    assert any(item.formula_id is not None and isinstance(item.value, PublicDecimal) for item in snapshot.observations)

    with pytest.raises(ValidationError, match="mismatched work-unit"):
        ModeloCalculationSnapshot.model_validate(snapshot.model_dump(mode="python") | {"work_unit_id": "a" * 64})
    with pytest.raises(ValidationError, match="duplicate names"):
        ModeloCalculationSnapshot.model_validate(
            snapshot.model_dump(mode="python")
            | {"casilla_values": (*snapshot.casilla_values, snapshot.casilla_values[0])}
        )
