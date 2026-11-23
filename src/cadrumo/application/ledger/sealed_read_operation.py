"""Registered exact-profile read of which movements a finalized declaration seals.

The window asks this before it offers a change to many movements at once. It
answers every named movement from one load of the catalogue and of the
finalized declarations, with the same guard a batch edit applies when it
refuses a sealed row, so the window never decides sealing itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.read_capture import capture_read_result
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .action_ports import LedgerActionPorts, LedgerActionPortsFactory, require_exact_ledger_action_ports
from .actions_common import blockers_by_source_transaction_id, transaction_modelo_source_ids
from .batch_update_contracts import LEDGER_BATCH_UPDATE_MAX_ROWS
from .models import LedgerRemovalBlocker
from .read_access import resolve_ledger_request_read_access
from .removal_receipt_projection import LedgerRemovalBlockerProjection, project_removal_blockers

LEDGER_SEALED_READ_OPERATION_DEFINITION_ID = "ledger.sealed.read"
LEDGER_SEALED_READ_SEAL_SAMPLE = 8
"""How many of a row's sealing declarations it names as a sample; ``seal_count`` says how many there are."""

_TransactionId = Annotated[str, Field(min_length=1, max_length=128)]


class LedgerSealedReadRequest(CredentialFreeOperationRequest):
    """An exact profile and the movements to answer, each named once."""

    profile_id: UUID
    transaction_ids: Annotated[tuple[_TransactionId, ...], Field(min_length=1, max_length=LEDGER_BATCH_UPDATE_MAX_ROWS)]

    @field_validator("transaction_ids")
    @classmethod
    def _each_once(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("a sealed read names each movement once")
        return value


class LedgerSealedRow(BaseModel):
    """Whether a batch edit would refuse this movement as sealed, and by what."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    transaction_id: _TransactionId
    state: Literal["sealed", "open", "not_found"]
    seal_count: int = Field(ge=0)
    seals: Annotated[tuple[LedgerRemovalBlockerProjection, ...], Field(max_length=LEDGER_SEALED_READ_SEAL_SAMPLE)] = ()

    @model_validator(mode="after")
    def _consistent(self) -> LedgerSealedRow:
        if (self.state == "sealed") != (self.seal_count > 0):
            raise ValueError("a sealed row names its declarations and only a sealed row does")
        if len(self.seals) != min(self.seal_count, LEDGER_SEALED_READ_SEAL_SAMPLE):
            raise ValueError("a row names every sealing declaration up to the bound")
        return self


class LedgerSealedReadResult(BaseModel):
    """Every asked movement in the order asked."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: Annotated[tuple[LedgerSealedRow, ...], Field(min_length=1, max_length=LEDGER_BATCH_UPDATE_MAX_ROWS)]


def sealed_rows(
    transaction_ids: tuple[str, ...],
    *,
    current: Mapping[str, tuple[str, ...]],
    blockers_by_txid: Mapping[str, tuple[LedgerRemovalBlocker, ...]],
) -> tuple[LedgerSealedRow, ...]:
    """Answer each movement from its lineage ids, as the batch edit's guard reads them."""
    rows: list[LedgerSealedRow] = []
    for transaction_id in transaction_ids:
        lineage = current.get(transaction_id)
        if lineage is None:
            rows.append(LedgerSealedRow(transaction_id=transaction_id, state="not_found", seal_count=0))
            continue
        found = tuple(blocker for txid in lineage for blocker in blockers_by_txid.get(txid, ()))
        rows.append(
            LedgerSealedRow(
                transaction_id=transaction_id,
                state="sealed" if found else "open",
                seal_count=len(found),
                seals=project_removal_blockers(found[:LEDGER_SEALED_READ_SEAL_SAMPLE]),
            )
        )
    return tuple(rows)


def read_sealed_rows(
    transaction_ids: tuple[str, ...], *, bucket_id: str, ports: LedgerActionPorts
) -> tuple[LedgerSealedRow, ...]:
    """Load the catalogue and the finalized declarations once and answer every asked movement."""
    catalogue = ports.transaction_repository.load()
    asked = set(transaction_ids)
    current = {
        txid: transaction_modelo_source_ids(transaction)
        for txid, transaction in catalogue.transactions.items()
        if txid in asked
    }
    blockers = blockers_by_source_transaction_id(
        bucket_id=bucket_id,
        work_unit_repository=ports.work_unit_repository,
        calculation_repository=ports.calculation_repository,
    )
    return sealed_rows(transaction_ids, current=current, blockers_by_txid=blockers)


class LedgerSealedReadExecutor:
    """Read the catalogue and the finalized declarations once for every asked movement."""

    def __init__(self, ports: LedgerActionPortsFactory) -> None:
        """Retain only the explicit profile-bound composition capability."""
        self._ports = ports

    async def execute(
        self, request: OperationRequest[LedgerSealedReadRequest], context: OperationExecutorContext
    ) -> str:
        """Publish an encrypted read result with no domain mutation effect."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != LEDGER_SEALED_READ_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_profile_operation_identity(request, context, payload.profile_id)
        await context.events.phase(LEDGER_SEALED_READ_OPERATION_DEFINITION_ID)

        def read() -> LedgerSealedReadResult:
            operation = context.authority_operation
            ports = self._ports(bucket_id=bucket_id, operation=operation)
            require_exact_ledger_action_ports(ports, bucket_id=bucket_id, operation=operation)
            return LedgerSealedReadResult(
                profile_id=payload.profile_id,
                rows=read_sealed_rows(payload.transaction_ids, bucket_id=bucket_id, ports=ports),
            )

        return await capture_read_result(context, read, task_name="ledger-sealed-read")


def build_ledger_sealed_read_definition(ports: LedgerActionPortsFactory) -> OperationDefinition:
    """Declare one local read without COMMIT or external-provider capability."""
    return build_single_phase_definition(
        definition_id=LEDGER_SEALED_READ_OPERATION_DEFINITION_ID,
        request_type=LedgerSealedReadRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerSealedReadResult,
        executor_type=LedgerSealedReadExecutor,
        build=lambda: LedgerSealedReadExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
    )


def build_ledger_sealed_read_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind strict result facts and the complete-profile read permission."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerSealedReadResult,
        access_resolver=resolve_ledger_sealed_read_access,
    )


def resolve_ledger_sealed_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Protect the complete catalogue and declaration history this read consults."""
    return resolve_ledger_request_read_access(
        request,
        context,
        definition_id=LEDGER_SEALED_READ_OPERATION_DEFINITION_ID,
        request_type=LedgerSealedReadRequest,
    )
