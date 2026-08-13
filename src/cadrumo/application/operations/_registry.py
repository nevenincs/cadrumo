"""Immutable registry for application-owned operation definitions."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, OperationInteractionKind
from ..operator_actions import ActionReference
from ._capabilities import OperationCapabilities
from ._events import OperationEventCode
from ._executor import OperationExecutor
from ._models import OperationDefinitionId


class OperationReconciliationPolicy(StrEnum):
    """Closed owner-loss behavior declared by an operation definition."""

    INTERRUPT = "interrupt"
    RESUME_FROM_CHECKPOINT = "resume_from_checkpoint"


class OperationFrontendProjection(StrEnum):
    """Frontend-neutral identities of permitted operation projections."""

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
        action_ids = tuple(
            item.action_reference.action_id for item in value if item.action_reference is not None
        )
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


__all__ = [
    "OperationDefinition",
    "OperationExecutorFactory",
    "OperationFrontendProjection",
    "OperationReconciliationPolicy",
    "OperationRegistry",
]
