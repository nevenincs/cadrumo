"""The generated operation-contract manifest and the registry that reads it.

Every registered operation's public contract -- its frontend-neutral shape,
schema identities and fingerprints -- is a pure function of its definition.
Computing it means importing the definition, its request and result models
and, through them, its handler. A process that only needs the contracts (a
sign-in's first screen, edit admission, the runtime's access policy) would
otherwise import every operation the product has.

The manifest is that function's output, generated from the real definitions
and shipped as package data. :class:`ManifestOperationRegistry` answers
contract questions from it and builds an operation's definition and handler
only when something needs them, one composition group at a time. A group is
admitted only when what it builds reproduces the manifest exactly, so a stale
manifest refuses rather than executing against contracts it does not describe.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import cache, cached_property
from threading import RLock
from typing import Literal, Self

from pydantic import BaseModel, Field, PrivateAttr, field_validator, model_validator

from ...core.errors.hierarchy import InternalInvariantError, pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.resources.bundled_data import packaged_data
from ..operator_actions.models import ActionReference
from ._registry_contracts import declared_public_schema_identities
from .operation_definition import OperationDefinition
from .registry import (
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationSchemaBindingV1,
)
from .schema_identity import OperationSchemaIdentityV1

#: Where the generated manifest ships, under ``cadrumo/_data``.
OPERATION_CONTRACT_MANIFEST_PARTS: tuple[str, ...] = ("operations", "contract_manifest.json")


@dataclass(frozen=True, slots=True)
class OperationGroupBuild:
    """The definitions and public registrations one composition group builds together."""

    definitions: tuple[OperationDefinition, ...]
    registrations: tuple[OperationPublicDefinitionRegistrationV1, ...]


#: Build one named composition group; the manifest names each operation's group.
OperationGroupBuilder = Callable[[str], OperationGroupBuild]


class OperationContractManifestEntryV1(BaseModel):
    """One registered operation: its contract and where its definition is composed."""

    model_config = STRICT_FROZEN_CONFIG

    group: str = Field(min_length=1)
    module: str = Field(min_length=1)
    ephemeral_secret_lifetime_seconds: float | None = Field(default=None, gt=0, le=3600)
    contract: OperationPublicDefinitionContractV1


class OperationContractManifestV1(BaseModel):
    """Every registered operation's contract, sorted by definition ID, with the set's digest."""

    model_config = STRICT_FROZEN_CONFIG

    manifest_version: Literal[1] = 1
    contract_set_digest: ContentDigest
    operations: tuple[OperationContractManifestEntryV1, ...] = Field(min_length=1)

    @field_validator("operations")
    @classmethod
    @pydantic_validation_boundary
    def _canonical_operations(
        cls, value: tuple[OperationContractManifestEntryV1, ...]
    ) -> tuple[OperationContractManifestEntryV1, ...]:
        identifiers = tuple(entry.contract.definition_id for entry in value)
        if identifiers != tuple(sorted(set(identifiers))):
            raise ValueError("manifest operations must be unique and sorted by definition ID")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_digest(self) -> OperationContractManifestV1:
        if self.contract_set.contract_set_digest != self.contract_set_digest:
            raise ValueError("operation contract manifest digest does not reproduce")
        return self

    @cached_property
    def contract_set(self) -> OperationPublicContractSetV1:
        """The canonical public contract set the manifest records."""
        return OperationPublicContractSetV1.build(tuple(entry.contract for entry in self.operations))

    @cached_property
    def entries(self) -> Mapping[str, OperationContractManifestEntryV1]:
        """Each entry by definition ID."""
        return {str(entry.contract.definition_id): entry for entry in self.operations}

    @cached_property
    def groups(self) -> Mapping[str, frozenset[str]]:
        """The definition IDs each composition group must build."""
        members: dict[str, set[str]] = {}
        for entry in self.operations:
            members.setdefault(entry.group, set()).add(str(entry.contract.definition_id))
        return {group: frozenset(ids) for group, ids in members.items()}

    @classmethod
    def from_registry(cls, registry: OperationRegistry, groups: Mapping[str, str]) -> Self:
        """Record an eagerly composed registry; ``groups`` names each definition's group."""
        entries: list[OperationContractManifestEntryV1] = []
        for definition in registry.definitions:
            lifetime = definition.ephemeral_secret.lifetime if definition.ephemeral_secret is not None else None
            entries.append(
                OperationContractManifestEntryV1(
                    group=groups[definition.definition_id],
                    module=definition.executor_factory.executor_type.__module__,
                    ephemeral_secret_lifetime_seconds=None if lifetime is None else lifetime.total_seconds(),
                    contract=registry.lookup_public_contract(definition.definition_id),
                )
            )
        contracts = registry.public_contract_set
        return cls(contract_set_digest=contracts.contract_set_digest, operations=tuple(entries))

    def render(self) -> str:
        """Serialize canonically: one operation per line, so a change reviews as one line."""
        header = {"contract_set_digest": self.contract_set_digest, "manifest_version": self.manifest_version}
        lines = [json.dumps(entry.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) for entry in self.operations]
        head = json.dumps(header, sort_keys=True, separators=(",", ":"))[:-1]
        return head + ',"operations":[\n' + ",\n".join(lines) + "\n]}\n"


@cache
def load_operation_contract_manifest() -> OperationContractManifestV1:
    """Read the manifest shipped with this installation."""
    document = packaged_data(*OPERATION_CONTRACT_MANIFEST_PARTS).read_bytes()
    return OperationContractManifestV1.model_validate_json(document)


class ManifestOperationRegistry(OperationRegistry):
    """Answer contracts from the manifest; compose a definition's group only when it is used.

    ``definitions`` is deliberately absent: a caller that needs every
    definition composes the eager :class:`OperationRegistry` instead.
    """

    _manifest: OperationContractManifestV1 = PrivateAttr()
    _build_group: OperationGroupBuilder = PrivateAttr()
    _lock: RLock = PrivateAttr(default_factory=RLock)
    _definitions: dict[str, OperationDefinition] = PrivateAttr(default_factory=dict)
    _registrations: dict[str, OperationPublicDefinitionRegistrationV1] = PrivateAttr(default_factory=dict)
    _schema_models: dict[tuple[str, int], tuple[ContentDigest, type[BaseModel]]] = PrivateAttr(default_factory=dict)

    @classmethod
    def from_manifest(cls, manifest: OperationContractManifestV1, build_group: OperationGroupBuilder) -> Self:
        """Bind the manifest to the composition that builds its groups."""
        registry = cls.model_construct(public_registrations=())
        registry._manifest = manifest
        registry._build_group = build_group
        return registry

    @cached_property
    def public_contract_set(self) -> OperationPublicContractSetV1:
        """Return the manifest's contracts without composing any operation."""
        return self._manifest.contract_set

    def _entry(self, definition_id: str) -> OperationContractManifestEntryV1:
        entry = self._manifest.entries.get(definition_id)
        if entry is None:
            raise KeyError(f"unknown operation definition ID: {definition_id!r}")
        return entry

    def _resolved(self, definition_id: str) -> tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]:
        entry = self._entry(definition_id)
        with self._lock:
            if definition_id not in self._definitions:
                self._admit(entry.group, self._build_group(entry.group))
            return self._definitions[definition_id], self._registrations[definition_id]

    def _admit(self, group: str, built: OperationGroupBuild) -> None:
        """Admit a composed group only when it reproduces the manifest exactly."""
        definitions = {str(definition.definition_id): definition for definition in built.definitions}
        registrations = {str(item.contract.definition_id): item for item in built.registrations}
        expected = self._manifest.groups[group]
        if (
            len(definitions) != len(built.definitions)
            or len(registrations) != len(built.registrations)
            or set(definitions) != expected
            or set(registrations) != expected
        ):
            raise InternalInvariantError(f"operation group {group!r} does not compose what the contract manifest names")
        schema_models = dict(self._schema_models)
        for definition_id, definition in definitions.items():
            registration = registrations[definition_id]
            entry = self._manifest.entries[definition_id]
            self._validate_public_registration(definition, registration)
            lifetime = definition.ephemeral_secret.lifetime if definition.ephemeral_secret is not None else None
            if registration.contract != entry.contract or lifetime != _lifetime(entry):
                raise InternalInvariantError(
                    f"operation {definition_id!r} no longer matches the contract manifest; regenerate it"
                )
            for binding in registration.schema_bindings:
                key = (binding.identity.schema_id, binding.identity.schema_version)
                current = (binding.identity.schema_fingerprint, binding.model_type)
                if schema_models.setdefault(key, current) != current:
                    raise InternalInvariantError("one operation schema identity must bind one exact model and fingerprint")
        self._schema_models = schema_models
        self._definitions.update(definitions)
        self._registrations.update(registrations)

    def lookup(self, definition_id: str) -> OperationDefinition:
        """Compose and return the exact registered definition, or fail closed."""
        return self._resolved(definition_id)[0]

    def lookup_public_contract(self, definition_id: str) -> OperationPublicDefinitionContractV1:
        """Return the manifest contract without composing the operation."""
        entry = self._manifest.entries.get(definition_id)
        if entry is None:
            raise KeyError(f"operation definition has no public contract: {definition_id!r}")
        return entry.contract

    def lookup_public_registration(self, definition_id: str) -> OperationPublicDefinitionRegistrationV1:
        """Compose and return the sole runtime binding for one operation."""
        if definition_id not in self._manifest.entries:
            raise KeyError(f"operation definition has no public registration: {definition_id!r}")
        return self._resolved(definition_id)[1]

    def lookup_public_schema_binding(self, identity: OperationSchemaIdentityV1) -> OperationSchemaBindingV1:
        """Compose the first operation declaring this exact identity and return its binding."""
        key = (identity.schema_id, identity.schema_version, identity.schema_fingerprint)
        for entry in self._manifest.operations:
            if key in declared_public_schema_identities(entry.contract):
                for binding in self._resolved(str(entry.contract.definition_id))[1].schema_bindings:
                    if binding.identity == identity:
                        return binding
        raise KeyError(
            "operation public schema identity is not registered: "
            f"{identity.schema_id!r} version {identity.schema_version}"
        )

    def lookup_action(self, action: ActionReference) -> OperationDefinition:
        """Resolve an action join from the manifest, composing only its operation."""
        for entry in self._manifest.operations:
            if entry.contract.action_reference == action:
                return self.lookup(str(entry.contract.definition_id))
        raise KeyError(f"operator action is not mapped to an operation definition: {action.action_id!r}")

    def declares_transient_financial_operands(self) -> bool:
        """Answer from the manifest contracts."""
        return any(entry.contract.transient_financial_operand is not None for entry in self._manifest.operations)

    def ephemeral_secret_lifetimes(self) -> tuple[timedelta, ...]:
        """Answer from the manifest entries."""
        return tuple(lifetime for entry in self._manifest.operations if (lifetime := _lifetime(entry)) is not None)


def _lifetime(entry: OperationContractManifestEntryV1) -> timedelta | None:
    seconds = entry.ephemeral_secret_lifetime_seconds
    return None if seconds is None else timedelta(seconds=seconds)


__all__ = [
    "OPERATION_CONTRACT_MANIFEST_PARTS",
    "ManifestOperationRegistry",
    "OperationContractManifestEntryV1",
    "OperationContractManifestV1",
    "OperationGroupBuild",
    "OperationGroupBuilder",
    "load_operation_contract_manifest",
]
