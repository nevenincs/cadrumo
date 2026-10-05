"""Immutable registry for application-owned operation definitions."""

from __future__ import annotations

import json
from enum import StrEnum
from functools import cached_property
from typing import Literal, Protocol, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    field_validator,
    model_validator,
)

from ...core.errors.hierarchy import InternalInvariantError, pydantic_validation_boundary
from ...core.hashing import canonical_json_bytes, content_hash_hex, reject_duplicate_json_members, reject_json_constant
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ..operator_actions.models import ActionReference
from ._registry_contracts import (
    build_public_contract as _build_public_contract,
)
from ._registry_contracts import (
    contract_set_digest as _contract_set_digest,
)
from ._registry_contracts import (
    definition_contract_digest as _definition_contract_digest,
)
from ._registry_contracts import (
    require_positional_callable_signature as _require_positional_callable_signature,
)
from ._registry_contracts import (
    validate_public_registration as _validate_public_registration,
)
from .access_port import OperationAccessResolver
from .capabilities import (
    OperationBaselinePolicy,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from .financial_operand_contract import OperationTransientFinancialOperandPublicDeclarationV1
from .interactions import OperationInteractionRequest
from .models import (
    OperationDefinitionId,
    OperationFailureErrorCode,
    OperationTerminalReceipt,
)
from .refusal_evidence import validate_refusal_code
from .registry_schema_validation import strict_model_json_schema
from .schema_identity import OperationPublicSchemaId, OperationSchemaIdentityV1

_STRICT_RUNTIME_BINDING_CONFIG = ConfigDict(
    strict=True,
    frozen=True,
    extra="forbid",
    arbitrary_types_allowed=True,
)


class OperationPublicDefinitionContractV1(BaseModel):
    """Renderer-neutral public manifest row for one operation definition."""

    model_config = STRICT_FROZEN_CONFIG

    manifest_version: Literal[2] = 2
    definition_id: OperationDefinitionId
    action_reference: ActionReference | None
    request_schema: OperationSchemaIdentityV1
    result_schema: OperationSchemaIdentityV1 | None
    refusal_detail_codes: frozenset[OperationFailureErrorCode]
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
    transient_financial_operand: OperationTransientFinancialOperandPublicDeclarationV1 | None = None
    definition_contract_digest: ContentDigest

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_digest(self) -> OperationPublicDefinitionContractV1:
        if self.refusal_detail_codes and self.result_schema is None:
            raise ValueError("refusal evidence requires a registered terminal projection schema")
        for code in self.refusal_detail_codes:
            validate_refusal_code(code)
        expected = _definition_contract_digest(self)
        if self.definition_contract_digest != expected:
            raise ValueError("operation definition contract digest does not reproduce")
        return self


class OperationPublicDefinitionDescriptionV1(BaseModel):
    """A registered request schema bound to the current public contract digest."""

    model_config = STRICT_FROZEN_CONFIG

    contract: OperationPublicDefinitionContractV1
    request_json_schema: dict[str, JsonValue]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_request_schema(self) -> OperationPublicDefinitionDescriptionV1:
        if content_hash_hex(self.request_json_schema) != self.contract.request_schema.schema_fingerprint:
            raise ValueError("operation request schema does not match its registered fingerprint")
        return self


class OperationPublicContractSetV1(BaseModel):
    """Canonical fixed-point inventory of all public operation contracts."""

    model_config = STRICT_FROZEN_CONFIG

    contract_set_version: Literal[1] = 1
    definitions: tuple[OperationPublicDefinitionContractV1, ...] = Field(min_length=1)
    contract_set_digest: ContentDigest

    @field_validator("definitions")
    @classmethod
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
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


class OperationReconciliationPolicy(StrEnum):
    """Closed owner-loss behavior declared by an operation definition."""

    INTERRUPT = "interrupt"
    RESUME_FROM_CHECKPOINT = "resume_from_checkpoint"


class OperationFrontendProjection(StrEnum):
    """Product-owned identities of permitted operation projections."""

    CLI = "cli"
    MCP = "mcp"
    TUI = "tui"


#: Every product frontend, for operations offered on all of them. Membership is
#: explicit so a new frontend is never granted to existing operations silently.
ALL_OPERATION_FRONTENDS: frozenset[OperationFrontendProjection] = frozenset(
    {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
)


from . import operation_definition as _operation_definition  # noqa: E402 — enums must exist before model binding

_operation_definition.OperationDefinition.model_rebuild(
    _types_namespace={
        "OperationFrontendProjection": OperationFrontendProjection,
        "OperationReconciliationPolicy": OperationReconciliationPolicy,
    }
)


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
    @pydantic_validation_boundary
    def _validate_narrowing(self) -> OperationEffectReceipt:
        if self.narrowed_from is not None and self.narrowed_from is self.effect:
            raise ValueError("an effect receipt records a narrowing only when the claim actually changed")
        return self


class OperationSchemaBindingV1(BaseModel):
    """Runtime-only binding from a public schema identity to its exact model."""

    model_config = _STRICT_RUNTIME_BINDING_CONFIG

    identity: OperationSchemaIdentityV1
    model_type: type[BaseModel]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_fingerprint(self) -> OperationSchemaBindingV1:
        schema = strict_model_json_schema(self.model_type)
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
        _interaction_facts: OperationInteractionRequest,
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
    access_resolver: OperationAccessResolver | None = None

    @field_validator("schema_bindings")
    @classmethod
    @pydantic_validation_boundary
    def _unique_schema_bindings(
        cls,
        value: tuple[OperationSchemaBindingV1, ...],
    ) -> tuple[OperationSchemaBindingV1, ...]:
        keys = tuple((binding.identity.schema_id, binding.identity.schema_version) for binding in value)
        if len(set(keys)) != len(keys):
            raise ValueError("registered operation schema identities must be unique")
        return tuple(sorted(value, key=lambda item: (item.identity.schema_id, item.identity.schema_version)))

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_adapter_signatures(self) -> OperationPublicDefinitionRegistrationV1:
        if self.access_resolver is not None:
            _require_positional_callable_signature(self.access_resolver, arity=2, label="Access resolver")
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
        definition: _operation_definition.OperationDefinition,
        request_schema_id: OperationPublicSchemaId,
        request_schema_version: int = 1,
        access_resolver: OperationAccessResolver | None = None,
    ) -> OperationPublicDefinitionRegistrationV1:
        """Bind the common operation shape with no public result or projection."""
        return cls.compose(
            definition=definition,
            access_resolver=access_resolver,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=request_schema_id,
                schema_version=request_schema_version,
                model_type=definition.request_type,
            ),
        )

    @classmethod
    def compose_request_result(
        cls,
        *,
        definition: _operation_definition.OperationDefinition,
        public_result_type: type[BaseModel],
        access_resolver: OperationAccessResolver,
        result_projector: OperationResultProjector | None = None,
        request_schema_version: int = 1,
    ) -> OperationPublicDefinitionRegistrationV1:
        """Bind the conventional version-1 ``<definition_id>.request`` and ``.result`` schemas.

        The request schema binds the definition's own request type. The result
        schema binds ``public_result_type``, which needs a ``result_projector``
        exactly when it differs from the definition's private result type. Any
        other schema identity or version is composed explicitly with ``compose``.
        """
        return cls.compose(
            definition=definition,
            request_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".request",
                schema_version=request_schema_version,
                model_type=definition.request_type,
            ),
            result_schema=OperationSchemaBindingV1.bind(
                schema_id=definition.definition_id + ".result",
                schema_version=1,
                model_type=public_result_type,
            ),
            result_projector=result_projector,
            access_resolver=access_resolver,
        )

    @classmethod
    def compose(
        cls,
        *,
        definition: _operation_definition.OperationDefinition,
        request_schema: OperationSchemaBindingV1,
        result_schema: OperationSchemaBindingV1 | None = None,
        review_projection_schema: OperationSchemaBindingV1 | None = None,
        interaction_response_schema: OperationSchemaBindingV1 | None = None,
        workspace_refresh_target_schema: OperationSchemaBindingV1 | None = None,
        reviewed_operand_type: type[BaseModel] | None = None,
        review_projector: OperationReviewProjector | None = None,
        workspace_refresh_adapter: OperationWorkspaceRefreshAdapter | None = None,
        result_projector: OperationResultProjector | None = None,
        access_resolver: OperationAccessResolver | None = None,
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
            access_resolver=access_resolver,
        )


class OperationRegistry(BaseModel):
    """Deterministic definition registry with fail-closed immutable lookup."""

    model_config = STRICT_FROZEN_CONFIG

    definitions: tuple[_operation_definition.OperationDefinition, ...] = Field(min_length=1)
    public_registrations: tuple[OperationPublicDefinitionRegistrationV1, ...] = ()

    @field_validator("definitions")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_definitions(
        cls, value: tuple[_operation_definition.OperationDefinition, ...]
    ) -> tuple[_operation_definition.OperationDefinition, ...]:
        definition_ids = tuple(item.definition_id for item in value)
        if len(set(definition_ids)) != len(definition_ids):
            raise ValueError("operation definition IDs must be unique")
        action_ids = tuple(item.action_reference.action_id for item in value if item.action_reference is not None)
        if len(set(action_ids)) != len(action_ids):
            raise ValueError("operator action references must map to at most one operation definition")
        return tuple(sorted(value, key=lambda item: item.definition_id))

    @model_validator(mode="after")
    @pydantic_validation_boundary
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
        definition: _operation_definition.OperationDefinition,
        registration: OperationPublicDefinitionRegistrationV1,
    ) -> None:
        _validate_public_registration(
            definition,
            registration,
            contract_builder=_public_contract_for_definition,
        )

    @cached_property
    def public_contract_set(self) -> OperationPublicContractSetV1:
        """Return the validated public set; refuse an uncomposed internal registry."""
        if not self.public_registrations:
            raise InternalInvariantError("operation registry has no public contract composition")
        return OperationPublicContractSetV1.build(
            tuple(registration.contract for registration in self.public_registrations),
        )

    def lookup(self, definition_id: str) -> _operation_definition.OperationDefinition:
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

    def describe_public_definition(self, definition_id: str) -> OperationPublicDefinitionDescriptionV1:
        """Describe the exact registered request model without constructing an executor."""
        contract = self.lookup_public_contract(definition_id)
        binding = self.lookup_public_schema_binding(contract.request_schema)
        return OperationPublicDefinitionDescriptionV1(
            contract=contract,
            request_json_schema=TypeAdapter(dict[str, JsonValue]).validate_python(
                strict_model_json_schema(binding.model_type), strict=True
            ),
        )

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

    def lookup_action(self, action: ActionReference) -> _operation_definition.OperationDefinition:
        """Resolve an optional canonical action join without owning its catalogue."""
        for definition in self.definitions:
            if definition.action_reference == action:
                return definition
        raise KeyError(f"operator action is not mapped to an operation definition: {action.action_id!r}")

    def resolve_credential_free_payload(self, definition_id: str, raw: str | bytes) -> BaseModel:
        """Hydrate a journal-safe payload only for its exact registered definition."""
        definition = self.lookup(definition_id)
        if definition.capabilities.request_storage is not OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL:
            raise ValueError("operation definition does not use credential-free journal request storage")
        return self.decode_request_payload(definition_id, raw)

    def decode_request_payload(self, definition_id: str, raw: str | bytes) -> BaseModel:
        """Decode exact registered operands, rejecting ambiguous nested JSON too."""
        definition = self.lookup(definition_id)
        value = json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
        return definition.request_type.model_validate_json(canonical_json_bytes(value))


def operation_public_schema_reference(identity: OperationSchemaIdentityV1) -> str:
    """Return the canonical internal reference for one registered public schema."""
    return f"schema:{identity.schema_id}.v{identity.schema_version}"


def _public_contract_for_definition(
    definition: _operation_definition.OperationDefinition,
    *,
    request_schema: OperationSchemaIdentityV1,
    result_schema: OperationSchemaIdentityV1 | None,
    review_projection_schema: OperationSchemaIdentityV1 | None,
    interaction_response_schema: OperationSchemaIdentityV1 | None,
    workspace_refresh_target_schema: OperationSchemaIdentityV1 | None,
) -> OperationPublicDefinitionContractV1:
    return _build_public_contract(
        contract_type=OperationPublicDefinitionContractV1,
        definition=definition,
        request_schema=request_schema,
        result_schema=result_schema,
        review_projection_schema=review_projection_schema,
        interaction_response_schema=interaction_response_schema,
        workspace_refresh_target_schema=workspace_refresh_target_schema,
    )


OperationPublicDefinitionContractV1.model_rebuild()


__all__ = [
    "ALL_OPERATION_FRONTENDS",
    "OperationEffectReceipt",
    "OperationFrontendProjection",
    "OperationPublicContractSetV1",
    "OperationPublicDefinitionContractV1",
    "OperationPublicDefinitionRegistrationV1",
    "OperationReconciliationPolicy",
    "OperationRegistry",
    "OperationResultProjector",
    "OperationReviewProjector",
    "OperationSchemaBindingV1",
    "OperationWorkspaceRefreshAdapter",
    "operation_public_schema_reference",
]
