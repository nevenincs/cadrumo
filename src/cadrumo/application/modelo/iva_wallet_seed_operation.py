"""Registered exact-profile operation for seeding IVA-wallet history."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
)
from ...core.period import Period
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.iva_compensation.errors import IvaCompensationSeedConflictError
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .iva_wallet_mutation import (
    IvaWalletCanonicalAmount,
    IvaWalletTaxpayerNif,
    bind_iva_wallet_profile_ports,
    build_iva_wallet_mutation_definition,
    iva_wallet_result_exceeds_limit,
    put_iva_wallet_mutation_report,
    require_iva_wallet_write_receipt,
    resolve_iva_wallet_mutation_access,
    validate_iva_wallet_amount,
)
from .iva_wallet_seed import ModeloIvaWalletSeedError, seed_iva_compensation_period_for_bucket
from .iva_wallet_seed_ports import ModeloIvaWalletSeedPortsFactory

MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID = "modelo.iva-wallet.seed"
_COMMIT_PHASE = f"{MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID}.commit"
_RESULT_PHASE = f"{MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID}.result"
_PHASES = (_COMMIT_PHASE, _RESULT_PHASE)


class ModeloIvaWalletSeedRequest(BaseModel):
    """Confidential opening-balance declaration scoped to one profile and period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod
    amount: IvaWalletCanonicalAmount

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        return validate_iva_wallet_amount(value)


class ModeloIvaWalletSeedProjection(BaseModel):
    """Allowlisted seed result retaining only the established CLI fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    period: PublicPeriod
    taxpayer_nif: IvaWalletTaxpayerNif
    amount: IvaWalletCanonicalAmount
    provenance: IvaCompensationStateProvenance
    register_status: Literal[None] = None

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        return validate_iva_wallet_amount(value)

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
    require_iva_wallet_write_receipt(
        receipt,
        definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        profile_id=projection.profile_id,
        message="IVA wallet seed result contradicts its terminal receipt",
    )
    if iva_wallet_result_exceeds_limit(projection):
        raise ValueError("IVA wallet seed result exceeds its projection limit")
    return projection


def _projection_from_state(
    *,
    profile_id: UUID,
    period: Period,
    state: IvaCompensationPeriodState,
    expected_amount: Decimal,
) -> ModeloIvaWalletSeedProjection:
    """Select and validate the small public result from the persisted seed state."""
    _require_seed_target(state, period)
    _require_seed_authority(state, period, expected_amount)
    return ModeloIvaWalletSeedProjection(
        profile_id=profile_id,
        period=PublicPeriod.from_period(period),
        taxpayer_nif=str(state.taxpayer_nif),
        amount=str(state.available_end_amount),
        provenance=state.provenance,
        register_status=None,
    )


def _require_seed_target(state: IvaCompensationPeriodState, period: Period) -> None:
    if state.period != period or state.filing_year != period.filing_year or state.taxpayer_nif is None:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_seed_authority(
    state: IvaCompensationPeriodState,
    period: Period,
    expected_amount: Decimal,
) -> None:
    reference = state.registry_snapshot_ref
    if (
        state.provenance is not IvaCompensationStateProvenance.OPERATOR_SEED
        or state.available_end_amount != expected_amount
        or state.available_end_amount < 0
        or state.status is not None
        or reference.modelo != form_for_role("iva.periodic")
        or reference.modelo_year != period.filing_year
        or reference.period != period.registry_token
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


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
        if request.definition_id != MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        period = payload.period.to_period()
        operation = context.authority_operation
        operation.snapshot("303", filing_year=period.filing_year, period=period.registry_token)
        ports = bind_iva_wallet_profile_ports(self._factory, profile_id=profile_id, operation=operation)

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
                return await put_iva_wallet_mutation_report(context, report)

        return await await_cancellation_complete(commit_and_publish(), task_name="modelo-iva-wallet-seed")


def build_modelo_iva_wallet_seed_definition(factory: ModeloIvaWalletSeedPortsFactory) -> OperationDefinition:
    """Declare a durable, confidential, profile-bound local mutation."""
    return build_iva_wallet_mutation_definition(
        definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        request_type=ModeloIvaWalletSeedRequest,
        result_type=ModeloIvaWalletSeedReport,
        executor_type=ModeloIvaWalletSeedExecutor,
        build=lambda: ModeloIvaWalletSeedExecutor(factory),
        phase_codes=_PHASES,
    )


def resolve_modelo_iva_wallet_seed_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require exact profile/period access and fresh COMMIT permission."""
    return resolve_iva_wallet_mutation_access(
        request,
        context,
        definition_id=MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
        payload_type=ModeloIvaWalletSeedRequest,
    )


def build_modelo_iva_wallet_seed_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the confidential request, bounded result and scoped access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloIvaWalletSeedProjection,
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
