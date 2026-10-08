"""Declare secure-reference operation definitions for spreadsheet services."""

from __future__ import annotations

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
    MODELO_SPREADSHEET_OPERATION_CONTRACTS,
    ModeloSpreadsheetExecutionResult,
    ModeloSpreadsheetOperationPortsFactory,
)


def build_modelo_spreadsheet_definitions(
    factory: ModeloSpreadsheetOperationPortsFactory,
) -> tuple[OperationDefinition, ...]:
    """Declare local XLSX export without constructing providers."""
    definitions: list[OperationDefinition] = []
    for definition_id, (request_type, _result_type, _outcome_type) in MODELO_SPREADSHEET_OPERATION_CONTRACTS.items():
        effects = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED})
        definitions.append(
            build_single_phase_definition(
                definition_id=definition_id,
                request_type=request_type,
                result_type=ModeloSpreadsheetExecutionResult,
                executor_type=ModeloSpreadsheetExecutor,
                build=lambda: ModeloSpreadsheetExecutor(factory),
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
                refusal_detail_codes=frozenset({"REFUSED_MODELO_EXPORT_OUTPUT_PATH"}),
            )
        )
    return tuple(sorted(definitions, key=lambda row: row.definition_id))


__all__ = ["build_modelo_spreadsheet_definitions"]
