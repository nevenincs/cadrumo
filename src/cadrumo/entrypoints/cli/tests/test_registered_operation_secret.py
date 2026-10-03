"""The CLI secret handoff binds one exact operation and clears caller bytes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ConfigDict

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationSchemaIdentityV1
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import RuntimeOperationRequest, RuntimeOperationSubmitted
from cadrumo.core.operations import profile_operation_subject

from ..errors import CliRefusedBoundaryError
from ..runtime_registered_operation import run_registered_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_OPERATION_ID = "a" * 64
_DEFINITION_ID = "auth.certificate-secret.set"
_SUBJECT = profile_operation_subject(str(_PROFILE_ID))
_CREDENTIAL_KIND = "certificate.passphrase"


class SecretRequest(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str


class SecretResult(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    name: str


class _Client:
    profile_id = _PROFILE_ID
    session_id = uuid4()
    frontend = OperationFrontendProjection.CLI

    def __init__(self, *, required_subject: str = _SUBJECT, secret_required: bool = True) -> None:
        self.required_subject = required_subject
        self.secret_required = secret_required
        self.submissions = 0
        self.secret_submissions = 0
        self.observed_secret = b""

    def contract(self, definition_id: str, *, deadline: float) -> SimpleNamespace:
        del deadline
        return SimpleNamespace(
            definition_id=definition_id,
            request_schema=OperationSchemaIdentityV1.from_model(
                schema_id=definition_id + ".request", schema_version=1, model_type=SecretRequest
            ),
            result_schema=OperationSchemaIdentityV1.from_model(
                schema_id=definition_id + ".result", schema_version=1, model_type=SecretResult
            ),
            permitted_frontends=frozenset({self.frontend}),
            ephemeral_secret_required=self.secret_required,
        )

    def operation(self, request: RuntimeOperationRequest, *, deadline: float) -> RuntimeOperationSubmitted:
        del deadline
        self.submissions += 1
        requirement = OperationSecretRequirement(
            identity=OperationIdentity(
                operation_id=_OPERATION_ID, definition_id=_DEFINITION_ID, subject_ref=self.required_subject
            ),
            interaction_id="b" * 64,
            revision=1,
            secret_kind=_CREDENTIAL_KIND,
            expires_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        return RuntimeOperationSubmitted(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION_ID, secret_requirement=requirement),
        )

    def submit_secret(self, requirement: OperationSecretRequirement, secret: bytearray, *, timeout: float) -> None:
        del requirement, timeout
        self.secret_submissions += 1
        self.observed_secret = bytes(secret)
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)


def _run(client: _Client, secret: bytearray) -> None:
    run_registered_operation(
        cast(RuntimeFrontendClient, client),
        SecretRequest(name="personal"),
        definition_id=_DEFINITION_ID,
        subject_ref=_SUBJECT,
        result_type=SecretResult,
        request_version=1,
        result_version=1,
        timeout=5,
        secret=secret,
    )


def test_exact_secret_handoff_uses_protected_channel_and_clears_caller_buffer() -> None:
    client = _Client()
    secret = bytearray(b"synthetic-passphrase")
    with pytest.raises(CliRefusedBoundaryError):
        _run(client, secret)
    assert client.submissions == client.secret_submissions == 1
    assert client.observed_secret == b"synthetic-passphrase"
    assert secret == bytes(len(secret))


def test_mismatched_requirement_refuses_before_secret_transfer_and_clears_buffer() -> None:
    client = _Client(required_subject=profile_operation_subject("22222222-2222-4222-8222-222222222222"))
    secret = bytearray(b"synthetic-passphrase")
    with pytest.raises(CliRefusedBoundaryError):
        _run(client, secret)
    assert client.submissions == 1
    assert client.secret_submissions == 0
    assert secret == bytes(len(secret))


def test_contract_refusal_clears_secret_before_any_submission() -> None:
    client = _Client(secret_required=False)
    secret = bytearray(b"synthetic-passphrase")
    with pytest.raises(RuntimeRefusalError):
        _run(client, secret)
    assert client.submissions == client.secret_submissions == 0
    assert secret == bytes(len(secret))
