"""Registered exact-profile operations for non-secret certificate-source verbs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .certificate_secret_backend import CertificateSecretBackendFactory
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
from .probes import PROBE_RESULTS_NEEDING_ATTENTION

CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID = "auth.certificate.source.register"
CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID = "auth.certificate.source.list"
CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID = "auth.certificate.source.select"
CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID = "auth.certificate.source.remove"
CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID = "auth.certificate.source.check"

_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
_HUMAN_FRONTENDS = frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI})
_READ_ACTIONS = frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT})
_MUTATION_ACTIONS = _READ_ACTIONS | {AccessAction.COMMIT}


class CertificateSourceRegisterRequest(BaseModel):
    """Register or re-point one named source in the exact active profile."""

    model_config = _CONFIG

    profile_id: UUID
    name: str = Field(min_length=1, max_length=128)
    certificate_path: Path
    friendly_name: str | None = Field(default=None, max_length=256)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("certificate source name must not be blank")
        return normalized

    @field_validator("friendly_name")
    @classmethod
    def _normalize_friendly_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class CertificateSourceListRequest(BaseModel):
    """List source metadata from the exact active profile."""

    model_config = _CONFIG

    profile_id: UUID


class CertificateSourceSelectRequest(BaseModel):
    """Select one previously registered certificate source."""

    model_config = _CONFIG

    profile_id: UUID
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("certificate source name must not be blank")
        return normalized


class CertificateSourceRemoveRequest(BaseModel):
    """Remove one named source; an absent name remains an idempotent no-op."""

    model_config = _CONFIG

    profile_id: UUID
    name: str = Field(min_length=1, max_length=128)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("certificate source name must not be blank")
        return normalized


class CertificateSourceCheckRequest(BaseModel):
    """Check local health for every named source in the exact active profile."""

    model_config = _CONFIG

    profile_id: UUID


class CertificateSourceRegisterProjection(BaseModel):
    """Registered-source receipt bound to the terminal profile subject."""

    model_config = _CONFIG

    profile_id: UUID
    result: CertificateSourceMutationResult


class CertificateSourceListProjection(BaseModel):
    """Source inventory bound to the terminal profile subject."""

    model_config = _CONFIG

    profile_id: UUID
    result: CertificateSourceListResult

    @field_validator("result")
    @classmethod
    def _validate_inventory(cls, result: CertificateSourceListResult) -> CertificateSourceListResult:
        names = tuple(source.name for source in result.sources)
        active_names = tuple(source.name for source in result.sources if source.active)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError("certificate source inventory is not canonically ordered")
        if active_names != ((result.active_source,) if result.active_source else ()):
            raise ValueError("certificate source inventory has an inconsistent active selection")
        return result


class CertificateSourceSelectProjection(BaseModel):
    """Selected-source receipt bound to the terminal profile subject."""

    model_config = _CONFIG

    profile_id: UUID
    result: CertificateSourceMutationResult


class CertificateSourceRemoveProjection(BaseModel):
    """Removal receipt bound to the terminal profile subject."""

    model_config = _CONFIG

    profile_id: UUID
    result: CertificateSourceMutationResult


class CertificateSourceCheckProjection(BaseModel):
    """Health report bound to the terminal profile subject."""

    model_config = _CONFIG

    profile_id: UUID
    result: CertificateSourceCheckReport

    @field_validator("result")
    @classmethod
    def _validate_report(cls, result: CertificateSourceCheckReport) -> CertificateSourceCheckReport:
        names = tuple(entry.name for entry in result.entries)
        active_names = tuple(entry.name for entry in result.entries if entry.active)
        expected_warnings = any(entry.result in PROBE_RESULTS_NEEDING_ATTENTION for entry in result.entries)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ValueError("certificate source health report is not canonically ordered")
        if len(active_names) > 1 or result.has_warnings is not expected_warnings:
            raise ValueError("certificate source health report has inconsistent summary facts")
        return result


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
        request_type, private_result_type, is_mutation = _OPERATION_SHAPES[self._definition_id]
        profile_id = getattr(payload, "profile_id", None)
        if (
            type(payload) is not request_type
            or request.definition_id != self._definition_id
            or not isinstance(profile_id, UUID)
            or request.subject_ref != profile_operation_subject(str(profile_id))
            or context.identity.definition_id != self._definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        await context.events.phase(_phase(self._definition_id, "preflight"))
        if is_mutation:

            async def commit() -> str:
                async with context.cancellation.irreversible_section():
                    await context.events.effect(OperationEffect.UNKNOWN)
                    await context.events.phase(_phase(self._definition_id, "commit"))
                    try:
                        result = await asyncio.to_thread(self._invoke_mutation, payload, context)
                    except CertificateSourceNotFoundError:
                        await context.events.effect(OperationEffect.NONE)
                        raise
                    checked = _validate_service_result(result, private_result_type)
                    effect = _mutation_effect(self._definition_id, checked)
                    await context.events.effect(effect)
                    await context.events.phase(_phase(self._definition_id, "settlement"))
                    return await context.operands.put(checked, written_at=now())

            return await await_cancellation_complete(commit(), task_name="certificate-source-mutation")

        async def read_and_publish() -> str:
            result = await asyncio.to_thread(self._invoke_read, payload)
            checked = _validate_service_result(result, private_result_type)
            await context.events.effect(OperationEffect.NONE)
            await context.events.phase(_phase(self._definition_id, "settlement"))
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


_OPERATION_SHAPES: dict[str, tuple[type[BaseModel], type[BaseModel], bool]] = {
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


def _validate_service_result[ResultModelT: BaseModel](value: object, expected: type[ResultModelT]) -> ResultModelT:
    if type(value) is not expected:
        raise ValueError("certificate source service returned an invalid result")
    return expected.model_validate_json(value.model_dump_json(), strict=True)


def _mutation_effect(definition_id: str, result: BaseModel) -> OperationEffect:
    if definition_id == CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID:
        mutation = _require_payload(result, CertificateSourceMutationResult)
        return OperationEffect.UPDATED if mutation.removed else OperationEffect.NONE
    return OperationEffect.UPDATED


def _phase(definition_id: str, stage: Literal["preflight", "commit", "settlement"]) -> str:
    return f"{definition_id}.{stage}"


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    ports: CertificateSourceOperationPorts,
    *,
    mutation: bool,
) -> OperationDefinition:
    phases = (
        (_phase(definition_id, "preflight"), _phase(definition_id, "commit"), _phase(definition_id, "settlement"))
        if mutation
        else (_phase(definition_id, "preflight"), _phase(definition_id, "settlement"))
    )
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=CertificateSourceOperationExecutor,
            build=lambda: CertificateSourceOperationExecutor(ports=ports, definition_id=definition_id),
        ),
        phase_codes=phases,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset(
                {OperationEffect.NONE, OperationEffect.UNKNOWN, OperationEffect.UPDATED}
                if mutation
                else {OperationEffect.NONE, OperationEffect.UNKNOWN}
            ),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=_HUMAN_FRONTENDS,
    )


def build_certificate_source_register_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound source registration with a fresh write authority."""
    return _definition(
        CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID,
        CertificateSourceRegisterRequest,
        CertificateSourceMutationResult,
        ports,
        mutation=True,
    )


def build_certificate_source_list_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound certificate-source inventory reading."""
    return _definition(
        CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID,
        CertificateSourceListRequest,
        CertificateSourceListResult,
        ports,
        mutation=False,
    )


def build_certificate_source_select_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound source selection with a fresh write authority."""
    return _definition(
        CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID,
        CertificateSourceSelectRequest,
        CertificateSourceMutationResult,
        ports,
        mutation=True,
    )


def build_certificate_source_remove_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound source removal with idempotent effect facts."""
    return _definition(
        CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID,
        CertificateSourceRemoveRequest,
        CertificateSourceMutationResult,
        ports,
        mutation=True,
    )


def build_certificate_source_check_definition(ports: CertificateSourceOperationPorts) -> OperationDefinition:
    """Declare profile-bound local health checking without mutation authority."""
    return _definition(
        CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID,
        CertificateSourceCheckRequest,
        CertificateSourceCheckReport,
        ports,
        mutation=False,
    )


def resolve_certificate_source_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require exact-profile human authority and fresh result disclosure."""
    payload = request.payload
    shape = _OPERATION_SHAPES.get(request.definition_id)
    if (
        shape is None
        or type(payload) is not shape[0]
        or not isinstance(
            payload,
            (
                CertificateSourceRegisterRequest,
                CertificateSourceListRequest,
                CertificateSourceSelectRequest,
                CertificateSourceRemoveRequest,
                CertificateSourceCheckRequest,
            ),
        )
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = payload.profile_id
    if (
        request.definition_id != context.contract.definition_id
        or profile_id != context.profile_id
        or request.subject_ref != profile_operation_subject(str(profile_id))
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if context.frontend not in _HUMAN_FRONTENDS:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    actions = _MUTATION_ACTIONS if shape[2] else _READ_ACTIONS
    if context.action not in actions:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)

    disclosures = frozenset[DisclosurePermission]()
    if context.action is AccessAction.OBSERVE:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
        disclosures = frozenset((cast(Any, disclosure),))
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None or schema.schema_id != request.definition_id + ".result":
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=DisclosureCategory.PROFILE_VALUES,
        )
        disclosures = frozenset((cast(Any, disclosure),))
    return ResolvedOperationAccess(
        request=OperationAccessRequest(
            profile_id=profile_id,
            definition_id=request.definition_id,
            action=context.action,
            frontend=context.frontend,
            periods=frozenset(),
            period_independent=True,
            destination_id=context.destination_id,
        ),
        policy=OperationAccessPolicy(
            definition_id=request.definition_id,
            definition_contract_digest=context.contract.definition_contract_digest,
            actions=actions,
            disclosures=disclosures,
            periods=frozenset(),
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=context.published_authority,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
            requires_human=True,
        ),
    )


def _profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if (
        receipt.identity.definition_id != definition_id
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("certificate source result contradicts its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("certificate source result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("certificate source result has an invalid profile subject")
    return profile_id


def project_certificate_source_register_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceRegisterProjection:
    """Project one successful source registration for its receipt profile."""
    private = _validate_service_result(result, CertificateSourceMutationResult)
    if not private.name or not private.certificate_path or private.removed:
        raise ValueError("certificate source registration result is incomplete")
    if receipt.effect is not OperationEffect.UPDATED:
        raise ValueError("certificate source registration effect is inconsistent")
    return CertificateSourceRegisterProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_list_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceListProjection:
    """Project a canonical source inventory for its receipt profile."""
    private = _validate_service_result(result, CertificateSourceListResult)
    if receipt.effect is not OperationEffect.NONE:
        raise ValueError("certificate source list effect is inconsistent")
    return CertificateSourceListProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_select_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceSelectProjection:
    """Project the newly selected source for its receipt profile."""
    private = _validate_service_result(result, CertificateSourceMutationResult)
    if not private.name or not private.certificate_path or not private.active or private.removed:
        raise ValueError("certificate source selection result is incomplete")
    if receipt.effect is not OperationEffect.UPDATED:
        raise ValueError("certificate source selection effect is inconsistent")
    return CertificateSourceSelectProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_remove_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceRemoveProjection:
    """Project a source removal, preserving its actual no-op or update effect."""
    private = _validate_service_result(result, CertificateSourceMutationResult)
    expected_effect = OperationEffect.UPDATED if private.removed else OperationEffect.NONE
    if not private.name or receipt.effect is not expected_effect:
        raise ValueError("certificate source removal result contradicts its effect")
    return CertificateSourceRemoveProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID),
        result=private,
    )


def project_certificate_source_check_result(
    result: BaseModel, receipt: OperationTerminalReceipt, /
) -> CertificateSourceCheckProjection:
    """Project local health facts for the profile identified by the receipt."""
    private = _validate_service_result(result, CertificateSourceCheckReport)
    if receipt.effect is not OperationEffect.NONE:
        raise ValueError("certificate source check effect is inconsistent")
    return CertificateSourceCheckProjection(
        profile_id=_profile_from_receipt(receipt, definition_id=CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID),
        result=private,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    projection_type: type[BaseModel],
    projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=request_type
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=projection_type
        ),
        access_resolver=resolve_certificate_source_access,
        result_projector=projector,
    )


def build_certificate_source_register_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind registration request and exact-profile result contracts."""
    return _registration(
        definition,
        request_type=CertificateSourceRegisterRequest,
        projection_type=CertificateSourceRegisterProjection,
        projector=project_certificate_source_register_result,
    )


def build_certificate_source_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind inventory request and exact-profile result contracts."""
    return _registration(
        definition,
        request_type=CertificateSourceListRequest,
        projection_type=CertificateSourceListProjection,
        projector=project_certificate_source_list_result,
    )


def build_certificate_source_select_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind selection request and exact-profile result contracts."""
    return _registration(
        definition,
        request_type=CertificateSourceSelectRequest,
        projection_type=CertificateSourceSelectProjection,
        projector=project_certificate_source_select_result,
    )


def build_certificate_source_remove_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind removal request and exact-profile result contracts."""
    return _registration(
        definition,
        request_type=CertificateSourceRemoveRequest,
        projection_type=CertificateSourceRemoveProjection,
        projector=project_certificate_source_remove_result,
    )


def build_certificate_source_check_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind health-check request and exact-profile result contracts."""
    return _registration(
        definition,
        request_type=CertificateSourceCheckRequest,
        projection_type=CertificateSourceCheckProjection,
        projector=project_certificate_source_check_result,
    )


__all__ = [
    "CERTIFICATE_SOURCE_CHECK_OPERATION_DEFINITION_ID",
    "CERTIFICATE_SOURCE_LIST_OPERATION_DEFINITION_ID",
    "CERTIFICATE_SOURCE_REGISTER_OPERATION_DEFINITION_ID",
    "CERTIFICATE_SOURCE_REMOVE_OPERATION_DEFINITION_ID",
    "CERTIFICATE_SOURCE_SELECT_OPERATION_DEFINITION_ID",
    "CertificateSourceCheckProjection",
    "CertificateSourceCheckRequest",
    "CertificateSourceListProjection",
    "CertificateSourceListRequest",
    "CertificateSourceOperationExecutor",
    "CertificateSourceOperationPorts",
    "CertificateSourceRegisterProjection",
    "CertificateSourceRegisterRequest",
    "CertificateSourceRemoveProjection",
    "CertificateSourceRemoveRequest",
    "CertificateSourceSelectProjection",
    "CertificateSourceSelectRequest",
    "build_certificate_source_check_definition",
    "build_certificate_source_check_registration",
    "build_certificate_source_list_definition",
    "build_certificate_source_list_registration",
    "build_certificate_source_register_definition",
    "build_certificate_source_register_registration",
    "build_certificate_source_remove_definition",
    "build_certificate_source_remove_registration",
    "build_certificate_source_select_definition",
    "build_certificate_source_select_registration",
    "project_certificate_source_check_result",
    "project_certificate_source_list_result",
    "project_certificate_source_register_result",
    "project_certificate_source_remove_result",
    "project_certificate_source_select_result",
    "resolve_certificate_source_access",
]
