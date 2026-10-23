"""A complete inventory crosses the worker channel in bounded chunks, up to its budget and no further."""

from __future__ import annotations

import base64
import time
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.contract_manifest import load_operation_contract_manifest
from cadrumo.application.operations.person_acts import operation_is_persons_act
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.access_projections import PublicApiKey, PublicAutomationGrant
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationInventory,
    EnrollmentReceipt,
    EnrollmentReview,
    EnrollmentStage,
)
from cadrumo.application.user_profile.automation_operations import AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    AuthorityState,
    Availability,
    DisclosureCategory,
    DisclosureCategoryGrant,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.enrollment_proposal import GRANT_DEFAULT_VALIDITY, EnrollmentKind, EnrollmentProposal
from cadrumo_client.contracts.submission_payload import SUBMISSION_PAYLOAD_CHUNK_BYTES, SubmissionPayloadChunk
from cadrumo_client.transport.frame_io import MAXIMUM_FRAME_BYTES, read_document, write_document
from cadrumo_client.transport.tests.memory_channel import MemoryChannel
from cadrumo_runtime.contracts.worker_authorization import (
    WORKER_AUTOMATION_INVENTORY_MAX_BYTES,
    WorkerAuthorizationReply,
    WorkerAutomationInventoryPermit,
    WorkerAutomationInventoryRequest,
    WorkerAutomationInventoryTransfer,
)

from ..worker_authorization import _require_inventory_ipc_budget, _write_permit
from ..worker_authorization_lease import _read_inventory_permit

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_ONE_MIB = 1024 * 1024
_AGENT_KEYS = 32


def _size(inventory: AutomationInventory) -> int:
    return len(canonical_json_bytes(inventory.model_dump(mode="json")))


def _agent_scope(destination_id: UUID) -> AccessScope:
    """Every registered operation but the person's own acts, with every disclosure category."""
    contracts = load_operation_contract_manifest().contract_set
    return AccessScope(
        operations=frozenset(
            contract.definition_id
            for contract in contracts.definitions
            if not operation_is_persons_act(
                contract.definition_id, ephemeral_secret_required=contract.ephemeral_secret_required
            )
        ),
        actions=frozenset(AccessAction),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
        disclosure_categories=frozenset(
            DisclosureCategoryGrant(destination_id=destination_id, category=category) for category in DisclosureCategory
        ),
    )


def _agent_key_inventory(count: int) -> AutomationInventory:
    """Agent keys each with their grant and completed enrollment request, which repeats the scope."""
    issued = now()
    expires_at = issued + GRANT_DEFAULT_VALIDITY
    profile_id = uuid4()
    grants: list[PublicAutomationGrant] = []
    keys: list[PublicApiKey] = []
    requests: list[EnrollmentReview] = []
    for _ in range(count):
        destination_id, grant_id, key_id = uuid4(), uuid4(), uuid4()
        scope = _agent_scope(destination_id)
        grants.append(
            PublicAutomationGrant(
                grant_id=grant_id,
                profile_id=profile_id,
                client_id=uuid4(),
                state=AuthorityState.ACTIVE,
                scope=scope,
                valid_from=issued,
                expires_at=expires_at,
                unattended=True,
                allow_os_lock=False,
            )
        )
        keys.append(
            PublicApiKey(
                key_id=key_id,
                grant_id=grant_id,
                profile_id=profile_id,
                state=AuthorityState.ACTIVE,
                valid_from=issued,
                expires_at=expires_at,
                last_used_at=issued,
            )
        )
        requests.append(
            EnrollmentReview(
                receipt=EnrollmentReceipt(
                    request_id=uuid4(),
                    profile_id=profile_id,
                    stage=EnrollmentStage.COMPLETE,
                    review_digest="0" * 64,
                    grant_id=grant_id,
                    key_id=key_id,
                    credential_reference=uuid4(),
                ),
                client_id=uuid4(),
                destination_id=destination_id,
                proposal=EnrollmentProposal(
                    kind=EnrollmentKind.ENROLL,
                    scope=scope,
                    expires_at=expires_at,
                    key_expires_at=expires_at,
                    unattended=True,
                    allow_os_lock=False,
                ),
                expires_at=expires_at,
            )
        )
    return AutomationInventory(grants=tuple(grants), keys=tuple(keys), requests=tuple(requests))


def _inventory_of_size(target: int) -> AutomationInventory:
    """Pad agent keys with one grant of synthetic operation IDs to exactly ``target`` canonical bytes."""
    base = _agent_key_inventory(4)
    issued = now()
    template = base.grants[0]
    padding_grant = uuid4()

    def build(operations: list[str]) -> AutomationInventory:
        padding = template.model_copy(
            update={
                "grant_id": padding_grant,
                "valid_from": issued,
                "scope": template.scope.model_copy(update={"operations": frozenset(operations)}),
            }
        )
        return base.model_copy(update={"grants": (*base.grants, padding)})

    def identifier(index: int, length: int) -> str:
        return f"p{index:06d}" + "a" * (length - 7)

    # Each further ID adds its length plus its quotes and separator, so the
    # padding is computed once and the exact size is then measured.
    operations = [identifier(0, 9)]
    deficit = target - _size(build(operations))
    filler = max(0, (deficit - 200) // 103 + 1)
    operations.extend(identifier(index, 100) for index in range(1, filler + 1))
    deficit -= 103 * filler
    first = (deficit - 6) // 2
    operations.append(identifier(filler + 1, first))
    operations.append(identifier(filler + 2, deficit - 6 - first))
    inventory = build(operations)
    assert _size(inventory) == target
    return inventory


def _permit(inventory: AutomationInventory, *, request_id: UUID, boot_id: UUID) -> WorkerAutomationInventoryPermit:
    return WorkerAutomationInventoryPermit(
        request_id=request_id,
        runtime_boot_id=boot_id,
        permit_id=uuid4(),
        expires_at=now() + timedelta(minutes=5),
        inventory=inventory,
    )


def _channels() -> tuple[MemoryChannel, MemoryChannel]:
    runtime, worker = MemoryChannel(), MemoryChannel()
    runtime.pair(worker)
    return runtime, worker


def _receive(worker: MemoryChannel, *, request_id: UUID, boot_id: UUID) -> WorkerAutomationInventoryPermit:
    """Read the announced permit the way the worker's lease does."""
    deadline = time.monotonic() + 5
    header = read_document(worker, WorkerAuthorizationReply, deadline=deadline).root
    assert isinstance(header, WorkerAutomationInventoryTransfer)
    return _read_inventory_permit(
        worker, header, _inventory_request(request_id), runtime_boot_id=boot_id, deadline=deadline
    )


def _inventory_request(request_id: UUID) -> WorkerAutomationInventoryRequest:
    definition_id = AUTOMATION_INVENTORY_OPERATION_DEFINITION_ID
    return WorkerAutomationInventoryRequest(
        request_id=request_id,
        connection_id=uuid4(),
        session_id=uuid4(),
        operation_id="a" * 64,
        request=OperationAccessRequest(
            profile_id=uuid4(),
            definition_id=definition_id,
            action=AccessAction.START,
            frontend=OperationFrontendProjection.CLI,
            periods=frozenset(),
            period_independent=True,
            destination_id=uuid4(),
        ),
        policy=OperationAccessPolicy(
            definition_id=definition_id,
            definition_contract_digest="b" * 64,
            actions=frozenset({AccessAction.START}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            backend=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            transaction_authority_required=False,
        ),
    )


def test_the_shipped_budget_is_one_mebibyte() -> None:
    assert WORKER_AUTOMATION_INVENTORY_MAX_BYTES == _ONE_MIB


def test_thirty_two_agent_keys_cross_the_worker_channel_whole() -> None:
    inventory = _agent_key_inventory(_AGENT_KEYS)
    assert _size(inventory) > MAXIMUM_FRAME_BYTES
    _require_inventory_ipc_budget(inventory)
    runtime, worker = _channels()
    request_id, boot_id = uuid4(), uuid4()
    permit = _permit(inventory, request_id=request_id, boot_id=boot_id)

    _write_permit(runtime, permit, deadline=time.monotonic() + 5)

    assert len(runtime.writes) > 2
    assert all(len(frame) <= MAXIMUM_FRAME_BYTES + 5 for frame in runtime.writes)
    received = _receive(worker, request_id=request_id, boot_id=boot_id)
    assert received == permit
    assert len(received.inventory.keys) == _AGENT_KEYS


def test_an_inventory_at_the_budget_is_released_and_one_byte_more_is_refused() -> None:
    at_budget = _inventory_of_size(_ONE_MIB)
    _require_inventory_ipc_budget(at_budget)
    runtime, worker = _channels()
    request_id, boot_id = uuid4(), uuid4()
    permit = _permit(at_budget, request_id=request_id, boot_id=boot_id)
    _write_permit(runtime, permit, deadline=time.monotonic() + 5)
    assert _receive(worker, request_id=request_id, boot_id=boot_id) == permit

    with pytest.raises(ProfileAccessRefusedError) as refused:
        _require_inventory_ipc_budget(_inventory_of_size(_ONE_MIB + 1))
    assert refused.value.reason is AccessDenialCode.OPERATION_UNAVAILABLE


def _announce(runtime: MemoryChannel, payload: bytes, *, request_id: UUID, boot_id: UUID, permit_id: UUID) -> None:
    write_document(
        runtime,
        WorkerAutomationInventoryTransfer(
            request_id=request_id,
            runtime_boot_id=boot_id,
            permit_id=permit_id,
            byte_count=len(payload),
            payload_digest=sha256_hex(payload),
        ),
        deadline=time.monotonic() + 5,
    )


def _send_chunks(runtime: MemoryChannel, payload: bytes) -> None:
    for offset in range(0, len(payload), SUBMISSION_PAYLOAD_CHUNK_BYTES):
        chunk = payload[offset : offset + SUBMISSION_PAYLOAD_CHUNK_BYTES]
        write_document(
            runtime,
            SubmissionPayloadChunk(offset=offset, encoded=base64.b64encode(chunk).decode("ascii")),
            deadline=time.monotonic() + 5,
        )


def test_a_transfer_whose_bytes_do_not_match_its_digest_is_refused() -> None:
    runtime, worker = _channels()
    request_id, boot_id = uuid4(), uuid4()
    permit = _permit(_agent_key_inventory(2), request_id=request_id, boot_id=boot_id)
    payload = canonical_json_bytes(permit.model_dump(mode="json"))
    _announce(runtime, payload, request_id=request_id, boot_id=boot_id, permit_id=permit.permit_id)
    tampered = payload.replace(b'"active"', b'"ACTIVE"', 1)
    assert len(tampered) == len(payload) and tampered != payload
    _send_chunks(runtime, tampered)

    with pytest.raises(RefusalError) as refused:
        _receive(worker, request_id=request_id, boot_id=boot_id)
    assert refused.value.reason is RefusalCode.INVALID_FRAME


def test_a_short_final_chunk_is_refused() -> None:
    runtime, worker = _channels()
    request_id, boot_id = uuid4(), uuid4()
    permit = _permit(_agent_key_inventory(2), request_id=request_id, boot_id=boot_id)
    payload = canonical_json_bytes(permit.model_dump(mode="json"))
    _announce(runtime, payload, request_id=request_id, boot_id=boot_id, permit_id=permit.permit_id)
    _send_chunks(runtime, payload[:-1])

    with pytest.raises(RefusalError) as refused:
        _receive(worker, request_id=request_id, boot_id=boot_id)
    assert refused.value.reason is RefusalCode.INVALID_FRAME


def test_a_permit_that_does_not_match_its_announcement_is_refused() -> None:
    runtime, worker = _channels()
    request_id, boot_id = uuid4(), uuid4()
    permit = _permit(_agent_key_inventory(1), request_id=request_id, boot_id=boot_id)
    payload = canonical_json_bytes(permit.model_dump(mode="json"))
    _announce(runtime, payload, request_id=request_id, boot_id=boot_id, permit_id=uuid4())
    _send_chunks(runtime, payload)

    with pytest.raises(RefusalError) as refused:
        _receive(worker, request_id=request_id, boot_id=boot_id)
    assert refused.value.reason is RefusalCode.INVALID_FRAME
