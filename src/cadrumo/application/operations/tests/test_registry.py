"""Real contract tests for the immutable operation-definition registry."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict, cast, override

import pytest
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    Json,
    PlainSerializer,
    SecretStr,
    ValidationError,
    ValidatorFunctionWrapHandler,
    computed_field,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from ....core.identity import ContentDigest, WorkUnitId
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
)
from ...operator_actions.models import ActionReference
from ..capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..interactions import OperationInteractionRequest
from ..models import (
    CredentialFreeOperationRequest,
    OperationIdentity,
    OperationRequest,
    OperationSnapshot,
    OperationTerminalReceipt,
)
from ..registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationSchemaBindingV1,
    OperationSchemaIdentityV1,
    _strict_model_json_schema,
    _validate_credential_free_schema,
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


class LaxNestedPayload(BaseModel):
    value: str


class StrictParentWithLaxNestedPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    nested: LaxNestedPayload


class AnyPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    payload: Any


class ObjectPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    payload: object


class OpenObjectPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    labels: dict[str, str]


class FixedTuplePayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: tuple[str, int]


class UntypedFixedTuplePayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: tuple[str, Any]


class OpenFixedTuplePayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: tuple[str, int]

    @classmethod
    @override
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        schema = handler(core_schema)
        properties = cast(dict[str, object], schema["properties"])
        values_schema = cast(dict[str, object], properties["values"])
        values_schema.pop("maxItems", None)
        return schema


class MutableListPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: list[str]


class MutableSetPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: set[str]


class MutableMappingPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: Mapping[str, str]


class MutableValues(TypedDict):
    value: str


class MutableTypedDictPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: MutableValues


class MutableJsonPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    values: Json[list[str]]


class SecretPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: SecretStr


class ComputedPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str

    @computed_field
    @property
    def projected_value(self) -> str:
        return self.value


#: Strict and frozen like the shared constant, but deliberately WITHOUT
#: ``validate_default``. The witness below needs to hold a default its own field
#: would reject; the shared constant now validates defaults, which makes that
#: violation inexpressible and leaves the gate with nothing to refuse.
_UNVALIDATED_DEFAULT_WITNESS_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid")


class InvalidDefaultPayload(BaseModel):
    model_config = _UNVALIDATED_DEFAULT_WITNESS_CONFIG

    value: int = cast(int, "not-an-integer")  # intentional admission witness


class ValidatedDefaultPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int = 0


class FieldSerializerPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str

    @field_serializer("value")
    def _serialize_value(self, value: str) -> dict[str, str]:
        return {"drifted": value}


class ModelSerializerPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: str

    @model_serializer
    def _serialize_model(self) -> dict[str, str]:
        return {"renamed": self.value}


def serialize_annotated_value(value: str) -> dict[str, str]:
    return {"drifted": value}


class AnnotatedSerializerPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: Annotated[
        str,
        PlainSerializer(serialize_annotated_value, return_type=dict[str, str]),
    ]


class LyingJsonSchemaPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int

    @classmethod
    @override
    def __get_pydantic_json_schema__(
        cls,
        core_schema: CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        schema = handler(core_schema)
        properties = cast(dict[str, object], schema["properties"])
        value_schema = cast(dict[str, object], properties["value"])
        value_schema["type"] = "string"
        return schema


class StructuralSchemaExtraPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int = Field(json_schema_extra={"type": "string"})


class BeforeFieldValidatorPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int

    @field_validator("value", mode="before")
    @classmethod
    def _accept_string_integer(cls, value: object) -> object:
        return int(value) if isinstance(value, str) else value


class PlainFieldValidatorPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int

    @field_validator("value", mode="plain")
    @classmethod
    def _accept_string_integer(cls, value: object) -> int:
        return int(value) if isinstance(value, str) else 0


class WrapFieldValidatorPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int

    @field_validator("value", mode="wrap")
    @classmethod
    def _accept_string_integer(cls, value: object, handler: ValidatorFunctionWrapHandler) -> int:
        resolved = handler(int(value)) if isinstance(value, str) else handler(value)
        assert isinstance(resolved, int)
        return resolved


class BeforeModelValidatorPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int

    @model_validator(mode="before")
    @classmethod
    def _accept_scalar(cls, value: object) -> object:
        return {"value": int(value)} if isinstance(value, str) else value


class AnnotationCoreSchemaPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: Annotated[
        int,
        BeforeValidator(lambda value: int(value) if isinstance(value, str) else value),
    ]


class ModelCoreSchemaHookPayload(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    value: int

    @classmethod
    @override
    def __get_pydantic_core_schema__(
        cls,
        source_type: object,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return handler(source_type)


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


def incompatible_review_projector(operand: BaseModel) -> BaseModel:
    del operand
    return ReviewPayload(summary_code="profile.sync.review")


def incompatible_refresh_adapter(receipt: OperationTerminalReceipt, extra: object) -> BaseModel:
    del receipt, extra
    return RefreshTarget(subject_ref="profile:active")


class AsyncReviewProjector:
    async def __call__(
        self,
        operand: BaseModel,
        interaction: OperationInteractionRequest,
    ) -> BaseModel:
        del operand, interaction
        return ReviewPayload(summary_code="profile.sync.review")


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
        reviewed_operand_type=ReviewPayload,
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
    with pytest.raises(ValueError, match="must set strict=True"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.unsafe",
            schema_version=1,
            model_type=NonStrictPayload,
        )
    with pytest.raises(ValueError, match=r"public schema\.nested model must set strict=True"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.lax-nested",
            schema_version=1,
            model_type=StrictParentWithLaxNestedPayload,
        )


@pytest.mark.parametrize("model_type", [AnyPayload, ObjectPayload])
def test_public_schema_identity_refuses_untyped_payload_branches(model_type: type[BaseModel]) -> None:
    with pytest.raises(ValueError, match="untyped branch"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.untyped",
            schema_version=1,
            model_type=model_type,
        )
    with pytest.raises(ValueError, match=r"mutable container|open object branch"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.open-object",
            schema_version=1,
            model_type=OpenObjectPayload,
        )


def test_public_schema_identity_accepts_one_closed_fixed_tuple() -> None:
    identity = OperationSchemaIdentityV1.from_model(
        schema_id="profile.sync.fixed-tuple",
        schema_version=1,
        model_type=FixedTuplePayload,
    )

    assert len(identity.schema_fingerprint) == 64


@pytest.mark.parametrize("model_type", [OpenFixedTuplePayload, UntypedFixedTuplePayload])
def test_public_schema_identity_refuses_open_or_untyped_fixed_tuples(model_type: type[BaseModel]) -> None:
    with pytest.raises(ValueError, match=r"customize its JSON schema|untyped branch"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.unsafe-tuple",
            schema_version=1,
            model_type=model_type,
        )


@pytest.mark.parametrize(
    "model_type",
    [MutableListPayload, MutableSetPayload, MutableMappingPayload, MutableTypedDictPayload, MutableJsonPayload],
)
def test_public_schema_identity_refuses_mutable_container_annotations(model_type: type[BaseModel]) -> None:
    with pytest.raises(ValueError, match=r"mutable container|mutable TypedDict"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.mutable-container",
            schema_version=1,
            model_type=model_type,
        )


def test_public_schema_identity_refuses_secret_capable_schema_branches() -> None:
    with pytest.raises(ValueError, match="secret-capable branch"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.secret",
            schema_version=1,
            model_type=SecretPayload,
        )


class _DigestNamedContentDigestPayload(CredentialFreeOperationRequest):
    """A digest-named field genuinely typed as ContentDigest - the admitted case."""

    model_config = STRICT_FROZEN_CONFIG

    permitted_surface_digest: ContentDigest


class _DigestNamedPlainStringPayload(CredentialFreeOperationRequest):
    """A digest-named field with no Hex64 shape at all - stays refused."""

    model_config = STRICT_FROZEN_CONFIG

    permitted_surface_digest: str


class _KeyNamedContentDigestPayload(CredentialFreeOperationRequest):
    """A Hex64-shaped field named for a DIFFERENT forbidden token - stays refused.

    The tripwire against the exemption swallowing a hex-encoded 256-bit
    secret that happens to share ``ContentDigest``'s 64-character shape.
    """

    model_config = STRICT_FROZEN_CONFIG

    encryption_key: ContentDigest


class _DigestNamedSiblingConceptPayload(CredentialFreeOperationRequest):
    """A digest-named field typed as a Hex64-shaped SIBLING concept - admitted.

    ``ContentDigest is WorkUnitId`` at runtime (both are ``= Hex64Str``), so
    there is no type-identity test available; this pins the accepted
    residual risk (a Hex64-shaped, digest-named field declared for a
    sibling concept is also admitted) as a documented test outcome rather
    than an undiscovered gap.
    """

    model_config = STRICT_FROZEN_CONFIG

    work_unit_digest: WorkUnitId


def test_credential_free_schema_admits_hex64_shaped_digest_named_field() -> None:
    schema = _strict_model_json_schema(_DigestNamedContentDigestPayload)
    _validate_credential_free_schema(schema)


def test_credential_free_schema_refuses_plain_string_digest_named_field() -> None:
    schema = _strict_model_json_schema(_DigestNamedPlainStringPayload)
    with pytest.raises(ValueError, match="forbidden security meaning"):
        _validate_credential_free_schema(schema)


def test_credential_free_schema_refuses_hex64_shaped_field_named_for_another_forbidden_token() -> None:
    schema = _strict_model_json_schema(_KeyNamedContentDigestPayload)
    with pytest.raises(ValueError, match="forbidden security meaning"):
        _validate_credential_free_schema(schema)


def test_credential_free_schema_admits_hex64_shaped_sibling_concept_named_digest() -> None:
    """Pins the accepted residual risk rather than leaving it undiscovered."""
    schema = _strict_model_json_schema(_DigestNamedSiblingConceptPayload)
    _validate_credential_free_schema(schema)


def test_public_schema_identity_refuses_computed_fields_absent_from_validation_schema() -> None:
    with pytest.raises(ValueError, match="computed fields"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.computed",
            schema_version=1,
            model_type=ComputedPayload,
        )


def test_public_schema_identity_refuses_unvalidated_typed_defaults() -> None:
    assert InvalidDefaultPayload.model_config.get("validate_default") is not True, (
        "the witness must omit validate_default, or it cannot express the violation this gate hunts"
    )

    with pytest.raises(ValueError, match="defaults must set validate_default=True"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.invalid-default",
            schema_version=1,
            model_type=InvalidDefaultPayload,
        )


def test_public_schema_identity_admits_a_validated_typed_default() -> None:
    """The refusal above must be about the missing validation, not about carrying a default at all."""
    identity = OperationSchemaIdentityV1.from_model(
        schema_id="profile.sync.validated-default",
        schema_version=1,
        model_type=ValidatedDefaultPayload,
    )

    assert identity.schema_id == "profile.sync.validated-default"


@pytest.mark.parametrize("model_type", [FieldSerializerPayload, ModelSerializerPayload])
def test_public_schema_identity_refuses_serializer_drift(model_type: type[BaseModel]) -> None:
    with pytest.raises(ValueError, match="serializers that drift"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.serializer-drift",
            schema_version=1,
            model_type=model_type,
        )


def test_public_schema_identity_refuses_annotated_serializer_drift() -> None:
    with pytest.raises(ValueError, match="must not customize its Pydantic core schema"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.annotated-serializer-drift",
            schema_version=1,
            model_type=AnnotatedSerializerPayload,
        )


def test_public_schema_identity_refuses_custom_json_schema_hooks() -> None:
    with pytest.raises(ValueError, match="must not customize its JSON schema"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.lying-schema-hook",
            schema_version=1,
            model_type=LyingJsonSchemaPayload,
        )


def test_public_schema_identity_refuses_structural_json_schema_extras() -> None:
    with pytest.raises(ValueError, match="schema extras must be nonstructural"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.structural-schema-extra",
            schema_version=1,
            model_type=StructuralSchemaExtraPayload,
        )


@pytest.mark.parametrize(
    "model_type",
    [
        BeforeFieldValidatorPayload,
        PlainFieldValidatorPayload,
        WrapFieldValidatorPayload,
        BeforeModelValidatorPayload,
    ],
)
def test_public_schema_identity_refuses_coercive_before_plain_or_wrap_validators(
    model_type: type[BaseModel],
) -> None:
    with pytest.raises(ValueError, match="must not declare coercive"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.coercive-validator",
            schema_version=1,
            model_type=model_type,
        )


def test_public_schema_identity_refuses_annotation_core_schema_hooks() -> None:
    with pytest.raises(ValueError, match="must not customize its Pydantic core schema"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.core-schema-hook",
            schema_version=1,
            model_type=AnnotationCoreSchemaPayload,
        )


def test_public_schema_identity_refuses_model_class_core_schema_hooks() -> None:
    with pytest.raises(ValueError, match="must not customize its Pydantic core schema"):
        OperationSchemaIdentityV1.from_model(
            schema_id="profile.sync.model-core-schema-hook",
            schema_version=1,
            model_type=ModelCoreSchemaHookPayload,
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
    assert registry.lookup_public_contract(item.definition_id) == registration.contract
    with pytest.raises(KeyError, match="no public contract"):
        OperationRegistry(definitions=(item,)).lookup_public_contract(item.definition_id)
    drifted = item.model_copy(update={"permitted_frontends": frozenset({OperationFrontendProjection.TUI})})
    with pytest.raises(ValidationError, match="not a live-registry fixed point"):
        OperationRegistry(definitions=(drifted,), public_registrations=(registration,))


def test_registry_refuses_missing_review_projector_and_refresh_adapter() -> None:
    item = definition(definition_id="profile.sync")
    registration = public_registration(item)

    without_review = registration.model_copy(update={"review_projector": None})
    with pytest.raises(ValidationError, match="registered review projector"):
        OperationRegistry(definitions=(item,), public_registrations=(without_review,))
    without_operand_type = registration.model_copy(update={"reviewed_operand_type": None})
    with pytest.raises(ValidationError, match="registered reviewed operand type"):
        OperationRegistry(definitions=(item,), public_registrations=(without_operand_type,))
    without_refresh = registration.model_copy(update={"workspace_refresh_adapter": None})
    with pytest.raises(ValidationError, match="schema and adapter"):
        OperationRegistry(definitions=(item,), public_registrations=(without_refresh,))


def test_registry_refuses_signature_incompatible_review_and_refresh_adapters() -> None:
    item = definition(definition_id="profile.sync")
    registration = public_registration(item)

    incompatible_review = registration.model_copy(update={"review_projector": incompatible_review_projector})
    with pytest.raises(ValidationError, match="REVIEW projector must accept exactly 2 positional arguments"):
        OperationRegistry(definitions=(item,), public_registrations=(incompatible_review,))
    incompatible_refresh = registration.model_copy(
        update={"workspace_refresh_adapter": incompatible_refresh_adapter},
    )
    with pytest.raises(ValidationError, match="refresh adapter must accept exactly 1 positional arguments"):
        OperationRegistry(definitions=(item,), public_registrations=(incompatible_refresh,))
    asynchronous_review = registration.model_copy(update={"review_projector": AsyncReviewProjector()})
    with pytest.raises(ValidationError, match="REVIEW projector must be synchronous"):
        OperationRegistry(definitions=(item,), public_registrations=(asynchronous_review,))


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


def _result_projector(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    del result, terminal_receipt
    return RefreshTarget(subject_ref="profile:active")


def _no_interaction_definition(definition_id: str = "profile.sync.settled") -> OperationDefinition:
    return OperationDefinition(
        definition_id=definition_id,
        request_type=RequestPayload,
        result_type=ResultPayload,
        executor_factory=OperationExecutorFactory(
            request_type=RequestPayload,
            executor_type=Executor,
            build=executor_factory,
        ),
        phase_codes=("profile.sync.settled.run",),
        interaction_kinds=frozenset(),
        capabilities=capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def test_registry_requires_a_result_projector_only_when_the_public_schema_diverges() -> None:
    """Symmetric with REVIEW: identical result schema needs no projector, a distinct one requires one."""
    item = _no_interaction_definition()

    identical_registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.request", schema_version=1, model_type=RequestPayload
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.result", schema_version=1, model_type=ResultPayload
        ),
    )
    OperationRegistry(definitions=(item,), public_registrations=(identical_registration,))

    identical_with_projector = identical_registration.model_copy(update={"result_projector": _result_projector})
    with pytest.raises(ValidationError, match="must not declare one"):
        OperationRegistry(definitions=(item,), public_registrations=(identical_with_projector,))

    distinct_registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.request", schema_version=1, model_type=RequestPayload
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.public-result", schema_version=1, model_type=RefreshTarget
        ),
        result_projector=_result_projector,
    )
    OperationRegistry(definitions=(item,), public_registrations=(distinct_registration,))

    distinct_without_projector = distinct_registration.model_copy(update={"result_projector": None})
    with pytest.raises(ValidationError, match="requires one registered result projector"):
        OperationRegistry(definitions=(item,), public_registrations=(distinct_without_projector,))


def test_registry_refuses_a_result_less_definition_declaring_a_result_projector() -> None:
    item = _no_interaction_definition().model_copy(update={"result_type": None})
    registration = OperationPublicDefinitionRegistrationV1.compose(
        definition=item,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=f"{item.definition_id}.request", schema_version=1, model_type=RequestPayload
        ),
        result_projector=_result_projector,
    )
    with pytest.raises(ValidationError, match="result-less operation definition cannot declare a result projector"):
        OperationRegistry(definitions=(item,), public_registrations=(registration,))
