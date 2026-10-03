"""CLI client for one exact-profile registered Modelo calculation."""

from __future__ import annotations

from decimal import Decimal

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.calculation_projection import ModeloCalculationSnapshot
from ...application.modelo.operation_definitions import (
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    ModeloWorkCalculatePublicResultV2,
    ModeloWorkCalculateRequest,
)
from ...application.modelo.result_summary_payload import ResultSummaryRowPayload
from ...application.operations.public_scalar import PublicDecimal, PublicNamedScalar
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.calculations.registry.modelo_localization import require_modelo_localization
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ._modelo_payloads import CalculationRevisionPayload
from ._modelo_rendering import casilla_inline_trace, casilla_trace_verbose_line
from ._modelo_revision_payload_parts import DetailRowPayload, ObservationPayload, SourceProvenancePayload
from .modelo_revision_rendering import calculation_revision_state_label
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def run_modelo_work_calculation(
    client: RuntimeFrontendClient,
    request: ModeloWorkCalculateRequest,
    *,
    timeout: float = 120,
) -> RegisteredOperationCompletion[ModeloWorkCalculatePublicResultV2]:
    """Run the canonical calculation and validate its writer-returned public facts."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
        subject_ref=request.work_unit_id,
        result_type=ModeloWorkCalculatePublicResultV2,
        request_version=4,
        result_version=2,
        timeout=timeout,
    )
    result = completed.projection
    if (
        not isinstance(result, ModeloWorkCalculatePublicResultV2)
        or result.unit.bucket_id != str(client.profile_id)
        or result.work_unit_id != request.work_unit_id
        or result.unit.current_calculation_revision_id != result.calculation_revision_id
        or (result.revision_published and completed.effect is not OperationEffect.UPDATED)
        or completed.effect is OperationEffect.PARTIAL
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed


def _decimal_fact(row: PublicNamedScalar) -> str:
    value = row.value
    if not isinstance(value, PublicDecimal):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return value.decimal


def _text_fact(row: PublicNamedScalar) -> str:
    value = row.value
    if not isinstance(value, str):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return value


def calculation_snapshot_payload(
    snapshot: ModeloCalculationSnapshot, *, language: OutputLanguage
) -> CalculationRevisionPayload:
    """Build the established CLI JSON fields from canonical visible snapshot facts."""
    return CalculationRevisionPayload(
        calculation_revision_id=snapshot.calculation_revision_id,
        work_unit_id=snapshot.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef.model_validate(
            snapshot.registry_snapshot_ref.model_dump(mode="python")
        ),
        state=snapshot.state.value,
        casilla_values={row.key: _decimal_fact(row) for row in snapshot.casilla_values},
        observations=tuple(
            ObservationPayload(
                casilla_id=row.casilla_id,
                value=row.value if isinstance(row.value, str) else row.value.decimal,
                formula_id=row.formula_id,
                op=row.op,
                operand_refs=row.operand_refs,
                operand_casilla_refs=row.operand_casilla_refs,
                operand_values=tuple(value.decimal for value in row.operand_values),
                legal_refs=row.legal_refs,
                source_refs=row.source_refs,
                absent_by_design=row.absent_by_design,
            )
            for row in snapshot.observations
        ),
        result_summary=tuple(
            ResultSummaryRowPayload(
                role=row.role,
                casilla_id=row.casilla_id,
                value=row.value.decimal,
                label=(
                    require_modelo_localization(row.label_keys, locale=language.value)
                    if row.label_keys
                    else str(row.casilla_id)
                ),
            )
            for row in snapshot.result_summary
        ),
        detail_rows=tuple(
            DetailRowPayload(
                index=row.index, row_type=row.row_type, fields={field.key: field.value for field in row.fields}
            )
            for row in snapshot.detail_rows
        ),
        source_provenance=tuple(
            SourceProvenancePayload.model_validate(row.model_dump(mode="python")) for row in snapshot.source_provenance
        ),
        binding_overrides={row.key: _text_fact(row) for row in snapshot.binding_overrides},
        relation_overrides={row.key: _text_fact(row) for row in snapshot.relation_overrides},
        input_values_by_casilla_id={row.key: _text_fact(row) for row in snapshot.input_values_by_casilla_id},
        created_at=snapshot.created_at.isoformat(),
        updated_at=snapshot.updated_at.isoformat(),
        verified_at=snapshot.verified_at.isoformat() if snapshot.verified_at else None,
        verified_by=snapshot.verified_by,
        filed_at=snapshot.filed_at.isoformat() if snapshot.filed_at else None,
        filed_by=snapshot.filed_by,
        superseded_at=snapshot.superseded_at.isoformat() if snapshot.superseded_at else None,
    )


def calculation_snapshot_lines(
    snapshot: ModeloCalculationSnapshot, *, language: OutputLanguage, verbose: bool = False
) -> list[str]:
    """Render the existing calculation text layout without rereading private state."""
    lines = [
        f"calculation_revision_id\t{snapshot.calculation_revision_id}",
        f"work_unit_id\t{snapshot.work_unit_id}",
        f"state\t{calculation_revision_state_label(snapshot.state.value)}",
        f"created_at\t{snapshot.created_at.isoformat()}",
        f"updated_at\t{snapshot.updated_at.isoformat()}",
    ]
    if snapshot.verified_at is not None:
        lines.extend((f"verified_at\t{snapshot.verified_at.isoformat()}", f"verified_by\t{snapshot.verified_by}"))
    if snapshot.filed_at is not None:
        lines.extend((f"filed_at\t{snapshot.filed_at.isoformat()}", f"filed_by\t{snapshot.filed_by}"))
    if snapshot.superseded_at is not None:
        lines.append(f"superseded_at\t{snapshot.superseded_at.isoformat()}")
    if snapshot.result_summary:
        lines.extend(
            (
                tr(
                    "cli.app.modelo.work.result_summary_header",
                    modelo=snapshot.modelo,
                    year=snapshot.filing_year,
                    period=snapshot.period.code,
                ),
                "role\tcasilla\tvalue\tlabel",
            )
        )
        lines.extend(
            f"{row.role}\t{row.casilla_id}\t{row.value.decimal}\t"
            + (
                require_modelo_localization(row.label_keys, locale=language.value)
                if row.label_keys
                else str(row.casilla_id)
            )
            for row in snapshot.result_summary
        )
    observations = {row.casilla_id: row for row in snapshot.observations}
    for fact in snapshot.casilla_values:
        line = f"casilla\t{fact.key}\t{_decimal_fact(fact)}"
        row = observations.get(fact.key)
        verbose_line = None
        if row is not None:
            observation = CasillaObservation(
                casilla_id=row.casilla_id,
                value_kind=row.value_kind,
                value=row.value if isinstance(row.value, str) else Decimal(row.value.decimal),
                formula_id=row.formula_id,
                op=row.op,
                operand_refs=row.operand_refs,
                operand_casilla_refs=row.operand_casilla_refs,
                operand_values=tuple(Decimal(value.decimal) for value in row.operand_values),
                legal_refs=row.legal_refs,
                source_refs=row.source_refs,
                absent_by_design=row.absent_by_design,
            )
            trace = casilla_inline_trace(observation)
            if trace is not None:
                line = f"{line}\t{trace}"
                if verbose:
                    verbose_line = casilla_trace_verbose_line(observation)
        lines.append(line)
        if verbose_line is not None:
            lines.append(verbose_line)
    lines.extend(
        f"detail_row\t{row.index}\t{row.row_type}\t" + " ".join(f"{field.key}={field.value}" for field in row.fields)
        for row in snapshot.detail_rows
    )
    return lines


__all__ = ["calculation_snapshot_lines", "calculation_snapshot_payload", "run_modelo_work_calculation"]
