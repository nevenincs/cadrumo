"""Registered exact-profile read of persisted IVA wallet history."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.iva_compensation.reconciliation import IvaCompensationDecisionReason
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
from .iva_remote_state import list_iva_compensation_history
from .iva_remote_state_ports import IvaRemoteStatePort
from .remote_state_models import (
    IvaCompensationCarryForwardLotRow,
    IvaCompensationHistoryReport,
    IvaCompensationHistoryRow,
    IvaWalletAuthorityDecisionRow,
)

IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID = "live.iva-wallet.history"


class IvaWalletHistoryRequest(CredentialFreeOperationRequest):
    """One exact-profile local history query."""

    profile_id: UUID
    as_of_year: int | None = Field(default=None, ge=2000, le=2099)


class IvaWalletHistoryRowPublic(BaseModel):
    """Closed public form of one stored history row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    year: int
    period: PublicPeriod
    provenance: IvaCompensationStateProvenance
    register_status: str | None
    presented_at: datetime
    prior_pending_amount: str | None
    applied_amount: str | None
    pending_for_later_amount: str | None
    period_result_amount: str | None
    final_result_amount: str | None
    generated_amount: str
    available_end_amount: str

    @classmethod
    def from_row(cls, row: IvaCompensationHistoryRow) -> IvaWalletHistoryRowPublic:
        """Copy one private history row into the closed public shape."""
        return cls.model_validate({**row.model_dump(), "period": PublicPeriod.from_period(row.period)})

    def to_row(self) -> IvaCompensationHistoryRow:
        """Restore a validated row for the existing CLI presentation."""
        return IvaCompensationHistoryRow.model_validate({**self.model_dump(), "period": self.period.to_period()})


class IvaWalletCarryForwardLotPublic(BaseModel):
    """Closed public form of one carry-forward lot."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    taxpayer_ref: str
    source_filing_year: int
    source_period: PublicPeriod
    generated_amount: str
    applied_amount: str
    remaining_amount: str
    age_years: int
    expiry_review_state: str
    source_observation_key: str

    @classmethod
    def from_row(cls, row: IvaCompensationCarryForwardLotRow) -> IvaWalletCarryForwardLotPublic:
        """Copy one private lot into the closed public shape."""
        return cls.model_validate({**row.model_dump(), "source_period": PublicPeriod.from_period(row.source_period)})

    def to_row(self) -> IvaCompensationCarryForwardLotRow:
        """Restore a validated lot for the existing CLI presentation."""
        return IvaCompensationCarryForwardLotRow.model_validate(
            {**self.model_dump(), "source_period": self.source_period.to_period()}
        )


class IvaWalletDecisionPublic(BaseModel):
    """Closed public form of a persisted wallet authority decision."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    taxpayer_ref: str
    target_year: int
    target_period: PublicPeriod
    selected_authority: str
    selected_amount: str | None
    wallet_amount: str | None
    local_recurrence_amount: str | None
    override_amount: str | None
    divergence: str
    blocked: bool
    stale_wallet: bool
    reason_identity: IvaCompensationDecisionReason
    operator_explanation: str | None
    wallet_captured_at: datetime | None
    decided_at: datetime
    authority_sources: tuple[str, ...]

    @classmethod
    def from_row(cls, row: IvaWalletAuthorityDecisionRow) -> IvaWalletDecisionPublic:
        """Copy one private decision into the closed public shape."""
        return cls.model_validate({**row.model_dump(), "target_period": PublicPeriod.from_period(row.target_period)})

    def to_row(self) -> IvaWalletAuthorityDecisionRow:
        """Restore a validated decision for the existing CLI presentation."""
        return IvaWalletAuthorityDecisionRow.model_validate(
            {**self.model_dump(), "target_period": self.target_period.to_period()}
        )


class IvaWalletHistoryProjection(BaseModel):
    """Profile-bound public result retaining the existing report's facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    row_count: int = Field(ge=0)
    rows: tuple[IvaWalletHistoryRowPublic, ...]
    as_of_year: int
    carry_forward_lot_count: int = Field(ge=0)
    carry_forward_lots: tuple[IvaWalletCarryForwardLotPublic, ...]
    unallocated_applied_amount: str
    authority_decision_count: int = Field(ge=0)
    authority_decisions: tuple[IvaWalletDecisionPublic, ...]

    @model_validator(mode="after")
    def _counts_match(self) -> IvaWalletHistoryProjection:
        """Refuse missing or surplus rows before any frontend sees the result."""
        if (
            self.row_count != len(self.rows)
            or self.carry_forward_lot_count != len(self.carry_forward_lots)
            or self.authority_decision_count != len(self.authority_decisions)
        ):
            raise ValueError("IVA wallet history counts do not match rows")
        return self

    @classmethod
    def from_report(cls, profile_id: UUID, report: IvaCompensationHistoryReport) -> IvaWalletHistoryProjection:
        """Project the canonical report with its exact profile identity."""
        return cls(
            profile_id=profile_id,
            row_count=report.row_count,
            rows=tuple(IvaWalletHistoryRowPublic.from_row(row) for row in report.rows),
            as_of_year=report.as_of_year,
            carry_forward_lot_count=report.carry_forward_lot_count,
            carry_forward_lots=tuple(IvaWalletCarryForwardLotPublic.from_row(row) for row in report.carry_forward_lots),
            unallocated_applied_amount=report.unallocated_applied_amount,
            authority_decision_count=report.authority_decision_count,
            authority_decisions=tuple(IvaWalletDecisionPublic.from_row(row) for row in report.authority_decisions),
        )

    def to_report(self) -> IvaCompensationHistoryReport:
        """Restore the canonical report for the existing CLI formatters."""
        return IvaCompensationHistoryReport(
            row_count=self.row_count,
            rows=tuple(row.to_row() for row in self.rows),
            as_of_year=self.as_of_year,
            carry_forward_lot_count=self.carry_forward_lot_count,
            carry_forward_lots=tuple(row.to_row() for row in self.carry_forward_lots),
            unallocated_applied_amount=self.unallocated_applied_amount,
            authority_decision_count=self.authority_decision_count,
            authority_decisions=tuple(row.to_row() for row in self.authority_decisions),
        )


class IvaWalletHistoryExecutor:
    """Read local encrypted history in the authenticated profile worker."""

    def __init__(self, ports_factory: Callable[[PinnedAuthorityOperation], IvaRemoteStatePort]) -> None:
        """Retain the entrypoint-composed local persistence port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self, request: OperationRequest[IvaWalletHistoryRequest], context: OperationExecutorContext
    ) -> str:
        """Read and store the report through supervised secure custody."""
        payload = request.payload
        if (
            request.definition_id != IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID
            or request.subject_ref != profile_operation_subject(str(payload.profile_id))
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != str(payload.profile_id)
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            report = await asyncio.to_thread(
                list_iva_compensation_history,
                ports=self._ports_factory(context.authority_operation),
                as_of_year=payload.as_of_year,
            )
            result = IvaWalletHistoryProjection.from_report(payload.profile_id, report)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="iva-wallet-history")


def build_iva_wallet_history_definition(
    ports_factory: Callable[[PinnedAuthorityOperation], IvaRemoteStatePort],
) -> OperationDefinition:
    """Declare a recorded local read with no provider or commit authority."""
    return OperationDefinition(
        definition_id=IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,
        request_type=IvaWalletHistoryRequest,
        result_type=IvaWalletHistoryProjection,
        executor_factory=OperationExecutorFactory(
            request_type=IvaWalletHistoryRequest,
            executor_type=IvaWalletHistoryExecutor,
            build=lambda: IvaWalletHistoryExecutor(ports_factory),
        ),
        phase_codes=(IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID,),
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
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def resolve_iva_wallet_history_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require all-period profile access for carried balances and decisions."""
    if request.definition_id != IVA_WALLET_HISTORY_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, IvaWalletHistoryRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def build_iva_wallet_history_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the closed request and result schemas to all-period access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=IvaWalletHistoryRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=IvaWalletHistoryProjection
        ),
        access_resolver=resolve_iva_wallet_history_access,
    )
