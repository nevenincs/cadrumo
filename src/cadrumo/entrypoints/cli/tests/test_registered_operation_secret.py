"""The CLI secret handoff binds one exact operation and clears caller bytes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from cadrumo.application.auth.certificate_secret_operation import (
    CERTIFICATE_CREDENTIAL_KIND,
    CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID,
    CertificateSecretMutationProjection,
    CertificateSecretMutationRequest,
    CertificateSecretOperationPorts,
    build_certificate_secret_operation_definitions,
    build_certificate_secret_operation_registrations,
)
from cadrumo.application.auth.operator_scope_ports import OperatorScopePorts
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.models import OperationIdentity
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1, OperationRegistry
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
from cadrumo.core.operations import OperationFrontendProjection, profile_operation_subject
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import OperationRequest, OperationSubmitted
from cadrumo_client.transport.frontend_client import FrontendClient

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]
_PROFILE_ID = UUID("11111111-1111-4111-8111-111111111111")
_OPERATION_ID = "a" * 64
_DEFINITION_ID = CERTIFICATE_CREDENTIAL_SET_OPERATION_DEFINITION_ID
_SUBJECT = profile_operation_subject(str(_PROFILE_ID))


def _registered_contract() -> OperationPublicDefinitionContractV1:
    """The public contract the registry publishes for the real certificate passphrase set."""
    # Only the published contract is read; no executor is built, so the ports stay unopened.
    ports = CertificateSecretOperationPorts(
        operator_scope_ports=cast(OperatorScopePorts, object()),
        certificate_secret_backend_factory=cast(CertificateSecretBackendFactory, object()),
    )
    definitions = build_certificate_secret_operation_definitions(ports)
    registrations = build_certificate_secret_operation_registrations(definitions)
    registry = OperationRegistry(
        definitions=definitions,
        public_registrations=tuple(sorted(registrations, key=lambda registration: registration.contract.definition_id)),
    )
    return registry.lookup_public_contract(_DEFINITION_ID)


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

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        del deadline
        contract = _registered_contract()
        assert contract.definition_id == definition_id
        if self.secret_required:
            return contract
        return contract.model_copy(update={"ephemeral_secret_required": False})

    def operation(self, request: OperationRequest, *, deadline: float) -> OperationSubmitted:
        del deadline
        self.submissions += 1
        requirement = OperationSecretRequirement(
            identity=OperationIdentity(
                operation_id=_OPERATION_ID, definition_id=_DEFINITION_ID, subject_ref=self.required_subject
            ),
            interaction_id="b" * 64,
            revision=1,
            secret_kind=CERTIFICATE_CREDENTIAL_KIND,
            expires_at=datetime.now(UTC) + timedelta(minutes=1),
        )
        return OperationSubmitted(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION_ID, secret_requirement=requirement),
        )

    def submit_secret(self, requirement: OperationSecretRequirement, secret: bytearray, *, timeout: float) -> None:
        del requirement, timeout
        self.secret_submissions += 1
        self.observed_secret = bytes(secret)
        raise RefusalError(RefusalCode.CONNECTION_CLOSED)


def _run(client: _Client, secret: bytearray) -> None:
    run_registered_operation(
        cast(FrontendClient, client),
        CertificateSecretMutationRequest(profile_id=_PROFILE_ID, name="personal"),
        definition_id=_DEFINITION_ID,
        subject_ref=_SUBJECT,
        result_type=CertificateSecretMutationProjection,
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
    with pytest.raises(RefusalError):
        _run(client, secret)
    assert client.submissions == client.secret_submissions == 0
    assert secret == bytes(len(secret))
