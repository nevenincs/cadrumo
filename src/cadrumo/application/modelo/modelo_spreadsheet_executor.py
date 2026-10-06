"""Supervised execution stages for the registered spreadsheet operations.

Core types: :class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_payload, require_operation_profile
from ..operations.refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..storage.calc_sheets.workbook_export import ModeloWorkbookExport, export_modelo_workbook
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .export_sink import LocalFileExportSink, ModeloExportOutputPathError
from .modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_OPERATION_CONTRACTS,
    ModeloSpreadsheetExecutionResult,
    ModeloSpreadsheetExportRequest,
    ModeloSpreadsheetOperationPorts,
    ModeloSpreadsheetOperationPortsFactory,
    ModeloSpreadsheetRequest,
    SpreadsheetOutputPathRefusal,
    SpreadsheetRefusal,
    spreadsheet_refusal_code,
)
from .modelo_spreadsheet_operation_projections import (
    ModeloSpreadsheetExportProjection,
    ModeloSpreadsheetProjection,
)

MAX_MODELO_SPREADSHEET_SCENARIO_BYTES = PROJECTION_DOCUMENT_MAX_BYTES


@dataclass(slots=True)
class _SpreadsheetExecution:
    request: OperationRequest[BaseModel]
    context: OperationExecutorContext
    payload: ModeloSpreadsheetRequest
    operation: PinnedAuthorityOperation
    ports: ModeloSpreadsheetOperationPorts
    period: Period
    snapshot: RegistrySnapshot
    coordinate: dict[str, Any]
    source_reader: Callable[[Path], bytes]
    loop: asyncio.AbstractEventLoop
    remote_dispatched: bool = False
    local_publication_started: bool = False


def _admit_spreadsheet_request(
    request: OperationRequest[BaseModel], context: OperationExecutorContext
) -> ModeloSpreadsheetRequest:
    pair = MODELO_SPREADSHEET_OPERATION_CONTRACTS.get(request.definition_id)
    if pair is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = require_access_request_payload(request, definition_id=request.definition_id, payload_type=pair[0])
    require_operation_profile(request, context, payload.profile_id)
    return payload


def _output_path_refusal(
    error: ModeloExportOutputPathError, payload: ModeloSpreadsheetExportRequest
) -> SpreadsheetOutputPathRefusal:
    reasons = {
        "path is empty": "empty",
        "path is an existing directory": "existing_directory",
        "path is an existing file": "existing_file",
        "parent directory does not exist": "missing_parent",
        "parent path is not a directory": "parent_not_directory",
    }
    reason = None if error.context is None else error.context.get("reason")
    return SpreadsheetOutputPathRefusal.model_validate(
        {
            "output_path": payload.output_path,
            "reason": reasons.get(reason, "publication_failed") if isinstance(reason, str) else "publication_failed",
        },
        strict=True,
    )


def _current_effect(scope: _SpreadsheetExecution) -> OperationEffect:
    attempted = scope.remote_dispatched or scope.local_publication_started
    return OperationEffect.UNKNOWN if attempted else OperationEffect.NONE


async def _refuse(scope: _SpreadsheetExecution, detail: SpreadsheetRefusal) -> OperationRefusalEvidence:
    effect = _current_effect(scope)
    refusal_effect: Literal["none", "unknown"] = "unknown" if effect is OperationEffect.UNKNOWN else "none"
    outcome_type = MODELO_SPREADSHEET_OPERATION_CONTRACTS[scope.request.definition_id][2]
    outcome = outcome_type.model_validate(
        {
            **scope.coordinate,
            "outcome": "refused",
            "refusal": detail.model_dump(mode="python"),
        },
        strict=True,
    )
    async with scope.context.cancellation.irreversible_section():
        _admit_spreadsheet_request(scope.request, scope.context)
        await scope.context.events.effect(effect)
        retained = ModeloSpreadsheetExecutionResult.model_validate(
            {"projection": outcome.model_dump(mode="python"), "effect": refusal_effect}, strict=True
        )
        detail_ref = await scope.context.operands.put(retained, written_at=now())
    return OperationRefusalEvidence(refusal_code=spreadsheet_refusal_code(detail), detail_ref=detail_ref)


async def _export_workbook(scope: _SpreadsheetExecution) -> ModeloSpreadsheetExportProjection:
    payload = cast(ModeloSpreadsheetExportRequest, scope.payload)
    sink = LocalFileExportSink(path=Path(payload.output_path), replace_existing=payload.replace_existing)
    sink.require_writable()

    def render() -> ModeloWorkbookExport:
        with validating_governed_facts(scope.operation):
            return export_modelo_workbook(
                modelo=payload.modelo,
                period=scope.period,
                materializer=scope.ports.materialize,
                prefill_relations=payload.prefill_relations,
                snapshot_resolver=lambda _modelo, _period: scope.snapshot,
                plan_builder=scope.ports.plan_builder,
            )

    workbook = await asyncio.to_thread(render)
    async with scope.context.cancellation.irreversible_section():
        _admit_spreadsheet_request(scope.request, scope.context)
        # Repeat the path precondition before claiming an actual publication attempt.
        sink.require_writable()
        scope.local_publication_started = True
        await scope.context.events.effect(OperationEffect.UNKNOWN)
        receipt = await asyncio.to_thread(sink.write, workbook.payload)
        if receipt.path != sink.path or receipt.sha256 != workbook.sha256 or receipt.byte_size != workbook.byte_size:
            raise ValueError("spreadsheet publication receipt contradicts its workbook")
        await scope.context.events.effect(OperationEffect.UPDATED)
    return ModeloSpreadsheetExportProjection(
        **scope.coordinate,
        output_path=str(receipt.path),
        byte_size=receipt.byte_size,
        sha256=receipt.sha256,
        tab_names=workbook.tab_names,
        casilla_count=workbook.casilla_count,
        prefill_relations=payload.prefill_relations,
    )


async def _dispatch(scope: _SpreadsheetExecution) -> ModeloSpreadsheetProjection | OperationRefusalEvidence:
    payload = scope.payload
    if isinstance(payload, ModeloSpreadsheetExportRequest):
        return await _export_workbook(scope)
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


async def _retain_success(scope: _SpreadsheetExecution, projection: ModeloSpreadsheetProjection) -> str:
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    effect = "updated"
    outcome_type = MODELO_SPREADSHEET_OPERATION_CONTRACTS[scope.request.definition_id][2]
    outcome = outcome_type.model_validate(
        {**scope.coordinate, "outcome": "succeeded", "result": projection.model_dump(mode="python")}, strict=True
    )
    retained = ModeloSpreadsheetExecutionResult.model_validate(
        {"projection": outcome.model_dump(mode="python"), "effect": effect}, strict=True
    )
    return await scope.context.operands.put(retained, written_at=now())


async def _execute_scope(scope: _SpreadsheetExecution) -> OperationExecutorResult:
    try:
        stage_result = await _dispatch(scope)
    except ModeloExportOutputPathError as error:
        if not isinstance(scope.payload, ModeloSpreadsheetExportRequest):
            raise
        return await _refuse(scope, _output_path_refusal(error, scope.payload))
    except BaseException:
        await scope.context.events.effect(_current_effect(scope))
        raise
    if isinstance(stage_result, OperationRefusalEvidence):
        return stage_result
    return await _retain_success(scope, stage_result)


class ModeloSpreadsheetExecutor:
    """Retain the profile pin while delegating algorithms through canonical ports."""

    def __init__(
        self, factory: ModeloSpreadsheetOperationPortsFactory, *, source_reader: Callable[[Path], bytes]
    ) -> None:
        """Bind lazy profile ports and the secure source reader."""
        self._factory = factory
        self._source_reader = source_reader

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Validate the pinned snapshot before supervised worker execution."""
        payload = _admit_spreadsheet_request(request, context)
        await context.events.phase(request.definition_id)
        operation = context.authority_operation
        ports = self._factory(profile_id=payload.profile_id, operation=operation)
        if ports.profile_id != payload.profile_id or ports.operation is not operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        period = payload.period.to_period()
        snapshot = operation.snapshot(payload.modelo, filing_year=period.filing_year, period=period.registry_token)
        if (
            snapshot.modelo.id != payload.modelo
            or snapshot.filing_year != period.filing_year
            or snapshot.period != period.registry_token
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        coordinate = ModeloSpreadsheetProjection(
            profile_id=payload.profile_id,
            modelo=snapshot.modelo.id,
            revision=snapshot.revision.id,
            period=payload.period,
        ).model_dump(mode="python")
        scope = _SpreadsheetExecution(
            request=request,
            context=context,
            payload=payload,
            operation=operation,
            ports=ports,
            period=period,
            snapshot=snapshot,
            coordinate=coordinate,
            source_reader=self._source_reader,
            loop=asyncio.get_running_loop(),
        )
        return await await_cancellation_complete(_execute_scope(scope), task_name=request.definition_id)


__all__ = ["MAX_MODELO_SPREADSHEET_SCENARIO_BYTES", "ModeloSpreadsheetExecutor"]
