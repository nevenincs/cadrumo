"""Protected enrollment client pins delivery and reads actual native custody."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.enrollment_access import (
    EnrollmentCredentialBinding,
    RuntimeEnrollmentDelivery,
    RuntimeEnrollmentIdle,
    RuntimeEnrollmentInspect,
    RuntimeEnrollmentPoll,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentRecorded,
    RuntimeEnrollmentSubmit,
)
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessScope, ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _prepared() -> RuntimeEnrollmentPrepared:
    return RuntimeEnrollmentPrepared(
        request_id=uuid4(),
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
        enrollment_request_id=uuid4(),
        client_id=uuid4(),
        destination_id=uuid4(),
        profile_binding=ProfileAccessBinding(
            profile_id=uuid4(),
            installation_id=uuid4(),
            os_owner_id="synthetic-client-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def _receipt(
    prepared: RuntimeEnrollmentPrepared, *, stage: EnrollmentStage = EnrollmentStage.REQUESTED
) -> AutomationReceiptProjection:
    return AutomationReceiptProjection(
        request_id=prepared.enrollment_request_id,
        profile_id=prepared.profile_binding.profile_id,
        stage=stage,
        review_digest="a" * 64,
        grant_id=uuid4(),
        key_id=None,
        credential_reference=None,
    )


def _proposal() -> EnrollmentProposal:
    instant = datetime.now(UTC)
    return EnrollmentProposal(
        kind=EnrollmentKind.ENROLL,
        scope=AccessScope(
            operations=frozenset({"user-profile.view"}),
            actions=frozenset((AccessAction.OBSERVE,)),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        expires_at=instant + timedelta(days=365),
        key_expires_at=instant + timedelta(days=90),
        unattended=True,
        allow_os_lock=False,
    )


class _Connection:
    """Explicit synchronous protocol driver; native identity is fixed by Prepared."""

    def __init__(self, prepared: RuntimeEnrollmentPrepared, receipt: AutomationReceiptProjection) -> None:
        self.hello = SimpleNamespace(boot_id=prepared.runtime_boot_id)
        self.connection_id = prepared.connection_id
        self.prepared = prepared
        self.receipt = receipt
        self.offer: EnrollmentCredentialBinding | None = None
        self.secret: SecretBytes | None = None
        self.action: Literal["store", "possession", "idle"] = "idle"
        self.possessed: SecretBytes | None = None
        self.saw_proposal = False
        self.proposal_buffer: bytearray | None = None

    def enrollment_submit(
        self, request: RuntimeEnrollmentSubmit, proposal: bytearray, *, deadline: float
    ) -> RuntimeEnrollmentRecorded:
        self.saw_proposal = b'"kind":"enroll"' in proposal
        self.proposal_buffer = proposal
        return RuntimeEnrollmentRecorded(
            request_id=request.request_id,
            runtime_boot_id=self.prepared.runtime_boot_id,
            connection_id=self.connection_id,
            receipt=self.receipt,
        )

    def enrollment_inspect(self, request: RuntimeEnrollmentInspect, *, deadline: float) -> RuntimeEnrollmentRecorded:
        return RuntimeEnrollmentRecorded(
            request_id=request.request_id,
            runtime_boot_id=self.prepared.runtime_boot_id,
            connection_id=self.connection_id,
            receipt=self.receipt,
        )

    def enrollment_poll(
        self,
        request: RuntimeEnrollmentPoll,
        *,
        store,
        possession,
        deadline: float,
    ) -> RuntimeEnrollmentDelivery | RuntimeEnrollmentIdle:
        if self.action == "idle":
            return RuntimeEnrollmentIdle(
                request_id=request.request_id,
                runtime_boot_id=self.prepared.runtime_boot_id,
                connection_id=self.connection_id,
            )
        offer = self.offer
        assert offer is not None
        if self.action == "store":
            assert self.secret is not None
            store(offer, self.secret)
        elif self.action == "possession":
            self.possessed = possession(offer)
        else:
            raise AssertionError("unexpected delivery action")
        return RuntimeEnrollmentDelivery(
            request_id=request.request_id,
            runtime_boot_id=self.prepared.runtime_boot_id,
            connection_id=self.connection_id,
            command_id=uuid4(),
            action=self.action,
            credential=offer,
        )


def _client(
    prepared: RuntimeEnrollmentPrepared, receipt: AutomationReceiptProjection, native: MemoryNativePort
) -> tuple[NativeEnrollmentClient, _Connection]:
    connection = _Connection(prepared, receipt)
    return (
        NativeEnrollmentClient(
            connection=cast(VerifiedRuntimeConnection, connection),
            prepared=prepared,
            secrets_store=native,
        ),
        connection,
    )


def _offer(
    prepared: RuntimeEnrollmentPrepared, receipt: AutomationReceiptProjection, key_id: UUID
) -> EnrollmentCredentialBinding:
    return EnrollmentCredentialBinding(
        profile_binding=prepared.profile_binding,
        client_id=prepared.client_id,
        destination_id=prepared.destination_id,
        credential_reference=uuid4(),
        grant_id=receipt.grant_id,
        key_id=key_id,
        review_digest=receipt.review_digest,
    )


def test_store_then_possession_uses_fresh_exact_native_record() -> None:
    prepared = _prepared()
    receipt = _receipt(prepared)
    native = MemoryNativePort()
    client, connection = _client(prepared, receipt, native)
    assert client.submit(_proposal()) == receipt
    assert connection.saw_proposal
    assert connection.proposal_buffer is not None
    assert all(value == 0 for value in connection.proposal_buffer)
    key_id, secret = CustodyAutomationKeyIssuer.generate()
    offer = _offer(prepared, receipt, key_id)
    connection.offer, connection.secret, connection.action = offer, secret, "store"
    assert client.poll() is not None
    connection.action = "possession"
    assert client.poll() is not None
    assert connection.possessed is not None
    assert connection.possessed.get_secret_value() == secret.get_secret_value()
    completed = receipt.model_copy(
        update={
            "stage": EnrollmentStage.COMPLETE,
            "key_id": offer.key_id,
            "credential_reference": offer.credential_reference,
        }
    )
    connection.receipt = completed
    assert client.inspect() == completed
    assert client.credential().get_secret_value() == secret.get_secret_value()
    native.items.clear()
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.MISSING):
        client.credential()
    connection.action = "possession"
    client.poll()
    assert connection.possessed is None


def test_foreign_delivery_or_retarged_candidate_cannot_write_or_read() -> None:
    prepared = _prepared()
    receipt = _receipt(prepared)
    native = MemoryNativePort()
    client, connection = _client(prepared, receipt, native)
    client.submit(_proposal())
    key_id, secret = CustodyAutomationKeyIssuer.generate()
    offer = _offer(prepared, receipt, key_id)
    connection.action, connection.secret = "store", secret
    connection.offer = offer.model_copy(update={"client_id": uuid4()})
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        client.poll()
    assert native.items == {}
    connection.offer = offer
    client.poll()
    connection.offer = offer.model_copy(update={"credential_reference": uuid4()})
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        client.poll()
    assert len(native.items) == 1
    connection.receipt = receipt.model_copy(update={"review_digest": "b" * 64})
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CONFLICT):
        client.inspect()


def test_repeated_submit_requires_the_same_pinned_review() -> None:
    prepared = _prepared()
    receipt = _receipt(prepared)
    client, connection = _client(prepared, receipt, MemoryNativePort())
    assert client.submit(_proposal()) == receipt
    assert client.submit(_proposal()) == receipt
    connection.receipt = receipt.model_copy(update={"review_digest": "b" * 64})
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CONFLICT):
        client.submit(_proposal())


def test_prepared_connection_and_expiry_are_exact() -> None:
    prepared = _prepared()
    receipt = _receipt(prepared)
    native = MemoryNativePort()
    connection = _Connection(prepared, receipt)
    with pytest.raises(RuntimeRefusalError, match=RuntimeRefusalCode.INVALID_FRAME):
        NativeEnrollmentClient(
            connection=cast(VerifiedRuntimeConnection, connection),
            prepared=prepared.model_copy(update={"connection_id": uuid4()}),
            secrets_store=native,
        )
    expired = prepared.model_copy(update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)})
    client, _ = _client(expired, receipt, native)
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        client.submit(_proposal())
