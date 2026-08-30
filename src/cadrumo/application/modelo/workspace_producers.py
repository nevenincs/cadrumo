"""Stamped producer contracts and atomic capture ports for Modelo Workspace V1."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal, Protocol, Self, TypedDict, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core import RegistryAuthorityGrade, RevisionReviewStatus
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.hashing import content_hash_hex
from ...core.source_connectivity import SourceConnectivityProofAuthority
from ...core.identity import BucketId, CalculationRevisionId, ContentDigest
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.static_inspection import RegistryRevisionInspection
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol, VerificationReportCatalogueRepositoryProtocol
from ...domain.modelos.calculation_revision import CalculationRevision
from ...domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ..filing import FilingExportProofAuthority
from ..registry.closure import RegistryClosureLimb
from ..registry.source_connectivity import SourceConnectivityCensusManifest
from ..state_projection import ModeloReadinessRequest, ProjectionModeloReadiness
from .work_addressing import ModeloWorkResolution, ModeloWorkSelectionMode, ModeloWorkSelectorRequest
from .work_review import ModeloWorkReview
from .workspace_manifest import ModeloWorkspaceFieldManifestV1
from .workspace_models import ModeloWorkspaceContributorIdentityV1

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import ValidatedRegistryAuthority

_PRODUCER_CONTRACT_VERSION = 1
_EPOCH_SCHEMA_VERSION = 2

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
    epoch_schema_version: Literal[2]


def modelo_workspace_projection_schema_fingerprint(projection_type: type[BaseModel]) -> ContentDigest:
    """Derive one deterministic fingerprint over the contract a consumer actually receives.

    A port projects outward: the caller reads the SERIALIZATION shape, never
    the validation shape, so the serialization schema alone is the contract
    the fingerprint has to identify. Fingerprinting BOTH schemas and demanding
    they coincide was standing in for a round-trip guarantee it never tested
    and does not need: a bare ``Decimal`` field validates as
    ``anyOf[number, string]`` but serializes as ``string`` alone, which is a
    faithful, round-trippable representation (``model_validate_json`` parses
    the dumped string straight back to ``Decimal``), not a broken contract.
    Refuse it here and every Decimal-bearing domain model -- the registry
    snapshot, the work review, the calculation revision -- becomes
    unregisterable for a shape difference that never breaks a round trip.
    """
    return content_hash_hex(projection_type.model_json_schema(mode="serialization"))


class ModeloWorkspaceProducerContractV1(_WorkspaceProducerModel):
    """Frozen declaration of one owner contribution to a successful Workspace result."""

    contract_version: Literal[1] = _PRODUCER_CONTRACT_VERSION
    contributor_kind: ModeloWorkspaceContributorKindV1
    contributor: ModeloWorkspaceContributorIdentityV1
    projection_discriminator: _ProducerCode
    projection_contract_version: Annotated[int, Field(ge=1)]
    projection_schema_fingerprint: ContentDigest
    epoch_kind: ModeloWorkspaceEpochKindV1 = ModeloWorkspaceEpochKindV1.MONOTONIC_GENERATION
    epoch_schema_version: Literal[2] = _EPOCH_SCHEMA_VERSION
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
        epoch_schema_version: Literal[2] = _EPOCH_SCHEMA_VERSION,
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
    """Owner generation that exposes every ABA transition within one process incarnation."""

    owner: _ProducerCode
    kind: ModeloWorkspaceEpochKindV1 = ModeloWorkspaceEpochKindV1.MONOTONIC_GENERATION
    schema_version: Literal[2] = _EPOCH_SCHEMA_VERSION
    comparison_domain: ContentDigest
    generation: Annotated[int, Field(ge=1)]

    def require_successor_of(self, predecessor: ModeloWorkspaceEpochV1) -> Self:
        """Require a later same-owner generation within one process incarnation."""
        self._require_same_comparison_domain(predecessor)
        if self.generation <= predecessor.generation:
            raise ValueError("workspace epoch generation must advance for the same owner")
        return self

    def require_current(self, current: ModeloWorkspaceEpochV1) -> Self:
        """Require this epoch to remain current within its exact comparison domain."""
        self._require_same_comparison_domain(current)
        if self.generation != current.generation:
            raise ValueError("workspace epoch generation is no longer current")
        return self

    def _require_same_comparison_domain(self, other: ModeloWorkspaceEpochV1) -> None:
        if self.owner != other.owner:
            raise ValueError("workspace epochs can compare only within one owner")
        if self.kind is not other.kind or self.schema_version != other.schema_version:
            raise ValueError("workspace epoch kind and schema version must remain stable for one owner")
        if self.comparison_domain != other.comparison_domain:
            raise ValueError("workspace epochs can compare only within one comparison domain")


class ModeloWorkspaceContributingProjectionV1[ProjectionT: BaseModel](_WorkspaceProducerModel):
    """One projection, stamp, and incarnation-scoped ABA-safe epoch from one atomic read."""

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
        """Return the current consistency coordinates for the second validation pass."""
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


# --- one application-owned port realization per contributor kind ---
#
# Every envelope below is a THIN adapter only: it exists because
# ModeloWorkspaceAtomicProjectionPortV1 binds ProjectionT to BaseModel, and a
# native capture can return a bare tuple (READINESS, CLOSURE) or a dataclass
# (LOCALE_CATALOGUE) that a single fixed schema fingerprint cannot describe on
# its own. Placed here rather than beside each native owner: every envelope
# needs modelo_workspace_projection_schema_fingerprint, defined in this
# module, so an envelope living with its owner would force that owner to
# import workspace_producers while workspace_producers must import the owner
# to realize its port -- a direct cycle. No envelope here recomputes,
# reshapes, or adds a field beyond what its native capture already produced.
#
# REGISTRY's native capture returns one of two admission-specific shapes
# (RegistryRevisionInspection for static inspection, RegistrySnapshot for a
# graded snapshot), never both -- a discriminated envelope, not a tuple or
# dataclass, is what a single fixed projection type needs here.
#
# The fingerprint was corrected to admit Decimal-bearing projections, which
# is what makes REGISTRY, BOUNDED_REVIEW (ModeloWorkReview) and CALCULATION
# (CalculationRevision) registerable at all.


class ModeloWorkspaceRegistryProjectionV1(_WorkspaceProducerModel):
    """Exactly one of the two registry admission shapes, never both."""

    inspection: RegistryRevisionInspection | None = None
    snapshot: RegistrySnapshot | None = None

    @model_validator(mode="after")
    def _require_exactly_one_admission_shape(self) -> Self:
        if (self.inspection is None) == (self.snapshot is None):
            raise ValueError("registry workspace projection must carry exactly one admission shape")
        return self

    @property
    def revision_id(self) -> RevisionId:
        """Return the one law-selected revision id, whichever admission shape carries it."""
        if self.inspection is not None:
            return self.inspection.revision_id
        assert self.snapshot is not None
        return self.snapshot.revision.id

    @property
    def review_status(self) -> RevisionReviewStatus:
        """Return the revision's own governance stamp, whichever admission shape carries it."""
        if self.inspection is not None:
            return self.inspection.review_status
        assert self.snapshot is not None
        return self.snapshot.revision.review_status


class ModeloWorkspaceReadinessProjectionV1(_WorkspaceProducerModel):
    """The complete readiness report set, exactly as the sole producer built it."""

    reports: tuple[ProjectionModeloReadiness, ...]


class ModeloWorkspaceClosureProjectionV1(_WorkspaceProducerModel):
    """Every filing-export and source-connectivity closure limb, unmodified."""

    limbs: tuple[RegistryClosureLimb, ...]


class ModeloWorkspaceLocaleCatalogueProjectionV1(_WorkspaceProducerModel):
    """One captured catalogue entry, exactly as the sole catalogue reader returned it."""

    locale: str
    translation_key: str
    present: bool
    value: str | None = None
    catalogue_digest: ContentDigest


def _declared_contract(
    *,
    contributor_kind: ModeloWorkspaceContributorKindV1,
    owner: str,
    producer: str,
    discriminator: str,
    projection_contract_version: int,
    projection_type: type[BaseModel],
) -> ModeloWorkspaceProducerContractV1:
    return ModeloWorkspaceProducerContractV1.declare(
        contributor_kind=contributor_kind,
        contributor=ModeloWorkspaceContributorIdentityV1(owner=owner, producer=producer),
        projection_discriminator=discriminator,
        projection_contract_version=projection_contract_version,
        projection_type=projection_type,
    )


# Owner and producer identities below reproduce the governing "contributor
# fixed point" table verbatim -- these are not free-form labels, they are the
# canonical semantic-owner and producer-identity columns the registry API
# surface is contractually bound to.

MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.REGISTRY,
    owner="domain.calculations.registry",
    producer="validated_registry_projection",
    discriminator="validated_registry_projection",
    projection_contract_version=1,
    projection_type=ModeloWorkspaceRegistryProjectionV1,
)
MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.WORK,
    owner="application.modelo.work_addressing",
    producer="resolved_work_target",
    discriminator="resolved_work_target",
    projection_contract_version=1,
    projection_type=ModeloWorkResolution,
)
MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.BOUNDED_REVIEW,
    owner="application.modelo.work_review",
    producer="modelo_work_review",
    discriminator="modelo_work_review",
    projection_contract_version=1,
    projection_type=ModeloWorkReview,
)
MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.CALCULATION,
    owner="application.modelo.calculation",
    producer="calculation_materialization",
    discriminator="calculation_materialization",
    projection_contract_version=1,
    projection_type=CalculationRevision,
)
MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.READINESS,
    owner="application.state_projection",
    producer="modelo_readiness",
    discriminator="modelo_readiness",
    projection_contract_version=1,
    projection_type=ModeloWorkspaceReadinessProjectionV1,
)
MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.CLOSURE,
    owner="application.registry",
    producer="registry_closure",
    discriminator="registry_closure",
    projection_contract_version=1,
    projection_type=ModeloWorkspaceClosureProjectionV1,
)
MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.LOCALE_CATALOGUE,
    owner="locales",
    producer="locale_catalogue",
    discriminator="locale_catalogue",
    projection_contract_version=1,
    projection_type=ModeloWorkspaceLocaleCatalogueProjectionV1,
)
MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1 = _declared_contract(
    contributor_kind=ModeloWorkspaceContributorKindV1.FIELD_MANIFEST,
    owner="application.modelo.workspace_manifest",
    producer="workspace_field_manifest",
    discriminator="workspace_field_manifest",
    projection_contract_version=1,
    projection_type=ModeloWorkspaceFieldManifestV1,
)

MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1 = ModeloWorkspaceProducerContractInventoryV1.generate(
    (
        MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1,
        MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1,
        MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1,
        MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1,
        MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1,
        MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1,
        MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1,
        MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1,
    ),
)


class ModeloWorkspaceRegistryPortV1:
    """Application-owned port realization delegating to the registry authority."""

    def __init__(
        self,
        *,
        authority: ValidatedRegistryAuthority,
        modelo_id: str,
        filing_year: int,
        period: str,
        on: date | None = None,
        grade: RegistryAuthorityGrade | None = None,
    ) -> None:
        """Bind the authority and coordinate this port captures a registry projection for."""
        self._authority = authority
        self._modelo_id = modelo_id
        self._filing_year = filing_year
        self._period = period
        self._on = on
        self._grade = grade

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen REGISTRY contributor contract."""
        return MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(
        self,
    ) -> ModeloWorkspaceContributingProjectionV1[ModeloWorkspaceRegistryProjectionV1]:
        """Atomically capture one law-selected registry projection and stamp it with its epoch."""
        capture = self._authority.capture_law_selected_projection(
            self._modelo_id,
            filing_year=self._filing_year,
            period=self._period,
            on=self._on,
            grade=self._grade,
        )
        projection = (
            ModeloWorkspaceRegistryProjectionV1(snapshot=capture.projection)
            if isinstance(capture.projection, RegistrySnapshot)
            else ModeloWorkspaceRegistryProjectionV1(inspection=capture.projection)
        )
        return _contributing_projection(
            self.producer_contract,
            projection=projection,
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current REGISTRY stamp and epoch for same-domain validation."""
        coordinate = self._authority.read_current_coordinate()
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


class ModeloWorkspaceWorkPortV1:
    """Application-owned port realization delegating to the sole WORK capture."""

    def __init__(
        self,
        *,
        request: ModeloWorkSelectorRequest,
        catalogue_repository: WorkUnitCatalogueRepositoryProtocol,
        mode: ModeloWorkSelectionMode = ModeloWorkSelectionMode.VISIBLE_OR_EXACT,
    ) -> None:
        """Bind the request and repository this port resolves against."""
        self._request = request
        self._catalogue_repository = catalogue_repository
        self._mode = mode

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen WORK contributor contract."""
        return MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(self) -> ModeloWorkspaceContributingProjectionV1[ModeloWorkResolution]:
        """Atomically capture one work resolution and stamp it with its epoch."""
        from .work_addressing import capture_modelo_work_resolution

        capture = capture_modelo_work_resolution(
            self._request,
            catalogue_repository=self._catalogue_repository,
            mode=self._mode,
        )
        return _contributing_projection(
            self.producer_contract,
            projection=capture.resolution,
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current WORK stamp and epoch for same-domain validation."""
        from .work_addressing import read_modelo_work_current_coordinate

        coordinate = read_modelo_work_current_coordinate(
            self._request,
            catalogue_repository=self._catalogue_repository,
        )
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


class ModeloWorkspaceBoundedReviewPortV1:
    """Application-owned port realization delegating to the sole BOUNDED_REVIEW capture."""

    def __init__(
        self,
        *,
        bucket_id: BucketId,
        modelo: ModeloCode,
        filing_year: int,
        period: Period,
        authority: ValidatedRegistryAuthority | None = None,
        work_unit_repository: WorkUnitCatalogueRepositoryProtocol,
        calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
        verification_repository: VerificationReportCatalogueRepositoryProtocol,
    ) -> None:
        """Bind the resolved target and repositories this port assembles a review from."""
        self._bucket_id = bucket_id
        self._modelo = modelo
        self._filing_year = filing_year
        self._period = period
        self._authority = authority
        self._work_unit_repository = work_unit_repository
        self._calculation_repository = calculation_repository
        self._verification_repository = verification_repository

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen BOUNDED_REVIEW contributor contract."""
        return MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(self) -> ModeloWorkspaceContributingProjectionV1[ModeloWorkReview]:
        """Atomically capture one work review and stamp it with its epoch."""
        from .work_review import capture_modelo_work_review

        capture = capture_modelo_work_review(
            self._bucket_id,
            self._modelo,
            self._filing_year,
            self._period,
            authority=self._authority,
            work_unit_repository=self._work_unit_repository,
            calculation_repository=self._calculation_repository,
            verification_repository=self._verification_repository,
        )
        return _contributing_projection(
            self.producer_contract,
            projection=capture.review,
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current BOUNDED_REVIEW stamp and epoch for same-domain validation."""
        from .work_review import read_modelo_work_review_current_coordinate

        coordinate = read_modelo_work_review_current_coordinate(
            self._bucket_id,
            self._modelo,
            self._filing_year,
            self._period,
            work_unit_repository=self._work_unit_repository,
            calculation_repository=self._calculation_repository,
            verification_repository=self._verification_repository,
        )
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


class ModeloWorkspaceCalculationPortV1:
    """Application-owned port realization delegating to the sole CALCULATION capture."""

    def __init__(
        self,
        *,
        calculation_revision_id: CalculationRevisionId,
        calculation_repository: CalculationRevisionCatalogueRepositoryProtocol | None = None,
    ) -> None:
        """Bind the calculation revision id this port materializes."""
        self._calculation_revision_id = calculation_revision_id
        self._calculation_repository = calculation_repository

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen CALCULATION contributor contract."""
        return MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(self) -> ModeloWorkspaceContributingProjectionV1[CalculationRevision]:
        """Atomically capture one calculation revision and stamp it with its epoch."""
        from .calculation import capture_modelo_calculation

        capture = capture_modelo_calculation(
            self._calculation_revision_id,
            calculation_repository=self._calculation_repository,
        )
        return _contributing_projection(
            self.producer_contract,
            projection=capture.revision,
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current CALCULATION stamp and epoch for same-domain validation."""
        from .calculation import read_modelo_calculation_current_coordinate

        coordinate = read_modelo_calculation_current_coordinate(
            self._calculation_revision_id,
            calculation_repository=self._calculation_repository,
        )
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


class ModeloWorkspaceReadinessPortV1:
    """Application-owned port realization delegating to the sole READINESS capture."""

    def __init__(self, *, requests: tuple[ModeloReadinessRequest, ...], active_profile_id: str) -> None:
        """Bind the readiness requests and active profile this port resolves against."""
        self._requests = requests
        self._active_profile_id = active_profile_id

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen READINESS contributor contract."""
        return MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(
        self,
    ) -> ModeloWorkspaceContributingProjectionV1[ModeloWorkspaceReadinessProjectionV1]:
        """Atomically capture the readiness report set and stamp it with its epoch."""
        from ..state_projection import capture_modelo_readiness

        capture = capture_modelo_readiness(self._requests, active_profile_id=self._active_profile_id)
        return _contributing_projection(
            self.producer_contract,
            projection=ModeloWorkspaceReadinessProjectionV1(reports=capture.reports),
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current READINESS stamp and epoch for same-domain validation."""
        from ..state_projection import read_modelo_readiness_current_coordinate

        coordinate = read_modelo_readiness_current_coordinate(
            self._requests,
            active_profile_id=self._active_profile_id,
        )
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


class ModeloWorkspaceClosurePortV1:
    """Application-owned port realization delegating to the sole CLOSURE capture."""

    def __init__(
        self,
        *,
        authority: ValidatedRegistryAuthority,
        census: SourceConnectivityCensusManifest,
        as_of: date,
        filing_proof_authority: FilingExportProofAuthority | None = None,
        connectivity_proof_authority: SourceConnectivityProofAuthority | None = None,
    ) -> None:
        """Bind the authority, census and dates this port composes closure from."""
        self._authority = authority
        self._census = census
        self._as_of = as_of
        self._filing_proof_authority = filing_proof_authority
        self._connectivity_proof_authority = connectivity_proof_authority

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen CLOSURE contributor contract."""
        return MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(
        self,
    ) -> ModeloWorkspaceContributingProjectionV1[ModeloWorkspaceClosureProjectionV1]:
        """Atomically capture the closure limbs and stamp them with their epoch."""
        from ..registry.closure_capture import capture_registry_closure

        capture = capture_registry_closure(
            authority=self._authority,
            census=self._census,
            as_of=self._as_of,
            filing_proof_authority=self._filing_proof_authority,
            connectivity_proof_authority=self._connectivity_proof_authority,
        )
        return _contributing_projection(
            self.producer_contract,
            projection=ModeloWorkspaceClosureProjectionV1(limbs=capture.limbs),
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current CLOSURE stamp and epoch for same-domain validation."""
        from ..registry.closure_capture import read_registry_closure_current_coordinate

        coordinate = read_registry_closure_current_coordinate(
            authority=self._authority,
            census=self._census,
            as_of=self._as_of,
            filing_proof_authority=self._filing_proof_authority,
            connectivity_proof_authority=self._connectivity_proof_authority,
        )
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


class ModeloWorkspaceLocaleCataloguePortV1:
    """Application-owned port realization delegating to the sole LOCALE_CATALOGUE capture."""

    def __init__(self, *, translation_key: str, locale: str) -> None:
        """Bind the translation key and locale this port resolves against."""
        self._translation_key = translation_key
        self._locale = locale

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen LOCALE_CATALOGUE contributor contract."""
        return MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(
        self,
    ) -> ModeloWorkspaceContributingProjectionV1[ModeloWorkspaceLocaleCatalogueProjectionV1]:
        """Atomically capture one catalogue entry and stamp it with its epoch."""
        from ...core.i18n.locale_catalogue import capture_locale_catalogue

        capture = capture_locale_catalogue(self._translation_key, locale=self._locale)
        return _contributing_projection(
            self.producer_contract,
            projection=ModeloWorkspaceLocaleCatalogueProjectionV1(
                locale=capture.locale,
                translation_key=capture.translation_key,
                present=capture.present,
                value=capture.value,
                catalogue_digest=capture.catalogue_digest,
            ),
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current LOCALE_CATALOGUE stamp and epoch for same-domain validation."""
        from ...core.i18n.locale_catalogue import read_locale_catalogue_current_coordinate

        coordinate = read_locale_catalogue_current_coordinate(locale=self._locale)
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


class ModeloWorkspaceFieldManifestPortV1:
    """Application-owned port realization delegating to the sole FIELD_MANIFEST capture.

    A static inspection and a graded snapshot make different authority
    claims and generate over different type universes -- this port accepts
    either admission's own authority object and dispatches to the matching
    generator, never filtering one universe's manifest down for the other.
    """

    def __init__(self, *, authority: RegistrySnapshot | RegistryRevisionInspection) -> None:
        """Bind the registry authority object this port generates the field manifest from."""
        self._authority = authority

    @property
    def producer_contract(self) -> ModeloWorkspaceProducerContractV1:
        """Return the frozen FIELD_MANIFEST contributor contract."""
        return MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1

    def capture_projection_with_epoch(
        self,
    ) -> ModeloWorkspaceContributingProjectionV1[ModeloWorkspaceFieldManifestV1]:
        """Atomically capture the field manifest and stamp it with its epoch."""
        if isinstance(self._authority, RegistrySnapshot):
            from .workspace_manifest import capture_modelo_workspace_manifest

            capture = capture_modelo_workspace_manifest(self._authority)
        else:
            from .workspace_manifest import capture_modelo_workspace_manifest_for_inspection

            capture = capture_modelo_workspace_manifest_for_inspection(self._authority)
        return _contributing_projection(
            self.producer_contract,
            projection=capture.manifest,
            comparison_domain=capture.comparison_domain,
            generation=capture.generation,
        )

    def read_current_stamp_and_epoch(self) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
        """Return the current FIELD_MANIFEST stamp and epoch for same-domain validation."""
        if isinstance(self._authority, RegistrySnapshot):
            from .workspace_manifest import read_modelo_workspace_manifest_current_coordinate

            coordinate = read_modelo_workspace_manifest_current_coordinate(self._authority)
        else:
            from .workspace_manifest import read_modelo_workspace_manifest_current_coordinate_for_inspection

            coordinate = read_modelo_workspace_manifest_current_coordinate_for_inspection(self._authority)
        return _current_stamp_and_epoch(self.producer_contract, coordinate)


def _contributing_projection[ProjectionT: BaseModel](
    contract: ModeloWorkspaceProducerContractV1,
    *,
    projection: ProjectionT,
    comparison_domain: str,
    generation: int,
) -> ModeloWorkspaceContributingProjectionV1[ProjectionT]:
    return ModeloWorkspaceContributingProjectionV1(
        projection=projection,
        stamp=ModeloWorkspaceProducerStampV1.from_contract(contract),
        epoch=ModeloWorkspaceEpochV1(
            owner=contract.contributor.owner,
            comparison_domain=comparison_domain,
            generation=generation,
        ),
    )


@runtime_checkable
class _NativeCurrentCoordinate(Protocol):
    """The comparison-domain/generation shape every native coordinate shares."""

    @property
    def comparison_domain(self) -> str: ...

    @property
    def generation(self) -> int: ...


def _current_stamp_and_epoch(
    contract: ModeloWorkspaceProducerContractV1,
    coordinate: _NativeCurrentCoordinate,
) -> tuple[ModeloWorkspaceProducerStampV1, ModeloWorkspaceEpochV1]:
    return (
        ModeloWorkspaceProducerStampV1.from_contract(contract),
        ModeloWorkspaceEpochV1(
            owner=contract.contributor.owner,
            comparison_domain=coordinate.comparison_domain,
            generation=coordinate.generation,
        ),
    )


__all__ = [
    "MODELO_WORKSPACE_BOUNDED_REVIEW_PRODUCER_CONTRACT_V1",
    "MODELO_WORKSPACE_CALCULATION_PRODUCER_CONTRACT_V1",
    "MODELO_WORKSPACE_CLOSURE_PRODUCER_CONTRACT_V1",
    "MODELO_WORKSPACE_FIELD_MANIFEST_PRODUCER_CONTRACT_V1",
    "MODELO_WORKSPACE_LOCALE_CATALOGUE_PRODUCER_CONTRACT_V1",
    "MODELO_WORKSPACE_PRODUCER_CONTRACT_INVENTORY_V1",
    "MODELO_WORKSPACE_READINESS_PRODUCER_CONTRACT_V1",
    "MODELO_WORKSPACE_REGISTRY_PRODUCER_CONTRACT_V1",
    "MODELO_WORKSPACE_WORK_PRODUCER_CONTRACT_V1",
    "ModeloWorkspaceAtomicProjectionPortV1",
    "ModeloWorkspaceBoundedReviewPortV1",
    "ModeloWorkspaceCalculationPortV1",
    "ModeloWorkspaceClosurePortV1",
    "ModeloWorkspaceClosureProjectionV1",
    "ModeloWorkspaceContributingProjectionV1",
    "ModeloWorkspaceContributorKindV1",
    "ModeloWorkspaceEpochKindV1",
    "ModeloWorkspaceEpochV1",
    "ModeloWorkspaceFieldManifestPortV1",
    "ModeloWorkspaceLocaleCataloguePortV1",
    "ModeloWorkspaceLocaleCatalogueProjectionV1",
    "ModeloWorkspaceProducerContractInventoryV1",
    "ModeloWorkspaceProducerContractV1",
    "ModeloWorkspaceProducerStampV1",
    "ModeloWorkspaceReadinessPortV1",
    "ModeloWorkspaceReadinessProjectionV1",
    "ModeloWorkspaceRegistryPortV1",
    "ModeloWorkspaceRegistryProjectionV1",
    "ModeloWorkspaceWorkPortV1",
    "modelo_workspace_projection_schema_fingerprint",
]
