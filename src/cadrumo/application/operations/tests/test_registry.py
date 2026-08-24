"""Real contract tests for the immutable operation-definition registry."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from ....core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationLifecycle,
)
from ...operator_actions import ActionReference
from .. import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationIdentity,
    OperationInteractionKind,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
    OperationSnapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class RequestPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str


class ResultPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    reference: str


class Executor:
    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: object,
    ) -> str | None:
        return request.subject_ref


def executor_factory() -> Executor:
    return Executor()


class ResumableExecutor(Executor):
    async def resume(self, request: OperationRequest[BaseModel], checkpoint: object, context: object) -> str | None:
        del checkpoint
        return await self.execute(request, context)


def resumable_executor_factory() -> ResumableExecutor:
    return ResumableExecutor()


def capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.COOPERATIVE,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.REQUEST_CANCEL,
    )


def definition(*, definition_id: str, action_id: str | None = None) -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=RequestPayload,
        result_type=ResultPayload,
        executor_factory=OperationExecutorFactory(
            request_type=RequestPayload,
            executor_type=Executor,
            build=executor_factory,
        ),
        phase_codes=("profile.sync.review", "profile.sync.read"),
        interaction_kinds=frozenset({OperationInteractionKind.REVIEW}),
        capabilities=capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
        action_reference=ActionReference(action_id=action_id) if action_id is not None else None,
    )


def request(*, definition_id: str = "profile.sync", value: str = "submitted") -> OperationRequest[RequestPayload]:
    return OperationRequest[RequestPayload](
        definition_id=definition_id,
        subject_ref="profile:active",
        payload=RequestPayload(value=value),
        idempotency_key="sync-2026-08-13",
    )


def snapshot(*, definition_id: str = "profile.sync", value: str = "submitted") -> OperationSnapshot[RequestPayload]:
    identity = OperationIdentity(
        operation_id="a" * 64,
        definition_id=definition_id,
        subject_ref="profile:active",
    )
    return OperationSnapshot[RequestPayload](
        identity=identity,
        request=request(definition_id=definition_id, value=value),
        revision=3,
        lifecycle=OperationLifecycle.RUNNING,
        updated_at=datetime(2026, 8, 13, 20, tzinfo=UTC),
        event_cursor=9,
    )


def test_registry_canonicalises_and_resolves_definition_and_action_identity() -> None:
    second = definition(definition_id="profile.sync", action_id="operator.profile.sync")
    first = definition(definition_id="auth.login")
    registry = OperationRegistry(definitions=(second, first))

    assert tuple(item.definition_id for item in registry.definitions) == ("auth.login", "profile.sync")
    assert registry.lookup("profile.sync") is second
    assert registry.lookup_action(ActionReference(action_id="operator.profile.sync")) is second
    assert second.phase_codes == ("profile.sync.read", "profile.sync.review")
    assert isinstance(second.executor_factory.create(), Executor)
    with pytest.raises(ValidationError):
        registry.definitions = ()


def test_registry_refuses_unknown_and_ambiguous_identities() -> None:
    item = definition(definition_id="profile.sync", action_id="operator.profile.sync")
    registry = OperationRegistry(definitions=(item,))

    with pytest.raises(KeyError, match="unknown operation definition"):
        registry.lookup("profile.unknown")
    with pytest.raises(KeyError, match="not mapped"):
        registry.lookup_action(ActionReference(action_id="operator.profile.unknown"))
    with pytest.raises(ValidationError, match="definition IDs must be unique"):
        OperationRegistry(definitions=(item, item))
    with pytest.raises(ValidationError, match="at most one"):
        OperationRegistry(
            definitions=(item, definition(definition_id="profile.sync.other", action_id="operator.profile.sync"))
        )


def test_definition_refuses_mismatched_factory_payload_and_factory_output() -> None:
    wrong_payload_factory = OperationExecutorFactory(
        request_type=ResultPayload,
        executor_type=Executor,
        build=executor_factory,
    )
    with pytest.raises(ValidationError, match="request type must match"):
        OperationDefinition(
            definition_id="profile.sync",
            request_type=RequestPayload,
            result_type=ResultPayload,
            executor_factory=wrong_payload_factory,
            phase_codes=("profile.sync.read",),
            interaction_kinds=frozenset(),
            capabilities=capabilities(),
            reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
            permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        )

    wrong_output_factory = OperationExecutorFactory(
        request_type=RequestPayload,
        executor_type=Executor,
        build=object,
    )
    with pytest.raises(TypeError, match="undeclared or invalid"):
        wrong_output_factory.create()


def test_definition_requires_explicit_reconciliation_and_projection_policy() -> None:
    payload = definition(definition_id="profile.sync").model_dump()
    payload.pop("reconciliation_policy")
    with pytest.raises(ValidationError):
        OperationDefinition.model_validate(payload)


def test_definition_requires_unknown_effect_for_owner_loss_reconciliation() -> None:
    payload = definition(definition_id="profile.sync").model_dump()
    payload["capabilities"]["permitted_effects"] = frozenset({OperationEffect.NONE})

    with pytest.raises(ValidationError, match="must permit unknown effect"):
        OperationDefinition.model_validate(payload)


def test_definition_allows_ephemeral_none_effect_without_owner_loss_unknown_effect() -> None:
    payload = definition(definition_id="profile.ephemeral").model_dump()
    payload["capabilities"] = {
        **payload["capabilities"],
        "durability": OperationDurability.EPHEMERAL,
        "cancellation": OperationCancellation.UNSUPPORTED,
        "deadline": OperationDeadline.ABSENT,
        "replay": OperationReplayPolicy.NONE,
        "baseline": OperationBaselinePolicy.NONE,
        "request_storage": OperationRequestStoragePolicy.SECURE_REFERENCE,
        "sensitive_input": OperationSensitiveInputPolicy.NONE,
        "conflict_scope": OperationConflictScope.NONE,
        "permitted_effects": frozenset({OperationEffect.NONE}),
        "close_policy": OperationClosePolicy.DETACH_ALLOWED,
    }

    resolved = OperationDefinition.model_validate(payload)

    assert resolved.capabilities.durability is OperationDurability.EPHEMERAL
    assert resolved.capabilities.permitted_effects == frozenset({OperationEffect.NONE})


@pytest.mark.parametrize(
    ("capabilities_payload", "interaction_kinds", "executor_type", "build", "message"),
    (
        (
            {
                "durability": OperationDurability.EPHEMERAL,
                "replay": OperationReplayPolicy.NONE,
                "conflict_scope": OperationConflictScope.NONE,
                "permitted_effects": frozenset({OperationEffect.NONE}),
            },
            frozenset({OperationInteractionKind.REVIEW}),
            ResumableExecutor,
            resumable_executor_factory,
            "resumable durability",
        ),
        (
            {"durability": OperationDurability.RECORDED, "replay": OperationReplayPolicy.IDEMPOTENT_SUBMIT},
            frozenset({OperationInteractionKind.REVIEW}),
            ResumableExecutor,
            resumable_executor_factory,
            "resumable durability",
        ),
        (
            {"durability": OperationDurability.RESUMABLE, "replay": OperationReplayPolicy.RESUMABLE},
            frozenset(),
            ResumableExecutor,
            resumable_executor_factory,
            "declared interaction checkpoint",
        ),
        (
            {"durability": OperationDurability.RESUMABLE, "replay": OperationReplayPolicy.RESUMABLE},
            frozenset({OperationInteractionKind.REVIEW}),
            Executor,
            executor_factory,
            "resumable executor",
        ),
    ),
)
def test_definition_refuses_invalid_resume_policy_combinations(
    capabilities_payload: dict[str, object],
    interaction_kinds: frozenset[OperationInteractionKind],
    executor_type: type[object],
    build: object,
    message: str,
) -> None:
    payload = definition(definition_id="profile.resume").model_dump()
    payload["capabilities"] = {**payload["capabilities"], **capabilities_payload}
    payload["interaction_kinds"] = interaction_kinds
    payload["executor_factory"] = OperationExecutorFactory(
        request_type=RequestPayload,
        executor_type=executor_type,
        build=build,
    )
    payload["reconciliation_policy"] = OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT

    with pytest.raises(ValidationError, match=message):
        OperationDefinition.model_validate(payload)


def test_registry_resolves_registered_concrete_request_and_snapshot_models() -> None:
    registry = OperationRegistry(definitions=(definition(definition_id="profile.sync"),))
    submitted = request()
    observed = snapshot()

    resolved_request = registry.resolve_request_json(submitted.model_dump_json().encode())
    resolved_snapshot = registry.resolve_snapshot_json(observed.model_dump_json())

    assert resolved_request == submitted
    assert isinstance(resolved_request.payload, RequestPayload)
    assert resolved_snapshot == observed
    assert isinstance(resolved_snapshot.request.payload, RequestPayload)


def test_registry_resolvers_hydrate_payload_mutations_through_the_registered_model() -> None:
    registry = OperationRegistry(definitions=(definition(definition_id="profile.sync"),))
    raw = snapshot().model_dump_json()
    mutated = raw.replace('"value":"submitted"', '"value":"changed"')
    assert mutated != raw, "the serialized request payload was not mutated"

    resolved = registry.resolve_snapshot_json(mutated)

    assert isinstance(resolved.request.payload, RequestPayload)
    assert resolved.request.payload.value == "changed"
    assert resolved != snapshot()


def test_registry_resolvers_refuse_unknown_definition_identity_and_payload_model_mismatch() -> None:
    registry = OperationRegistry(
        definitions=(definition(definition_id="auth.login"), definition(definition_id="profile.sync")),
    )
    raw = snapshot().model_dump_json()
    unknown_request = request().model_dump_json().replace("profile.sync", "profile.unknown")
    unknown_snapshot = raw.replace("profile.sync", "profile.unknown")
    wrong_payload_model = raw.replace('"value":"submitted"', '"reference":"unexpected"')
    wrong_request_payload_model = request().model_dump_json().replace('"value":"submitted"', '"reference":"unexpected"')
    mismatched_identity = raw.replace('"definition_id":"profile.sync"', '"definition_id":"auth.login"', 1)
    mismatched_subject = raw.replace('"subject_ref":"profile:active"', '"subject_ref":"profile:other"', 1)

    assert unknown_request != request().model_dump_json(), "the request definition identity was not mutated"
    assert unknown_snapshot != raw, "the snapshot definition identity was not mutated"
    assert wrong_payload_model != raw, "the serialized payload model was not mutated"
    assert wrong_request_payload_model != request().model_dump_json(), "the request payload model was not mutated"
    assert mismatched_identity != raw, "the snapshot definition identity was not mutated"
    assert mismatched_subject != raw, "the snapshot subject identity was not mutated"
    with pytest.raises(KeyError, match="unknown operation definition"):
        registry.resolve_request_json(unknown_request)
    with pytest.raises(KeyError, match="unknown operation definition"):
        registry.resolve_snapshot_json(unknown_snapshot)
    with pytest.raises(ValidationError):
        registry.resolve_snapshot_json(wrong_payload_model)
    with pytest.raises(ValidationError):
        registry.resolve_request_json(wrong_request_payload_model)
    with pytest.raises(ValidationError, match="request definition"):
        registry.resolve_snapshot_json(mismatched_identity)
    with pytest.raises(ValidationError, match="request subject"):
        registry.resolve_snapshot_json(mismatched_subject)


def test_registry_resolvers_refuse_malformed_json_as_controlled_validation_errors() -> None:
    registry = OperationRegistry(definitions=(definition(definition_id="profile.sync"),))

    with pytest.raises(ValidationError, match="Invalid JSON"):
        registry.resolve_request_json('{"definition_id":')
    with pytest.raises(ValidationError, match="Invalid JSON"):
        registry.resolve_snapshot_json(b'{"identity":')

    payload = definition(definition_id="profile.sync").model_dump()
    payload["permitted_frontends"] = frozenset()
    with pytest.raises(ValidationError):
        OperationDefinition.model_validate(payload)
