"""Registered exact-profile operation for a local IVA-wallet correction."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.modelos.filing_text import OperatorReason
from ..ledger.read_access import resolve_ledger_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .iva_wallet_mutation import (
    IVA_WALLET_MUTATION_RESULT_MAX_BYTES,
    IvaWalletCanonicalAmount,
    IvaWalletTaxpayerNif,
    bind_iva_wallet_profile_ports,
    require_iva_wallet_write_receipt,
    validate_iva_wallet_amount,
)
from .iva_wallet_seed import (
    ModeloIvaWalletSeedError,
    correct_iva_compensation_period_for_bucket,
)
from .iva_wallet_seed_ports import ModeloIvaWalletSeedPortsFactory

MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID = "modelo.iva-wallet.correct"
_COMMIT_PHASE = f"{MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID}.commit"
_RESULT_PHASE = f"{MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID}.result"
_PHASES = (_COMMIT_PHASE, _RESULT_PHASE)


class ModeloIvaWalletCorrectionRequest(BaseModel):
    """Confidential correction intent scoped to one profile and filing period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod
    amount: IvaWalletCanonicalAmount
    reason: OperatorReason

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        return validate_iva_wallet_amount(value)


class ModeloIvaWalletCorrectionProjection(BaseModel):
    """Allowlisted correction result retaining only the established CLI fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    period: PublicPeriod
    taxpayer_nif: IvaWalletTaxpayerNif
    previous_amount: IvaWalletCanonicalAmount
    amount: IvaWalletCanonicalAmount
    provenance: IvaCompensationStateProvenance
    register_status: Literal[None] = None
    reason: OperatorReason

    @field_validator("previous_amount", "amount")
    @classmethod
    def _canonical_amounts(cls, value: str) -> str:
        return validate_iva_wallet_amount(value)

    @model_validator(mode="after")
    def _operator_correction_shape(self) -> Self:
        if self.provenance is not IvaCompensationStateProvenance.OPERATOR_CORRECTION:
            raise ValueError("IVA wallet correction must retain operator-correction provenance")
        if Decimal(self.amount) < 0 or Decimal(self.previous_amount) < 0:
            raise ValueError("IVA wallet correction amounts must be non-negative")
        return self


class ModeloIvaWalletCorrectionReport(BaseModel):
    """Private operation result before terminal-receipt-bound projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloIvaWalletCorrectionProjection
    local_write_performed: Literal[True]


def project_modelo_iva_wallet_correction_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release the bounded correction result only for its matching write receipt."""
    if type(result) is not ModeloIvaWalletCorrectionReport:
        raise ValueError("invalid IVA wallet correction operation result")
    report = ModeloIvaWalletCorrectionReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    require_iva_wallet_write_receipt(
        receipt,
        definition_id=MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
        profile_id=projection.profile_id,
        message="IVA wallet correction result contradicts its terminal receipt",
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > IVA_WALLET_MUTATION_RESULT_MAX_BYTES:
        raise ValueError("IVA wallet correction result exceeds its projection limit")
    return projection


class ModeloIvaWalletCorrectionExecutor:
    """Run the existing guarded correction service in one profile worker."""

    def __init__(self, factory: ModeloIvaWalletSeedPortsFactory) -> None:
        """Bind this executor to the application port factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloIvaWalletCorrectionRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Correct one seeded period behind a fresh COMMIT fence."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        period = payload.period.to_period()
        ports = bind_iva_wallet_profile_ports(
            self._factory, profile_id=profile_id, operation=context.authority_operation
        )

        async def commit_and_publish() -> str:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.phase(_COMMIT_PHASE)
                previous = await asyncio.to_thread(ports.iva_compensation_history_repository.load_period, period)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    state = await asyncio.to_thread(
                        correct_iva_compensation_period_for_bucket,
                        bucket_id=profile_id,
                        period=period,
                        amount=Decimal(payload.amount),
                        reason=payload.reason,
                        ports=ports,
                        operation=context.authority_operation,
                    )
                except ModeloIvaWalletSeedError:
                    await context.events.effect(OperationEffect.NONE)
                    raise

                await context.events.effect(OperationEffect.UPDATED)
                if previous is None:
                    raise ValueError("IVA wallet correction completed without a prior seeded period")
                projection = _projection_from_state(
                    profile_id=payload.profile_id,
                    period=period,
                    previous_state=previous,
                    state=state,
                    expected_amount=Decimal(payload.amount),
                    reason=payload.reason,
                )
                await context.events.phase(_RESULT_PHASE)
                report = ModeloIvaWalletCorrectionReport(projection=projection, local_write_performed=True)
                if len(canonical_json_bytes(report.model_dump(mode="json"))) > IVA_WALLET_MUTATION_RESULT_MAX_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                return await context.operands.put(report, written_at=now())

        return await await_cancellation_complete(commit_and_publish(), task_name="modelo-iva-wallet-correction")


def _projection_from_state(
    *,
    profile_id: UUID,
    period: Period,
    previous_state: IvaCompensationPeriodState,
    state: IvaCompensationPeriodState,
    expected_amount: Decimal,
    reason: str,
) -> ModeloIvaWalletCorrectionProjection:
    """Select and validate the small public result from persisted wallet states."""
    if (
        previous_state.period != period
        or state.period != period
        or state.taxpayer_nif is None
        or state.provenance is not IvaCompensationStateProvenance.OPERATOR_CORRECTION
        or state.available_end_amount != expected_amount
        or state.available_end_amount < 0
        or state.status is not None
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ModeloIvaWalletCorrectionProjection(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        taxpayer_nif=str(state.taxpayer_nif),
        previous_amount=str(previous_state.available_end_amount),
        amount=str(state.available_end_amount),
        provenance=state.provenance,
        register_status=None,
        reason=reason,
    )


def build_modelo_iva_wallet_correction_definition(
    factory: ModeloIvaWalletSeedPortsFactory,
) -> OperationDefinition:
    """Declare a durable, confidential, profile-bound local mutation."""
    return OperationDefinition(
        definition_id=MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
        request_type=ModeloIvaWalletCorrectionRequest,
        result_type=ModeloIvaWalletCorrectionReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloIvaWalletCorrectionRequest,
            executor_type=ModeloIvaWalletCorrectionExecutor,
            build=lambda: ModeloIvaWalletCorrectionExecutor(factory),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_modelo_iva_wallet_correction_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require exact profile/period access and fresh COMMIT permission."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
        payload_type=ModeloIvaWalletCorrectionRequest,
        access_profile_id=context.profile_id,
    )
    return resolve_ledger_commit_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset({payload.period.to_period()}),
    )


def build_modelo_iva_wallet_correction_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the confidential request, bounded result and scoped access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloIvaWalletCorrectionProjection,
        result_projector=project_modelo_iva_wallet_correction_result,
        access_resolver=resolve_modelo_iva_wallet_correction_access,
    )


__all__ = [
    "MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID",
    "ModeloIvaWalletCorrectionExecutor",
    "ModeloIvaWalletCorrectionProjection",
    "ModeloIvaWalletCorrectionReport",
    "ModeloIvaWalletCorrectionRequest",
    "build_modelo_iva_wallet_correction_definition",
    "build_modelo_iva_wallet_correction_registration",
    "project_modelo_iva_wallet_correction_result",
    "resolve_modelo_iva_wallet_correction_access",
]
