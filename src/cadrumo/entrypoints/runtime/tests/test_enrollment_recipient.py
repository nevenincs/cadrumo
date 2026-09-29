"""Volatile enrollment handoff refuses missing, late, or misbound client proof."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from threading import Thread
from uuid import uuid4

import pytest
from pydantic import SecretBytes

from cadrumo.adapters.persistence.storage.custody.automation_crypto import CustodyAutomationKeyIssuer
from cadrumo.application.runtime.enrollment_recipient import (
    EnrollmentMissing,
    EnrollmentPresent,
    EnrollmentRefused,
    EnrollmentStored,
    EnrollmentWorkAction,
    VolatileEnrollmentRecipient,
)
from cadrumo.application.user_profile.access_contracts import AccessAction, AccessScope, ProfileAccessBinding
from cadrumo.application.user_profile.automation_administration import enrollment_review_digest
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentRecord,
    EnrollmentRequester,
    EnrollmentStage,
)
from cadrumo.core.time.clock import now

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _record() -> tuple[EnrollmentRecord, SecretBytes]:
    instant = now()
    binding = ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )
    requester = EnrollmentRequester(
        runtime_boot_id=uuid4(), connection_id=uuid4(), client_id=uuid4(), destination_id=uuid4()
    )
    key_id, secret = CustodyAutomationKeyIssuer.generate()
    record = EnrollmentRecord(
        request_id=uuid4(),
        binding=binding,
        requester=requester,
        proposal=EnrollmentProposal(
            kind=EnrollmentKind.ENROLL,
            scope=AccessScope(
                operations=frozenset({"user-profile.field-mutation"}),
                actions=frozenset({AccessAction.SUBMIT}),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            expires_at=instant + timedelta(days=2),
            key_expires_at=instant + timedelta(days=1),
            unattended=True,
            allow_os_lock=False,
        ),
        created_at=instant,
        expires_at=instant + timedelta(minutes=2),
        stage=EnrollmentStage.CANDIDATE,
        grant_id=uuid4(),
        candidate_key_id=key_id,
        credential_reference=uuid4(),
    )
    return record, secret


def _broker(record: EnrollmentRecord, *, milliseconds: int = 3000) -> VolatileEnrollmentRecipient:
    return VolatileEnrollmentRecipient(
        requester=record.requester,
        issuer=CustodyAutomationKeyIssuer(),
        profile_binding=record.binding,
        enrollment_request_id=record.request_id,
        review_digest=enrollment_review_digest(record),
        offer_expires_at=now() + timedelta(milliseconds=milliseconds),
    )


class _Call:
    def __init__(self, target: Callable[[], object]) -> None:
        self.value: object = None
        self.error: BaseException | None = None
        self.thread = Thread(target=self._run, args=(target,), daemon=True)
        self.thread.start()

    def _run(self, target: Callable[[], object]) -> None:
        try:
            self.value = target()
        except BaseException as error:
            self.error = error

    def finish(self) -> object:
        self.thread.join(5)
        assert not self.thread.is_alive(), "broker waiter exceeded its bounded deadline"
        if self.error is not None:
            raise self.error
        return self.value


def test_store_then_possession_requires_two_exact_client_completions() -> None:
    record, secret = _record()
    broker = _broker(record)
    store = _Call(lambda: broker.deliver(record, secret))
    with broker.borrow() as work:
        assert work is not None
        assert work.action is EnrollmentWorkAction.STORE
        assert work.credential_binding.profile_binding == record.binding
        assert work.credential_binding.credential_reference == record.credential_reference
        assert work.credential_binding.review_digest == enrollment_review_digest(record)
        assert work.candidate == secret and secret.get_secret_value() not in repr(work).encode()
        work.complete(work.command_id, EnrollmentStored())
    assert work.candidate is None
    assert store.finish() is None

    possession = _Call(lambda: broker.possession(record))
    with broker.borrow() as work:
        assert work is not None and work.action is EnrollmentWorkAction.POSSESSION
        assert work.candidate is None
        work.complete(work.command_id, EnrollmentPresent(secret))
    assert possession.finish() == secret
    broker.close()


def test_known_missing_is_none_and_client_refusal_is_typed() -> None:
    record, _ = _record()
    broker = _broker(record)
    missing = _Call(lambda: broker.possession(record))
    with broker.borrow() as work:
        assert work is not None
        work.complete(work.command_id, EnrollmentMissing())
    assert missing.finish() is None

    refused = _Call(lambda: broker.possession(record))
    with broker.borrow() as work:
        assert work is not None
        work.complete(work.command_id, EnrollmentRefused(AutomationCustodyCode.CREDENTIAL_REJECTED))
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        refused.finish()


def test_review_and_candidate_are_pinned_before_work_is_offered() -> None:
    record, secret = _record()
    broker = _broker(record)
    altered = record.model_copy(update={"request_id": uuid4()})
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        broker.deliver(altered, secret)
    altered = record.model_copy(update={"grant_id": uuid4()})
    with pytest.raises(AutomationCustodyError, match="conflict"):
        broker.possession(altered)
    wrong_key = CustodyAutomationKeyIssuer.generate()[1]
    with pytest.raises(AutomationCustodyError, match="credential_rejected"):
        broker.deliver(record, wrong_key)
    broker.close()


def test_wrong_command_and_abandoned_borrow_fail_without_retry() -> None:
    record, secret = _record()
    broker = _broker(record)
    pending = _Call(lambda: broker.deliver(record, secret))
    with broker.borrow() as work:
        assert work is not None
        with pytest.raises(AutomationCustodyError, match="credential_rejected"):
            work.complete(uuid4(), EnrollmentStored())
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        pending.finish()
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        broker.deliver(record, secret)


def test_one_outstanding_job_rejects_overlap_and_wrong_action_reply() -> None:
    record, secret = _record()
    broker = _broker(record)
    pending = _Call(lambda: broker.deliver(record, secret))
    with broker.borrow() as work:
        assert work is not None
        with pytest.raises(AutomationCustodyError, match="conflict"):
            broker.possession(record)
        with pytest.raises(AutomationCustodyError, match="invalid"):
            work.complete(work.command_id, EnrollmentMissing())
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        pending.finish()


def test_close_wakes_waiter_and_rejects_late_completion() -> None:
    record, secret = _record()
    broker = _broker(record)
    pending = _Call(lambda: broker.deliver(record, secret))
    with broker.borrow() as work:
        assert work is not None
        broker.close()
        with pytest.raises(AutomationCustodyError, match="credential_rejected"):
            work.complete(work.command_id, EnrollmentStored())
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        pending.finish()


def test_offer_expiry_fails_producer_and_never_accepts_late_poll() -> None:
    record, secret = _record()
    broker = _broker(record, milliseconds=75)
    pending = _Call(lambda: broker.deliver(record, secret))
    with pytest.raises(AutomationCustodyError, match="unavailable"):
        pending.finish()
    with pytest.raises(AutomationCustodyError, match="unavailable"), broker.borrow():
        pass
