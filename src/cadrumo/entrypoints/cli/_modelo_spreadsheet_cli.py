"""Workbook transport and calculation commands for ``aeat app modelo spreadsheet``.

Spreadsheet commands resolve a
:class:`RegistrySnapshot` before exporting
or pulling sheet rows against the live calculation schema.
"""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import TypeAdapter, ValidationError

from ...adapters.outbound.google.active_profile import resolve_active_profile
from ...adapters.outbound.google.calc_sheets_pull_records import relation_edit_payload
from ...adapters.outbound.google.errors import GoogleAuthError
from ...adapters.outbound.storage.errors import OutboundStorageError
from ...adapters.outbound.storage.factory import build_google_credentials, resolve_drive_root_folder_id
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.config import load_settings
from ...core.decimal.coercion import coerce_decimal
from ...core.period import Period
from ...core.type_guards import is_object_dict
from ...domain.calculations.registry.authority import bundled_authority as _bundled_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.ids import BindingId, RelationId
from ._common import emit_envelope
from ._modelo_spreadsheet_payloads import (
    ModeloSpreadsheetCalculateCasillaPayload,
    ModeloSpreadsheetCalculateResult,
    ModeloSpreadsheetPullRelationEditPayload,
    ModeloSpreadsheetPullResult,
    ModeloSpreadsheetPushResult,
    ModeloSpreadsheetVerifyDivergencePayload,
    ModeloSpreadsheetVerifyResult,
)
from .config.google_errors import google_refusal
from .errors import CliRefusedBoundaryError

if TYPE_CHECKING:
    import typer
    from google.auth.credentials import Credentials

    from ...adapters.outbound.google.calc_sheets_pull_records import (
        BindingEdit,
        OperatorEdit,
        PullResult,
        RelationEdit,
        RowSetEdit,
    )
    from ...application.export.google_operation import GoogleSheetsExportPublicResultV1
    from ...application.storage.calc_sheets.casilla_parity import CasillaParity
    from ...application.storage.calc_sheets.parity_harness import OperatorInputScenario, ParityReport
    from ...domain.calculations.registry.formula_runtime import RegistryCalculationResult
    from ...domain.calculations.registry.schema import RegistrySnapshot


def resolve_credentials_and_root(profile: str) -> tuple[Credentials, str]:
    """Hydrate refreshable Google credentials + the configured Drive root."""
    settings = load_settings()
    credentials = build_google_credentials(profile=profile)
    root_folder_id = resolve_drive_root_folder_id(profile=profile, settings=settings)
    if not root_folder_id:
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.spreadsheet.push.root_folder_required",
        )
    return credentials, root_folder_id


def filing_period_or_refusal(*, modelo: str, period: str, year: int) -> Period:
    try:
        return Period.from_year_and_code(year, period)
    except ValueError as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.spreadsheet.push.snapshot_failure",
            context={"modelo": modelo, "period": period, "year": year},
        ) from exc


def _resolve_active_profile_or_refuse() -> str:
    """Resolve the active profile through the canonical Google profile authority."""
    try:
        return resolve_active_profile()
    except GoogleAuthError as exc:
        raise google_refusal(exc) from exc


def _resolve_credentials_or_refuse(profile: str) -> tuple[Credentials, str]:
    """Hydrate Google credentials and Drive root through the CLI refusal boundary."""
    try:
        return resolve_credentials_and_root(profile)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise google_refusal(exc) from exc


def load_snapshot(modelo: str, period: Period) -> RegistrySnapshot:
    authority = _bundled_authority()
    if modelo not in {candidate.id for candidate in authority.modelos}:
        available = ", ".join(sorted(candidate.id for candidate in authority.modelos))
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.spreadsheet.push.unknown_modelo",
            context={"modelo": modelo, "available": available},
        )
    try:
        return authority.snapshot(modelo, filing_year=period.filing_year, period=period.registry_token)
    except (RegistrySnapshotError, RegistryValidationError) as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.spreadsheet.push.snapshot_failure",
            context={
                "modelo": modelo,
                "period": period.registry_token,
                "year": period.filing_year,
            },
        ) from exc


def _pull_operator_edits_for_command(
    *,
    modelo: str,
    period: str,
    year: int,
    spreadsheet_id: str,
) -> tuple[str, RegistrySnapshot, PullResult]:
    """Resolve the active profile, credentials, and snapshot, then pull operator edits.

    Shared by the ``pull`` and ``compute`` commands: each surface refuses on the
    same :class:`GoogleAuthError` / :class:`OutboundStorageError` boundaries with
    identical translated messages, so the resolution is one implementation.
    """
    from ...adapters.outbound.google.calc_sheets_pull import pull_operator_edits

    active = _resolve_active_profile_or_refuse()
    credentials, _ = _resolve_credentials_or_refuse(active)

    snapshot = load_snapshot(modelo, filing_period_or_refusal(modelo=modelo, period=period, year=year))

    try:
        result: PullResult = pull_operator_edits(
            snapshot,
            spreadsheet_id=spreadsheet_id,
            credentials=credentials,
        )
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise google_refusal(exc) from exc

    return active, snapshot, result


def modelo_spreadsheet_push(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    prefill_relations: bool = False,
    dry_run: bool = False,
) -> None:
    """Export the registry calculation surface for a modelo + period to a Google Sheets workbook."""
    active, result = execute_google_sheets_export(
        modelo=modelo,
        period=period,
        year=year,
        prefill_relations=prefill_relations,
        dry_run=dry_run,
    )

    export_result = ModeloSpreadsheetPushResult(
        profile=active,
        modelo=result.modelo,
        revision=result.revision,
        period=result.period,
        year=result.filing_year,
        engine_version=result.engine_version,
        registry_sha=result.registry_sha,
        root_folder_id=result.root_folder_id or "",
        dry_run=result.dry_run,
        spreadsheet_exists=result.spreadsheet_exists,
        folder_id=result.folder_id,
        spreadsheet_id=result.spreadsheet_id,
        spreadsheet_url=result.spreadsheet_url,
        value_cells_written=result.value_cells_written,
        formula_cells_written=result.formula_cells_written,
        protected_ranges_written=result.protected_ranges_written,
        tab_count=result.tab_count,
        ranges_to_clear=list(result.ranges_to_clear),
        value_cells_changed=result.value_cells_changed,
        value_cells_unchanged=result.value_cells_unchanged,
        formula_cells_to_write=result.formula_cells_to_write,
    )
    lines = (
        "operation\tconfig.google.sync.calc.export",
        f"profile\t{active}",
        f"modelo\t{result.modelo}",
        f"revision\t{result.revision}",
        f"period\t{result.period}",
        f"year\t{result.filing_year}",
        f"dry_run\t{result.dry_run}",
        f"folder_id\t{result.folder_id}",
        f"spreadsheet_id\t{result.spreadsheet_id}",
        f"spreadsheet_url\t{result.spreadsheet_url}",
        f"value_cells_written\t{result.value_cells_written}",
        f"formula_cells_written\t{result.formula_cells_written}",
        f"protected_ranges_written\t{result.protected_ranges_written}",
        f"tab_count\t{result.tab_count}",
    )
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.push",
        result=export_result,
        lines=lines,
    )


def _google_operation_error(code: str, *, diagnostic_ref: str | None) -> Exception:
    """Project a supervised failure solely through canonical ErrorCode metadata."""
    from ...core.errors.error_codes import ErrorCategory, get_registered_error_code_by_code

    error_code = get_registered_error_code_by_code(code)
    if error_code.category not in {ErrorCategory.ERROR, ErrorCategory.INTERNAL}:
        return CliRefusedBoundaryError(translated_message=error_code.message_key)
    return RuntimeError(f"supervised Google Sheets export failed ({diagnostic_ref or 'no diagnostic'})")


def execute_google_sheets_export(
    *,
    modelo: str,
    period: str,
    year: int,
    prefill_relations: bool = False,
    dry_run: bool = False,
) -> tuple[str, GoogleSheetsExportPublicResultV1]:
    """Submit the export through supervision and project its terminal result."""
    from uuid import UUID

    from ...application.export.google_operation import (
        GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
        GoogleSheetsExportOperationRequest,
        GoogleSheetsExportPublicResultV1,
    )
    from ...application.operations.frontend_requests import (
        OperationObservationRequestV1,
        OperationObservationSuccessV1,
        OperationResultProjectionRefusalV1,
        OperationResultProjectionRequestV1,
        OperationResultProjectionSuccessV1,
    )
    from ...application.operations.models import OperationRequest
    from ...core.operations import OperationTerminalCondition, profile_operation_subject
    from ...entrypoints.operation_composition import compose_operation_dependencies

    active = resolve_active_profile()

    async def run() -> GoogleSheetsExportPublicResultV1:
        services = compose_operation_dependencies()
        try:
            request = OperationRequest(
                definition_id=GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(active),
                payload=GoogleSheetsExportOperationRequest(
                    profile_id=UUID(active),
                    modelo=modelo,
                    filing_year=year,
                    period=period,
                    prefill_relations=prefill_relations,
                    dry_run=dry_run,
                ),
            )
            submitted = await services.submission.submit(
                request,
                actor_ref="operator:modelo-spreadsheet-push",
            )
            await services.submission.start(submitted.receipt.operation_id)
            observed = await services.observation.observe(
                OperationObservationRequestV1(
                    operation_id=submitted.receipt.operation_id,
                    after_cursor=0,
                    page_limit=64,
                )
            )
            if not isinstance(observed, OperationObservationSuccessV1):
                raise RuntimeError("supervised Google Sheets export observation is unavailable")
            projection = observed.projection
            code = projection.refusal_ref or projection.failure_error_code
            if code is not None:
                raise _google_operation_error(code, diagnostic_ref=projection.diagnostic_ref)
            if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
                raise RuntimeError(
                    f"supervised Google Sheets export failed ({projection.diagnostic_ref or 'no diagnostic'})"
                )
            result_schema = projection.definition_contract.result_schema
            if result_schema is None:
                raise RuntimeError("supervised Google Sheets export has no public result schema")
            resolved: (
                OperationResultProjectionSuccessV1[GoogleSheetsExportPublicResultV1]
                | OperationResultProjectionRefusalV1
            ) = await services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=projection.operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=projection.definition_contract.definition_contract_digest,
                    result_schema=result_schema,
                )
            )
            if not isinstance(resolved, OperationResultProjectionSuccessV1) or not isinstance(
                resolved.projection, GoogleSheetsExportPublicResultV1
            ):
                raise RuntimeError("supervised Google Sheets export result is unavailable")
            return resolved.projection
        finally:
            await services.shutdown()

    return active, asyncio.run(run())


def _scenario_decimal_value(value: object) -> Decimal:
    """Decode a scenario scalar through the shared decimal coercion boundary."""
    return coerce_decimal(value) or Decimal("0")


def _scenario_binding_id(value: object, adapter: TypeAdapter[str]) -> BindingId:
    """Decode one canonical binding identifier or retain the registry refusal."""
    try:
        return adapter.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"scenario binding key must be canonical: {value!r}") from exc


def _scenario_relation_id(value: object, adapter: TypeAdapter[str]) -> RelationId:
    """Decode one canonical relation identifier or retain the registry refusal."""
    try:
        return adapter.validate_python(value)
    except ValidationError as exc:
        raise RegistryValidationError(f"scenario relation key must be canonical: {value!r}") from exc


def _scenario_casilla_decimal_map(node: object) -> dict[CasillaId, Decimal]:
    """Decode an optional casilla-to-decimal scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {
        validated_casilla_id(k, surface="google sync calc scenario casilla.id"): _scenario_decimal_value(v)
        for k, v in node.items()
    }


def _scenario_binding_decimal_map(
    node: object,
    adapter: TypeAdapter[str],
) -> dict[BindingId, Decimal]:
    """Decode an optional numeric binding scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {_scenario_binding_id(k, adapter): _scenario_decimal_value(v) for k, v in node.items()}


def _scenario_enum_binding_map(node: object, adapter: TypeAdapter[str]) -> dict[BindingId, str]:
    """Decode an optional enum binding scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {_scenario_binding_id(k, adapter): str(v) for k, v in node.items()}


def _scenario_relation_decimal_map(
    node: object,
    adapter: TypeAdapter[str],
) -> dict[RelationId, Decimal]:
    """Decode an optional relation-to-decimal scenario mapping."""
    if not is_object_dict(node):
        return {}
    return {_scenario_relation_id(k, adapter): _scenario_decimal_value(v) for k, v in node.items()}


def _load_parity_scenario(scenario_path: Path | None) -> OperatorInputScenario:
    """Load the CLI scenario file into the parity harness's canonical model."""
    from ...application.storage.calc_sheets.parity_harness import OperatorInputScenario

    if scenario_path is None:
        return OperatorInputScenario(scenario_label="empty-defaults")

    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    binding_id_adapter: TypeAdapter[str] = TypeAdapter(BindingId)
    relation_id_adapter: TypeAdapter[str] = TypeAdapter(RelationId)
    return OperatorInputScenario(
        inputs_by_casilla_id=_scenario_casilla_decimal_map(raw.get("inputs_by_casilla_id")),
        bindings=_scenario_binding_decimal_map(raw.get("bindings"), binding_id_adapter),
        enum_bindings=_scenario_enum_binding_map(raw.get("enum_bindings"), binding_id_adapter),
        relation_values=_scenario_relation_decimal_map(raw.get("relation_values"), relation_id_adapter),
        expected_by_casilla_id=_scenario_casilla_decimal_map(raw.get("expected_by_casilla_id")),
        scenario_label=str(raw.get("scenario_label") or scenario_path.stem),
    )


def _verify_divergence_payload(divergence: CasillaParity) -> ModeloSpreadsheetVerifyDivergencePayload:
    """Project one parity divergence into the typed CLI payload."""
    return ModeloSpreadsheetVerifyDivergencePayload(
        casilla_id=divergence.casilla_id,
        label=divergence.label,
        local=str(divergence.local) if divergence.local is not None else None,
        sheets=str(divergence.sheets) if divergence.sheets is not None else None,
        aeat=str(divergence.aeat) if divergence.aeat is not None else None,
    )


def _verify_result(profile: str, report: ParityReport) -> ModeloSpreadsheetVerifyResult:
    """Project a parity report onto the public verify schema."""
    return ModeloSpreadsheetVerifyResult(
        profile=profile,
        modelo=report.modelo_id,
        revision=report.revision_id,
        period=report.period.registry_token,
        year=report.filing_year,
        spreadsheet_id=report.spreadsheet_id,
        spreadsheet_url=report.spreadsheet_url,
        verdict=report.verdict,
        aeat_oracle_present=report.aeat_oracle_present,
        computed_count=len(report.casillas),
        divergence_count=len(report.divergences),
        divergences=[_verify_divergence_payload(divergence) for divergence in report.divergences],
    )


def _verify_lines(profile: str, report: ParityReport) -> list[str]:
    """Render the stable tabular projection of a parity report."""
    lines = [
        "operation\tconfig.google.sync.calc.verify",
        f"profile\t{profile}",
        f"modelo\t{report.modelo_id}",
        f"revision\t{report.revision_id}",
        f"period\t{report.period}",
        f"year\t{report.filing_year}",
        f"spreadsheet_url\t{report.spreadsheet_url}",
        f"verdict\t{report.verdict}",
        f"aeat_oracle_present\t{report.aeat_oracle_present}",
        f"computed_count\t{len(report.casillas)}",
        f"divergence_count\t{len(report.divergences)}",
    ]
    for divergence in report.divergences:
        lines.append(
            f"divergence\t{divergence.casilla_id}\tlocal={divergence.local}"
            f"\tsheets={divergence.sheets}\taeat={divergence.aeat}",
        )
    return lines


def modelo_spreadsheet_verify(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    scenario_path: Path | None = None,
) -> None:
    """Run a three-way parity check across AEAT oracle, local Decimal runtime, and Sheets."""
    from ...application.storage.calc_sheets.parity_harness import verify_modelo_parity
    from ...application.user_profile.capabilities import resolve_active_capability
    from ...core.capabilities import ServiceCapability

    # `verify` creates a Drive spreadsheet and writes cells, so it is a Google
    # export egress and is gated on the same capability as `export`.
    if not resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled:
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.spreadsheet.push.capability_disabled",
        )

    active = _resolve_active_profile_or_refuse()
    credentials, root_folder_id = _resolve_credentials_or_refuse(active)

    snapshot = load_snapshot(modelo, filing_period_or_refusal(modelo=modelo, period=period, year=year))
    scenario = _load_parity_scenario(scenario_path)

    report = verify_modelo_parity(snapshot, scenario, credentials=credentials, root_folder_id=root_folder_id)
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.verify",
        result=_verify_result(active, report),
        lines=tuple(_verify_lines(active, report)),
    )


def _populated_pull_edits(
    result: PullResult,
) -> tuple[list[OperatorEdit], list[BindingEdit], list[RelationEdit], list[RowSetEdit]]:
    """Select populated edit families while leaving the adapter result immutable."""
    return (
        [edit for edit in result.operator_edits if edit.value is not None],
        [edit for edit in result.binding_edits if edit.value is not None],
        [edit for edit in result.relation_edits if edit.value is not None],
        [row_set for row_set in result.row_set_edits if row_set.cells],
    )


def _pull_metadata_payload(result: PullResult) -> dict[str, object]:
    """Project the adapter's workbook metadata into the public pull payload."""
    return {
        "modelo_id": result.metadata.modelo_id,
        "revision_id": result.metadata.revision_id,
        "filing_year": result.metadata.filing_year,
        "period": result.metadata.period,
        "engine_version": result.metadata.engine_version,
        "registry_sha": result.metadata.registry_sha,
        "exported_at": result.metadata.exported_at,
    }


def _pull_operator_payload(edits: list[OperatorEdit]) -> list[dict[str, object]]:
    """Project populated operator casilla edits into typed-boundary rows."""
    return [
        {
            "casilla_id": edit.casilla_id,
            "label": edit.label,
            "value": str(edit.value) if edit.value is not None else None,
        }
        for edit in edits
    ]


def _pull_binding_payload(edits: list[BindingEdit]) -> list[dict[str, object]]:
    """Project populated numeric/enum binding edits into boundary rows."""
    return [{"binding": edit.binding, "value": str(edit.value) if edit.value is not None else None} for edit in edits]


def _pull_relation_payload(edits: list[RelationEdit]) -> list[ModeloSpreadsheetPullRelationEditPayload]:
    """Project populated relation edits with their adapter-provided grounding."""
    return [ModeloSpreadsheetPullRelationEditPayload.model_validate(relation_edit_payload(edit)) for edit in edits]


def _pull_row_set_payload(row_sets: list[RowSetEdit]) -> list[dict[str, object]]:
    """Project populated row-set cells without changing their coordinates."""
    return [
        {
            "grouping": row_set.grouping,
            "cells": [
                {
                    "binding": cell.binding,
                    "row_index": cell.row_index,
                    "value": str(cell.value) if cell.value is not None else None,
                }
                for cell in row_set.cells
            ],
        }
        for row_set in row_sets
    ]


def _pull_result(
    *,
    active: str,
    snapshot: RegistrySnapshot,
    result: PullResult,
    populated_operator: list[OperatorEdit],
    populated_bindings: list[BindingEdit],
    populated_relations: list[RelationEdit],
    populated_row_sets: list[RowSetEdit],
    row_set_cells_total: int,
    assembled_groupings: list[dict[str, object]],
    assembled_observation_count: int,
) -> ModeloSpreadsheetPullResult:
    """Build and validate the public pull result from canonical adapter records."""
    payload: dict[str, object] = {
        "operation": "config.google.sync.calc.pull",
        "profile": active,
        "modelo": snapshot.modelo.id,
        "revision": snapshot.revision.id,
        "period": snapshot.period,
        "year": snapshot.filing_year,
        "spreadsheet_id": result.spreadsheet_id,
        "metadata_match": result.metadata_match,
        "metadata": _pull_metadata_payload(result),
        "cells_read": result.cells_read,
        "operator_edits_total": len(result.operator_edits),
        "operator_edits_populated": len(populated_operator),
        "binding_edits_populated": len(populated_bindings),
        "relation_edits_populated": len(populated_relations),
        "operator_edits": _pull_operator_payload(populated_operator),
        "binding_edits": _pull_binding_payload(populated_bindings),
        "relation_edits": _pull_relation_payload(populated_relations),
        "row_set_edits_populated": len(populated_row_sets),
        "row_set_cells_populated": row_set_cells_total,
        "assembled_groupings": assembled_groupings,
        "assembled_observation_count": assembled_observation_count,
        "row_set_edits": _pull_row_set_payload(populated_row_sets),
    }
    return ModeloSpreadsheetPullResult.model_validate(payload)


def _pull_lines(
    *,
    active: str,
    snapshot: RegistrySnapshot,
    result: PullResult,
    populated_operator: list[OperatorEdit],
    populated_bindings: list[BindingEdit],
    populated_relations: list[RelationEdit],
    populated_row_sets: list[RowSetEdit],
    row_set_cells_total: int,
    assembled_groupings: list[dict[str, object]],
) -> list[str]:
    """Render the stable tabular projection of a workbook pull."""
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.pull",
        f"profile\t{active}",
        f"modelo\t{snapshot.modelo.id}",
        f"revision\t{snapshot.revision.id}",
        f"period\t{snapshot.period}",
        f"year\t{snapshot.filing_year}",
        f"spreadsheet_id\t{result.spreadsheet_id}",
        f"metadata_match\t{result.metadata_match}",
        f"metadata.modelo_id\t{result.metadata.modelo_id}",
        f"metadata.revision_id\t{result.metadata.revision_id}",
        f"metadata.registry_sha\t{result.metadata.registry_sha}",
        f"cells_read\t{result.cells_read}",
        f"operator_edits_populated\t{len(populated_operator)}",
        f"binding_edits_populated\t{len(populated_bindings)}",
        f"relation_edits_populated\t{len(populated_relations)}",
        f"row_set_edits_populated\t{len(populated_row_sets)}",
        f"row_set_cells_populated\t{row_set_cells_total}",
    ]
    for edit in populated_operator:
        lines.append(f"casilla_id\t{edit.casilla_id}\t{edit.value}\t{edit.label}")
    for edit in populated_bindings:
        lines.append(f"binding\t{edit.binding}\t{edit.value}")
    for edit in populated_relations:
        lines.append(f"relation\t{edit.relation}\t{edit.value}")
    for row_set in populated_row_sets:
        for cell in row_set.cells:
            lines.append(f"row_set\t{row_set.grouping}\t{cell.row_index}\t{cell.binding}\t{cell.value}")
    for assembled in assembled_groupings:
        lines.append(
            f"assembled\t{assembled['grouping']}\t{assembled['source_kind']}\t{assembled['observation_count']}",
        )
    return lines


def modelo_spreadsheet_pull(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    spreadsheet_id: str,
    assemble_observations: bool = False,
) -> None:
    """Read operator-edited cells back from a workbook into typed records."""
    active, snapshot, result = _pull_operator_edits_for_command(
        modelo=modelo,
        period=period,
        year=year,
        spreadsheet_id=spreadsheet_id,
    )

    populated_operator, populated_bindings, populated_relations, populated_row_sets = _populated_pull_edits(result)
    row_set_cells_total = sum(len(rs.cells) for rs in populated_row_sets)

    assembled_groupings, assembled_observation_count = _assemble_pull_observations(
        populated_row_sets=populated_row_sets,
        snapshot=snapshot,
        enabled=assemble_observations,
    )

    emit_envelope(
        ctx,
        command="modelo.spreadsheet.pull",
        result=_pull_result(
            active=active,
            snapshot=snapshot,
            result=result,
            populated_operator=populated_operator,
            populated_bindings=populated_bindings,
            populated_relations=populated_relations,
            populated_row_sets=populated_row_sets,
            row_set_cells_total=row_set_cells_total,
            assembled_groupings=assembled_groupings,
            assembled_observation_count=assembled_observation_count,
        ),
        lines=tuple(
            _pull_lines(
                active=active,
                snapshot=snapshot,
                result=result,
                populated_operator=populated_operator,
                populated_bindings=populated_bindings,
                populated_relations=populated_relations,
                populated_row_sets=populated_row_sets,
                row_set_cells_total=row_set_cells_total,
                assembled_groupings=assembled_groupings,
            ),
        ),
    )


def _computed_casilla_entries(
    calculation: RegistryCalculationResult,
) -> list[ModeloSpreadsheetCalculateCasillaPayload]:
    """Project registry calculation entries into the public compute schema."""
    return [
        ModeloSpreadsheetCalculateCasillaPayload(
            casilla_id=entry.target_casilla_id,
            value=str(entry.value),
            formula_id=entry.formula_id,
            legal_refs=tuple(entry.legal_refs),
            source_refs=tuple(entry.source_refs),
        )
        for entry in calculation.entries
    ]


def _calculate_result(
    *,
    active: str,
    snapshot: RegistrySnapshot,
    result: PullResult,
    populated_operator: list[OperatorEdit],
    populated_bindings: list[BindingEdit],
    populated_relations: list[RelationEdit],
    computed: list[ModeloSpreadsheetCalculateCasillaPayload],
) -> ModeloSpreadsheetCalculateResult:
    """Build the typed compute result from canonical pull and engine records."""
    return ModeloSpreadsheetCalculateResult(
        profile=active,
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        period=snapshot.period,
        year=snapshot.filing_year,
        spreadsheet_id=result.spreadsheet_id,
        metadata_match=result.metadata_match,
        cells_read=result.cells_read,
        operator_edits_populated=len(populated_operator),
        binding_edits_populated=len(populated_bindings),
        relation_edits_populated=len(populated_relations),
        computed=computed,
    )


def _calculate_lines(
    *,
    active: str,
    snapshot: RegistrySnapshot,
    result: PullResult,
    populated_operator: list[OperatorEdit],
    populated_bindings: list[BindingEdit],
    populated_relations: list[RelationEdit],
    computed: list[ModeloSpreadsheetCalculateCasillaPayload],
) -> list[str]:
    """Render the stable tabular projection of a workbook calculation."""
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.compute",
        f"profile\t{active}",
        f"modelo\t{snapshot.modelo.id}",
        f"revision\t{snapshot.revision.id}",
        f"period\t{snapshot.period}",
        f"year\t{snapshot.filing_year}",
        f"spreadsheet_id\t{result.spreadsheet_id}",
        f"metadata_match\t{result.metadata_match}",
        f"cells_read\t{result.cells_read}",
        f"operator_edits_populated\t{len(populated_operator)}",
        f"binding_edits_populated\t{len(populated_bindings)}",
        f"relation_edits_populated\t{len(populated_relations)}",
    ]
    for entry in computed:
        lines.append(f"computed\t{entry.casilla_id}\t{entry.value}\t{entry.formula_id}")
    return lines


def modelo_spreadsheet_calculate(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    spreadsheet_id: str,
) -> None:
    """Compute casilla values from a workbook's operator edits; persist nothing."""
    from ...adapters.outbound.google.calc_sheets_pull import compute_from_pull

    active, snapshot, result = _pull_operator_edits_for_command(
        modelo=modelo,
        period=period,
        year=year,
        spreadsheet_id=spreadsheet_id,
    )

    if result.metadata_match != "matches":
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.spreadsheet.compute.refused_stale",
            context={"metadata_match": result.metadata_match},
        )

    try:
        calc = compute_from_pull(snapshot, result)
    except OutboundStorageError as exc:
        raise google_refusal(exc) from exc

    computed_casilla_entries = _computed_casilla_entries(calc)
    populated_operator, populated_bindings, populated_relations, _ = _populated_pull_edits(result)
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.calculate",
        result=_calculate_result(
            active=active,
            snapshot=snapshot,
            result=result,
            populated_operator=populated_operator,
            populated_bindings=populated_bindings,
            populated_relations=populated_relations,
            computed=computed_casilla_entries,
        ),
        lines=tuple(
            _calculate_lines(
                active=active,
                snapshot=snapshot,
                result=result,
                populated_operator=populated_operator,
                populated_bindings=populated_bindings,
                populated_relations=populated_relations,
                computed=computed_casilla_entries,
            ),
        ),
    )


def _assemble_pull_observations(
    *,
    populated_row_sets: list[RowSetEdit],
    snapshot: RegistrySnapshot,
    enabled: bool,
) -> tuple[list[dict[str, object]], int]:
    """Guarded whole-pull assembly of the operator row-set blocks.

    The worksheet ingress guard is applied once over every populated block, so
    a block claiming a row coordinate an earlier block already owns is refused
    rather than silently overwriting part of a declared figure.  Per-block
    validation could not observe that cross-block collision.
    """
    if not enabled:
        return [], 0
    from ...application.storage.calc_sheets.row_set_assembly import assemble_row_sets_for_snapshot

    try:
        assembled = assemble_row_sets_for_snapshot(populated_row_sets, snapshot)
    except (OutboundStorageError, RegistryValidationError) as exc:
        raise google_refusal(exc) from exc

    groupings: list[dict[str, object]] = []
    total = 0
    for row_set, (source_kind, observations) in zip(populated_row_sets, assembled, strict=True):
        total += len(observations)
        groupings.append(
            {
                "grouping": row_set.grouping,
                "source_kind": source_kind,
                "observation_count": len(observations),
                "observations": [obs.model_dump(mode="json") for obs in observations],
            },
        )
    return groupings, total


__all__ = [
    "execute_google_sheets_export",
    "modelo_spreadsheet_calculate",
    "modelo_spreadsheet_pull",
    "modelo_spreadsheet_push",
    "modelo_spreadsheet_verify",
]
