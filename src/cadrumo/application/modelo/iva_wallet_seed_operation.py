"""Registered exact-profile operation for seeding IVA-wallet history."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import canonical_json_bytes
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
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
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.iva_compensation.errors import IvaCompensationSeedConflictError
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
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
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .iva_wallet_seed import ModeloIvaWalletSeedError, seed_iva_compensation_period_for_bucket
from .iva_wallet_seed_ports import ModeloIvaWalletSeedPorts, ModeloIvaWalletSeedPortsFactory

MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID = "modelo.iva-wallet.seed"
_COMMIT_PHASE = f"{MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID}.commit"
_RESULT_PHASE = f"{MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID}.result"
_PHASES = (_COMMIT_PHASE, _RESULT_PHASE)
_MAX_RESULT_BYTES = 16 * 1024
_CanonicalAmount = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$",
    ),
]
_TaxpayerNif = Annotated[str, Field(min_length=1, max_length=32)]


def _validate_amount(value: str) -> str:
    """Keep monetary inputs and projections within the CLI's canonical grammar."""
    if try_parse_canonical_decimal(value, max_fraction_digits=2) is None:
        raise ValueError("wallet amounts must be canonical decimal text")
    return value


class ModeloIvaWalletSeedRequest(BaseModel):
    """Confidential opening-balance declaration scoped to one profile and period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod
    amount: _CanonicalAmount

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        return _validate_amount(value)


class ModeloIvaWalletSeedProjection(BaseModel):
    """Allowlisted seed result retaining only the established CLI fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    period: PublicPeriod
    taxpayer_nif: _TaxpayerNif
    amount: _CanonicalAmount
    provenance: IvaCompensationStateProvenance
    register_status: Literal[None] = None

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        return _validate_amount(value)

    @model_validator(mode="after")
    def _operator_seed_shape(self) -> Self:
        if self.provenance is not IvaCompensationStateProvenance.OPERATOR_SEED:
            raise ValueError("IVA wallet seed must retain operator-seed provenance")
        if Decimal(self.amount) < 0:
            raise ValueError("IVA wallet seed amount must be non-negative")
        return self


class ModeloIvaWalletSeedReport(BaseModel):
    """Private operation result before terminal-receipt-bound projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloIvaWalletSeedProjection
    local_write_performed: Literal[True]


def project_modelo_iva_wallet_seed_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release the bounded seed result only for its matching write receipt."""
    if type(result) is not ModeloIvaWalletSeedReport:
        raise ValueError("invalid IVA wallet seed operation result")
    report = ModeloIvaWalletSeedReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    if (
        receipt.identity.definition_id != MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("IVA wallet seed result contradicts its terminal receipt")
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
        raise ValueError("IVA wallet seed result exceeds its projection limit")
    return projection


def _profile_ports(
    factory: ModeloIvaWalletSeedPortsFactory,
    *,
    profile_id: str,
) -> ModeloIvaWalletSeedPorts:
    """Build the existing wallet repository bundle and reject a foreign factory result."""
    ports = factory(bucket_id=profile_id)
    if ports.work_unit_repository.bucket_id != profile_id or ports.calculation_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _projection_from_state(
    *,
    profile_id: UUID,
    period: Period,
    state: IvaCompensationPeriodState,
    expected_amount: Decimal,
) -> ModeloIvaWalletSeedProjection:
    """Select and validate the small public result from the persisted seed state."""
    reference = state.registry_snapshot_ref
    if (
        state.period != period
        or state.filing_year != period.filing_year
        or state.taxpayer_nif is None
        or state.provenance is not IvaCompensationStateProvenance.OPERATOR_SEED
        or state.available_end_amount != expected_amount
        or state.available_end_amount < 0
        or state.status is not None
        or reference.modelo != "303"
        or reference.modelo_year != period.filing_year
        or reference.period != period.registry_token
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ModeloIvaWalletSeedProjection(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        taxpayer_nif=str(state.taxpayer_nif),
        amount=str(state.available_end_amount),
        provenance=state.provenance,
        register_status=None,
    )


class ModeloIvaWalletSeedExecutor:
    """Run the existing canonical seed service inside one profile worker."""

    def __init__(self, factory: ModeloIvaWalletSeedPortsFactory) -> None:
        """Bind this executor to the composition-supplied exact-profile port factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloIvaWalletSeedRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Seed one period behind fresh access, pinned authority and COMMIT custody."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        subject = profile_operation_subject(profile_id)
        if (
            request.definition_id != MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        period = payload.period.to_period()
        operation = context.authority_operation
        operation.snapshot("303", filing_year=period.filing_year, period=period.registry_token)
        ports = _profile_ports(self._factory, profile_id=profile_id)

        async def commit_and_publish() -> str:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.phase(_COMMIT_PHASE)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    state = await asyncio.to_thread(
                        seed_iva_compensation_period_for_bucket,
                        bucket_id=profile_id,
                        period=period,
                        amount=Decimal(payload.amount),
                        ports=ports,
                        operation=operation,
                    )
                except (ModeloIvaWalletSeedError, IvaCompensationSeedConflictError):
                    await context.events.effect(OperationEffect.NONE)
                    raise

                await context.events.effect(OperationEffect.UPDATED)
                projection = _projection_from_state(
                    profile_id=payload.profile_id,
                    period=period,
                    state=state,
                    expected_amount=Decimal(payload.amount),
                )
                await context.events.phase(_RESULT_PHASE)
                report = ModeloIvaWalletSeedReport(projection=projection, local_write_performed=True)
                if len(canonical_json_bytes(report.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                return await context.operands.put(report, written_at=now())

        return await await_cancellation_complete(commit_and_publish(), task_name="modelo-iva-wallet-seed")


def build_modelo_iva_wallet_seed_definition(factory: ModeloIvaWalletSeedPortsFactory) -> OperationDefinition:
    """Declare a durable, confidential, profile-bound local mutation."""
    return OperationDefinition(
        definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        request_type=ModeloIvaWalletSeedRequest,
        result_type=ModeloIvaWalletSeedReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloIvaWalletSeedRequest,
            executor_type=ModeloIvaWalletSeedExecutor,
            build=lambda: ModeloIvaWalletSeedExecutor(factory),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_modelo_iva_wallet_seed_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require exact profile/period access and fresh COMMIT permission."""
    if request.definition_id != MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, ModeloIvaWalletSeedRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset({payload.period.to_period()}),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_modelo_iva_wallet_seed_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the confidential request, bounded result and scoped access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloIvaWalletSeedRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloIvaWalletSeedProjection,
        ),
        result_projector=project_modelo_iva_wallet_seed_result,
        access_resolver=resolve_modelo_iva_wallet_seed_access,
    )


__all__ = [
    "MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID",
    "ModeloIvaWalletSeedExecutor",
    "ModeloIvaWalletSeedProjection",
    "ModeloIvaWalletSeedReport",
    "ModeloIvaWalletSeedRequest",
    "build_modelo_iva_wallet_seed_definition",
    "build_modelo_iva_wallet_seed_registration",
    "project_modelo_iva_wallet_seed_result",
    "resolve_modelo_iva_wallet_seed_access",
]
