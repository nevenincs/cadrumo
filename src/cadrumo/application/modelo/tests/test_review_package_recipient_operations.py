"""Registered recipient operations preserve exact-profile effects and projections."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from pydantic import BaseModel, ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...bucket_event_repository import BucketEventHistoryRepositoryFactory
from ...operations.access_resolution import OperationAccessContext
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import review_package_recipient_operations as operation
from ..review_package_recipient_registry import (
    RecipientAlreadyRegisteredError,
    RecipientFingerprintRecord,
    RecipientFingerprintRegister,
    RecipientNotRegisteredError,
)
from ..review_package_recipient_registry_ports import (
    RecipientFingerprintRegistryPorts,
    RecipientFingerprintRegistryRepositoryPort,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_NOW = datetime(2026, 4, 10, 9, 0, tzinfo=UTC)


class _Registry:
    def __init__(self, records: tuple[RecipientFingerprintRecord, ...] = ()) -> None:
        self.register = RecipientFingerprintRegister(records=records)
        self.saves = 0

    def load(self) -> RecipientFingerprintRegister:
        return self.register

    def save(self, register: RecipientFingerprintRegister) -> None:
        self.saves += 1
        self.register = register


class _Recorder:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.phases: list[str] = []
        self.operand: object | None = None
        self.inside_commit = False

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        assert not self.inside_commit
        self.inside_commit = True
        try:
            yield
        finally:
            self.inside_commit = False

    async def phase(self, code: str) -> None:
        self.phases.append(code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)

    async def put(self, operand: object, *, written_at: datetime) -> str:
        assert not self.inside_commit
        assert written_at.tzinfo is not None
        self.operand = operand
        return "a" * 64


def _context(recorder: _Recorder, definition_id: str) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=definition_id,
                    subject_ref=profile_operation_subject(str(_PROFILE)),
                ),
                cancellation=recorder,
                events=recorder,
                operands=recorder,
            ),
        ),
    )


def _public_key() -> str:
    return X25519PrivateKey.generate().public_key().public_bytes_raw().hex()


def _record(recipient_id: str, *, key: str | None = None, label: str = "Accountant") -> RecipientFingerprintRecord:
    return RecipientFingerprintRecord(
        recipient_id=recipient_id,
        label=label,
        public_key_hex=key or _public_key(),
        added_at=_NOW,
    )


def _factories(
    registry: _Registry,
) -> tuple[
    operation._RecipientPorts,
    list[tuple[str, object]],
]:
    ports = RecipientFingerprintRegistryPorts(
        registry_repository=cast(RecipientFingerprintRegistryRepositoryPort, registry)
    )
    audit_calls: list[tuple[str, object]] = []

    def registry_factory(*, bucket_id: str) -> RecipientFingerprintRegistryPorts:
        assert bucket_id == str(_PROFILE)
        return ports

    def event_factory(*, bucket_id: str) -> BucketEventHistoryRepositoryProtocol:
        assert bucket_id == str(_PROFILE)
        return cast(BucketEventHistoryRepositoryProtocol, object())

    return (
        operation._RecipientPorts(
            registry_factory=registry_factory,
            event_repository_factory=cast(BucketEventHistoryRepositoryFactory, event_factory),
        ),
        audit_calls,
    )


def _request[RequestT: BaseModel](
    definition_id: str,
    payload: RequestT,
) -> OperationRequest[RequestT]:
    return OperationRequest[RequestT](
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


def test_public_key_request_is_exact_lowercase_hex_and_full_row_is_derived() -> None:
    key = _public_key()
    request = operation.ReviewPackageRecipientAddRequest(
        profile_id=_PROFILE,
        recipient_id="accountant",
        public_key_hex=key,
        label="Tax adviser",
    )
    projection = operation.ReviewPackageRecipientProjection.from_record(_record("accountant", key=key))

    assert operation.ReviewPackageRecipientAddRequest.model_validate_json(request.model_dump_json()) == request
    assert projection.public_key_hex == key
    assert len(projection.fingerprint_sha256) == 64
    with pytest.raises(ValidationError):
        operation.ReviewPackageRecipientAddRequest(
            profile_id=_PROFILE,
            recipient_id="accountant",
            public_key_hex="not-hex",
        )
    with pytest.raises(ValidationError):
        operation.ReviewPackageRecipientAddRequest(
            profile_id=_PROFILE,
            recipient_id="accountant",
            public_key_hex=key.upper(),
        )
    with pytest.raises(ValidationError):
        operation.ReviewPackageRecipientAddRequest(
            profile_id=_PROFILE,
            recipient_id="accountant",
            public_key_hex=f" {key}",
        )


@pytest.mark.asyncio
async def test_add_commits_registry_and_audit_then_releases_complete_row(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _Registry()
    ports, audit_calls = _factories(registry)
    recorder = _Recorder()
    key = _public_key()
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    def emit(record: RecipientFingerprintRecord, *, bucket_id: str, repository: object) -> None:
        assert recorder.inside_commit
        assert bucket_id == str(_PROFILE)
        audit_calls.append(("registered", (record, repository)))

    monkeypatch.setattr(operation, "emit_collab_recipient_registered_event", emit)
    request = _request(
        operation.REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        operation.ReviewPackageRecipientAddRequest(
            profile_id=_PROFILE,
            recipient_id="accountant",
            public_key_hex=key,
            label="Tax adviser",
        ),
    )

    returned = await operation.ReviewPackageRecipientAddExecutor(ports).execute(
        request,
        _context(recorder, operation.REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID),
    )

    assert returned == "a" * 64
    assert registry.saves == 1
    assert [effect for effect in recorder.effects] == [
        OperationEffect.NONE,
        OperationEffect.UNKNOWN,
        OperationEffect.PARTIAL,
        OperationEffect.UNKNOWN,
        OperationEffect.UPDATED,
    ]
    assert audit_calls[0][0] == "registered"
    assert isinstance(recorder.operand, operation._RecipientAddExecutionResult)
    assert recorder.operand.result.recipient.public_key_hex == key
    assert recorder.operand.result.recipient.fingerprint_sha256 == registry.register.records[0].fingerprint_sha256


@pytest.mark.asyncio
async def test_duplicate_and_missing_refusals_settle_none_without_a_write(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = _record("accountant")
    registry = _Registry((existing,))
    ports, _audit_calls = _factories(registry)
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    add_events = _Recorder()
    add_request = _request(
        operation.REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        operation.ReviewPackageRecipientAddRequest(
            profile_id=_PROFILE,
            recipient_id="accountant",
            public_key_hex=_public_key(),
        ),
    )
    with pytest.raises(RecipientAlreadyRegisteredError):
        await operation.ReviewPackageRecipientAddExecutor(ports).execute(
            add_request,
            _context(add_events, operation.REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID),
        )
    assert registry.saves == 0
    assert add_events.effects[-1] is OperationEffect.NONE
    assert add_events.operand is None

    remove_events = _Recorder()
    remove_request = _request(
        operation.REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID,
        operation.ReviewPackageRecipientRemoveRequest(profile_id=_PROFILE, recipient_id="missing"),
    )
    with pytest.raises(RecipientNotRegisteredError):
        await operation.ReviewPackageRecipientRemoveExecutor(ports).execute(
            remove_request,
            _context(remove_events, operation.REVIEW_PACKAGE_RECIPIENT_REMOVE_OPERATION_DEFINITION_ID),
        )
    assert registry.saves == 0
    assert remove_events.effects[-1] is OperationEffect.NONE
    assert remove_events.operand is None


@pytest.mark.asyncio
async def test_audit_failure_keeps_the_known_registry_commit_as_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = _Registry()
    ports, _audit_calls = _factories(registry)
    recorder = _Recorder()
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))

    def fail_audit(*_args: object, **_kwargs: object) -> None:
        assert recorder.inside_commit
        raise OSError("synthetic audit append failure")

    monkeypatch.setattr(operation, "emit_collab_recipient_registered_event", fail_audit)
    request = _request(
        operation.REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        operation.ReviewPackageRecipientAddRequest(
            profile_id=_PROFILE,
            recipient_id="accountant",
            public_key_hex=_public_key(),
        ),
    )
    with pytest.raises(OSError, match="synthetic audit append failure"):
        await operation.ReviewPackageRecipientAddExecutor(ports).execute(
            request,
            _context(recorder, operation.REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID),
        )

    assert registry.saves == 1
    assert len(registry.register.records) == 1
    assert recorder.effects == [
        OperationEffect.NONE,
        OperationEffect.UNKNOWN,
        OperationEffect.PARTIAL,
        OperationEffect.UNKNOWN,
        OperationEffect.PARTIAL,
    ]
    assert recorder.operand is None


@pytest.mark.asyncio
async def test_list_is_complete_sorted_and_discloses_the_full_registered_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zulu = _record("zulu", label="Last")
    alpha = _record("alpha", label="First")
    registry = _Registry((zulu, alpha))
    ports, _audit_calls = _factories(registry)
    recorder = _Recorder()
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    request = _request(
        operation.REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID,
        operation.ReviewPackageRecipientListRequest(profile_id=_PROFILE),
    )

    returned = await operation.ReviewPackageRecipientListExecutor(ports.registry_factory).execute(
        request,
        _context(recorder, operation.REVIEW_PACKAGE_RECIPIENT_LIST_OPERATION_DEFINITION_ID),
    )

    assert returned == "a" * 64
    assert registry.saves == 0
    assert recorder.effects == [OperationEffect.NONE]
    assert isinstance(recorder.operand, operation._RecipientListExecutionResult)
    projection = recorder.operand.result
    assert projection.count == 2
    assert [row.recipient_id for row in projection.recipients] == ["alpha", "zulu"]
    assert projection.recipients[0].public_key_hex == alpha.public_key_hex
    assert projection.recipients[0].label == "First"
    assert projection.recipients[0].fingerprint_sha256 == alpha.fingerprint_sha256
    assert projection.recipients[0].added_at == _NOW


def test_definitions_and_access_resolvers_are_exact_profile_and_profile_values() -> None:
    def registry_factory(*, bucket_id: str) -> RecipientFingerprintRegistryPorts:
        raise AssertionError(bucket_id)

    def event_factory(*, bucket_id: str) -> BucketEventHistoryRepositoryProtocol:
        raise AssertionError(bucket_id)

    add_definition = operation.build_review_package_recipient_add_definition(
        registry_factory,
        cast(BucketEventHistoryRepositoryFactory, event_factory),
    )
    add_registration = operation.build_review_package_recipient_add_registration(add_definition)
    add_payload = operation.ReviewPackageRecipientAddRequest(
        profile_id=_PROFILE,
        recipient_id="accountant",
        public_key_hex=_public_key(),
    )
    add_request = _request(add_definition.definition_id, add_payload)
    context = OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=uuid4(),
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        contract=add_registration.contract,
        published_authority=Availability.AVAILABLE,
    )
    broad_request = OperationRequest[BaseModel](
        definition_id=add_request.definition_id,
        subject_ref=add_request.subject_ref,
        payload=add_request.payload,
    )
    access = operation.resolve_review_package_recipient_add_access(broad_request, context)

    assert access.request.period_independent
    assert not access.request.periods
    assert AccessAction.COMMIT in access.policy.actions
    assert add_definition.capabilities.replay.value == "none"
    assert add_definition.reconciliation_policy.value == "interrupt"
    assert add_definition.capabilities.permitted_effects == frozenset(
        {OperationEffect.NONE, OperationEffect.PARTIAL, OperationEffect.UPDATED, OperationEffect.UNKNOWN}
    )

    result_context = replace(context, action=AccessAction.RESULT)
    result_access = operation.resolve_review_package_recipient_add_access(broad_request, result_context)
    permission = next(iter(result_access.policy.disclosures))
    assert permission.category is DisclosureCategory.PROFILE_VALUES
    assert permission.destination_id == result_context.destination_id

    wrong_profile = replace(context, profile_id=uuid4())
    with pytest.raises(ProfileAccessRefusedError) as refused:
        operation.resolve_review_package_recipient_add_access(broad_request, wrong_profile)
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH


def test_result_projector_requires_successful_exact_effect_receipt() -> None:
    row = _record("accountant")
    projection = operation.ReviewPackageRecipientAddProjection(
        profile_id=_PROFILE,
        recipient=operation.ReviewPackageRecipientProjection.from_record(row),
    )
    private = operation._RecipientAddExecutionResult(profile_id=_PROFILE, result=projection)
    identity = OperationIdentity(
        operation_id="a" * 64,
        definition_id=operation.REVIEW_PACKAGE_RECIPIENT_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_NOW,
        result_ref="sha256:result",
    )

    assert operation.project_review_package_recipient_add_result(private, receipt) == projection
    with pytest.raises(ValueError, match="terminal receipt"):
        operation.project_review_package_recipient_add_result(
            private,
            receipt.model_copy(update={"effect": OperationEffect.NONE}),
        )
