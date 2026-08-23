"""Immutable registry for application-owned operation definitions."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, OperationDurability, OperationEffect, OperationInteractionKind
from ..operator_actions import ActionReference
from ._capabilities import OperationCapabilities
from ._events import OperationEventCode
from ._executor import OperationExecutor, OperationResumableExecutor
from ._models import OperationDefinitionId, OperationIdentity, OperationRequest, OperationSnapshot


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


class OperationRegistry(BaseModel):
    """Deterministic definition registry with fail-closed immutable lookup."""

    model_config = STRICT_FROZEN_CONFIG

    definitions: tuple[OperationDefinition, ...] = Field(min_length=1)

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

    def lookup(self, definition_id: str) -> OperationDefinition:
        """Return the exact registered definition or fail closed."""
        for definition in self.definitions:
            if definition.definition_id == definition_id:
                return definition
        raise KeyError(f"unknown operation definition ID: {definition_id!r}")

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


__all__ = [
    "OperationDefinition",
    "OperationExecutorFactory",
    "OperationFrontendProjection",
    "OperationReconciliationPolicy",
    "OperationRegistry",
]
