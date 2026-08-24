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
    OperationInteractionRequest,
    OperationOwnedResource,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationSchemaBindingV1,
    OperationSchemaIdentityV1,
    OperationSensitiveInputPolicy,
    OperationSnapshot,
    OperationTerminalReceipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class RequestPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str


class ResultPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    reference: str


class ReviewPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    summary_code: str


class RefreshTarget(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    subject_ref: str


class AlternateRequestPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    count: int


class NonStrictPayload(BaseModel):
    value: str


class OpenObjectPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    labels: dict[str, str]


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


def review_projector(operand: BaseModel, interaction: OperationInteractionRequest) -> BaseModel:
    del operand, interaction
    return ReviewPayload(summary_code="profile.sync.review")


def refresh_adapter(receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    return RefreshTarget(subject_ref="profile:active")


def public_registration(
    item: OperationDefinition,
    *,
    request_type: type[BaseModel] = RequestPayload,
    request_schema_id: str | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=request_schema_id or f"{item.definition_id}.request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.result",
            schema_version=1,
            model_type=ResultPayload,
        ),
        review_projection_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.review",
            schema_version=1,
            model_type=ReviewPayload,
        ),
        workspace_refresh_target_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.refresh",
            schema_version=1,
            model_type=RefreshTarget,
        ),
        review_projector=review_projector,
        workspace_refresh_adapter=refresh_adapter,
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


def test_public_schema_identity_is_exact_and_refuses_non_strict_models() -> None:
    first = OperationSchemaIdentityV1.from_model(
        schema_id="profile.sync.request",
        schema_version=1,
        model_type=RequestPayload,
    )
    second = OperationSchemaIdentityV1.from_model(
        schema_id="profile.sync.request",
        schema_version=1,
        model_type=RequestPayload,
    )

    assert first == second
    assert first.schema_fingerprint == "2d580ffa1af222cf9aba76e58220104f26fe5e3737b1fa1a674cde21fe93cee1"
    with pytest.raises(ValueError, match="strict, frozen"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.unsafe",
            schema_version=1,
            model_type=NonStrictPayload,
        )
    with pytest.raises(ValueError, match="open object payload bags"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.open-object",
            schema_version=1,
            model_type=OpenObjectPayload,
        )


def test_public_definition_and_contract_set_digests_are_deterministic_and_self_validating() -> None:
    first_definition = definition(definition_id="profile.alpha")
    second_definition = definition(definition_id="profile.zeta")
    first = public_registration(first_definition).contract
    second = public_registration(second_definition).contract

    contract_set = OperationPublicContractSetV1.build((second, first))
    rebuilt = OperationPublicContractSetV1.build((first, second))

    assert contract_set == rebuilt
    assert tuple(item.definition_id for item in contract_set.definitions) == ("profile.alpha", "profile.zeta")
    set_order_one = first_definition.model_copy(
        update={
            "interaction_kinds": frozenset(
                [OperationInteractionKind.REVIEW],
            ),
            "permitted_frontends": frozenset(
                [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI],
            ),
            "capabilities": first_definition.capabilities.model_copy(
                update={
                    "owned_resources": frozenset(
                        [OperationOwnedResource.ASYNC_TASK, OperationOwnedResource.PROCESS],
                    ),
                    "permitted_effects": frozenset(
                        [OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN],
                    ),
                },
            ),
        },
    )
    set_order_two = first_definition.model_copy(
        update={
            "interaction_kinds": frozenset(
                [OperationInteractionKind.REVIEW],
            ),
            "permitted_frontends": frozenset(
                [OperationFrontendProjection.TUI, OperationFrontendProjection.CLI],
            ),
            "capabilities": first_definition.capabilities.model_copy(
                update={
                    "owned_resources": frozenset(
                        [OperationOwnedResource.PROCESS, OperationOwnedResource.ASYNC_TASK],
                    ),
                    "permitted_effects": frozenset(
                        [OperationEffect.UNKNOWN, OperationEffect.UPDATED, OperationEffect.NONE],
                    ),
                },
            ),
        },
    )
    assert public_registration(set_order_one).contract.definition_contract_digest == (
        public_registration(set_order_two).contract.definition_contract_digest
    )
    tampered_contract = {field_name: getattr(first, field_name) for field_name in first.__class__.model_fields}
    tampered_contract["permitted_frontends"] = frozenset({OperationFrontendProjection.TUI})
    with pytest.raises(ValidationError, match="digest does not reproduce"):
        OperationPublicDefinitionContractV1.model_validate(tampered_contract)
    tampered_set = {field_name: getattr(contract_set, field_name) for field_name in contract_set.__class__.model_fields}
    tampered_set["contract_set_digest"] = "f" * 64
    with pytest.raises(ValidationError, match="contract-set digest does not reproduce"):
        OperationPublicContractSetV1.model_validate(tampered_set)


def test_registry_public_contract_is_a_live_definition_fixed_point() -> None:
    item = definition(definition_id="profile.sync")
    registration = public_registration(item)
    registry = OperationRegistry(definitions=(item,), public_registrations=(registration,))

    assert registration.contract.definition_contract_digest == (
        "52cca15e062028441c31313f2337360487b878bb89fc90d8817a9848dabc7cb3"
    )
    assert registry.public_contract_set.contract_set_digest == (
        "44d6bb71a45ff1e0d67881d3dc26433de7c509e2c26cfcd25d4fa84937c373f2"
    )
    assert registry.public_contract_set.definitions == (registration.contract,)
    drifted = item.model_copy(update={"permitted_frontends": frozenset({OperationFrontendProjection.TUI})})
    with pytest.raises(ValidationError, match="not a live-registry fixed point"):
        OperationRegistry(definitions=(drifted,), public_registrations=(registration,))


def test_registry_refuses_missing_review_projector_and_refresh_adapter() -> None:
    item = definition(definition_id="profile.sync")
    registration = public_registration(item)

    without_review = registration.model_copy(update={"review_projector": None})
    with pytest.raises(ValidationError, match="registered review projector"):
        OperationRegistry(definitions=(item,), public_registrations=(without_review,))
    without_refresh = registration.model_copy(update={"workspace_refresh_adapter": None})
    with pytest.raises(ValidationError, match="schema and adapter"):
        OperationRegistry(definitions=(item,), public_registrations=(without_refresh,))


def test_registry_refuses_incomplete_public_inventory_and_request_model_rebinding() -> None:
    first = definition(definition_id="profile.alpha")
    second = definition(definition_id="profile.zeta")

    with pytest.raises(ValidationError, match="exactly cover"):
        OperationRegistry(definitions=(first, second), public_registrations=(public_registration(first),))
    with pytest.raises(ValidationError, match="request schema"):
        OperationRegistry(
            definitions=(first,),
            public_registrations=(public_registration(first, request_type=AlternateRequestPayload),),
        )


def test_registry_refuses_one_schema_identity_redeclared_for_different_models() -> None:
    first = definition(definition_id="profile.alpha")
    second = definition(definition_id="profile.zeta")
    second_factory = OperationExecutorFactory(
        request_type=AlternateRequestPayload,
        executor_type=Executor,
        build=executor_factory,
    )
    second = second.model_copy(update={"request_type": AlternateRequestPayload, "executor_factory": second_factory})
    first_registration = public_registration(first, request_schema_id="profile.shared.request")
    second_registration = public_registration(
        second,
        request_type=AlternateRequestPayload,
        request_schema_id="profile.shared.request",
    )

    with pytest.raises(ValidationError, match="one exact model and fingerprint"):
        OperationRegistry(
            definitions=(first, second),
            public_registrations=(first_registration, second_registration),
        )
