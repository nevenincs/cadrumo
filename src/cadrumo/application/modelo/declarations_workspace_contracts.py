"""Immutable safe coordinates and source observations for the Declarations workspace."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Protocol, Self

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.casilla_id import CasillaId
from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NamespacedId
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, FilingRecordId, WorkUnitId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.time.utc import UtcInstant
from ...domain.modelos.calculation_revision import (
    CalculationRevisionState,
)
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecordStatus,
)
from ...domain.modelos.work_unit import WorkUnitState
from .declaration_summary import DeclarationSummary
from .declaration_targets import DeclarationTarget

if TYPE_CHECKING:
    pass


DECLARATIONS_WORKSPACE_CONTRACT_VERSION: Final[int] = 1


class DeclarationsWorkspaceProjectionError(CadrumoError):
    """The supplied authorities cannot form one coherent safe snapshot."""


class DeclarationsWorkspaceZone(StrEnum):
    """Exact read areas owned by the Declarations landing."""

    DECLARATIONS = "declarations"
    CALCULATION_REVISIONS = "calculation_revisions"
    FILING_HISTORY = "filing_history"


class DeclarationsWorkspaceSource(StrEnum):
    """Canonical source axes retained by the projection."""

    LOCAL_DECLARATIONS = "local.declarations"
    LOCAL_CALCULATIONS = "local.calculations"
    LOCAL_FILINGS = "local.filings"
    LOCAL_LIFECYCLE = "local.lifecycle"
    AEAT_EVIDENCE = "aeat.evidence"


class DeclarationsWorkspaceAvailability(StrEnum):
    """Whether a source snapshot can make an authoritative claim."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class DeclarationsLifecycleKind(StrEnum):
    """Sanitized lifecycle meanings accepted by the workspace projection.

    ``VERIFICATION_REFUSED`` exists because a refusal has nowhere else honest to
    go. Without it a surface reading the kind alone would either drop the event,
    which turns a refusal into an absence, or fold it into ``VERIFIED``, which
    reports a refused verification as a passed one.
    """

    CREATED = "created"
    RENAMED = "renamed"
    CALCULATED = "calculated"
    VERIFIED = "verified"
    VERIFICATION_REFUSED = "verification_refused"
    FILED = "filed"
    SUPERSEDED = "superseded"
    AMENDED = "amended"
    DISCARDED = "discarded"
    EXTERNAL_EVIDENCE_IMPORTED = "external_evidence_imported"
    EXPORTED = "exported"
    RECONCILED = "reconciled"
    OBSERVATION_OVERRIDDEN = "observation_overridden"
    OBSERVATION_OVERRIDE_CLEARED = "observation_override_cleared"


class DeclarationsWorkspaceZoneObservationV1(BaseModel):
    """Caller-observed availability before any rows are projected."""

    model_config = STRICT_FROZEN_CONFIG

    zone: DeclarationsWorkspaceZone
    availability: DeclarationsWorkspaceAvailability
    observed_at: UtcInstant | None = None
    reason_code: NamespacedId | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _availability_has_truthful_evidence(self) -> Self:
        observable = self.availability in {
            DeclarationsWorkspaceAvailability.AVAILABLE,
            DeclarationsWorkspaceAvailability.STALE,
        }
        if observable and self.observed_at is None:
            raise ValueError("an available or stale Declarations zone requires an observation time")
        if self.availability is DeclarationsWorkspaceAvailability.AVAILABLE and self.reason_code is not None:
            raise ValueError("an available Declarations zone cannot carry a reason")
        if self.availability is not DeclarationsWorkspaceAvailability.AVAILABLE and self.reason_code is None:
            raise ValueError("a non-available Declarations zone requires a reason")
        if self.availability is DeclarationsWorkspaceAvailability.NEVER_CAPTURED and self.observed_at is not None:
            raise ValueError("a never-captured Declarations zone cannot carry an observation time")
        return self


class DeclarationsWorkspaceZoneStateV1(DeclarationsWorkspaceZoneObservationV1):
    """One zone's authority, freshness, and measured cardinality."""

    sources: tuple[DeclarationsWorkspaceSource, ...]
    item_count: NonNegativeInt | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _count_matches_observability(self) -> Self:
        observable = self.availability in {
            DeclarationsWorkspaceAvailability.AVAILABLE,
            DeclarationsWorkspaceAvailability.STALE,
        }
        if observable != (self.item_count is not None):
            raise ValueError("only observable Declarations zones carry a measured item count")
        if not self.sources or len(self.sources) != len(set(self.sources)):
            raise ValueError("a Declarations zone requires unique source authorities")
        return self


class DeclarationsWorkspaceDeclarationRefV1(BaseModel):
    """Safe natural coordinate for one local declaration."""

    model_config = STRICT_FROZEN_CONFIG

    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    state: WorkUnitState
    has_current_calculation: bool
    has_current_filing: bool
    settled_result: str | None = None
    summary: DeclarationSummary | None = None
    """The declaration's own settled figure, when the registry grounds one.

    `None` means the answer is UNKNOWN, and a surface must render it that way
    rather than as a blank or a zero. Three distinct situations reach it, and
    none of them is "the result is nothing": the modelo's settlement chain is
    not modelled (303 and 130 today declare no result role at all), no current
    calculation exists yet, or the calculation exists and has not computed that
    cell.
    """

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _period_matches_year(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("declaration period must match its filing year")
        return self


class DeclarationsWorkspaceCalculationRevisionRefV1(BaseModel):
    """Safe state reference for one calculation version."""

    model_config = STRICT_FROZEN_CONFIG

    calculation_revision_id: CalculationRevisionId = Field(exclude=True, repr=False)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    state: CalculationRevisionState
    created_at: UtcInstant
    updated_at: UtcInstant
    is_current: bool
    is_filed: bool

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _period_matches_year(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("calculation revision period must match its filing year")
        return self


class DeclarationsWorkspaceFilingRefV1(BaseModel):
    """One chain entry: local currency, origin, AEAT confirmation and correction link."""

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: FilingRecordId = Field(exclude=True, repr=False)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    calculation_revision_id: CalculationRevisionId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    filed_at: UtcInstant
    local_status: ModeloRecordStatus
    origin: FilingOrigin
    confirmation: AeatConfirmationState
    declaration_kind: FilingDeclarationKind
    amends_filing_record_id: FilingRecordId | None = Field(default=None, exclude=True, repr=False)
    evidence_kind: ExternalEvidenceKind | None = None

    @property
    def aeat_accepted(self) -> bool:
        """Return whether AEAT has been observed to hold this entry."""
        return self.confirmation is AeatConfirmationState.CONFIRMADA

    @property
    def amends_prior_entry(self) -> bool:
        """Return whether this entry corrects an earlier declaration of its period."""
        return self.amends_filing_record_id is not None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _evidence_axes_are_truthful(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("filing period must match its filing year")
        if self.aeat_accepted != (self.evidence_kind is not None):
            raise ValueError("AEAT confirmation and external evidence presence must agree")
        if self.origin is FilingOrigin.AEAT and not self.aeat_accepted:
            raise ValueError("an AEAT-origin chain entry must be confirmed")
        return self


class DeclarationsSanitizedLifecycleFactV1(BaseModel):
    """Payload-free lifecycle fact supplied by an application authority."""

    model_config = STRICT_FROZEN_CONFIG

    fact_id: str = Field(exclude=True, repr=False, min_length=1, max_length=128)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    occurred_at: UtcInstant
    kind: DeclarationsLifecycleKind


class DeclarationsWorkspaceLifecycleRefV1(BaseModel):
    """Sanitized lifecycle fact joined to its natural declaration address."""

    model_config = STRICT_FROZEN_CONFIG

    fact_id: str = Field(exclude=True, repr=False, min_length=1, max_length=128)
    work_unit_id: WorkUnitId = Field(exclude=True, repr=False)
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    occurred_at: UtcInstant
    kind: DeclarationsLifecycleKind


class DeclarationsWorkspaceProjectionV1(BaseModel):
    """Immutable safe index over one coherent preloaded Declarations snapshot."""

    model_config = STRICT_FROZEN_CONFIG

    contract_version: int = DECLARATIONS_WORKSPACE_CONTRACT_VERSION
    bucket_id: BucketId = Field(exclude=True, repr=False)
    zones: tuple[DeclarationsWorkspaceZoneStateV1, ...]
    declarations: tuple[DeclarationsWorkspaceDeclarationRefV1, ...]
    calculation_revisions: tuple[DeclarationsWorkspaceCalculationRevisionRefV1, ...]
    filings: tuple[DeclarationsWorkspaceFilingRefV1, ...]
    lifecycle: tuple[DeclarationsWorkspaceLifecycleRefV1, ...]
    #: The natural filing coordinates the new-declaration picker offers, from the pinned authority.
    creation_targets: tuple[DeclarationTarget, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _zones_are_total_and_ordered(self) -> Self:
        if tuple(state.zone for state in self.zones) != tuple(DeclarationsWorkspaceZone):
            raise ValueError("Declarations zones must cover the closed catalogue in canonical order")
        return self


DeclarationResultCasillaReaderV1 = Callable[[ModeloCode, int, Period], str | None]
"""Names the casilla that settles one modelo revision, or nothing.

Injected rather than resolved here: this module joins already-loaded local
authorities and holds no registry access, and giving it some would put registry
loading inside a projection that is meant to be a pure join.
"""


class SettledResultUnitV1(Protocol):
    """The work-unit surface :func:`~cadrumo.application.modelo.declarations_workspace._settled_result` actually reads.

    Declared structurally so the reader's contract is the four attributes it
    consumes rather than the whole :class:`WorkUnit` aggregate. A caller that
    can supply a modelo, year, period and current calculation id is a valid
    argument, which is what the settlement tests exercise.
    """

    @property
    def modelo(self) -> ModeloCode:
        """Return the declaration’s exact modelo coordinate."""
        ...

    @property
    def filing_year(self) -> FilingYear:
        """Return the declaration’s filing year."""
        ...

    @property
    def period(self) -> Period:
        """Return the declaration’s period."""
        ...

    @property
    def current_calculation_revision_id(self) -> str | None:
        """Return the selected calculation identity or its absence."""
        ...


class SettledResultRevisionV1(Protocol):
    """Computed values consumed by the declaration settlement reader."""

    @property
    def casilla_values(self) -> Mapping[CasillaId, Decimal]:
        """Return the actual computed values without inventing missing cells."""
        ...
