"""Declare secure-reference operation definitions for spreadsheet services."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import OperationFrontendProjection
from .modelo_spreadsheet_executor import ModeloSpreadsheetExecutor
from .modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_OPERATION_CONTRACTS,
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE,
    MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
    ModeloSpreadsheetExecutionResult,
    ModeloSpreadsheetOperationPortsFactory,
)


def _declared_refusal_codes(definition_id: str) -> frozenset[str]:
    if definition_id == MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID:
        return frozenset({"REFUSED_MODELO_EXPORT_OUTPUT_PATH"})
    if definition_id == MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID:
        return frozenset({MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE, "REFUSED_OUTBOUND_STORAGE_CONFLICT"})
    if definition_id == MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID:
        return frozenset({"REFUSED_OUTBOUND_STORAGE_CONFLICT"})
    return frozenset[str]()


def build_modelo_spreadsheet_definitions(
    factory: ModeloSpreadsheetOperationPortsFactory, *, source_reader: Callable[[Path], bytes] = Path.read_bytes
) -> tuple[OperationDefinition, ...]:
    """Declare four secure-reference operations without constructing providers."""
    definitions: list[OperationDefinition] = []
    for definition_id, (request_type, _result_type, _outcome_type) in MODELO_SPREADSHEET_OPERATION_CONTRACTS.items():
        mutates = definition_id in {
            MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
            MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
        }
        effects = (
            frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED})
            if mutates
            else frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
        )
        definitions.append(
            build_single_phase_definition(
                definition_id=definition_id,
                request_type=request_type,
                result_type=ModeloSpreadsheetExecutionResult,
                executor_type=ModeloSpreadsheetExecutor,
                build=lambda: ModeloSpreadsheetExecutor(factory, source_reader=source_reader),
                capabilities=OperationCapabilities(
                    durability=OperationDurability.RECORDED,
                    cancellation=OperationCancellation.UNSUPPORTED,
                    deadline=OperationDeadline.ABSENT,
                    replay=OperationReplayPolicy.NONE,
                    baseline=OperationBaselinePolicy.REQUEST_BOUND,
                    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
                    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
                    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
                    owned_resources=frozenset(),
                    permitted_effects=effects,
                    close_policy=OperationClosePolicy.DETACH_ALLOWED,
                ),
                permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
                refusal_detail_codes=_declared_refusal_codes(definition_id),
            )
        )
    return tuple(sorted(definitions, key=lambda row: row.definition_id))


__all__ = ["build_modelo_spreadsheet_definitions"]
