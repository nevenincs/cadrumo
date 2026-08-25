"""Stamped producer contracts and atomic capture ports for Modelo Workspace V1."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, TypedDict, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import STRICT_FROZEN_CONFIG, content_hash_hex
from ...core.identity import ContentDigest
from ._workspace_models import ModeloWorkspaceContributorIdentityV1

_PRODUCER_CONTRACT_VERSION = 1
_EPOCH_SCHEMA_VERSION = 1

type _ProducerCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[a-z][a-z0-9_.-]*$"),
]


class _WorkspaceProducerModel(BaseModel):
    """Common strict, immutable posture for Workspace producer records."""

    model_config = STRICT_FROZEN_CONFIG


class ModeloWorkspaceContributorKindV1(StrEnum):
    """The closed contributor denominator for one successful Workspace V1 read."""

    REGISTRY = "registry"
    WORK = "work"
    BOUNDED_REVIEW = "bounded_review"
    CALCULATION = "calculation"
    READINESS = "readiness"
    CLOSURE = "closure"
    LOCALE_CATALOGUE = "locale_catalogue"
    FIELD_MANIFEST = "field_manifest"


class ModeloWorkspaceEpochKindV1(StrEnum):
    """The accepted owner-scoped invalidation mechanism for Workspace contributors."""

    MONOTONIC_GENERATION = "monotonic_generation"


class _ProducerContractValues(TypedDict):
    contributor_kind: ModeloWorkspaceContributorKindV1
    contributor: ModeloWorkspaceContributorIdentityV1
    projection_discriminator: _ProducerCode
    projection_contract_version: int
    projection_schema_fingerprint: ContentDigest
    epoch_schema_version: int


def modelo_workspace_projection_schema_fingerprint(projection_type: type[BaseModel]) -> ContentDigest:
    """Derive one deterministic closed-schema fingerprint for a producer projection."""
    validation_schema = projection_type.model_json_schema(mode="validation")
    serialization_schema = projection_type.model_json_schema(mode="serialization")
    if validation_schema != serialization_schema:
        raise ValueError("workspace producer projection schema must have identical validation and serialization shapes")
    return content_hash_hex(validation_schema)


class ModeloWorkspaceProducerContractV1(_WorkspaceProducerModel):
    """Frozen declaration of one owner contribution to a successful Workspace result."""

    contract_version: Literal[1] = _PRODUCER_CONTRACT_VERSION
    contributor_kind: ModeloWorkspaceContributorKindV1
    contributor: ModeloWorkspaceContributorIdentityV1
    projection_discriminator: _ProducerCode
    projection_contract_version: Annotated[int, Field(ge=1)]
    projection_schema_fingerprint: ContentDigest
    epoch_kind: ModeloWorkspaceEpochKindV1 = ModeloWorkspaceEpochKindV1.MONOTONIC_GENERATION
    epoch_schema_version: Annotated[int, Field(ge=1)] = _EPOCH_SCHEMA_VERSION
    atomic_read_operation: Literal["capture_projection_with_epoch"] = "capture_projection_with_epoch"
    contract_digest: ContentDigest

    @model_validator(mode="after")
    def _require_reproducible_contract_digest(self) -> ModeloWorkspaceProducerContractV1:
        if self.contract_digest != _producer_contract_digest(self):
            raise ValueError("workspace producer contract is stale: digest does not reproduce")
        return self

    @classmethod
    def declare(
        cls,
        *,
        contributor_kind: ModeloWorkspaceContributorKindV1,
        contributor: ModeloWorkspaceContributorIdentityV1,
        projection_discriminator: _ProducerCode,
        projection_contract_version: int,
        projection_type: type[BaseModel],
        epoch_schema_version: int = _EPOCH_SCHEMA_VERSION,
    ) -> Self:
        """Declare a contract from the exact public projection schema it returns."""
        values: _ProducerContractValues = {
            "contributor_kind": contributor_kind,
            "contributor": contributor,
            "projection_discriminator": projection_discriminator,
            "projection_contract_version": projection_contract_version,
            "projection_schema_fingerprint": modelo_workspace_projection_schema_fingerprint(projection_type),
            "epoch_schema_version": epoch_schema_version,
        }
        provisional = cls.model_construct(**values, contract_digest="0" * 64)
        return cls(**values, contract_digest=_producer_contract_digest(provisional))


class ModeloWorkspaceProducerStampV1(_WorkspaceProducerModel):
    """The captured declaration identity that binds one value to its producer contract."""

    stamp_version: Literal[1] = 1
    contributor_kind: ModeloWorkspaceContributorKindV1
    contributor: ModeloWorkspaceContributorIdentityV1
    contract_digest: ContentDigest
    projection_discriminator: _ProducerCode
    projection_contract_version: Annotated[int, Field(ge=1)]
    projection_schema_fingerprint: ContentDigest

    @classmethod
    def from_contract(cls, contract: ModeloWorkspaceProducerContractV1) -> Self:
        """Mint the one stamp that exactly represents ``contract``."""
        return cls(
            contributor_kind=contract.contributor_kind,
            contributor=contract.contributor,
            contract_digest=contract.contract_digest,
            projection_discriminator=contract.projection_discriminator,
            projection_contract_version=contract.projection_contract_version,
            projection_schema_fingerprint=contract.projection_schema_fingerprint,
        )

    def require_contract(self, contract: ModeloWorkspaceProducerContractV1) -> Self:
        """Refuse a capture whose stamp differs from the declared current contract."""
        if self != self.from_contract(contract):
            raise ValueError("workspace producer stamp does not match its declared contract")
        return self


class ModeloWorkspaceEpochV1(_WorkspaceProducerModel):
    """Owner-scoped monotonic generation that makes every ABA transition observable."""

    owner: _ProducerCode
    kind: ModeloWorkspaceEpochKindV1 = ModeloWorkspaceEpochKindV1.MONOTONIC_GENERATION
    schema_version: Annotated[int, Field(ge=1)] = _EPOCH_SCHEMA_VERSION
    generation: Annotated[int, Field(ge=1)]

    def require_successor_of(self, predecessor: ModeloWorkspaceEpochV1) -> Self:
        """Require one later generation for the same owner, even when values repeat."""
        if self.owner != predecessor.owner:
            raise ValueError("workspace epochs can compare only within one owner")
        if self.kind is not predecessor.kind or self.schema_version != predecessor.schema_version:
            raise ValueError("workspace epoch kind and schema version must remain stable for one owner")
        if self.generation <= predecessor.generation:
            raise ValueError("workspace epoch generation must advance for the same owner")
        return self


class ModeloWorkspaceContributingProjectionV1[ProjectionT: BaseModel](_WorkspaceProducerModel):
    """One projection, contract stamp, and ABA-safe epoch from a single atomic read."""

    projection: ProjectionT
    stamp: ModeloWorkspaceProducerStampV1
    epoch: ModeloWorkspaceEpochV1

    def require_contract(self, contract: ModeloWorkspaceProducerContractV1) -> Self:
        """Validate the captured projection against its declared contract without a live reread."""
        self.stamp.require_contract(contract)
        if self.epoch.owner != contract.contributor.owner:
            raise ValueError("workspace contributor epoch must be scoped to its declared owner")
        if self.epoch.kind is not contract.epoch_kind or self.epoch.schema_version != contract.epoch_schema_version:
            raise ValueError("workspace contributor epoch must match its declared contract")
        if (
            modelo_workspace_projection_schema_fingerprint(type(self.projection))
            != contract.projection_schema_fingerprint
        ):
            raise ValueError("workspace captured projection schema does not match its declared contract")
        return self


@runtime_checkable
class ModeloWorkspaceAtomicProjectionPortV1[ProjectionT: BaseModel](Protocol):
    """One owner-bound port whose capture keeps a projection and epoch inseparable."""

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the current frozen contract for this owner contribution."""
        ...

    def capture_projection_with_epoch(self) -> ModeloWorkspaceContributingProjectionV1[ProjectionT]:
        """Atomically return one projection with the stamp and epoch that produced it."""
        ...

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current consistency coordinates for S128's second validation pass."""
        ...


class ModeloWorkspaceProducerContractInventoryV1(_WorkspaceProducerModel):
    """Generated fixed point over the complete, current Workspace contributor denominator."""

    inventory_version: Literal[1] = 1
    contracts: Annotated[
        tuple[ModeloWorkspaceProducerContractV1, ...],
        Field(
            min_length=len(ModeloWorkspaceContributorKindV1),
            max_length=len(ModeloWorkspaceContributorKindV1),
        ),
    ]
    inventory_digest: ContentDigest

    @field_validator("contracts")
    @classmethod
    def _require_sorted_unique_contributor_contracts(
        cls,
        value: tuple[ModeloWorkspaceProducerContractV1, ...],
    ) -> tuple[ModeloWorkspaceProducerContractV1, ...]:
        if any(contract.contract_digest != _producer_contract_digest(contract) for contract in value):
            raise ValueError("workspace producer inventory cannot include a stale contract")
        identities = tuple((contract.contributor.owner, contract.contributor.producer) for contract in value)
        if len(set(identities)) != len(identities):
            raise ValueError("workspace producer contracts must not duplicate a contributor identity")
        kinds = tuple(contract.contributor_kind for contract in value)
        if set(kinds) != set(ModeloWorkspaceContributorKindV1) or len(set(kinds)) != len(kinds):
            raise ValueError("workspace producer contracts must classify every contributor kind exactly once")
        if identities != tuple(sorted(identities)):
            raise ValueError("workspace producer contracts must be sorted by owner and producer")
        return value

    @model_validator(mode="after")
    def _require_reproducible_inventory_digest(self) -> ModeloWorkspaceProducerContractInventoryV1:
        if self.inventory_digest != _producer_contract_inventory_digest(self.contracts):
            raise ValueError("workspace producer contract inventory digest does not reproduce")
        return self

    @classmethod
    def generate(cls, contracts: tuple[ModeloWorkspaceProducerContractV1, ...]) -> Self:
        """Generate the deterministic inventory from the contributors composed on this tree."""
        canonical = tuple(
            sorted(contracts, key=lambda contract: (contract.contributor.owner, contract.contributor.producer))
        )
        return cls(
            contracts=canonical,
            inventory_digest=_producer_contract_inventory_digest(canonical),
        )

    def require_current(self, contracts: tuple[ModeloWorkspaceProducerContractV1, ...]) -> Self:
        """Refuse a missing, duplicate, unclassified, or stale contributor contract set."""
        if self != self.generate(contracts):
            raise ValueError("workspace producer contract inventory is stale")
        return self


def _producer_contract_digest(contract: ModeloWorkspaceProducerContractV1) -> ContentDigest:
    return content_hash_hex(
        {
            "contract_version": contract.contract_version,
            "contributor_kind": contract.contributor_kind.value,
            "contributor": contract.contributor.model_dump(mode="json"),
            "projection_discriminator": contract.projection_discriminator,
            "projection_contract_version": contract.projection_contract_version,
            "projection_schema_fingerprint": contract.projection_schema_fingerprint,
            "epoch_kind": contract.epoch_kind.value,
            "epoch_schema_version": contract.epoch_schema_version,
            "atomic_read_operation": contract.atomic_read_operation,
        }
    )


def _producer_contract_inventory_digest(
    contracts: tuple[ModeloWorkspaceProducerContractV1, ...],
) -> ContentDigest:
    return content_hash_hex(
        {
            "inventory_version": 1,
            "contracts": [contract.model_dump(mode="json") for contract in contracts],
        }
    )


__all__ = [
    "ModeloWorkspaceAtomicProjectionPortV1",
    "ModeloWorkspaceContributingProjectionV1",
    "ModeloWorkspaceContributorKindV1",
    "ModeloWorkspaceEpochKindV1",
    "ModeloWorkspaceEpochV1",
    "ModeloWorkspaceProducerContractInventoryV1",
    "ModeloWorkspaceProducerContractV1",
    "ModeloWorkspaceProducerStampV1",
    "modelo_workspace_projection_schema_fingerprint",
]
