"""Modelo 349 calculation display and export parity for operator rows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from ....application.filing._draft_construction import _filing_binding_values
from ....core import Modelo, Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.snapshot import build_snapshot
from ....domain.filing.schema import ModeloCasillaProvenance, ModeloDraft, ModeloValue, ModeloValueKind, compute_modelo_draft_id
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.row_models import Modelo349OperadorRow
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.submission import ModeloDraftStatus
from ....entrypoints.cli import (
    calculation_revision_lines,
    calculation_revision_payload,
)
from .._calculation_actions import _suppress_m349_row_field_template_outputs
from .._calculation_helpers import build_typed_observations
from .._revision_replay_inputs import _m349_detail_row_replay_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
_BUCKET_ID = "9c4acfdc-abb7-4206-8755-1d8c027b6114"  # was 'm349-display-export-parity'
_PROFILE_TAX_ID = "12345678Z"
_DECL_NUMERO_OPERADORES: CasillaId = validated_casilla_id(
    "decl.numero-operadores",
    surface="test_m349_calculation_display_export",
)
_DECL_IMPORTE_OPERACIONES: CasillaId = validated_casilla_id(
    "decl.importe-operaciones",
    surface="test_m349_calculation_display_export",
)
_DECL_NUMERO_RECTIFICACIONES: CasillaId = validated_casilla_id(
    "decl.numero-rectificaciones",
    surface="test_m349_calculation_display_export",
)
_DECL_IMPORTE_RECTIFICACIONES: CasillaId = validated_casilla_id(
    "decl.importe-rectificaciones",
    surface="test_m349_calculation_display_export",
)


def _m349_snapshot(*, period: str) -> RegistrySnapshot:
    authority = bundled_authority()
    modelo = authority.modelo(Modelo.M349.value)
    return build_snapshot(
        modelo,
        authority.catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period=period,
    )


def _work_unit(*, period: str, snapshot: RegistrySnapshot) -> WorkUnit:
    filing_period = Period.from_year_and_code(2026, period)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="349",
            filing_year=2026,
            period=filing_period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("349"),
        filing_year=2026,
        period=filing_period,
        revision_id=snapshot.revision.id,
        name=f"349-2026-{period}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _calculated_revision(
    *,
    period: str,
    country: str,
    iva_id: str,
    name: str,
    clave: str,
    amount: Decimal,
) -> tuple[RegistrySnapshot, WorkUnit, CalculationRevision]:
    snapshot = _m349_snapshot(period=period)
    work_unit = _work_unit(period=period, snapshot=snapshot)
    row = Modelo349OperadorRow.model_validate(
        {
            "codigo_pais": country,
            "nif_comunitario": iva_id,
            "razon_social": name,
            "clave_operacion": clave,
            "importe": amount,
        }
    )
    binding_values = {
        "iva-349-declarante-numero-operadores": Decimal("1"),
        "iva-349-declarante-importe-operaciones": amount,
        "iva-349-declarante-numero-rectificaciones": Decimal("0"),
        "iva-349-declarante-importe-rectificaciones": Decimal("0"),
    }
    inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    engine_result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": work_unit.period.end_date},
        binding_values=binding_values,
    )
    raw_casilla_values = dict(engine_result.values)
    raw_observations = build_typed_observations(engine_result=engine_result, snapshot=snapshot)

    assert raw_casilla_values["op.codigo-pais"] == Decimal("0")
    assert raw_casilla_values["op.nif-comunitario"] == Decimal("0")
    assert raw_casilla_values["op.clave-operacion"] == Decimal("0")
    assert raw_casilla_values["op.base-imponible"] == Decimal("0")

    input_values = {casilla_id: str(value) for casilla_id, value in inputs.items()}
    binding_overrides = {binding_id: str(value) for binding_id, value in binding_values.items()}
    detail_rows = (row,)
    legacy_revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=input_values,
            binding_overrides=binding_overrides,
            casilla_values=raw_casilla_values,
            detail_rows=detail_rows,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=input_values,
        binding_overrides=binding_overrides,
        casilla_values=raw_casilla_values,
        observations=raw_observations,
        detail_rows=detail_rows,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    calc_lines: Any = calculation_revision_lines
    calc_payload: Any = calculation_revision_payload
    legacy_rendered_revision = "\n".join(calc_lines(legacy_revision))
    legacy_payload = calc_payload(legacy_revision)
    assert "casilla\top." not in legacy_rendered_revision
    assert "casilla\trect." not in legacy_rendered_revision
    assert not any(casilla_id.startswith("op.") for casilla_id in legacy_payload.casilla_values)
    assert not any(casilla_id.startswith("rect.") for casilla_id in legacy_payload.casilla_values)

    casilla_values, observations = _suppress_m349_row_field_template_outputs(
        work_unit=work_unit,
        revision=snapshot.revision,
        casilla_values=raw_casilla_values,
        observations=raw_observations,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=input_values,
        binding_overrides=binding_overrides,
        casilla_values=casilla_values,
        detail_rows=detail_rows,
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return (
        snapshot,
        work_unit,
        CalculationRevision(
            calculation_revision_id=revision_id,
            work_unit_id=work_unit.work_unit_id,
            state=CalculationRevisionState.BORRADOR,
            input_values_by_casilla_id=input_values,
            binding_overrides=binding_overrides,
            casilla_values=casilla_values,
            observations=observations,
            detail_rows=detail_rows,
            created_at=_CLOCK,
            updated_at=_CLOCK,
            filing_instance_evidence=None,
            source_provenance=(),
        ),
    )


def _approved_draft(
    *,
    snapshot: RegistrySnapshot,
    work_unit: WorkUnit,
    revision: CalculationRevision,
) -> ModeloDraft:
    values = tuple(
        ModeloValue(
            casilla_id=casilla_id,
            value=value,
            kind=ModeloValueKind.INHERITED,
            source="registry calculation",
        )
        for casilla_id, value in sorted(revision.casilla_values.items())
    )
    replay_inputs = _m349_detail_row_replay_inputs(revision=revision, work_unit=work_unit)
    bindings_by_id = {binding.id: binding for binding in snapshot.revision.bindings}
    binding_values = tuple(_filing_binding_values(replay_inputs, bindings_by_id))
    casilla_provenance = tuple(
        ModeloCasillaProvenance(
            casilla_id=casilla.id,
            formula_id=casilla.formula,
            legal_refs=tuple(casilla.legal_refs),
            source_refs=tuple(casilla.source_refs),
        )
        for casilla in sorted(snapshot.revision.casillas, key=lambda item: item.id)
    )
    schema_version = f"registry:{snapshot.modelo.id}:{snapshot.revision.id}"
    snapshot_ref = RegistrySnapshotRef(
        modelo="349",
        revision_id=snapshot.revision.id,
        modelo_year=2026,
        period=work_unit.period.registry_token,
    )
    draft_id = compute_modelo_draft_id(
        modelo="349",
        period=work_unit.period,
        profile_tax_id=_PROFILE_TAX_ID,
        snapshot_ref=snapshot_ref,
        values=values,
        binding_values=binding_values,
    )
    return ModeloDraft(
        draft_id=draft_id,
        modelo="349",
        period=work_unit.period,
        profile_tax_id=_PROFILE_TAX_ID,
        subject_tax_id=_PROFILE_TAX_ID,
        snapshot_ref=snapshot_ref,
        status=ModeloDraftStatus.APROBADO,
        values=values,
        binding_values=binding_values,
        casilla_provenance=casilla_provenance,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        schema_version=schema_version,
        approved_at=_CLOCK,
        approved_by="operator",
    )
