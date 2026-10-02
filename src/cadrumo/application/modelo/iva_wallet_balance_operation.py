"""Registered exact-profile operation for an IVA-wallet balance read."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, field_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.decimal.grammar import is_non_negative_canonical_decimal
from ...core.filing_year import FilingYear
from ...core.hashing import canonical_json_bytes
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
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva_compensation.balance import CompensationExpiryYear, IvaWalletBalanceReport
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.iva_wallet_balance import query_iva_wallet_balance
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
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .iva_wallet_seed_ports import ModeloIvaWalletSeedPortsFactory

MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID = "modelo.iva-wallet.balance"
_READ_PHASE = f"{MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID}.read"
_MAX_RESULT_BYTES = 16 * 1024
_BalanceAmount = Annotated[str, Field(min_length=1, max_length=128)]


class ModeloIvaWalletBalanceRequest(CredentialFreeOperationRequest):
    """Profile and reference year for one local wallet balance query."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    as_of_year: FilingYear


class ModeloIvaWalletBalanceProjection(BaseModel):
    """Closed, bounded balance facts released for one profile and year."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    as_of_year: FilingYear
    total_balance: _BalanceAmount
    active_balance: _BalanceAmount
    expired_balance: _BalanceAmount
    lot_count: NonNegativeInt
    next_expiry_year: CompensationExpiryYear | None = None
    unallocated_applied_amount: _BalanceAmount

    @field_validator("total_balance", "active_balance", "expired_balance", "unallocated_applied_amount")
    @classmethod
    def _canonical_non_negative_amount(cls, value: str) -> str:
        if not is_non_negative_canonical_decimal(value):
            raise ValueError("wallet balance amounts must be non-negative canonical decimal text")
        return value

    @classmethod
    def from_report(
        cls,
        profile_id: UUID,
        report: IvaWalletBalanceReport,
        *,
        expected_year: int,
    ) -> ModeloIvaWalletBalanceProjection:
        """Copy the established application report into the bounded public shape."""
        if report.as_of_year != expected_year:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return cls(
            profile_id=profile_id,
            as_of_year=report.as_of_year,
            total_balance=str(report.total_balance),
            active_balance=str(report.active_balance),
            expired_balance=str(report.expired_balance),
            lot_count=report.lot_count,
            next_expiry_year=report.next_expiry_year,
            unallocated_applied_amount=str(report.unallocated_applied_amount),
        )


class ModeloIvaWalletBalanceOperationReport(BaseModel):
    """Private executor result kept distinct from the published schema model."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloIvaWalletBalanceProjection
    local_read_completed: Literal[True]


def project_modelo_iva_wallet_balance_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release only a bounded balance tied to its matching successful read receipt."""
    if type(result) is not ModeloIvaWalletBalanceOperationReport:
        raise ValueError("invalid IVA wallet balance operation result")
    report = ModeloIvaWalletBalanceOperationReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    if (
        receipt.identity.definition_id != MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("IVA wallet balance result contradicts its terminal receipt")
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
        raise ValueError("IVA wallet balance result exceeds its projection limit")
    return projection


def _profile_history_repository(
    factory: ModeloIvaWalletSeedPortsFactory,
    *,
    profile_id: str,
) -> IvaCompensationHistoryRepositoryProtocol:
    """Build the existing wallet port bundle for the requested profile only."""
    ports = factory(bucket_id=profile_id)
    if ports.work_unit_repository.bucket_id != profile_id or ports.calculation_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports.iva_compensation_history_repository


class ModeloIvaWalletBalanceExecutor:
    """Read the authenticated profile's local carry-forward balance."""

    def __init__(self, factory: ModeloIvaWalletSeedPortsFactory) -> None:
        """Retain the composition-supplied exact-profile wallet port factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloIvaWalletBalanceRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Capture one bounded balance projection and report no domain effect."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        subject = profile_operation_subject(profile_id)
        if (
            request.definition_id != MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        repository = _profile_history_repository(self._factory, profile_id=profile_id)

        async def capture() -> str:
            await context.events.phase(_READ_PHASE)

            def read_report() -> IvaWalletBalanceReport:
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                with validating_governed_facts(context.authority_operation):
                    return query_iva_wallet_balance(
                        as_of_year=payload.as_of_year,
                        repository=repository,
                    )

            report = await asyncio.to_thread(read_report)
            projection = ModeloIvaWalletBalanceProjection.from_report(
                payload.profile_id,
                report,
                expected_year=payload.as_of_year,
            )
            if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            report_result = ModeloIvaWalletBalanceOperationReport(
                projection=projection,
                local_read_completed=True,
            )
            reference = await context.operands.put(report_result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-iva-wallet-balance")


def build_modelo_iva_wallet_balance_definition(
    factory: ModeloIvaWalletSeedPortsFactory,
) -> OperationDefinition:
    """Declare a credential-free, recorded, nonmutating local balance read."""
    return OperationDefinition(
        definition_id=MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
        request_type=ModeloIvaWalletBalanceRequest,
        result_type=ModeloIvaWalletBalanceOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloIvaWalletBalanceRequest,
            executor_type=ModeloIvaWalletBalanceExecutor,
            build=lambda: ModeloIvaWalletBalanceExecutor(factory),
        ),
        phase_codes=(_READ_PHASE,),
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
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_modelo_iva_wallet_balance_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Require exact-profile access to the complete history through one year."""
    if request.definition_id != MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, ModeloIvaWalletBalanceRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset(),
    )


def build_modelo_iva_wallet_balance_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the closed request/result and exact-profile all-history access resolver."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloIvaWalletBalanceRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloIvaWalletBalanceProjection,
        ),
        result_projector=project_modelo_iva_wallet_balance_result,
        access_resolver=resolve_modelo_iva_wallet_balance_access,
    )


__all__ = [
    "MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID",
    "ModeloIvaWalletBalanceExecutor",
    "ModeloIvaWalletBalanceOperationReport",
    "ModeloIvaWalletBalanceProjection",
    "ModeloIvaWalletBalanceRequest",
    "build_modelo_iva_wallet_balance_definition",
    "build_modelo_iva_wallet_balance_registration",
    "project_modelo_iva_wallet_balance_result",
    "resolve_modelo_iva_wallet_balance_access",
]
