"""Worker-executed local certificate-source services and their effect lifecycle."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import (
    OperationEffect,
)
from ...core.time.clock import now
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .certificate_secret_backend import CertificateSecretBackendFactory
from .certificate_source_contracts import (
    CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
    CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
    CertificateSourceCheckRequest,
    CertificateSourceListRequest,
    CertificateSourceRegisterRequest,
    CertificateSourceRemoveRequest,
    CertificateSourceSelectRequest,
)
from .certificate_source_operations import (
    check_operator_certificate_sources,
    list_operator_certificate_sources,
    register_operator_certificate_source,
    remove_operator_certificate_source,
    select_operator_certificate_source,
)
from .operator_probe_ports import OperatorProbePorts
from .operator_results import (
    CertificateSourceCheckReport,
    CertificateSourceListResult,
    CertificateSourceMutationResult,
    CertificateSourceNotFoundError,
)
from .operator_scope_ports import OperatorScopePorts


@dataclass(frozen=True, slots=True)
class CertificateSourceOperationPorts:
    """Outward local-auth capabilities used by the existing source services."""

    operator_scope_ports: OperatorScopePorts
    operator_probe_ports: OperatorProbePorts
    certificate_secret_backend_factory: CertificateSecretBackendFactory


class CertificateSourceOperationExecutor:
    """Run one existing certificate-source service under worker custody."""

    def __init__(self, *, ports: CertificateSourceOperationPorts, definition_id: str) -> None:
        """Retain local-auth ports and the exact registered verb."""
        self._ports = ports
        self._definition_id = definition_id

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Dispatch one service call with profile custody and truthful effect facts."""
        payload = request.payload
        request_type, private_result_type, is_mutation = CERTIFICATE_SOURCE_OPERATION_SHAPES[self._definition_id]
        profile_id = getattr(payload, "profile_id", None)
        if (
            type(payload) is not request_type
            or request.definition_id != self._definition_id
            or not isinstance(profile_id, UUID)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, profile_id)

        await context.events.phase(certificate_source_phase_code(self._definition_id, "preflight"))
        if is_mutation:

            async def commit() -> str:
                async with context.cancellation.irreversible_section():
                    await context.events.effect(OperationEffect.UNKNOWN)
                    await context.events.phase(certificate_source_phase_code(self._definition_id, "commit"))
                    try:
                        result = await asyncio.to_thread(self._invoke_mutation, payload, context)
                    except CertificateSourceNotFoundError:
                        await context.events.effect(OperationEffect.NONE)
                        raise
                    checked = validate_certificate_source_service_result(result, private_result_type)
                    effect = _mutation_effect(self._definition_id, checked)
                    await context.events.effect(effect)
                    await context.events.phase(certificate_source_phase_code(self._definition_id, "settlement"))
                    return await context.operands.put(checked, written_at=now())

            return await await_cancellation_complete(commit(), task_name="certificate-source-mutation")

        async def read_and_publish() -> str:
            result = await asyncio.to_thread(self._invoke_read, payload)
            checked = validate_certificate_source_service_result(result, private_result_type)
            await context.events.effect(OperationEffect.NONE)
            await context.events.phase(certificate_source_phase_code(self._definition_id, "settlement"))
            return await context.operands.put(checked, written_at=now())

        return await await_cancellation_complete(read_and_publish(), task_name="certificate-source-read-result")

    def _invoke_mutation(self, payload: BaseModel, context: OperationExecutorContext) -> BaseModel:
        if self._definition_id == CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID:
            request = _require_payload(payload, CertificateSourceRegisterRequest)
            return register_operator_certificate_source(
                name=request.name,
                certificate_path=request.certificate_path,
                friendly_name=request.friendly_name,
                operation=context.authority_operation,
                operator_scope_ports=self._ports.operator_scope_ports,
            )
        if self._definition_id == CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID:
            request = _require_payload(payload, CertificateSourceSelectRequest)
            return select_operator_certificate_source(
                name=request.name,
                operation=context.authority_operation,
                operator_scope_ports=self._ports.operator_scope_ports,
            )
        if self._definition_id == CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID:
            request = _require_payload(payload, CertificateSourceRemoveRequest)
            return remove_operator_certificate_source(
                name=request.name,
                operation=context.authority_operation,
                operator_scope_ports=self._ports.operator_scope_ports,
            )
        raise ValueError("certificate source operation is not a mutation")

    def _invoke_read(self, payload: BaseModel) -> BaseModel:
        if self._definition_id == CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID:
            _require_payload(payload, CertificateSourceListRequest)
            return list_operator_certificate_sources()
        if self._definition_id == CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID:
            _require_payload(payload, CertificateSourceCheckRequest)
            return check_operator_certificate_sources(
                certificate_secret_backend_factory=self._ports.certificate_secret_backend_factory,
                operator_probe_ports=self._ports.operator_probe_ports,
                operator_scope_ports=self._ports.operator_scope_ports,
            )
        raise ValueError("certificate source operation is not a read")


CERTIFICATE_SOURCE_OPERATION_SHAPES: dict[str, tuple[type[BaseModel], type[BaseModel], bool]] = {
    CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID: (
        CertificateSourceRegisterRequest,
        CertificateSourceMutationResult,
        True,
    ),
    CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID: (
        CertificateSourceListRequest,
        CertificateSourceListResult,
        False,
    ),
    CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID: (
        CertificateSourceSelectRequest,
        CertificateSourceMutationResult,
        True,
    ),
    CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID: (
        CertificateSourceRemoveRequest,
        CertificateSourceMutationResult,
        True,
    ),
    CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID: (
        CertificateSourceCheckRequest,
        CertificateSourceCheckReport,
        False,
    ),
}


def _require_payload[PayloadT: BaseModel](payload: BaseModel, expected: type[PayloadT]) -> PayloadT:
    if type(payload) is not expected:
        raise ValueError("certificate source operation payload has the wrong type")
    return expected.model_validate_json(payload.model_dump_json(), strict=True)


def validate_certificate_source_service_result[ResultModelT: BaseModel](
    value: object, expected: type[ResultModelT]
) -> ResultModelT:
    """Round-trip one exact service result into its closed private schema."""
    if type(value) is not expected:
        raise ValueError("certificate source service returned an invalid result")
    return expected.model_validate_json(value.model_dump_json(), strict=True)


def _mutation_effect(definition_id: str, result: BaseModel) -> OperationEffect:
    if definition_id == CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID:
        mutation = _require_payload(result, CertificateSourceMutationResult)
        return OperationEffect.UPDATED if mutation.removed else OperationEffect.NONE
    return OperationEffect.UPDATED


def certificate_source_phase_code(definition_id: str, stage: Literal["preflight", "commit", "settlement"]) -> str:
    """Name one declared lifecycle phase for the exact certificate-source verb."""
    return f"{definition_id}.{stage}"
