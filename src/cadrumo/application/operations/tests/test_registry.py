"""Real contract tests for the immutable operation-definition registry."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from ....core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...operator_actions import ActionReference
from .. import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationInteractionKind,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationRequest,
    OperationSensitiveInputPolicy,
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


def capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.COOPERATIVE,
        deadline=OperationDeadline.COOPERATIVE,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.REQUEST_BOUND,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED}),
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

    payload = definition(definition_id="profile.sync").model_dump()
    payload["permitted_frontends"] = frozenset()
    with pytest.raises(ValidationError):
        OperationDefinition.model_validate(payload)
