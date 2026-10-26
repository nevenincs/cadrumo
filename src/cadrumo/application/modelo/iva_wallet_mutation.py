"""Contract shared by the operator-local IVA-wallet seed, override and correction operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..ledger.read_access import resolve_ledger_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.events import OperationEventCode
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import ProfileAccessPayload, require_access_request_profile_payload
from ..operations.public_period import PublicPeriod
from ..operations.registry import OperationReconciliationPolicy
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .iva_wallet_seed_ports import ModeloIvaWalletSeedPorts, ModeloIvaWalletSeedPortsFactory

IVA_WALLET_MUTATION_RESULT_MAX_BYTES = 16 * 1024
"""Encoded size ceiling of one wallet mutation's report and public projection."""

IvaWalletCanonicalAmount = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$",
    ),
]
"""Monetary text in the CLI's canonical two-decimal grammar."""

IvaWalletTaxpayerNif = Annotated[str, Field(min_length=1, max_length=32)]
"""The persisted wallet state's taxpayer NIF, as projected."""


def validate_iva_wallet_amount(value: str) -> str:
    """Keep monetary inputs and projections within the CLI's canonical grammar."""
    if try_parse_canonical_decimal(value, max_fraction_digits=2) is None:
        raise ValueError("wallet amounts must be canonical decimal text")
    return value


def bind_iva_wallet_profile_ports(
    factory: ModeloIvaWalletSeedPortsFactory,
    *,
    profile_id: str,
    operation: PinnedAuthorityOperation,
) -> ModeloIvaWalletSeedPorts:
    """Build the wallet repository bundle for one profile and reject a foreign factory result."""
    ports = factory(bucket_id=profile_id, operation=operation)
    if ports.work_unit_repository.bucket_id != profile_id or ports.calculation_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


class IvaWalletPeriodPayload(ProfileAccessPayload, Protocol):
    """A wallet mutation payload that names its profile and the filing period it writes."""

    @property
    def period(self) -> PublicPeriod:
        """The filing period the mutation targets."""
        ...


def build_iva_wallet_mutation_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build: Callable[[], object],
    phase_codes: tuple[OperationEventCode, ...],
) -> OperationDefinition:
    """Declare a durable, confidential, profile-bound local wallet mutation."""
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=result_type,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=executor_type,
            build=build,
        ),
        phase_codes=phase_codes,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
    )


def resolve_iva_wallet_mutation_access[PayloadT: IvaWalletPeriodPayload](
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[PayloadT],
) -> ResolvedOperationAccess:
    """Require exact profile/period access and fresh COMMIT permission."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=definition_id,
        payload_type=payload_type,
        access_profile_id=context.profile_id,
    )
    return resolve_ledger_commit_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset({payload.period.to_period()}),
    )


def iva_wallet_result_exceeds_limit(result: BaseModel) -> bool:
    """Report whether ``result`` encodes beyond the wallet mutation result ceiling."""
    return len(canonical_json_bytes(result.model_dump(mode="json"))) > IVA_WALLET_MUTATION_RESULT_MAX_BYTES


async def put_iva_wallet_mutation_report(context: OperationExecutorContext, report: BaseModel) -> str:
    """Persist a bounded wallet mutation report as the operation's encrypted result operand."""
    if iva_wallet_result_exceeds_limit(report):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return await context.operands.put(report, written_at=now())


def require_iva_wallet_write_receipt(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    message: str,
) -> None:
    """Raise ``ValueError(message)`` unless ``receipt`` settled this profile's wallet write.

    The write must have succeeded with an updating effect, name its result and
    carry no refusal or failure facts.
    """
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        effect=OperationEffect.UPDATED,
        message=message,
    )


__all__ = [
    "IVA_WALLET_MUTATION_RESULT_MAX_BYTES",
    "IvaWalletCanonicalAmount",
    "IvaWalletPeriodPayload",
    "IvaWalletTaxpayerNif",
    "bind_iva_wallet_profile_ports",
    "build_iva_wallet_mutation_definition",
    "iva_wallet_result_exceeds_limit",
    "put_iva_wallet_mutation_report",
    "require_iva_wallet_write_receipt",
    "resolve_iva_wallet_mutation_access",
    "validate_iva_wallet_amount",
]
