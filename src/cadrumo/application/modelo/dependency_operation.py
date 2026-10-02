"""Registered cross-period dependency inspection under one authority pin."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..calculations.cross_period_clean_state import (
    cross_period_dependency_inventory,
    cross_period_dependency_requirements,
    evaluate_cross_period_clean_state,
)
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
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
from .dependency_projection import DependencyCleanStateSnapshot, DependencyInventoryItemSnapshot
from .dependency_read_ports import DependencyReadPortsFactory
from .verification_cross_period import cross_period_expected_member_sets_from_profile

MODELO_DEPENDENCY_OPERATION_DEFINITION_ID = "modelo.work.dependencies"


class ModeloDependencyRequest(CredentialFreeOperationRequest):
    """Public filing coordinates; taxpayer facts are never supplied by a client."""

    profile_id: UUID
    filing_year: int = Field(ge=1900, le=9999)
    modelo: Annotated[str, Field(pattern=r"^[0-9]{3}$")] | None = None
    period: PublicPeriod | None = None

    @model_validator(mode="after")
    def _target(self) -> Self:
        if self.period is not None and (self.modelo is None or self.period.filing_year != self.filing_year):
            raise ValueError("dependency period requires a matching modelo and filing year")
        return self


class ModeloDependencySnapshot(BaseModel):
    """Existing dependency inventory and optional private clean-state facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    filing_year: int = Field(ge=1900, le=9999)
    modelo_filter: Annotated[str, Field(pattern=r"^[0-9]{3}$")] | None
    period_filter: PublicPeriod | None
    target_modelos: tuple[str, ...]
    source_modelos: tuple[str, ...]
    items: tuple[DependencyInventoryItemSnapshot, ...]
    clean_state: DependencyCleanStateSnapshot | None

    @model_validator(mode="after")
    def _coordinates(self) -> Self:
        if any(item.target_filing_year != self.filing_year for item in self.items):
            raise ValueError("dependency inventory contains another filing year")
        if self.modelo_filter is not None and any(item.target_modelo != self.modelo_filter for item in self.items):
            raise ValueError("dependency inventory contains another target modelo")
        clean = self.clean_state
        if self.period_filter is None:
            if clean is not None:
                raise ValueError("unfiltered dependency inventory cannot contain private clean-state facts")
        elif (
            self.period_filter.filing_year != self.filing_year
            or self.modelo_filter is None
            or clean is None
            or clean.target_modelo != self.modelo_filter
            or clean.target_period != self.period_filter
            or clean.target_filing_year != self.filing_year
        ):
            raise ValueError("dependency clean state differs from its target")
        return self


class ModeloDependencyResult(BaseModel):
    """Private encrypted dependency operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    snapshot: ModeloDependencySnapshot


class ModeloDependencyProjection(BaseModel):
    """Independent closed projection of authorized dependency facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    snapshot: ModeloDependencySnapshot


def project_modelo_dependency_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only a successful no-effect result for the exact profile subject."""
    if type(result) is not ModeloDependencyResult:
        raise ValueError("invalid dependency result type")
    private = ModeloDependencyResult.model_validate(result.model_dump(mode="python"), strict=True)
    if (
        receipt.identity.definition_id != MODELO_DEPENDENCY_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(private.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("dependency result differs from its terminal receipt")
    return ModeloDependencyProjection(profile_id=private.profile_id, snapshot=private.snapshot)


def dependency_access_periods(
    payload: ModeloDependencyRequest, operation: PinnedAuthorityOperation
) -> frozenset[Period]:
    """Cover the target and every possible source period from published authority."""
    if payload.period is None:
        return frozenset[Period]()
    if payload.modelo is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    snapshot = operation.snapshot(payload.modelo, filing_year=payload.filing_year, period=payload.period.code)
    requirements = cross_period_dependency_requirements(snapshot)
    return frozenset({payload.period.to_period(), *(item.period for item in requirements)})


class ModeloDependencyExecutor:
    """Evaluate canonical clean state without opening a new public authority."""

    def __init__(self, factory: DependencyReadPortsFactory) -> None:
        """Retain the host's exact-profile capability factory."""
        self._factory = factory

    def _capture(self, payload: ModeloDependencyRequest, operation: PinnedAuthorityOperation) -> ModeloDependencyResult:
        profile_id = str(payload.profile_id)
        ports = self._factory(bucket_id=profile_id, operation=operation)
        repositories = ports.repositories
        if ports.bucket_id != profile_id or any(
            repository.bucket_id != profile_id
            for repository in (
                repositories.work_unit,
                repositories.calculation,
                repositories.filing,
                repositories.verification,
            )
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        inventory = cross_period_dependency_inventory(
            operation,
            filing_year=payload.filing_year,
            modelos=(payload.modelo,) if payload.modelo is not None else None,
        )
        clean_state = None
        if payload.period is not None and payload.modelo is not None:
            snapshot = operation.snapshot(payload.modelo, filing_year=payload.filing_year, period=payload.period.code)
            verdict = evaluate_cross_period_clean_state(
                snapshot,
                operation=operation,
                bucket_id=profile_id,
                observation_repository=repositories.observation,
                filing_repository=repositories.filing,
                calculation_repository=repositories.calculation,
                verification_repository=repositories.verification,
                justificante_repository=repositories.justificante,
                expected_member_sets=cross_period_expected_member_sets_from_profile(ports.profile),
                taxpayer_tax_id=ports.profile.tax_id,
                activity_start_date=ports.profile.activity_start_date,
                taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(ports.profile),
                m111_no_retenciones_periods=ports.m111_no_retenciones_periods,
            )
            allowed = dependency_access_periods(payload, operation)
            if verdict.bucket_id != profile_id or any(
                item.requirement.period not in allowed for item in verdict.dependencies
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.PERIOD_DENIED)
            clean_state = DependencyCleanStateSnapshot.from_verdict(verdict)
        return ModeloDependencyResult(
            profile_id=payload.profile_id,
            snapshot=ModeloDependencySnapshot(
                filing_year=payload.filing_year,
                modelo_filter=payload.modelo,
                period_filter=payload.period,
                target_modelos=inventory.target_modelos,
                source_modelos=inventory.source_modelos,
                items=tuple(DependencyInventoryItemSnapshot.from_item(item) for item in inventory.items),
                clean_state=clean_state,
            ),
        )

    async def execute(
        self, request: OperationRequest[ModeloDependencyRequest], context: OperationExecutorContext
    ) -> str:
        """Capture and encrypt current facts with cancellation-complete ownership."""
        payload = request.payload
        if (
            request.definition_id != MODELO_DEPENDENCY_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(MODELO_DEPENDENCY_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(self._capture, payload, context.authority_operation)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-dependency-read")


def build_modelo_dependency_definition(factory: DependencyReadPortsFactory) -> OperationDefinition:
    """Declare the registered read and its independent frontend projection."""
    return OperationDefinition(
        definition_id=MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,
        request_type=ModeloDependencyRequest,
        result_type=ModeloDependencyResult,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloDependencyRequest,
            executor_type=ModeloDependencyExecutor,
            build=lambda: ModeloDependencyExecutor(factory),
        ),
        phase_codes=(MODELO_DEPENDENCY_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_dependency_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Require every authority-derived source period before private inspection."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, ModeloDependencyRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
            str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        independent = payload.period is None
        admitted = context.admitted_request
        if admitted is not None and context.action in {
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
        }:
            if (
                admitted.profile_id != context.profile_id
                or admitted.definition_id != request.definition_id
                or admitted.action is not AccessAction.SUBMIT
                or admitted.period_independent != independent
                or (payload.period is not None and payload.period.to_period() not in admitted.periods)
                or (independent and admitted.periods)
            ):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            periods = admitted.periods
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            periods = dependency_access_periods(payload, context.authority_operation)
        disclosures = frozenset[DisclosurePermission]()
        if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                )
            )
        elif context.action is AccessAction.RESULT:
            schema = context.contract.result_schema
            if schema is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            disclosures = frozenset(
                (
                    DisclosurePermission(
                        destination_id=context.destination_id,
                        projection_id=schema.schema_id,
                        category=DisclosureCategory.TAX_VALUES,
                    ),
                )
            )
        return ResolvedOperationAccess(
            request=OperationAccessRequest(
                profile_id=context.profile_id,
                definition_id=request.definition_id,
                action=context.action,
                frontend=context.frontend,
                periods=periods,
                period_independent=independent,
                destination_id=context.destination_id,
            ),
            policy=OperationAccessPolicy(
                definition_id=request.definition_id,
                definition_contract_digest=context.contract.definition_contract_digest,
                actions=frozenset(
                    {
                        AccessAction.SUBMIT,
                        AccessAction.START,
                        AccessAction.RESUME,
                        AccessAction.OBSERVE,
                        AccessAction.RESULT,
                        AccessAction.CANCEL,
                        AccessAction.DETACH,
                    }
                ),
                disclosures=disclosures,
                periods=periods,
                allow_period_independent=independent,
                requires_all_periods=independent,
                backend=Availability.AVAILABLE,
                published_authority=context.published_authority,
                provider=Availability.NOT_REQUIRED,
                transaction_authority_required=False,
            ),
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloDependencyRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloDependencyProjection,
        ),
        access_resolver=resolve,
        result_projector=project_modelo_dependency_result,
    )
