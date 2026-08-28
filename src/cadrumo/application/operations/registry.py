"""Immutable registry for application-owned operation definitions."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from enum import StrEnum
from typing import Annotated, Literal, Protocol, TypedDict, cast, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PydanticInvalidForJsonSchema,
    field_validator,
    model_validator,
)

from ...core import (
    STRICT_FROZEN_CONFIG,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
    content_hash_hex,
)
from ...core.identity import ContentDigest
from ..operator_actions import ActionReference
from ._model_contract import require_strict_frozen_operation_model_graph
from .capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .events import OperationEventCode
from .financial_operand import OperationTransientFinancialOperandDeclaration
from .financial_operand_custody import (
    OperationFinancialOperandCrashClassification,
    OperationFinancialOperandCustodyCheckpoint,
)
from .interactions import OperationInteractionRequest
from .models import (
    CredentialFreeOperationRequest,
    OperationDefinitionId,
    OperationIdentity,
    OperationRequest,
    OperationSnapshot,
    OperationTerminalReceipt,
)
from .owner import OperationExecutor, OperationResumableExecutor
from .secret_submission import OperationEphemeralSecretDeclaration

_FORBIDDEN_CREDENTIAL_FREE_FIELD_PARTS = frozenset(
    {
        "auth",
        "bearer",
        "callback",
        "cookie",
        "credential",
        "ciphertext",
        "digest",
        "encrypted",
        "frontend",
        "hash",
        "key",
        "passphrase",
        "password",
        "proof",
        "secret",
        "session",
        "signature",
        "token",
        "transport",
        "verifier",
        "wrapped",
    }
)
_FORBIDDEN_OPERATION_SCHEMA_FORMATS = frozenset({"binary", "byte", "password"})
_STRICT_RUNTIME_BINDING_CONFIG = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
    arbitrary_types_allowed=True,
)
_STRICT_PUBLIC_MODEL_CONFIG = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
    validate_default=True,
)

type OperationPublicSchemaId = Annotated[
    str,
    Field(min_length=3, max_length=160, pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$"),
]


class OperationSchemaIdentityV1(BaseModel):
    """Stable public identity of one exact strict Pydantic JSON schema."""

    model_config = _STRICT_PUBLIC_MODEL_CONFIG

    schema_id: OperationPublicSchemaId
    schema_version: Annotated[int, Field(ge=1)]
    schema_fingerprint: ContentDigest

    @classmethod
    def from_model(
        cls,
        *,
        schema_id: OperationPublicSchemaId,
        schema_version: int,
        model_type: type[BaseModel],
    ) -> OperationSchemaIdentityV1:
        """Derive the identity from the canonical closed schema of ``model_type``."""
        schema = _strict_model_json_schema(model_type)
        return cls(
            schema_id=schema_id,
            schema_version=schema_version,
            schema_fingerprint=content_hash_hex(schema),
        )


class OperationPublicDefinitionContractV1(BaseModel):
    """Renderer-neutral public manifest row for one operation definition."""

    model_config = _STRICT_PUBLIC_MODEL_CONFIG

    manifest_version: Literal[1] = 1
    definition_id: OperationDefinitionId
    action_reference: ActionReference | None
    request_schema: OperationSchemaIdentityV1
    result_schema: OperationSchemaIdentityV1 | None
    review_projection_schema: OperationSchemaIdentityV1 | None
    interaction_response_schema: OperationSchemaIdentityV1 | None
    workspace_refresh_target_schema: OperationSchemaIdentityV1 | None
    interaction_kinds: frozenset[OperationInteractionKind]
    request_storage: OperationRequestStoragePolicy
    durability: OperationDurability
    cancellation: OperationCancellation
    deadline: OperationDeadline
    replay: OperationReplayPolicy
    baseline: OperationBaselinePolicy
    sensitive_input: OperationSensitiveInputPolicy
    conflict_scope: OperationConflictScope
    owned_resources: frozenset[OperationOwnedResource]
    permitted_effects: frozenset[OperationEffect]
    close_policy: OperationClosePolicy
    reconciliation_policy: OperationReconciliationPolicy
    permitted_frontends: frozenset[OperationFrontendProjection]
    ephemeral_secret_required: bool
    definition_contract_digest: ContentDigest

    @model_validator(mode="after")
    def _validate_digest(self) -> OperationPublicDefinitionContractV1:
        expected = _definition_contract_digest(self)
        if self.definition_contract_digest != expected:
            raise ValueError("operation definition contract digest does not reproduce")
        return self


class OperationPublicContractSetV1(BaseModel):
    """Canonical fixed-point inventory of all public operation contracts."""

    model_config = _STRICT_PUBLIC_MODEL_CONFIG

    contract_set_version: Literal[1] = 1
    definitions: tuple[OperationPublicDefinitionContractV1, ...] = Field(min_length=1)
    contract_set_digest: ContentDigest

    @field_validator("definitions")
    @classmethod
    def _canonical_contracts(
        cls,
        value: tuple[OperationPublicDefinitionContractV1, ...],
    ) -> tuple[OperationPublicDefinitionContractV1, ...]:
        definition_ids = tuple(contract.definition_id for contract in value)
        if len(set(definition_ids)) != len(definition_ids):
            raise ValueError("public operation definition IDs must be unique")
        if definition_ids != tuple(sorted(definition_ids)):
            raise ValueError("public operation contracts must be sorted by definition ID")
        return value

    @model_validator(mode="after")
    def _validate_digest(self) -> OperationPublicContractSetV1:
        expected = _contract_set_digest(self.definitions)
        if self.contract_set_digest != expected:
            raise ValueError("operation public contract-set digest does not reproduce")
        return self

    @classmethod
    def build(
        cls,
        definitions: tuple[OperationPublicDefinitionContractV1, ...],
    ) -> OperationPublicContractSetV1:
        """Build the canonical sorted set and its deterministic digest."""
        canonical = tuple(sorted(definitions, key=lambda item: item.definition_id))
        return cls(definitions=canonical, contract_set_digest=_contract_set_digest(canonical))


class _OperationRequestResolutionHeader(BaseModel):
    """Minimal request identity used only to select its registered model."""

    model_config = ConfigDict(strict=True, frozen=True, extra="ignore")

    definition_id: OperationDefinitionId


class _OperationSnapshotResolutionHeader(BaseModel):
    """Minimal snapshot identity used only to select its registered model."""

    model_config = ConfigDict(strict=True, frozen=True, extra="ignore")

    identity: OperationIdentity


def _specialize_request_model(request_type: type[BaseModel]) -> type[OperationRequest[BaseModel]]:
    """Bind the runtime registry model while erasing only its payload subtype.

    Pydantic's generic ``__class_getitem__`` is the runtime dispatch point for
    a model class selected from the validated registry. Static typing cannot
    express a type parameter supplied by a value at runtime, so this boundary
    cast records the sound part of the contract: the returned class is an
    ``OperationRequest`` whose payload is at least a ``BaseModel``.
    """
    specialized = OperationRequest.__class_getitem__(request_type)
    return cast(type[OperationRequest[BaseModel]], specialized)


def _specialize_snapshot_model(request_type: type[BaseModel]) -> type[OperationSnapshot[BaseModel]]:
    """Bind the runtime registry model for one persisted snapshot."""
    specialized = OperationSnapshot.__class_getitem__(request_type)
    return cast(type[OperationSnapshot[BaseModel]], specialized)


class OperationReconciliationPolicy(StrEnum):
    """Closed owner-loss behavior declared by an operation definition."""

    INTERRUPT = "interrupt"
    RESUME_FROM_CHECKPOINT = "resume_from_checkpoint"


class OperationFrontendProjection(StrEnum):
    """Product-owned identities of permitted operation projections."""

    CLI = "cli"
    MCP = "mcp"
    TUI = "tui"


class OperationExecutorFactory(BaseModel):
    """Non-effectful descriptor binding an executor class to its request type."""

    model_config = STRICT_FROZEN_CONFIG

    request_type: type[BaseModel]
    executor_type: type[object]
    build: Callable[[], object]

    @model_validator(mode="after")
    def _validate_executor_type(self) -> OperationExecutorFactory:
        if not issubclass(self.executor_type, OperationExecutor):
            raise ValueError("operation executor type must structurally implement OperationExecutor")
        return self

    def create(self) -> OperationExecutor[BaseModel]:
        """Construct and validate the declared executor without running it."""
        executor = self.build()
        if not isinstance(executor, self.executor_type) or not isinstance(executor, OperationExecutor):
            raise TypeError("operation executor factory returned an undeclared or invalid executor")
        return cast(OperationExecutor[BaseModel], executor)


class OperationDefinition(BaseModel):
    """Complete generic contract registered for one operation type."""

    model_config = STRICT_FROZEN_CONFIG

    definition_id: OperationDefinitionId
    request_type: type[BaseModel]
    result_type: type[BaseModel] | None
    executor_factory: OperationExecutorFactory
    phase_codes: tuple[OperationEventCode, ...] = Field(min_length=1)
    interaction_kinds: frozenset[OperationInteractionKind]
    capabilities: OperationCapabilities
    reconciliation_policy: OperationReconciliationPolicy
    permitted_frontends: frozenset[OperationFrontendProjection] = Field(min_length=1)
    action_reference: ActionReference | None = None
    ephemeral_secret: OperationEphemeralSecretDeclaration | None = None
    transient_financial_operands: tuple[OperationTransientFinancialOperandDeclaration, ...] = ()

    @field_validator("phase_codes")
    @classmethod
    def _canonical_phase_codes(cls, value: tuple[OperationEventCode, ...]) -> tuple[OperationEventCode, ...]:
        if len(set(value)) != len(value):
            raise ValueError("operation definition phase codes must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _validate_factory_request_type(self) -> OperationDefinition:
        if self.executor_factory.request_type is not self.request_type:
            raise ValueError("operation executor factory request type must match the definition request type")
        self._validate_request_storage()
        self._validate_ephemeral_secret()
        self._validate_transient_financial_operands()
        if (
            self.capabilities.durability is not OperationDurability.EPHEMERAL
            and OperationEffect.UNKNOWN not in self.capabilities.permitted_effects
        ):
            raise ValueError("operation definition must permit unknown effect for owner-loss reconciliation")
        if self.reconciliation_policy is OperationReconciliationPolicy.RESUME_FROM_CHECKPOINT:
            if self.capabilities.durability is not OperationDurability.RESUMABLE:
                raise ValueError("checkpoint reconciliation requires resumable durability")
            if not self.interaction_kinds:
                raise ValueError("checkpoint reconciliation requires a declared interaction checkpoint")
            if not issubclass(self.executor_factory.executor_type, OperationResumableExecutor):
                raise ValueError("checkpoint reconciliation requires a resumable executor")
        return self

    def _validate_request_storage(self) -> None:
        if self.capabilities.request_storage is not OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL:
            return
        if not issubclass(self.request_type, CredentialFreeOperationRequest):
            raise ValueError(
                "credential-free journal request type must explicitly inherit CredentialFreeOperationRequest"
            )
        schema = _strict_model_json_schema(self.request_type)
        _validate_credential_free_schema(schema)

    def _validate_ephemeral_secret(self) -> None:
        if self.ephemeral_secret is None:
            return
        if self.capabilities.durability is not OperationDurability.RECORDED:
            raise ValueError("ephemeral secret operations require recorded durability")
        if self.reconciliation_policy is not OperationReconciliationPolicy.INTERRUPT:
            raise ValueError("ephemeral secret operations cannot resume after owner loss")
        if OperationEffect.NONE not in self.capabilities.permitted_effects:
            raise ValueError("ephemeral secret operations must permit a pre-entry none effect")

    def _validate_transient_financial_operands(self) -> None:
        """Refuse an operand declaration the runtime could not honour.

        An operand lives only in the memory of the process that received it, so
        a definition that expects to resume after owner loss is declaring
        something custody cannot deliver: the restart would have to invent the
        amount or the acknowledgement.
        """
        if not self.transient_financial_operands:
            return
        kinds = [declaration.operand_kind for declaration in self.transient_financial_operands]
        if len(set(kinds)) != len(kinds):
            raise ValueError("operation definition cannot declare one financial operand kind twice")
        if self.capabilities.durability is not OperationDurability.RECORDED:
            raise ValueError("transient financial operand operations require recorded durability")
        if self.reconciliation_policy is not OperationReconciliationPolicy.INTERRUPT:
            raise ValueError("transient financial operand operations cannot resume after owner loss")
        if OperationInteractionKind.INPUT not in self.interaction_kinds:
            raise ValueError("transient financial operand operations must declare an input interaction")
        if OperationEffect.UNKNOWN not in self.capabilities.permitted_effects:
            raise ValueError("transient financial operand operations must permit an uncertain-delivery effect")


class OperationEffectReceipt(BaseModel):
    """What committed evidence lets an operation claim about its own effect.

    A claim is narrowed, never widened. An executor that reports it changed
    nothing is believed; one that reports a mutation is held to the evidence
    the application actually committed, because an operation interrupted
    mid-flight cannot know on its own whether its write landed.
    """

    model_config = STRICT_FROZEN_CONFIG

    definition_id: OperationDefinitionId
    effect: OperationEffect
    interrupted: bool
    narrowed_from: OperationEffect | None = None

    @model_validator(mode="after")
    def _validate_narrowing(self) -> OperationEffectReceipt:
        if self.narrowed_from is not None and self.narrowed_from is self.effect:
            raise ValueError("an effect receipt records a narrowing only when the claim actually changed")
        return self


def resolve_effect_receipt(
    definition: OperationDefinition,
    *,
    claimed_effect: OperationEffect,
    committed_evidence: bool,
    custody: OperationFinancialOperandCustodyCheckpoint | None = None,
) -> OperationEffectReceipt:
    """Narrow one recorded effect claim against committed application evidence.

    ``committed_evidence`` is whether the application durably recorded the
    mutation this operation claims. Without it an ``UPDATED`` or ``PARTIAL``
    claim narrows to ``UNKNOWN``: the operation may well have succeeded, and
    saying so without evidence is exactly the over-claim that makes a later
    reconciliation trust a write that never landed.

    ``custody`` carries the operand wait, if the operation had one. Only its
    crash classification is read - never any operand material, which the
    checkpoint does not hold in the first place. A wait whose delivery is
    uncertain cannot support a definite effect claim.
    """
    if claimed_effect not in definition.capabilities.permitted_effects:
        raise ValueError(f"operation {definition.definition_id!r} may not claim effect {claimed_effect.value!r}")
    interrupted = custody is not None and (
        custody.crash_classification is OperationFinancialOperandCrashClassification.DELIVERY_UNCERTAIN
    )
    definite = claimed_effect in {OperationEffect.UPDATED, OperationEffect.PARTIAL}
    if definite and (not committed_evidence or interrupted):
        return OperationEffectReceipt(
            definition_id=definition.definition_id,
            effect=OperationEffect.UNKNOWN,
            interrupted=interrupted,
            narrowed_from=claimed_effect,
        )
    return OperationEffectReceipt(
        definition_id=definition.definition_id,
        effect=claimed_effect,
        interrupted=interrupted,
    )


class _PublicDefinitionContractValues(TypedDict):
    definition_id: OperationDefinitionId
    action_reference: ActionReference | None
    request_schema: OperationSchemaIdentityV1
    result_schema: OperationSchemaIdentityV1 | None
    review_projection_schema: OperationSchemaIdentityV1 | None
    interaction_response_schema: OperationSchemaIdentityV1 | None
    workspace_refresh_target_schema: OperationSchemaIdentityV1 | None
    interaction_kinds: frozenset[OperationInteractionKind]
    request_storage: OperationRequestStoragePolicy
    durability: OperationDurability
    cancellation: OperationCancellation
    deadline: OperationDeadline
    replay: OperationReplayPolicy
    baseline: OperationBaselinePolicy
    sensitive_input: OperationSensitiveInputPolicy
    conflict_scope: OperationConflictScope
    owned_resources: frozenset[OperationOwnedResource]
    permitted_effects: frozenset[OperationEffect]
    close_policy: OperationClosePolicy
    reconciliation_policy: OperationReconciliationPolicy
    permitted_frontends: frozenset[OperationFrontendProjection]
    ephemeral_secret_required: bool


class OperationSchemaBindingV1(BaseModel):
    """Runtime-only binding from a public schema identity to its exact model."""

    model_config = _STRICT_RUNTIME_BINDING_CONFIG

    identity: OperationSchemaIdentityV1
    model_type: type[BaseModel]

    @model_validator(mode="after")
    def _validate_fingerprint(self) -> OperationSchemaBindingV1:
        schema = _strict_model_json_schema(self.model_type)
        fingerprint = content_hash_hex(schema)
        if fingerprint != self.identity.schema_fingerprint:
            raise ValueError("registered operation schema fingerprint does not match its exact model")
        return self

    @classmethod
    def bind(
        cls,
        *,
        schema_id: OperationPublicSchemaId,
        schema_version: int,
        model_type: type[BaseModel],
    ) -> OperationSchemaBindingV1:
        """Bind one stable identity to the model that produces its fingerprint."""
        return cls(
            identity=OperationSchemaIdentityV1.from_model(
                schema_id=schema_id,
                schema_version=schema_version,
                model_type=model_type,
            ),
            model_type=model_type,
        )


@runtime_checkable
class OperationReviewProjector(Protocol):
    """Domain-owned, side-effect-free safe REVIEW projection contract."""

    def __call__(
        self,
        reviewed_operand: BaseModel,
        interaction_facts: OperationInteractionRequest,
        /,
    ) -> BaseModel:
        """Project one resolved operand and its current interaction facts."""
        ...


@runtime_checkable
class OperationWorkspaceRefreshAdapter(Protocol):
    """Domain-owned adapter from safe terminal facts to a refresh target."""

    def __call__(self, terminal_receipt: OperationTerminalReceipt, /) -> BaseModel:
        """Return the typed target derived from one settled receipt."""
        ...


@runtime_checkable
class OperationResultProjector(Protocol):
    """Domain-owned, side-effect-free safe settled-result projection contract.

    Symmetric with :class:`OperationReviewProjector`: the resolver reloads the
    private settled result behind the secure application port and hands it,
    plus the safe terminal receipt, to this projector -- never the reverse.
    Registered only when the public result schema is a distinct projection of
    the definition's private result type; a result schema identical to that
    private type declares no projector.
    """

    def __call__(self, result: BaseModel, terminal_receipt: OperationTerminalReceipt, /) -> BaseModel:
        """Project one resolved settled result and its safe terminal receipt."""
        ...


class OperationPublicDefinitionRegistrationV1(BaseModel):
    """Live models and adapters bound to one serializable public contract."""

    model_config = _STRICT_RUNTIME_BINDING_CONFIG

    contract: OperationPublicDefinitionContractV1
    schema_bindings: tuple[OperationSchemaBindingV1, ...] = Field(min_length=1)
    reviewed_operand_type: type[BaseModel] | None = None
    review_projector: OperationReviewProjector | None = None
    workspace_refresh_adapter: OperationWorkspaceRefreshAdapter | None = None
    result_projector: OperationResultProjector | None = None

    @field_validator("schema_bindings")
    @classmethod
    def _unique_schema_bindings(
        cls,
        value: tuple[OperationSchemaBindingV1, ...],
    ) -> tuple[OperationSchemaBindingV1, ...]:
        keys = tuple((binding.identity.schema_id, binding.identity.schema_version) for binding in value)
        if len(set(keys)) != len(keys):
            raise ValueError("registered operation schema identities must be unique")
        return tuple(sorted(value, key=lambda item: (item.identity.schema_id, item.identity.schema_version)))

    @model_validator(mode="after")
    def _validate_adapter_signatures(self) -> OperationPublicDefinitionRegistrationV1:
        if self.review_projector is not None:
            _require_positional_callable_signature(self.review_projector, arity=2, label="REVIEW projector")
        if self.workspace_refresh_adapter is not None:
            _require_positional_callable_signature(
                self.workspace_refresh_adapter,
                arity=1,
                label="Workspace refresh adapter",
            )
        return self

    @classmethod
    def compose_request_only(
        cls,
        *,
        definition: OperationDefinition,
        request_schema_id: OperationPublicSchemaId,
        request_schema_version: int = 1,
    ) -> OperationPublicDefinitionRegistrationV1:
        """Bind the common operation shape with no public result or projection."""
        return cls.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=request_schema_id,
                schema_version=request_schema_version,
                model_type=definition.request_type,
            ),
        )

    @classmethod
    def compose(
        cls,
        *,
        definition: OperationDefinition,
        request_schema: OperationSchemaBindingV1,
        result_schema: OperationSchemaBindingV1 | None = None,
        review_projection_schema: OperationSchemaBindingV1 | None = None,
        interaction_response_schema: OperationSchemaBindingV1 | None = None,
        workspace_refresh_target_schema: OperationSchemaBindingV1 | None = None,
        reviewed_operand_type: type[BaseModel] | None = None,
        review_projector: OperationReviewProjector | None = None,
        workspace_refresh_adapter: OperationWorkspaceRefreshAdapter | None = None,
        result_projector: OperationResultProjector | None = None,
    ) -> OperationPublicDefinitionRegistrationV1:
        """Compose a manifest and its runtime-only bindings from one definition."""
        bindings = tuple(
            binding
            for binding in (
                request_schema,
                result_schema,
                review_projection_schema,
                interaction_response_schema,
                workspace_refresh_target_schema,
            )
            if binding is not None
        )
        contract = _public_contract_for_definition(
            definition,
            request_schema=request_schema.identity,
            result_schema=result_schema.identity if result_schema is not None else None,
            review_projection_schema=(
                review_projection_schema.identity if review_projection_schema is not None else None
            ),
            interaction_response_schema=(
                interaction_response_schema.identity if interaction_response_schema is not None else None
            ),
            workspace_refresh_target_schema=(
                workspace_refresh_target_schema.identity if workspace_refresh_target_schema is not None else None
            ),
        )
        return cls(
            contract=contract,
            schema_bindings=bindings,
            reviewed_operand_type=reviewed_operand_type,
            review_projector=review_projector,
            workspace_refresh_adapter=workspace_refresh_adapter,
            result_projector=result_projector,
        )


class OperationRegistry(BaseModel):
    """Deterministic definition registry with fail-closed immutable lookup."""

    model_config = STRICT_FROZEN_CONFIG

    definitions: tuple[OperationDefinition, ...] = Field(min_length=1)
    public_registrations: tuple[OperationPublicDefinitionRegistrationV1, ...] = ()

    @field_validator("definitions")
    @classmethod
    def _canonical_definitions(cls, value: tuple[OperationDefinition, ...]) -> tuple[OperationDefinition, ...]:
        definition_ids = tuple(item.definition_id for item in value)
        if len(set(definition_ids)) != len(definition_ids):
            raise ValueError("operation definition IDs must be unique")
        action_ids = tuple(item.action_reference.action_id for item in value if item.action_reference is not None)
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("operator action references must map to at most one operation definition")
        return tuple(sorted(value, key=lambda item: item.definition_id))

    @model_validator(mode="after")
    def _validate_public_fixed_point(self) -> OperationRegistry:
        if not self.public_registrations:
            return self
        registrations = tuple(sorted(self.public_registrations, key=lambda item: item.contract.definition_id))
        if registrations != self.public_registrations:
            raise ValueError("public operation registrations must be sorted by definition ID")
        definition_ids = tuple(definition.definition_id for definition in self.definitions)
        registration_ids = tuple(registration.contract.definition_id for registration in registrations)
        if registration_ids != definition_ids:
            raise ValueError("public operation registrations must exactly cover the immutable registry")
        seen_schema_identities: dict[tuple[str, int], tuple[ContentDigest, type[BaseModel]]] = {}
        contracts: list[OperationPublicDefinitionContractV1] = []
        for definition, registration in zip(self.definitions, registrations, strict=True):
            self._validate_public_registration(definition, registration)
            contracts.append(registration.contract)
            for binding in registration.schema_bindings:
                key = (binding.identity.schema_id, binding.identity.schema_version)
                current = (binding.identity.schema_fingerprint, binding.model_type)
                existing = seen_schema_identities.setdefault(key, current)
                if existing != current:
                    raise ValueError("one operation schema identity must bind one exact model and fingerprint")
        OperationPublicContractSetV1.build(tuple(contracts))
        return self

    @staticmethod
    def _validate_public_registration(
        definition: OperationDefinition,
        registration: OperationPublicDefinitionRegistrationV1,
    ) -> None:
        contract = registration.contract
        bindings = {
            _schema_identity_key(binding.identity): binding.model_type for binding in registration.schema_bindings
        }
        declared_identities = {
            _schema_identity_key(identity)
            for identity in (
                contract.request_schema,
                contract.result_schema,
                contract.review_projection_schema,
                contract.interaction_response_schema,
                contract.workspace_refresh_target_schema,
            )
            if identity is not None
        }
        if set(bindings) != declared_identities:
            raise ValueError("public operation schema bindings must exactly match the declared manifest")
        if bindings[_schema_identity_key(contract.request_schema)] is not definition.request_type:
            raise ValueError("public operation request schema must bind the definition request type")
        if definition.result_type is None:
            if contract.result_schema is not None:
                raise ValueError("result-less operation definition cannot declare a public result schema")
            if registration.result_projector is not None:
                raise ValueError("result-less operation definition cannot declare a result projector")
        elif contract.result_schema is not None:
            bound_result_type = bindings[_schema_identity_key(contract.result_schema)]
            distinct_result_projection = bound_result_type is not definition.result_type
            if distinct_result_projection != (registration.result_projector is not None):
                raise ValueError(
                    "a public result schema distinct from the definition result type requires one registered "
                    "result projector, and one identical to it must not declare one"
                )
        elif registration.result_projector is not None:
            raise ValueError("a result projector requires a declared public result schema")
        if registration.result_projector is not None:
            _require_positional_callable_signature(
                registration.result_projector,
                arity=2,
                label="result projector",
            )
        declares_review = OperationInteractionKind.REVIEW in definition.interaction_kinds
        if declares_review != (contract.review_projection_schema is not None):
            raise ValueError("REVIEW operation definitions require one public review schema")
        if declares_review != (registration.review_projector is not None):
            raise ValueError("REVIEW operation definitions require one registered review projector")
        if declares_review != (registration.reviewed_operand_type is not None):
            raise ValueError("REVIEW operation definitions require one registered reviewed operand type")
        if registration.reviewed_operand_type is not None:
            require_strict_frozen_operation_model_graph(
                registration.reviewed_operand_type,
                path="reviewed operand",
                reject_mutable_annotations=True,
                require_validated_defaults=True,
            )
        if registration.review_projector is not None:
            _require_positional_callable_signature(
                registration.review_projector,
                arity=2,
                label="REVIEW projector",
            )
        declares_refresh = contract.workspace_refresh_target_schema is not None
        if declares_refresh != (registration.workspace_refresh_adapter is not None):
            raise ValueError("Workspace refresh schema and adapter must be declared together")
        if registration.workspace_refresh_adapter is not None:
            _require_positional_callable_signature(
                registration.workspace_refresh_adapter,
                arity=1,
                label="Workspace refresh adapter",
            )
        expected = _public_contract_for_definition(
            definition,
            request_schema=contract.request_schema,
            result_schema=contract.result_schema,
            review_projection_schema=contract.review_projection_schema,
            interaction_response_schema=contract.interaction_response_schema,
            workspace_refresh_target_schema=contract.workspace_refresh_target_schema,
        )
        if expected != contract:
            raise ValueError("public operation definition contract is not a live-registry fixed point")

    @property
    def public_contract_set(self) -> OperationPublicContractSetV1:
        """Return the validated public set; refuse an uncomposed internal registry."""
        if not self.public_registrations:
            raise RuntimeError("operation registry has no public contract composition")
        return OperationPublicContractSetV1.build(
            tuple(registration.contract for registration in self.public_registrations),
        )

    def lookup(self, definition_id: str) -> OperationDefinition:
        """Return the exact registered definition or fail closed."""
        for definition in self.definitions:
            if definition.definition_id == definition_id:
                return definition
        raise KeyError(f"unknown operation definition ID: {definition_id!r}")

    def lookup_public_contract(self, definition_id: str) -> OperationPublicDefinitionContractV1:
        """Return the exact live public contract or refuse incomplete composition."""
        for registration in self.public_registrations:
            if registration.contract.definition_id == definition_id:
                return registration.contract
        raise KeyError(f"operation definition has no public contract: {definition_id!r}")

    def lookup_public_registration(self, definition_id: str) -> OperationPublicDefinitionRegistrationV1:
        """Return the sole runtime binding for one public operation definition."""
        for registration in self.public_registrations:
            if registration.contract.definition_id == definition_id:
                return registration
        raise KeyError(f"operation definition has no public registration: {definition_id!r}")

    def lookup_public_schema_binding(self, identity: OperationSchemaIdentityV1) -> OperationSchemaBindingV1:
        """Resolve one exact schema identity without accepting an ID-only match."""
        for registration in self.public_registrations:
            for binding in registration.schema_bindings:
                if binding.identity == identity:
                    return binding
        raise KeyError(
            "operation public schema identity is not registered: "
            f"{identity.schema_id!r} version {identity.schema_version}"
        )

    def lookup_action(self, action: ActionReference) -> OperationDefinition:
        """Resolve an optional canonical action join without owning its catalogue."""
        for definition in self.definitions:
            if definition.action_reference == action:
                return definition
        raise KeyError(f"operator action is not mapped to an operation definition: {action.action_id!r}")

    def resolve_request_json(self, raw: str | bytes) -> OperationRequest[BaseModel]:
        """Hydrate one request through the concrete model registered for its definition."""
        header = _OperationRequestResolutionHeader.model_validate_json(raw)
        request_type = self.lookup(header.definition_id).request_type
        return _specialize_request_model(request_type).model_validate_json(raw)

    def resolve_snapshot_json(self, raw: str | bytes) -> OperationSnapshot[BaseModel]:
        """Hydrate one snapshot through the concrete model registered for its definition."""
        header = _OperationSnapshotResolutionHeader.model_validate_json(raw)
        request_type = self.lookup(header.identity.definition_id).request_type
        return _specialize_snapshot_model(request_type).model_validate_json(raw)

    def resolve_credential_free_payload(self, definition_id: str, raw: str | bytes) -> BaseModel:
        """Hydrate a journal-safe payload only for its exact registered definition."""
        definition = self.lookup(definition_id)
        if definition.capabilities.request_storage is not OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL:
            raise ValueError("operation definition does not use credential-free journal request storage")
        return definition.request_type.model_validate_json(raw)


_HEX64_DIGEST_PATTERN = "^[0-9a-f]{64}$"


def _is_hex64_shaped_schema(value: object) -> bool:
    """Report whether one field's JSON-schema fragment matches the Hex64Str/ContentDigest shape.

    ``ContentDigest`` is a bare assignment to ``Hex64Str`` (``ContentDigest
    is Hex64Str``), not a distinct type, and ``Hex64Str`` is deliberately
    shared by several unrelated concepts (``WorkUnitId``,
    ``CalculationRevisionId``, ``SnapshotId``, ``TransactionId``). There is
    therefore no runtime type-identity test for "declared as
    ``ContentDigest`` specifically" - only a SHAPE test for "64 lowercase
    hex characters", which every one of those sibling concepts also
    satisfies. Recurses through ``anyOf`` (an ``X | None`` field) and
    ``items`` (a ``tuple[X, ...]`` field) to reach the underlying string
    schema.
    """
    if not isinstance(value, dict):
        return False
    mapping = cast(dict[str, object], value)
    if (
        mapping.get("type") == "string"
        and mapping.get("pattern") == _HEX64_DIGEST_PATTERN
        and mapping.get("minLength") == 64
        and mapping.get("maxLength") == 64
    ):
        return True
    any_of = mapping.get("anyOf")
    if isinstance(any_of, list):
        return any(
            _is_hex64_shaped_schema(cast(dict[str, object], item))
            for item in cast(list[object], any_of)
            if isinstance(item, dict) and cast(dict[str, object], item).get("type") != "null"
        )
    items = mapping.get("items")
    if isinstance(items, dict):
        return _is_hex64_shaped_schema(cast(dict[str, object], items))
    return False


def _validate_credential_free_schema(schema: object) -> None:
    """Reject request schemas capable of carrying credentials or opaque transports.

    A field name matching ONLY the ``digest`` forbidden token (no other
    forbidden token also matches) is admitted when its schema shape is
    exactly Hex64 - a compare-and-swap content digest, never a bearer token
    or passphrase by shape. A field matching any OTHER forbidden token is
    refused regardless of shape, and regardless of whether it also matches
    ``digest``; the exemption never widens any token but ``digest`` and
    never overrides a second, independently-matched forbidden token on the
    same field. See ``2026-08-27-tui-architecture-credential-free-type-aware-gate-adr``
    for the residual risk this accepts: a Hex64-shaped field declared as one
    of ``ContentDigest``'s shape-sharing siblings, named ``*_digest``, is
    also admitted by this rule.
    """
    if isinstance(schema, list):
        for item in cast(list[object], schema):
            _validate_credential_free_schema(item)
        return
    if not isinstance(schema, dict):
        return
    mapping = cast(dict[str, object], schema)
    schema_format = mapping.get("format")
    if schema_format in _FORBIDDEN_OPERATION_SCHEMA_FORMATS:
        raise ValueError("credential-free journal request schema contains a secret-capable format")
    properties = mapping.get("properties")
    if isinstance(properties, dict):
        for field_name, field_schema in cast(dict[str, object], properties).items():
            parts = set(field_name.lower().replace("-", "_").split("_"))
            matched = parts & _FORBIDDEN_CREDENTIAL_FREE_FIELD_PARTS
            if not matched:
                continue
            if matched == {"digest"} and _is_hex64_shaped_schema(field_schema):
                continue
            raise ValueError(f"credential-free journal request field {field_name!r} has a forbidden security meaning")
    for value in mapping.values():
        _validate_credential_free_schema(value)


def _strict_model_json_schema(model_type: type[BaseModel]) -> dict[str, object]:
    """Return one exact closed schema after enforcing the public model baseline."""
    require_strict_frozen_operation_model_graph(model_type, path="public schema")
    try:
        validation_schema = model_type.model_json_schema(mode="validation")
        serialization_schema = model_type.model_json_schema(mode="serialization")
    except PydanticInvalidForJsonSchema as error:
        raise ValueError("public operation schema model must have a closed JSON schema") from error
    if validation_schema != serialization_schema:
        raise ValueError("public operation schema validation and serialization shapes must be identical")
    closed_schema = cast(dict[str, object], validation_schema)
    _validate_closed_json_schema(closed_schema, path=model_type.__name__)
    return closed_schema


def _validate_closed_json_schema(schema: dict[str, object], *, path: str) -> None:
    """Refuse every untyped or open branch of one generated public schema."""
    if schema.get("format") in _FORBIDDEN_OPERATION_SCHEMA_FORMATS or schema.get("writeOnly") is True:
        raise ValueError(f"public operation schema {path} contains a secret-capable branch")
    definitions = schema.get("$defs")
    if isinstance(definitions, dict):
        for definition_name, definition in cast(dict[str, object], definitions).items():
            if not isinstance(definition, dict):
                raise ValueError(f"public operation schema {path} has an invalid definition")
            _validate_closed_json_schema(
                cast(dict[str, object], definition),
                path=f"{path}.$defs.{definition_name}",
            )
    if schema.get("patternProperties") is not None:
        raise ValueError(f"public operation schema {path} contains a pattern-properties payload bag")
    if "$ref" in schema or "enum" in schema or "const" in schema:
        return
    for combinator in ("anyOf", "oneOf", "allOf"):
        branches = schema.get(combinator)
        if branches is None:
            continue
        if not isinstance(branches, list) or not branches:
            raise ValueError(f"public operation schema {path} has an invalid {combinator}")
        for index, branch in enumerate(cast(list[object], branches)):
            if not isinstance(branch, dict):
                raise ValueError(f"public operation schema {path} has an invalid {combinator} branch")
            _validate_closed_json_schema(
                cast(dict[str, object], branch),
                path=f"{path}.{combinator}[{index}]",
            )
        return
    schema_type = schema.get("type")
    if not isinstance(schema_type, str):
        raise ValueError(f"public operation schema {path} contains an untyped branch")
    if schema_type == "object":
        if schema.get("additionalProperties") is not False:
            raise ValueError(f"public operation schema {path} contains an open object branch")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"public operation schema {path} has invalid properties")
        for field_name, field_schema in cast(dict[str, object], properties).items():
            if not isinstance(field_schema, dict):
                raise ValueError(f"public operation schema {path}.{field_name} is invalid")
            _validate_closed_json_schema(
                cast(dict[str, object], field_schema),
                path=f"{path}.{field_name}",
            )
    elif schema_type == "array":
        prefix_items = schema.get("prefixItems")
        if prefix_items is not None:
            if not isinstance(prefix_items, list) or not prefix_items:
                raise ValueError(f"public operation schema {path} has invalid fixed tuple items")
            typed_prefix_items = cast(list[object], prefix_items)
            item_count = len(typed_prefix_items)
            if schema.get("minItems") != item_count or schema.get("maxItems") != item_count:
                raise ValueError(f"public operation schema {path} contains an open fixed tuple")
            trailing_items = schema.get("items")
            if trailing_items is not None and trailing_items is not False:
                raise ValueError(f"public operation schema {path} permits undeclared trailing tuple items")
            for index, item in enumerate(typed_prefix_items):
                if not isinstance(item, dict):
                    raise ValueError(f"public operation schema {path} has an invalid fixed tuple item")
                _validate_closed_json_schema(
                    cast(dict[str, object], item),
                    path=f"{path}.prefixItems[{index}]",
                )
            return
        items = schema.get("items")
        if not isinstance(items, dict):
            raise ValueError(f"public operation schema {path} contains an untyped array")
        _validate_closed_json_schema(cast(dict[str, object], items), path=f"{path}.items")


def _definition_contract_digest(contract: OperationPublicDefinitionContractV1) -> ContentDigest:
    return content_hash_hex(_definition_contract_value(contract, include_digest=False))


def _contract_set_digest(
    definitions: tuple[OperationPublicDefinitionContractV1, ...],
) -> ContentDigest:
    payload = {
        "contract_set_version": 1,
        "definitions": [_definition_contract_value(definition, include_digest=True) for definition in definitions],
    }
    return content_hash_hex(payload)


def _schema_identity_key(identity: OperationSchemaIdentityV1) -> tuple[str, int, ContentDigest]:
    return identity.schema_id, identity.schema_version, identity.schema_fingerprint


def operation_public_schema_reference(identity: OperationSchemaIdentityV1) -> str:
    """Return the canonical internal reference for one registered public schema."""
    return f"schema:{identity.schema_id}.v{identity.schema_version}"


def _definition_contract_value(
    contract: OperationPublicDefinitionContractV1,
    *,
    include_digest: bool,
) -> dict[str, object]:
    """Return the explicitly ordered, JSON-safe value governed by the digest."""
    payload: dict[str, object] = {
        "manifest_version": contract.manifest_version,
        "definition_id": contract.definition_id,
        "action_reference": (
            None if contract.action_reference is None else contract.action_reference.model_dump(mode="json")
        ),
        "request_schema": contract.request_schema.model_dump(mode="json"),
        "result_schema": None if contract.result_schema is None else contract.result_schema.model_dump(mode="json"),
        "review_projection_schema": (
            None
            if contract.review_projection_schema is None
            else contract.review_projection_schema.model_dump(mode="json")
        ),
        "interaction_response_schema": (
            None
            if contract.interaction_response_schema is None
            else contract.interaction_response_schema.model_dump(mode="json")
        ),
        "workspace_refresh_target_schema": (
            None
            if contract.workspace_refresh_target_schema is None
            else contract.workspace_refresh_target_schema.model_dump(mode="json")
        ),
        "interaction_kinds": tuple(sorted(item.value for item in contract.interaction_kinds)),
        "request_storage": contract.request_storage.value,
        "durability": contract.durability.value,
        "cancellation": contract.cancellation.value,
        "deadline": contract.deadline.value,
        "replay": contract.replay.value,
        "baseline": contract.baseline.value,
        "sensitive_input": contract.sensitive_input.value,
        "conflict_scope": contract.conflict_scope.value,
        "owned_resources": tuple(sorted(item.value for item in contract.owned_resources)),
        "permitted_effects": tuple(sorted(item.value for item in contract.permitted_effects)),
        "close_policy": contract.close_policy.value,
        "reconciliation_policy": contract.reconciliation_policy.value,
        "permitted_frontends": tuple(sorted(item.value for item in contract.permitted_frontends)),
        "ephemeral_secret_required": contract.ephemeral_secret_required,
    }
    if include_digest:
        payload["definition_contract_digest"] = contract.definition_contract_digest
    return payload


def _require_positional_callable_signature(
    callable_value: Callable[..., object],
    *,
    arity: int,
    label: str,
) -> None:
    if inspect.iscoroutinefunction(callable_value) or inspect.iscoroutinefunction(type(callable_value).__call__):
        raise ValueError(f"operation {label} must be synchronous")
    try:
        signature = inspect.signature(callable_value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"operation {label} must expose an inspectable signature") from error
    parameters = tuple(signature.parameters.values())
    positional_kinds = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(parameters) != arity or any(parameter.kind not in positional_kinds for parameter in parameters):
        raise ValueError(f"operation {label} must accept exactly {arity} positional arguments")


def _public_contract_for_definition(
    definition: OperationDefinition,
    *,
    request_schema: OperationSchemaIdentityV1,
    result_schema: OperationSchemaIdentityV1 | None,
    review_projection_schema: OperationSchemaIdentityV1 | None,
    interaction_response_schema: OperationSchemaIdentityV1 | None,
    workspace_refresh_target_schema: OperationSchemaIdentityV1 | None,
) -> OperationPublicDefinitionContractV1:
    capabilities = definition.capabilities
    values: _PublicDefinitionContractValues = {
        "definition_id": definition.definition_id,
        "action_reference": definition.action_reference,
        "request_schema": request_schema,
        "result_schema": result_schema,
        "review_projection_schema": review_projection_schema,
        "interaction_response_schema": interaction_response_schema,
        "workspace_refresh_target_schema": workspace_refresh_target_schema,
        "interaction_kinds": definition.interaction_kinds,
        "request_storage": capabilities.request_storage,
        "durability": capabilities.durability,
        "cancellation": capabilities.cancellation,
        "deadline": capabilities.deadline,
        "replay": capabilities.replay,
        "baseline": capabilities.baseline,
        "sensitive_input": capabilities.sensitive_input,
        "conflict_scope": capabilities.conflict_scope,
        "owned_resources": capabilities.owned_resources,
        "permitted_effects": capabilities.permitted_effects,
        "close_policy": capabilities.close_policy,
        "reconciliation_policy": definition.reconciliation_policy,
        "permitted_frontends": definition.permitted_frontends,
        "ephemeral_secret_required": definition.ephemeral_secret is not None,
    }
    provisional = OperationPublicDefinitionContractV1.model_construct(
        **values,
        definition_contract_digest=cast(ContentDigest, "0" * 64),
    )
    return OperationPublicDefinitionContractV1(
        **values,
        definition_contract_digest=_definition_contract_digest(provisional),
    )


OperationPublicDefinitionContractV1.model_rebuild()


__all__ = [
    "OperationDefinition",
    "OperationEffectReceipt",
    "OperationExecutorFactory",
    "OperationFrontendProjection",
    "OperationPublicContractSetV1",
    "OperationPublicDefinitionContractV1",
    "OperationPublicDefinitionRegistrationV1",
    "OperationPublicSchemaId",
    "OperationReconciliationPolicy",
    "OperationRegistry",
    "OperationResultProjector",
    "OperationReviewProjector",
    "OperationSchemaBindingV1",
    "OperationSchemaIdentityV1",
    "OperationWorkspaceRefreshAdapter",
    "operation_public_schema_reference",
    "resolve_effect_receipt",
]
