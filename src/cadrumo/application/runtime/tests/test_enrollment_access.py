"""Strict credential-free enrollment messages at the native protocol boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.enrollment_access import (
    EnrollmentCredentialBinding,
    RuntimeEnrollmentClientReply,
    RuntimeEnrollmentDelivery,
    RuntimeEnrollmentIdle,
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentRecorded,
    RuntimeEnrollmentReplyEnvelope,
    RuntimeEnrollmentRequestEnvelope,
    RuntimeEnrollmentSubmit,
)
from cadrumo.application.user_profile.access_contracts import ProfileAccessBinding
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.automation_enrollment import AutomationReceiptProjection, EnrollmentStage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _binding() -> ProfileAccessBinding:
    return ProfileAccessBinding(
        profile_id=uuid4(),
        installation_id=uuid4(),
        os_owner_id="synthetic-owner",
        custody_generation=1,
        dek_epoch=uuid4(),
    )


class _ReplyFields(TypedDict):
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


def _reply_fields() -> _ReplyFields:
    return {"request_id": uuid4(), "runtime_boot_id": uuid4(), "connection_id": uuid4()}


def test_prepare_and_submit_carry_only_server_minted_coordinates() -> None:
    profile_id = uuid4()
    prepare = RuntimeEnrollmentPrepare(
        request_id=uuid4(), profile_id=profile_id, frontend=OperationFrontendProjection.CLI
    )
    submitted = RuntimeEnrollmentSubmit(request_id=uuid4(), profile_id=profile_id, enrollment_request_id=uuid4())
    assert RuntimeEnrollmentRequestEnvelope.model_validate(prepare.model_dump()).root == prepare
    assert RuntimeEnrollmentRequestEnvelope.model_validate(submitted.model_dump()).root == submitted
    for document in (prepare.model_dump(), submitted.model_dump()):
        assert not {"client_id", "destination_id", "password", "proposal", "candidate", "credential"} & document.keys()
    with pytest.raises(ValidationError):
        RuntimeEnrollmentPrepare.model_validate({**prepare.model_dump(), "client_id": uuid4()})
    with pytest.raises(ValidationError):
        RuntimeEnrollmentSubmit.model_validate({**submitted.model_dump(), "proposal": "secret"})
    with pytest.raises(ValidationError):
        RuntimeEnrollmentRequestEnvelope.model_validate({**prepare.model_dump(), "action": "enrollment_unknown"})


def test_replies_are_closed_and_keep_client_credential_binding_nonsecret() -> None:
    binding = _binding()
    credential = EnrollmentCredentialBinding(
        profile_binding=binding,
        client_id=uuid4(),
        destination_id=uuid4(),
        credential_reference=uuid4(),
        grant_id=uuid4(),
        key_id=uuid4(),
        review_digest="a" * 64,
    )
    prepared = RuntimeEnrollmentPrepared(
        **_reply_fields(),
        enrollment_request_id=uuid4(),
        client_id=credential.client_id,
        destination_id=credential.destination_id,
        profile_binding=binding,
        expires_at=datetime.now(UTC),
    )
    receipt = AutomationReceiptProjection(
        request_id=prepared.enrollment_request_id,
        profile_id=binding.profile_id,
        stage=EnrollmentStage.REQUESTED,
        review_digest=credential.review_digest,
        grant_id=credential.grant_id,
        key_id=None,
        credential_reference=None,
    )
    recorded = RuntimeEnrollmentRecorded(**_reply_fields(), receipt=receipt)
    idle = RuntimeEnrollmentIdle(**_reply_fields())
    delivery = RuntimeEnrollmentDelivery(**_reply_fields(), command_id=uuid4(), action="store", credential=credential)
    for reply in (prepared, recorded, idle, delivery):
        assert RuntimeEnrollmentReplyEnvelope.model_validate(reply.model_dump()).root == reply
        encoded = reply.model_dump_json()
        assert not any(secret in encoded for secret in ("password", "candidate_secret", "wrapped_dek", "proposal"))
    with pytest.raises(ValidationError):
        RuntimeEnrollmentDelivery.model_validate({**delivery.model_dump(), "candidate": "secret"})
    with pytest.raises(ValidationError):
        EnrollmentCredentialBinding.model_validate({**credential.model_dump(), "secret": "secret"})
    with pytest.raises(ValidationError):
        RuntimeEnrollmentIdle.model_validate({**idle.model_dump(), "receipt": receipt.model_dump()})


@pytest.mark.parametrize("outcome", ("stored", "present", "missing"))
def test_client_success_or_absence_cannot_carry_a_refusal_code(outcome: str) -> None:
    with pytest.raises(ValidationError):
        RuntimeEnrollmentClientReply.model_validate(
            {"command_id": uuid4(), "outcome": outcome, "code": AutomationCustodyCode.UNAVAILABLE}
        )
    assert RuntimeEnrollmentClientReply.model_validate({"command_id": uuid4(), "outcome": outcome}).code is None


def test_client_refusal_requires_typed_code_and_no_secret_fields() -> None:
    with pytest.raises(ValidationError):
        RuntimeEnrollmentClientReply.model_validate({"command_id": uuid4(), "outcome": "refused"})
    refused = RuntimeEnrollmentClientReply(
        command_id=uuid4(), outcome="refused", code=AutomationCustodyCode.CREDENTIAL_REJECTED
    )
    assert refused.code is AutomationCustodyCode.CREDENTIAL_REJECTED
    with pytest.raises(ValidationError):
        RuntimeEnrollmentClientReply.model_validate({**refused.model_dump(), "credential": "secret"})
