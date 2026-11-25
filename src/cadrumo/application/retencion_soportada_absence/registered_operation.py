"""Registration and access wiring for the suffered-withholding absence attestations."""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_exact_request_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from .contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODES,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
)
from .executor import RetencionSoportadaAbsenceExecutor
from .ports import RetencionSoportadaAbsencePortsFactory
from .projections import project_retencion_soportada_absence_list_result, project_retencion_soportada_absence_result
from .requests import (
    RetencionSoportadaAbsenceAttestRequest,
    RetencionSoportadaAbsenceListRequest,
    RetencionSoportadaAbsenceProfileRequest,
    RetencionSoportadaAbsenceWithdrawRequest,
)
from .results import (
    RetencionSoportadaAbsenceExecutionResult,
    RetencionSoportadaAbsenceListProjection,
    RetencionSoportadaAbsenceMutationProjection,
)

__all__ = [
    "build_retencion_soportada_absence_attest_definition",
    "build_retencion_soportada_absence_list_definition",
    "build_retencion_soportada_absence_list_registration",
    "build_retencion_soportada_absence_registration",
    "build_retencion_soportada_absence_withdraw_definition",
    "resolve_retencion_soportada_absence_operation_access",
]

_REQUEST_TYPES: Final[dict[str, type[RetencionSoportadaAbsenceProfileRequest]]] = {
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID: RetencionSoportadaAbsenceListRequest,
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID: RetencionSoportadaAbsenceAttestRequest,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID: RetencionSoportadaAbsenceWithdrawRequest,
}


def resolve_retencion_soportada_absence_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind each attestation operation to the exact profile and all periods; only writes commit."""
    return resolve_ledger_exact_request_access(
        request,
        context,
        request_types=_REQUEST_TYPES,
        commit_definition_ids=frozenset(
            {
                RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
                RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
            }
        ),
    )


def _definition(definition_id: str, ports_factory: RetencionSoportadaAbsencePortsFactory) -> OperationDefinition:
    request_type = _REQUEST_TYPES[definition_id]
    is_list = request_type is RetencionSoportadaAbsenceListRequest
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=RetencionSoportadaAbsenceExecutionResult,
        executor_type=RetencionSoportadaAbsenceExecutor,
        build=lambda: RetencionSoportadaAbsenceExecutor(ports_factory, definition_id=definition_id),
        capabilities=(
            RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
            if is_list
            else RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
        ),
        refusal_detail_codes=frozenset() if is_list else RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODES,
    )


def build_retencion_soportada_absence_attest_definition(
    ports_factory: RetencionSoportadaAbsencePortsFactory,
) -> OperationDefinition:
    """Build the revision-guarded absence attestation definition."""
    return _definition(RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID, ports_factory)


def build_retencion_soportada_absence_withdraw_definition(
    ports_factory: RetencionSoportadaAbsencePortsFactory,
) -> OperationDefinition:
    """Build the revision-guarded absence withdrawal definition."""
    return _definition(RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID, ports_factory)


def build_retencion_soportada_absence_list_definition(
    ports_factory: RetencionSoportadaAbsencePortsFactory,
) -> OperationDefinition:
    """Build the per-ejercicio attestation list definition."""
    return _definition(RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID, ports_factory)


def build_retencion_soportada_absence_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list projection to its disclosure guard."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=RetencionSoportadaAbsenceListProjection,
        result_projector=project_retencion_soportada_absence_list_result,
        access_resolver=resolve_retencion_soportada_absence_operation_access,
    )


def build_retencion_soportada_absence_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind an attestation or withdrawal projection and its typed refusal contract."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=RetencionSoportadaAbsenceMutationProjection,
        result_projector=project_retencion_soportada_absence_result,
        access_resolver=resolve_retencion_soportada_absence_operation_access,
    )
