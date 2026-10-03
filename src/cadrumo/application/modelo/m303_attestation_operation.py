"""Registered profile-worker admission of ordinary M303 Modelo 390 evidence."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.hex_ids import WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...core.time.utc import validate_utc_aware
from ...domain.attachments.m303_filing_evidence import M303Exonerado390ApplicabilityAssertion
from ...domain.attachments.protocols import AttachmentStoreProtocol
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_errors import M303Exonerado390AttestationUnadmissibleError
from .m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
    M303Exonerado390ApplicabilityAttestationRequest,
    admit_m303_exonerado_390_applicability_attestation,
)
from .profile_readiness_gate import load_modelo_work_profile
from .work_lifecycle import ActiveWorkUnitUse, require_active_work_unit
from .work_lifecycle_ports import ActiveWorkLifecyclePortsFactory

MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID = "modelo.work.m303_attestation"


class ModeloWorkM303AttestationRequest(CredentialFreeOperationRequest):
    """Exact profile and one explicit work-unit or period target."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    work_unit_id: WorkUnitId | None = None
    period: PublicPeriod | None = None
    observed_at: datetime
    actor: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _utc_observation(self) -> Self:
        validate_utc_aware(self.observed_at)
        if (self.work_unit_id is None) == (self.period is None):
            raise ValueError("M303 attestation requires exactly one target")
        return self

    @property
    def subject_ref(self) -> str:
        """Address the selected work unit or the exact owning profile."""
        return self.work_unit_id or profile_operation_subject(str(self.profile_id))


class ModeloWorkM303AttestationPublicResultV2(BaseModel):
    """Encrypted-result attachment identity bound to the persisted work target."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[2] = 2
    profile_id: UUID
    work_unit_id: WorkUnitId | None
    filing_year: FilingYear
    period: PublicPeriod
    attachment_id: Hex64Str
    sha256: Hex64Str

    @model_validator(mode="after")
    def _bound_admission(self) -> Self:
        if self.attachment_id != self.sha256 or self.period.filing_year != self.filing_year:
            raise ValueError("M303 attestation receipt identity or period does not match")
        return self

    def to_admission(self) -> M303Exonerado390ApplicabilityAttestationAdmission:
        """Restore the canonical evidence identity for the TUI handoff."""
        return M303Exonerado390ApplicabilityAttestationAdmission(attachment_id=self.attachment_id, sha256=self.sha256)


class ModeloWorkM303AttestationExecutor:
    """Admit and store evidence wholly inside the retained profile worker."""

    def __init__(
        self,
        *,
        work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
        attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
    ) -> None:
        self._work_lifecycle_ports_factory = work_lifecycle_ports_factory
        self._attachment_store_factory = attachment_store_factory

    async def execute(
        self, request: OperationRequest[ModeloWorkM303AttestationRequest], context: OperationExecutorContext
    ) -> str:
        """Guard the attachment write and store only its typed receipt."""
        payload = request.payload
        if (
            request.definition_id != MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID
            or request.subject_ref != payload.subject_ref
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        await context.events.phase("modelo.work.m303_attestation.preconditions")

        def admit() -> ModeloWorkM303AttestationPublicResultV2:
            bucket_id = str(payload.profile_id)
            if require_active_bucket_id() != bucket_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if payload.work_unit_id is not None:
                ports = self._work_lifecycle_ports_factory()
                if ports.work_unit_repository.bucket_id != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                unit = require_active_work_unit(
                    ports.work_unit_repository.load(),
                    work_unit_id=payload.work_unit_id,
                    repository_bucket_id=ports.work_unit_repository.bucket_id,
                    use=ActiveWorkUnitUse.CALCULATE,
                )
                if unit.bucket_id != bucket_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                if str(unit.modelo) != "303":
                    raise M303Exonerado390AttestationUnadmissibleError(
                        "Modelo 390 applicability attestation requires a Modelo 303 work unit",
                        context={"work_unit_id": unit.work_unit_id},
                    )
                period = unit.period
            else:
                if payload.period is None:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                period = payload.period.to_period()
            profile = load_modelo_work_profile(
                bucket_id=bucket_id,
                profile_decode_context=context.authority_operation.profile_decode_context(),
            )
            admission = admit_m303_exonerado_390_applicability_attestation(
                bucket_id=bucket_id,
                request=M303Exonerado390ApplicabilityAttestationRequest(
                    filing_year=period.filing_year,
                    period=period,
                    asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
                    observed_at=payload.observed_at,
                ),
                actor=payload.actor,
                operation=context.authority_operation,
                store=self._attachment_store_factory(bucket_id),
                profile=profile,
            )
            return ModeloWorkM303AttestationPublicResultV2(
                profile_id=payload.profile_id,
                work_unit_id=payload.work_unit_id,
                filing_year=period.filing_year,
                period=PublicPeriod.from_period(period),
                attachment_id=admission.attachment_id,
                sha256=admission.sha256,
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(admit)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="modelo-work-m303-attestation")


def build_modelo_work_m303_attestation_definition(
    *,
    work_lifecycle_ports_factory: ActiveWorkLifecyclePortsFactory,
    attachment_store_factory: Callable[[str], AttachmentStoreProtocol],
) -> OperationDefinition:
    """Bind the canonical secure-attachment admission as a worker operation."""

    def build() -> ModeloWorkM303AttestationExecutor:
        return ModeloWorkM303AttestationExecutor(
            work_lifecycle_ports_factory=work_lifecycle_ports_factory,
            attachment_store_factory=attachment_store_factory,
        )

    return OperationDefinition(
        definition_id=MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkM303AttestationRequest,
        result_type=ModeloWorkM303AttestationPublicResultV2,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkM303AttestationRequest,
            executor_type=ModeloWorkM303AttestationExecutor,
            build=build,
        ),
        phase_codes=("modelo.work.m303_attestation.preconditions",),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_m303_attestation_registration(
    definition: OperationDefinition, *, access_resolver: OperationAccessResolver | None = None
) -> OperationPublicDefinitionRegistrationV1:
    """Bind schema version two and the composition-owned exact target."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=2,
            model_type=ModeloWorkM303AttestationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=2,
            model_type=ModeloWorkM303AttestationPublicResultV2,
        ),
        access_resolver=access_resolver,
    )


__all__ = [
    "MODELO_WORK_M303_ATTESTATION_OPERATION_DEFINITION_ID",
    "ModeloWorkM303AttestationPublicResultV2",
    "ModeloWorkM303AttestationRequest",
    "build_modelo_work_m303_attestation_definition",
    "build_modelo_work_m303_attestation_registration",
]
