"""Registered exact-profile operation for recording IVA-wallet overrides."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, StringConstraints, field_validator, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.buckets.event import BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH
from ...domain.iva_compensation.reconciliation import (
    IvaCompensationAuthority,
    IvaCompensationDecisionReason,
    IvaCompensationDivergence,
    IvaCompensationReconciliationDecision,
)
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
from .iva_wallet_seed import ModeloIvaWalletSeedError, record_iva_compensation_override_for_bucket
from .iva_wallet_seed_ports import ModeloIvaWalletSeedPortsFactory

MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID = "modelo.iva-wallet.override"
_COMMIT_PHASE = f"{MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID}.commit"
_RESULT_PHASE = f"{MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID}.result"
_PHASES = (_COMMIT_PHASE, _RESULT_PHASE)
_EvidenceLocator = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH),
]


class ModeloIvaWalletOverrideRequest(BaseModel):
    """Confidential taxpayer override intent scoped to one profile and period."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    period: PublicPeriod
    amount: IvaWalletCanonicalAmount
    reason: OperatorReason
    evidence_locator: _EvidenceLocator

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        return validate_iva_wallet_amount(value)


class ModeloIvaWalletOverrideProjection(BaseModel):
    """Allowlisted override result retaining only the established CLI fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    period: PublicPeriod
    taxpayer_nif: IvaWalletTaxpayerNif
    amount: IvaWalletCanonicalAmount
    reason: OperatorReason
    evidence_locator: _EvidenceLocator
    selected_authority: IvaCompensationAuthority
    divergence: IvaCompensationDivergence

    @field_validator("amount")
    @classmethod
    def _canonical_amount(cls, value: str) -> str:
        return validate_iva_wallet_amount(value)

    @model_validator(mode="after")
    def _operator_override_shape(self) -> Self:
        if Decimal(self.amount) < 0:
            raise ValueError("IVA wallet override amount must be non-negative")
        if self.selected_authority != "taxpayer_override" or self.divergence != "override":
            raise ValueError("IVA wallet override must retain taxpayer-override authority")
        return self


class ModeloIvaWalletOverrideReport(BaseModel):
    """Private operation result before terminal-receipt-bound projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloIvaWalletOverrideProjection
    local_write_performed: Literal[True]


def project_modelo_iva_wallet_override_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release the bounded override result only for its matching write receipt."""
    if type(result) is not ModeloIvaWalletOverrideReport:
        raise ValueError("invalid IVA wallet override operation result")
    report = ModeloIvaWalletOverrideReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    require_iva_wallet_write_receipt(
        receipt,
        definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
        profile_id=projection.profile_id,
        message="IVA wallet override result contradicts its terminal receipt",
    )
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > IVA_WALLET_MUTATION_RESULT_MAX_BYTES:
        raise ValueError("IVA wallet override result exceeds its projection limit")
    return projection


def _projection_from_decision(
    *,
    profile_id: UUID,
    period: PublicPeriod,
    decision: IvaCompensationReconciliationDecision,
    expected_amount: Decimal,
    reason: str,
    evidence_locator: str,
) -> ModeloIvaWalletOverrideProjection:
    """Select only the taxpayer override facts proved by its persisted decision."""
    _require_override_target(decision, period)
    _require_override_decision(decision, expected_amount=expected_amount, reason=reason)
    return ModeloIvaWalletOverrideProjection(
        profile_id=profile_id,
        period=period,
        taxpayer_nif=str(decision.taxpayer_nif),
        amount=str(decision.selected_amount),
        reason=reason,
        evidence_locator=evidence_locator,
        selected_authority=decision.selected_authority,
        divergence=decision.divergence,
    )


def _require_override_target(
    decision: IvaCompensationReconciliationDecision,
    period: PublicPeriod,
) -> None:
    if (
        decision.target_year != period.filing_year
        or decision.target_period != period.to_period()
        or not decision.taxpayer_nif
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _require_override_decision(
    decision: IvaCompensationReconciliationDecision,
    *,
    expected_amount: Decimal,
    reason: str,
) -> None:
    if (
        decision.selected_authority != "taxpayer_override"
        or decision.selected_amount != expected_amount
        or decision.override_amount != expected_amount
        or decision.divergence != "override"
        or decision.blocked
        or decision.reason_identity is not IvaCompensationDecisionReason.TAXPAYER_OVERRIDE
        or decision.operator_explanation != reason
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


class ModeloIvaWalletOverrideExecutor:
    """Run the existing canonical override service inside one profile worker."""

    def __init__(self, factory: ModeloIvaWalletSeedPortsFactory) -> None:
        """Bind this executor to the composition-supplied exact-profile port factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloIvaWalletOverrideRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Record one override behind fresh access, pinned authority and COMMIT custody."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        period = payload.period.to_period()
        operation = context.authority_operation
        operation.snapshot("303", filing_year=period.filing_year, period=period.registry_token)
        ports = bind_iva_wallet_profile_ports(
            self._factory, profile_id=profile_id, operation=context.authority_operation
        )

        async def commit_and_publish() -> str:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.phase(_COMMIT_PHASE)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    decision = await asyncio.to_thread(
                        record_iva_compensation_override_for_bucket,
                        bucket_id=profile_id,
                        period=period,
                        amount=Decimal(payload.amount),
                        reason=payload.reason,
                        evidence_locator=payload.evidence_locator,
                        ports=ports,
                        operation=operation,
                    )
                except ModeloIvaWalletSeedError:
                    await context.events.effect(OperationEffect.NONE)
                    raise

                await context.events.effect(OperationEffect.UPDATED)
                projection = _projection_from_decision(
                    profile_id=payload.profile_id,
                    period=payload.period,
                    decision=decision,
                    expected_amount=Decimal(payload.amount),
                    reason=payload.reason,
                    evidence_locator=payload.evidence_locator,
                )
                await context.events.phase(_RESULT_PHASE)
                report = ModeloIvaWalletOverrideReport(projection=projection, local_write_performed=True)
                if len(canonical_json_bytes(report.model_dump(mode="json"))) > IVA_WALLET_MUTATION_RESULT_MAX_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                return await context.operands.put(report, written_at=now())

        return await await_cancellation_complete(commit_and_publish(), task_name="modelo-iva-wallet-override")


def build_modelo_iva_wallet_override_definition(factory: ModeloIvaWalletSeedPortsFactory) -> OperationDefinition:
    """Declare a durable, confidential, profile-bound local mutation."""
    return OperationDefinition(
        definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
        request_type=ModeloIvaWalletOverrideRequest,
        result_type=ModeloIvaWalletOverrideReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloIvaWalletOverrideRequest,
            executor_type=ModeloIvaWalletOverrideExecutor,
            build=lambda: ModeloIvaWalletOverrideExecutor(factory),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_modelo_iva_wallet_override_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require exact profile/period access and fresh COMMIT permission."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
        payload_type=ModeloIvaWalletOverrideRequest,
        access_profile_id=context.profile_id,
    )
    return resolve_ledger_commit_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset({payload.period.to_period()}),
    )


def build_modelo_iva_wallet_override_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the confidential request, bounded result and scoped access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloIvaWalletOverrideProjection,
        result_projector=project_modelo_iva_wallet_override_result,
        access_resolver=resolve_modelo_iva_wallet_override_access,
    )


__all__ = [
    "MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID",
    "ModeloIvaWalletOverrideExecutor",
    "ModeloIvaWalletOverrideProjection",
    "ModeloIvaWalletOverrideReport",
    "ModeloIvaWalletOverrideRequest",
    "build_modelo_iva_wallet_override_definition",
    "build_modelo_iva_wallet_override_registration",
    "project_modelo_iva_wallet_override_result",
    "resolve_modelo_iva_wallet_override_access",
]
