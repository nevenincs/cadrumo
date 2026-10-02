"""Requester orchestration keeps protected delivery and terminal truth separate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Literal, cast
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.local_runtime.automation_requester import (
    AutomationReconcile,
    AutomationRequesterJourney,
    AutomationRequesterUncertainError,
)
from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
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
            os_owner_id="test-owner",
            custody_generation=1,
            dek_epoch=uuid4(),
        ),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def _proposal(kind: EnrollmentKind) -> EnrollmentProposal:
    instant = datetime.now(UTC)
    return EnrollmentProposal(
        kind=kind,
        scope=AccessScope(
            operations=frozenset({"user-profile.view"}),
            actions=frozenset({AccessAction.OBSERVE}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        expires_at=instant + timedelta(days=30),
        key_expires_at=instant + timedelta(days=15) if kind in {EnrollmentKind.ENROLL, EnrollmentKind.ROTATE} else None,
        unattended=True,
        allow_os_lock=False,
        target_grant_id=None if kind is EnrollmentKind.ENROLL else uuid4(),
        target_key_id=uuid4() if kind is EnrollmentKind.ROTATE else None,
    )


def _receipt(prepared: RuntimeEnrollmentPrepared) -> AutomationReceiptProjection:
    return AutomationReceiptProjection(
        request_id=prepared.enrollment_request_id,
        profile_id=prepared.profile_binding.profile_id,
        stage=EnrollmentStage.REQUESTED,
        review_digest="a" * 64,
        grant_id=uuid4(),
        key_id=None,
        credential_reference=None,
    )


class _Wire:
    """Strict connection double, with real NativeEnrollmentClient and native store."""

    def __init__(self, prepared: RuntimeEnrollmentPrepared, receipt: AutomationReceiptProjection) -> None:
        self.hello = SimpleNamespace(boot_id=prepared.runtime_boot_id)
        self.connection_id = prepared.connection_id
        self.prepared = prepared
        self.receipt = receipt
        self.offer: EnrollmentCredentialBinding | None = None
        self.secret: SecretBytes | None = None
        self.action: Literal["store", "possession", "idle", "refuse"] = "idle"
        self.inspect_refused = False
        self.submit_refused = False
        self.submits = 0
        self.possessed: SecretBytes | None = None

    def enrollment_submit(
        self, request: RuntimeEnrollmentSubmit, proposal: bytearray, *, deadline: float
    ) -> RuntimeEnrollmentRecorded:
        self.submits += 1
        if self.submit_refused:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        assert proposal and deadline > 0
        return RuntimeEnrollmentRecorded(
            request_id=request.request_id,
            runtime_boot_id=self.prepared.runtime_boot_id,
            connection_id=self.connection_id,
            receipt=self.receipt,
        )

    def enrollment_inspect(self, request: RuntimeEnrollmentInspect, *, deadline: float) -> RuntimeEnrollmentRecorded:
        if self.inspect_refused:
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        return RuntimeEnrollmentRecorded(
            request_id=request.request_id,
            runtime_boot_id=self.prepared.runtime_boot_id,
            connection_id=self.connection_id,
            receipt=self.receipt,
        )

    def enrollment_poll(
        self, request: RuntimeEnrollmentPoll, *, store, possession, deadline: float
    ) -> RuntimeEnrollmentDelivery | RuntimeEnrollmentIdle:
        if self.action == "refuse":
            self.inspect_refused = True
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
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
        else:
            self.possessed = possession(offer)
        return RuntimeEnrollmentDelivery(
            request_id=request.request_id,
            runtime_boot_id=self.prepared.runtime_boot_id,
            connection_id=self.connection_id,
            command_id=uuid4(),
            action=self.action,
            credential=offer,
        )


def _journey(
    *, reconcile: AutomationReconcile | None = None
) -> tuple[AutomationRequesterJourney, NativeEnrollmentClient, _Wire, MemoryNativePort]:
    prepared = _prepared()
    native = MemoryNativePort()
    wire = _Wire(prepared, _receipt(prepared))
    client = NativeEnrollmentClient(
        connection=cast(VerifiedRuntimeConnection, wire), prepared=prepared, secrets_store=native
    )
    return AutomationRequesterJourney(client, timeout=30, reconcile=reconcile), client, wire, native


def _offer(wire: _Wire, key_id: UUID) -> EnrollmentCredentialBinding:
    return EnrollmentCredentialBinding(
        profile_binding=wire.prepared.profile_binding,
        client_id=wire.prepared.client_id,
        destination_id=wire.prepared.destination_id,
        credential_reference=uuid4(),
        grant_id=wire.receipt.grant_id,
        key_id=key_id,
        review_digest=wire.receipt.review_digest,
    )


@pytest.mark.parametrize("kind", [EnrollmentKind.ENROLL, EnrollmentKind.ROTATE])
def test_key_change_needs_protected_delivery_then_exact_fresh_native_verification(kind: EnrollmentKind) -> None:
    journey, client, wire, native = _journey()
    submitted = journey.submit(_proposal(kind))
    assert submitted.stage is EnrollmentStage.REQUESTED
    assert journey.submitted == submitted and journey.completion is None
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        client.read_delivered_credential()
    key_id, secret = CustodyAutomationKeyIssuer.generate()
    offer = _offer(wire, key_id)
    wire.offer, wire.secret, wire.action = offer, secret, "store"
    assert journey.step() == submitted
    assert client.delivered_credential_metadata().credential_reference == offer.credential_reference
    assert client.read_delivered_credential().get_secret_value() == secret.get_secret_value()
    # Possession is still required for canonical activation; custody alone
    # neither marks the request complete nor authenticates a new API session.
    assert journey.completion is None
    wire.action = "possession"
    assert journey.step() == submitted
    assert wire.possessed is not None and wire.possessed.get_secret_value() == secret.get_secret_value()
    wire.receipt = submitted.model_copy(
        update={
            "stage": EnrollmentStage.COMPLETE,
            "key_id": offer.key_id,
            "credential_reference": offer.credential_reference,
        }
    )
    assert journey.step() == wire.receipt
    completed = journey.completion
    assert completed is not None and completed.terminal == wire.receipt
    assert completed.credential is not None
    assert completed.credential.credential_reference == offer.credential_reference
    assert completed.credential.key_id == offer.key_id
    assert client.credential().get_secret_value() == secret.get_secret_value()
    native.items.clear()
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.MISSING):
        client.verified_terminal()


def test_key_bearing_completion_without_delivered_offer_refuses() -> None:
    journey, _, wire, native = _journey()
    submitted = journey.submit(_proposal(EnrollmentKind.ENROLL))
    key_id, secret = CustodyAutomationKeyIssuer.generate()
    offer = _offer(wire, key_id)
    # An item at the expected reference alone is not proof that this requester
    # received and acknowledged the canonical protected delivery.
    NativeClientCredentialStore(
        secrets_store=native,
        binding=wire.prepared.profile_binding,
        client_id=wire.prepared.client_id,
        destination_id=wire.prepared.destination_id,
    ).replace(
        credential_reference=offer.credential_reference,
        grant_id=offer.grant_id,
        key_id=offer.key_id,
        review_digest=offer.review_digest,
        credential=secret,
    )
    wire.receipt = submitted.model_copy(
        update={"stage": EnrollmentStage.COMPLETE, "key_id": key_id, "credential_reference": offer.credential_reference}
    )
    with pytest.raises(AutomationRequesterUncertainError) as caught:
        journey.step()
    assert caught.value.reason == AutomationCustodyCode.CREDENTIAL_REJECTED.value
    assert isinstance(caught.value.__cause__, AutomationCustodyError)
    assert journey.completion is None


@pytest.mark.parametrize("kind", [EnrollmentKind.ENROLL, EnrollmentKind.ROTATE])
def test_key_change_cannot_report_keyless_complete(kind: EnrollmentKind) -> None:
    journey, _, wire, _ = _journey()
    submitted = journey.submit(_proposal(kind))
    wire.receipt = submitted.model_copy(update={"stage": EnrollmentStage.COMPLETE})
    with pytest.raises(AutomationRequesterUncertainError) as caught:
        journey.step()
    assert caught.value.request_id == submitted.request_id
    assert journey.completion is None


@pytest.mark.parametrize("kind", [EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE])
def test_retired_source_uses_only_fresh_reconciled_terminal_without_republication(kind: EnrollmentKind) -> None:
    observed: list[tuple[AutomationReceiptProjection, float]] = []

    def reconcile(receipt: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
        observed.append((receipt, timeout))
        return receipt.model_copy(update={"stage": EnrollmentStage.COMPLETE})

    journey, _, wire, _ = _journey(reconcile=reconcile)
    submitted = journey.submit(_proposal(kind))
    wire.action = "refuse"
    assert journey.step().stage is EnrollmentStage.COMPLETE
    assert observed and observed[0][0] == submitted and 10 < observed[0][1] <= 30
    assert journey.completion is not None and journey.completion.credential is None
    assert wire.submits == 1


def test_decline_is_terminal_without_key_or_poll_success_claim() -> None:
    journey, _, wire, _ = _journey()
    submitted = journey.submit(_proposal(EnrollmentKind.ENROLL))
    wire.receipt = submitted.model_copy(update={"stage": EnrollmentStage.DECLINED})
    assert journey.wait_for_terminal().terminal == wire.receipt
    assert journey.completion is not None and journey.completion.credential is None
    assert wire.submits == 1


def test_declined_candidate_retains_review_key_identity_without_conferring_credential() -> None:
    journey, client, wire, _ = _journey()
    submitted = journey.submit(_proposal(EnrollmentKind.ENROLL))
    key_id, secret = CustodyAutomationKeyIssuer.generate()
    offer = _offer(wire, key_id)
    wire.offer, wire.secret, wire.action = offer, secret, "store"
    journey.step()
    candidate = submitted.model_copy(
        update={
            "stage": EnrollmentStage.CANDIDATE,
            "key_id": key_id,
            "credential_reference": offer.credential_reference,
        }
    )
    wire.receipt = candidate
    assert journey.step() == candidate
    wire.receipt = candidate.model_copy(update={"stage": EnrollmentStage.DECLINED})
    assert journey.wait_for_terminal().terminal == wire.receipt
    assert journey.completion is not None and journey.completion.credential is None
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CREDENTIAL_REJECTED):
        client.credential()


def test_retirement_without_fresh_reconciliation_keeps_original_refusal_and_request_identity() -> None:
    journey, _, wire, _ = _journey()
    journey.submit(_proposal(EnrollmentKind.RENEW))
    wire.action = "refuse"
    with pytest.raises(AutomationRequesterUncertainError) as caught:
        journey.step()
    assert caught.value.request_id == wire.prepared.enrollment_request_id
    assert caught.value.reason == AutomationCustodyCode.CREDENTIAL_REJECTED.value
    assert isinstance(caught.value.__cause__, AutomationCustodyError)
    assert journey.completion is None and wire.submits == 1


def test_reconciliation_of_foreign_terminal_cannot_complete_request() -> None:
    def foreign(receipt: AutomationReceiptProjection, *, timeout: float) -> AutomationReceiptProjection:
        assert timeout > 0
        return receipt.model_copy(update={"stage": EnrollmentStage.COMPLETE, "profile_id": uuid4()})

    journey, _, wire, _ = _journey(reconcile=foreign)
    journey.submit(_proposal(EnrollmentKind.CHANGE_SCOPE))
    wire.inspect_refused = True
    with pytest.raises(AutomationRequesterUncertainError) as caught:
        journey.step()
    assert caught.value.request_id == wire.prepared.enrollment_request_id
    assert journey.completion is None


def test_uncertain_submission_preserves_prepared_request_id_without_retry() -> None:
    journey, _, wire, _ = _journey()
    wire.submit_refused = True
    with pytest.raises(AutomationRequesterUncertainError) as caught:
        journey.submit(_proposal(EnrollmentKind.ENROLL))
    assert caught.value.request_id == wire.prepared.enrollment_request_id
    assert caught.value.context == {
        "request_id": str(wire.prepared.enrollment_request_id),
        "completion": "unknown",
        "reason": AutomationCustodyCode.UNAVAILABLE.value,
    }
    with pytest.raises(AutomationCustodyError, match=AutomationCustodyCode.CONFLICT):
        journey.submit(_proposal(EnrollmentKind.ENROLL))
    assert wire.submits == 1
