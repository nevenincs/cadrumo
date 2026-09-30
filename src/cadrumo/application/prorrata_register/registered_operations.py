"""Exact-profile registered operations for the IVA prorrata register."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, ValidationError, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.prorrata_register_catalogue import (
    carried_prior_definitiva_prorrata_provenance,
    especial_prorrata_register_regime,
    general_prorrata_register_regime,
    opcion_prorrata_transition,
    prorrata_electable_provenances,
    prorrata_sector_letters,
    require_prorrata_provenance,
    revocacion_prorrata_transition,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    ProrrataRegisterValidationError,
    SectorDefinition,
)
from ..ledger.read_access import resolve_ledger_read_access
from ..modelo.calculation_action_ports import CalculationActionPortsFactory
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .election import ProrrataElectionError
from .ports import ProrrataPriorSettlementSnapshotRepositoryProtocol, ProrrataRegisterRepositoryFactory
from .sector_lifecycle import ProrrataSectorLifecycleUnavailableError
from .seed import ProrrataPriorDefinitivaSeed, ProrrataSeedFinding
from .service import (
    ProrrataRegisterService,
    ProrrataWholeSeedUnavailableError,
    ProrrataWholeSeedUnavailableReason,
)

PRORRATA_LIST_OPERATION_DEFINITION_ID = "ledger.prorrata.list"
PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID = "ledger.prorrata.declare_sector"
PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID = "ledger.prorrata.elect_especial"
PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID = "ledger.prorrata.elect_general"
PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID = "ledger.prorrata.revoke_especial"
PRORRATA_SEED_OPERATION_DEFINITION_ID = "ledger.prorrata.seed"
PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID = "ledger.prorrata.seed_sector"
PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID = "ledger.prorrata.settle_sector"

PRORRATA_VALIDATION_REFUSAL_CODE = "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION"
PRORRATA_ELECTION_REFUSAL_CODE = "REFUSED_PRORRATA_ELECTION"
PRORRATA_WHOLE_SEED_REFUSAL_CODE = "REFUSED_PROFILE_PRORRATA_WHOLE_SEED"
PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE = "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE"

type ProrrataOperationId = Literal[
    "list",
    "declare_sector",
    "elect_especial",
    "elect_general",
    "revoke_especial",
    "seed",
    "seed_sector",
    "settle_sector",
]
type ProrrataRefusalReason = Literal[
    "validation",
    "provenance_required",
    "provenance_not_electable",
    "reference_required",
    "reference_not_permitted",
    "seed_source_absent",
    "seed_source_blocked",
    "seed_existing_blocked",
    "regulated_override_standing",
    "sector_prior_definitive_absent",
    "sector_settlement_entry_absent",
]
type ProrrataRefusalCode = Literal[
    "REFUSED_PROFILE_PRORRATA_REGISTER_VALIDATION",
    "REFUSED_PRORRATA_ELECTION",
    "REFUSED_PROFILE_PRORRATA_WHOLE_SEED",
    "REFUSED_PROFILE_PRORRATA_SECTOR_LIFECYCLE",
]


class _ProfileRequest(BaseModel):
    """Common hidden exact-profile binding for prorrata register operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class ProrrataListRequest(_ProfileRequest):
    """Read the complete prorrata singleton for the selected profile."""


class ProrrataDeclareSectorRequest(_ProfileRequest):
    """Declare the taxpayer-authored differentiated-sector partition row."""

    sector_id: str
    letra: str
    member_activity_codes: tuple[str, ...] = ()


class _ProrrataElectionRequest(_ProfileRequest):
    """Operator-authored provisional percentage and evidence reference."""

    ejercicio: int
    percentage: PublicDecimal
    provenance: str | None = None
    reference: str | None = None
    sector_id: str | None = None


class ProrrataElectEspecialRequest(_ProrrataElectionRequest):
    """Elect especial prorrata for one exercise."""

    evidence_reference: str | None = None


class ProrrataElectGeneralRequest(_ProrrataElectionRequest):
    """Elect general prorrata for one exercise."""


class ProrrataRevokeEspecialRequest(_ProrrataElectionRequest):
    """Record the evidence-backed revocation of especial prorrata."""

    evidence_reference: str


class ProrrataSeedRequest(_ProfileRequest):
    """Carry whole-entity prior definitive from the pinned 303 observation."""

    ejercicio: int


class ProrrataSeedSectorRequest(_ProfileRequest):
    """Carry one differentiated sector from its latest prior register definitive."""

    ejercicio: int
    sector_id: str


class ProrrataSettleSectorRequest(_ProfileRequest):
    """Compute and record one sector's year-end definitive prorrata."""

    ejercicio: int
    sector_id: str
    con_derecho_volume: PublicDecimal
    sin_derecho_volume: PublicDecimal


class ProrrataSnapshotRefProjection(BaseModel):
    """Schema-safe projection of one registry coordinate cited by an entry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    revision_id: str
    modelo_year: int
    period: str


class ProrrataEspecialTransitionProjection(BaseModel):
    """Complete bounded option or revocation evidence carried by an entry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: str
    evidence_reference: str


class ProrrataEntryProjection(BaseModel):
    """Complete result projection of one canonical cross-period register entry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    ejercicio: int
    regime: str
    especial_transition: ProrrataEspecialTransitionProjection | None
    sector_id: str | None
    interrupted: bool
    provisional_percentage: PublicDecimal | None
    provisional_provenance: str | None
    authorisation_reference: str | None
    definitive_percentage: PublicDecimal | None
    definitive_volume_con_derecho: PublicDecimal | None
    definitive_volume_sin_derecho: PublicDecimal | None
    source_observation_ref: str | None
    source_registry_snapshot_refs: tuple[ProrrataSnapshotRefProjection, ...]
    schema_version: str

    @classmethod
    def from_entry(cls, entry: ProrrataRegisterEntry) -> ProrrataEntryProjection:
        """Project every persisted register field without exposing opaque token schemas."""
        transition = entry.especial_transition
        return cls(
            ejercicio=entry.ejercicio,
            regime=entry.regime.value,
            especial_transition=(
                ProrrataEspecialTransitionProjection(
                    kind=transition.kind.value,
                    evidence_reference=transition.evidence_reference,
                )
                if transition is not None
                else None
            ),
            sector_id=entry.sector_id,
            interrupted=entry.interrupted,
            provisional_percentage=_public_decimal(entry.provisional_percentage),
            provisional_provenance=(entry.provisional_provenance.value if entry.provisional_provenance else None),
            authorisation_reference=entry.authorisation_reference,
            definitive_percentage=_public_decimal(entry.definitive_percentage),
            definitive_volume_con_derecho=_public_decimal(entry.definitive_volume_con_derecho),
            definitive_volume_sin_derecho=_public_decimal(entry.definitive_volume_sin_derecho),
            source_observation_ref=entry.source_observation_ref,
            source_registry_snapshot_refs=tuple(
                ProrrataSnapshotRefProjection(
                    modelo=reference.modelo,
                    revision_id=reference.revision_id,
                    modelo_year=reference.modelo_year,
                    period=reference.period,
                )
                for reference in entry.source_registry_snapshot_refs
            ),
            schema_version=entry.schema_version,
        )


class ProrrataSectorDefinitionProjection(BaseModel):
    """Complete projection of one operator-authored differentiated-sector row."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    sector_id: str
    letra: str
    member_activity_codes: tuple[str, ...]

    @classmethod
    def from_definition(cls, definition: SectorDefinition) -> ProrrataSectorDefinitionProjection:
        """Project every canonical sector coordinate."""
        return cls(
            sector_id=definition.sector_id,
            letra=definition.letra.value,
            member_activity_codes=definition.member_activity_codes,
        )


class ProrrataFindingProjection(BaseModel):
    """Complete source-finding details for seed advisory and refusal surfaces."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: str
    blocking: bool
    message: str
    source_modelo: str
    source_filing_year: int
    source_period: str
    stamped_revision_id: str
    selected_revision_id: str | None

    @classmethod
    def from_finding(cls, finding: ProrrataSeedFinding) -> ProrrataFindingProjection:
        """Project the complete application finding without reducing it to a flag."""
        return cls(
            code=finding.code,
            blocking=finding.blocking,
            message=finding.message,
            source_modelo=finding.source_modelo,
            source_filing_year=finding.source_filing_year,
            source_period=finding.source_period,
            stamped_revision_id=finding.stamped_revision_id,
            selected_revision_id=finding.selected_revision_id,
        )


class ProrrataSeedSourceProjection(BaseModel):
    """Identity of the local stamped observation that supplied a carried seed."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    modelo: str
    filing_year: int
    period: str
    casilla_id: str
    stamped_revision_id: str
    authority: Literal["local_prior_observation"] = "local_prior_observation"

    @classmethod
    def from_seed(cls, seed: ProrrataPriorDefinitivaSeed) -> ProrrataSeedSourceProjection:
        """Project all safe source coordinates from the canonical seed result."""
        return cls(
            modelo=seed.source_modelo,
            filing_year=seed.source_filing_year,
            period=seed.source_period,
            casilla_id=str(seed.source_casilla_id),
            stamped_revision_id=seed.stamped_revision_id,
        )


class ProrrataRefusalProjection(BaseModel):
    """Finite typed explanation for a known refusal that committed no mutation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: ProrrataRefusalCode
    reason: ProrrataRefusalReason
    detail: str
    ejercicio: int | None = None
    sector_id: str | None = None
    findings: tuple[ProrrataFindingProjection, ...] = ()
    accepted_provenances: tuple[str, ...] = ()
    existing_provenance: str | None = None

    @model_validator(mode="after")
    def _standing_provenance_is_exact(self) -> ProrrataRefusalProjection:
        if (self.reason == "regulated_override_standing") != (self.existing_provenance is not None):
            raise ValueError("whole-seed standing refusal must retain the actual provisional provenance")
        return self


class ProrrataOperationExecutionResult(BaseModel):
    """Private complete outcome retained under secure operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: ProrrataOperationId
    profile_id: UUID
    outcome: Literal["success", "refused"]
    register_snapshot: ProrrataRegister | None = None
    entry: ProrrataRegisterEntry | None = None
    sector_definition: SectorDefinition | None = None
    seed_source: ProrrataSeedSourceProjection | None = None
    findings: tuple[ProrrataFindingProjection, ...] = ()
    prior_ejercicio: int | None = None
    count: NonNegativeInt | None = None
    refusal: ProrrataRefusalProjection | None = None

    @model_validator(mode="after")
    def _result_arm_is_closed(self) -> ProrrataOperationExecutionResult:
        success_values = (
            self.register_snapshot,
            self.entry,
            self.sector_definition,
            self.seed_source,
            self.prior_ejercicio,
            self.count,
        )
        if self.outcome == "refused":
            if (
                self.operation_id == "list"
                or self.refusal is None
                or any(value is not None for value in success_values)
                or self.findings
            ):
                raise ValueError("prorrata refusal result has an incompatible payload")
            return self
        if self.refusal is not None or self.register_snapshot is None or self.count is None:
            raise ValueError("prorrata success result is incomplete")
        if self.operation_id == "list":
            if any(value is not None for value in (self.entry, self.sector_definition, self.seed_source)):
                raise ValueError("prorrata list result contains mutation details")
        elif self.operation_id == "declare_sector":
            if self.sector_definition is None or any(
                value is not None for value in (self.entry, self.seed_source, self.prior_ejercicio)
            ):
                raise ValueError("prorrata sector declaration result is incomplete")
        else:
            if self.entry is None or self.sector_definition is not None:
                raise ValueError("prorrata entry mutation result is incomplete")
            if (self.operation_id == "seed") != (self.seed_source is not None):
                raise ValueError("prorrata whole-seed source differs from its operation")
            if (self.operation_id == "seed_sector") != (self.prior_ejercicio is not None):
                raise ValueError("prorrata sector prior year differs from its operation")
        return self


class ProrrataListProjection(BaseModel):
    """Complete all-period list result for the profile's prorrata singleton."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    entries: tuple[ProrrataEntryProjection, ...]
    sectors: tuple[ProrrataSectorDefinitionProjection, ...]
    count: NonNegativeInt

    @model_validator(mode="after")
    def _count_matches_entries(self) -> ProrrataListProjection:
        if self.count != len(self.entries):
            raise ValueError("prorrata list count differs from its complete entry rows")
        return self


class ProrrataMutationProjection(BaseModel):
    """Closed CLI/MCP/TUI projection for one prorrata mutation or its refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: ProrrataOperationId
    profile_id: UUID
    outcome: Literal["success", "refused"]
    entry: ProrrataEntryProjection | None = None
    sector_definition: ProrrataSectorDefinitionProjection | None = None
    seed_source: ProrrataSeedSourceProjection | None = None
    findings: tuple[ProrrataFindingProjection, ...] = ()
    prior_ejercicio: int | None = None
    count: NonNegativeInt | None = None
    refusal: ProrrataRefusalProjection | None = None

    @model_validator(mode="after")
    def _projection_arm_is_closed(self) -> ProrrataMutationProjection:
        if self.operation_id == "list":
            raise ValueError("prorrata mutation projection cannot describe a list operation")
        if self.outcome == "refused":
            if (
                self.refusal is None
                or any(
                    value is not None
                    for value in (
                        self.entry,
                        self.sector_definition,
                        self.seed_source,
                        self.prior_ejercicio,
                        self.count,
                    )
                )
                or self.findings
            ):
                raise ValueError("prorrata refusal projection is incomplete")
            return self
        if self.refusal is not None or self.count is None:
            raise ValueError("prorrata success projection is incomplete")
        if self.operation_id == "declare_sector":
            if self.sector_definition is None or self.entry is not None:
                raise ValueError("prorrata sector projection has an incompatible payload")
        elif self.entry is None or self.sector_definition is not None:
            raise ValueError("prorrata entry projection is incomplete")
        if (self.operation_id == "seed") != (self.seed_source is not None):
            raise ValueError("prorrata seed projection is missing its source identity")
        if (self.operation_id == "seed_sector") != (self.prior_ejercicio is not None):
            raise ValueError("prorrata sector seed projection is missing its prior year")
        if self.operation_id != "seed" and self.findings:
            raise ValueError("non-seed prorrata result contains seed findings")
        return self


@dataclass(frozen=True, slots=True)
class _OperationShape:
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    mutation: bool
    refusal_codes: frozenset[str]


_MUTATION_REFUSALS = frozenset({PRORRATA_VALIDATION_REFUSAL_CODE})
_ELECTION_REFUSALS = _MUTATION_REFUSALS | {PRORRATA_ELECTION_REFUSAL_CODE}
_SEED_REFUSALS = _MUTATION_REFUSALS | {PRORRATA_WHOLE_SEED_REFUSAL_CODE}
_SECTOR_LIFECYCLE_REFUSALS = _MUTATION_REFUSALS | {PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE}
_SHAPES: dict[str, _OperationShape] = {
    PRORRATA_LIST_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataListRequest,
        projection_type=ProrrataListProjection,
        mutation=False,
        refusal_codes=frozenset(),
    ),
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataDeclareSectorRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_MUTATION_REFUSALS,
    ),
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataElectEspecialRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataElectGeneralRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataRevokeEspecialRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    PRORRATA_SEED_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataSeedRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SEED_REFUSALS,
    ),
    PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataSeedSectorRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SECTOR_LIFECYCLE_REFUSALS,
    ),
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=ProrrataSettleSectorRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SECTOR_LIFECYCLE_REFUSALS,
    ),
}


@dataclass(frozen=True, slots=True)
class _CommittedMutation:
    register: ProrrataRegister
    entry: ProrrataRegisterEntry | None = None
    sector_definition: SectorDefinition | None = None
    seed: ProrrataPriorDefinitivaSeed | None = None
    findings: tuple[ProrrataSeedFinding, ...] = ()
    prior_ejercicio: int | None = None


class _ProrrataPreflightRefusalError(Exception):
    reason: ProrrataRefusalReason
    detail: str
    accepted_provenances: tuple[str, ...]

    def __init__(
        self,
        reason: ProrrataRefusalReason,
        detail: str,
        *,
        accepted_provenances: tuple[str, ...] = (),
    ) -> None:
        self.reason = reason
        self.detail = detail
        self.accepted_provenances = accepted_provenances
        super().__init__(detail)


def _public_decimal(value: Decimal | None) -> PublicDecimal | None:
    return PublicDecimal(decimal=str(value)) if value is not None else None


def _refusal(
    *,
    reason: ProrrataRefusalReason,
    detail: str,
    ejercicio: int | None = None,
    sector_id: str | None = None,
    findings: tuple[ProrrataSeedFinding, ...] = (),
    accepted_provenances: tuple[str, ...] = (),
    existing_provenance: str | None = None,
    code: ProrrataRefusalCode = PRORRATA_VALIDATION_REFUSAL_CODE,
) -> ProrrataRefusalProjection:
    return ProrrataRefusalProjection(
        code=code,
        reason=reason,
        detail=detail,
        ejercicio=ejercicio,
        sector_id=sector_id,
        findings=tuple(ProrrataFindingProjection.from_finding(item) for item in findings),
        accepted_provenances=accepted_provenances,
        existing_provenance=existing_provenance,
    )


def _build_election_entry(
    operation_id: ProrrataOperationId,
    payload: _ProrrataElectionRequest,
) -> ProrrataRegisterEntry:
    carried = carried_prior_definitiva_prorrata_provenance()
    accepted_provenances = tuple(item.value for item in prorrata_electable_provenances() if item != carried)
    if payload.provenance is None:
        raise _ProrrataPreflightRefusalError(
            "provenance_required",
            "manual prorrata election requires evidence provenance",
            accepted_provenances=accepted_provenances,
        )
    try:
        provenance = require_prorrata_provenance(payload.provenance)
    except ProrrataRegisterValidationError as exc:
        raise _ProrrataPreflightRefusalError(
            "provenance_not_electable",
            str(exc),
            accepted_provenances=accepted_provenances,
        ) from exc
    if provenance == carried:
        raise _ProrrataPreflightRefusalError(
            "provenance_required",
            "carried prior definitive must use the seed operation",
            accepted_provenances=accepted_provenances,
        )
    try:
        from .election import validate_prorrata_election

        provenance, reference = validate_prorrata_election(provenance=provenance, reference=payload.reference)
    except ProrrataElectionError as exc:
        raise _ProrrataPreflightRefusalError(
            exc.refusal.value,
            str(exc),
            accepted_provenances=accepted_provenances,
        ) from exc

    transition: ProrrataEspecialTransitionEvidence | None = None
    regime = general_prorrata_register_regime()
    if operation_id == "elect_especial":
        regime = especial_prorrata_register_regime()
        if not isinstance(payload, ProrrataElectEspecialRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.evidence_reference is not None:
            transition = ProrrataEspecialTransitionEvidence(
                kind=opcion_prorrata_transition(),
                evidence_reference=payload.evidence_reference,
            )
    elif operation_id == "revoke_especial":
        if not isinstance(payload, ProrrataRevokeEspecialRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        transition = ProrrataEspecialTransitionEvidence(
            kind=revocacion_prorrata_transition(),
            evidence_reference=payload.evidence_reference,
        )

    try:
        return ProrrataRegisterEntry(
            ejercicio=payload.ejercicio,
            regime=regime,
            especial_transition=transition,
            sector_id=payload.sector_id,
            provisional_percentage=Decimal(payload.percentage.decimal),
            provisional_provenance=provenance,
            authorisation_reference=reference,
            source_registry_snapshot_refs=(),
        )
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        raise _ProrrataPreflightRefusalError("validation", str(exc)) from exc


def _from_whole_seed_reason(reason: ProrrataWholeSeedUnavailableReason) -> ProrrataRefusalReason:
    mapping: dict[ProrrataWholeSeedUnavailableReason, ProrrataRefusalReason] = {
        "source_absent": "seed_source_absent",
        "source_blocked": "seed_source_blocked",
        "existing_blocked": "seed_existing_blocked",
        "regulated_override_standing": "regulated_override_standing",
    }
    try:
        return mapping[reason]
    except KeyError:
        raise RuntimeError("whole-entity seed refusal returned an unknown finite reason") from None


def _profile_id_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if receipt.identity.definition_id != definition_id:
        raise ValueError("prorrata result definition differs from its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("prorrata result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("prorrata result has an invalid profile subject")
    return profile_id


class ProrrataOperationExecutor:
    """Run one canonical prorrata service call under exact-profile worker custody."""

    def __init__(
        self,
        repository_factory: ProrrataRegisterRepositoryFactory,
        *,
        definition_id: str,
        calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
    ) -> None:
        """Bind canonical bucket repository factories for this operation."""
        self._repository_factory = repository_factory
        self._definition_id = definition_id
        self._calculation_action_ports_factory = calculation_action_ports_factory

    def _service(self, profile_id: UUID, authority: PinnedAuthorityOperation) -> ProrrataRegisterService:
        return ProrrataRegisterService(
            repository=self._repository_factory(bucket_id=str(profile_id)),
            operation=authority,
        )

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Execute one exact-profile request with a truthful terminal effect."""
        shape = _SHAPES.get(self._definition_id)
        if shape is None or type(request.payload) is not shape.request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        if not isinstance(payload, _ProfileRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        profile_id = payload.profile_id
        profile = str(profile_id)
        if (
            request.definition_id != self._definition_id
            or request.subject_ref != profile_operation_subject(profile)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(self._definition_id)

        if self._definition_id == PRORRATA_LIST_OPERATION_DEFINITION_ID:

            async def read() -> str:
                def work() -> ProrrataRegister:
                    with validating_governed_facts(context.authority_operation):
                        return self._service(profile_id, context.authority_operation).list_all()

                register = await asyncio.to_thread(work)
                execution = ProrrataOperationExecutionResult(
                    operation_id="list",
                    profile_id=profile_id,
                    outcome="success",
                    register_snapshot=register,
                    count=len(register.entries),
                )
                reference = await context.operands.put(execution, written_at=now())
                await context.events.effect(OperationEffect.NONE)
                return reference

            return await await_cancellation_complete(read(), task_name="prorrata-list")

        operation_id = _OPERATION_ID_BY_DEFINITION[self._definition_id]
        try:
            with validating_governed_facts(context.authority_operation):
                prepared = self._preflight(operation_id, payload, context)
        except _ProrrataPreflightRefusalError as exc:
            return await self._store_refusal(
                context,
                profile_id=profile_id,
                operation_id=operation_id,
                refusal=_refusal(
                    reason=exc.reason,
                    detail=exc.detail,
                    ejercicio=getattr(payload, "ejercicio", None),
                    sector_id=getattr(payload, "sector_id", None),
                    code=(
                        PRORRATA_ELECTION_REFUSAL_CODE
                        if operation_id in {"elect_especial", "elect_general", "revoke_especial"}
                        and exc.reason in {"provenance_not_electable", "reference_required", "reference_not_permitted"}
                        else PRORRATA_VALIDATION_REFUSAL_CODE
                    ),
                    accepted_provenances=exc.accepted_provenances,
                ),
            )
        except (ProrrataRegisterValidationError, ValidationError) as exc:
            return await self._store_refusal(
                context,
                profile_id=profile_id,
                operation_id=operation_id,
                refusal=_refusal(
                    reason="validation",
                    detail=str(exc),
                    ejercicio=getattr(payload, "ejercicio", None),
                    sector_id=getattr(payload, "sector_id", None),
                ),
            )

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)

                def work() -> _CommittedMutation:
                    with validating_governed_facts(context.authority_operation):
                        service = self._service(profile_id, context.authority_operation)
                        return self._perform_mutation(operation_id, payload, prepared, service, context)

                try:
                    committed = await asyncio.to_thread(work)
                except ProrrataWholeSeedUnavailableError as exc:
                    return await self._persist_refusal(
                        context,
                        profile_id=profile_id,
                        operation_id=operation_id,
                        refusal=_refusal(
                            reason=_from_whole_seed_reason(exc.reason),
                            detail=str(exc),
                            ejercicio=getattr(payload, "ejercicio", None),
                            sector_id=getattr(payload, "sector_id", None),
                            findings=exc.findings,
                            existing_provenance=(
                                exc.existing_provenance.value if exc.existing_provenance is not None else None
                            ),
                            code=PRORRATA_WHOLE_SEED_REFUSAL_CODE,
                        ),
                    )
                except ProrrataSectorLifecycleUnavailableError as exc:
                    reason: ProrrataRefusalReason = (
                        "sector_prior_definitive_absent"
                        if operation_id == "seed_sector"
                        else "sector_settlement_entry_absent"
                    )
                    return await self._persist_refusal(
                        context,
                        profile_id=profile_id,
                        operation_id=operation_id,
                        refusal=_refusal(
                            reason=reason,
                            detail=str(exc),
                            ejercicio=getattr(payload, "ejercicio", None),
                            sector_id=getattr(payload, "sector_id", None),
                            code=PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE,
                        ),
                    )
                except ProrrataRegisterValidationError as exc:
                    # Repository singleton validation runs while rebuilding the
                    # latest candidate, before its revision-guarded write.
                    return await self._persist_refusal(
                        context,
                        profile_id=profile_id,
                        operation_id=operation_id,
                        refusal=_refusal(
                            reason="validation",
                            detail=str(exc),
                            ejercicio=getattr(payload, "ejercicio", None),
                            sector_id=getattr(payload, "sector_id", None),
                        ),
                    )

                execution = ProrrataOperationExecutionResult(
                    operation_id=operation_id,
                    profile_id=profile_id,
                    outcome="success",
                    register_snapshot=committed.register,
                    entry=committed.entry,
                    sector_definition=committed.sector_definition,
                    seed_source=(
                        ProrrataSeedSourceProjection.from_seed(committed.seed) if committed.seed is not None else None
                    ),
                    findings=tuple(ProrrataFindingProjection.from_finding(item) for item in committed.findings),
                    prior_ejercicio=committed.prior_ejercicio,
                    count=(
                        len(committed.register.sector_definitions)
                        if operation_id == "declare_sector"
                        else len(committed.register.entries)
                    ),
                )
                reference = await context.operands.put(execution, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name=f"prorrata-{operation_id}")

    def _preflight(
        self,
        operation_id: ProrrataOperationId,
        payload: BaseModel,
        context: OperationExecutorContext,
    ) -> object:
        if operation_id == "declare_sector" and isinstance(payload, ProrrataDeclareSectorRequest):
            letter = next((item for item in prorrata_sector_letters() if item.value == payload.letra), None)
            if letter is None:
                raise _ProrrataPreflightRefusalError(
                    "validation",
                    "sector letter is not present in the pinned prorrata authority",
                )
            return SectorDefinition(
                sector_id=payload.sector_id,
                letra=letter,
                member_activity_codes=payload.member_activity_codes,
            )
        if operation_id in {"elect_especial", "elect_general", "revoke_especial"}:
            if not isinstance(payload, _ProrrataElectionRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            return _build_election_entry(operation_id, payload)
        if operation_id == "settle_sector" and isinstance(payload, ProrrataSettleSectorRequest):
            # Reject malformed volumes before UNKNOWN. The service still derives
            # the settled entry from the latest CAS candidate during COMMIT.
            from ...domain.iva.prorrata import ProrrataInputs

            ProrrataInputs(
                operaciones_con_derecho_deduccion=Decimal(payload.con_derecho_volume.decimal),
                operaciones_sin_derecho_deduccion=Decimal(payload.sin_derecho_volume.decimal),
            )
            return context.authority_operation.snapshot(
                "303",
                filing_year=payload.ejercicio,
                period="4T",
            ).snapshot_ref
        if operation_id == "seed" and isinstance(payload, ProrrataSeedRequest):
            if self._calculation_action_ports_factory is None:
                raise RuntimeError("whole-entity prorrata seed has no observation source capability")
            return None
        if operation_id == "seed_sector" and isinstance(payload, ProrrataSeedSectorRequest):
            return None
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def _perform_mutation(
        self,
        operation_id: ProrrataOperationId,
        payload: BaseModel,
        prepared: object,
        service: ProrrataRegisterService,
        context: OperationExecutorContext,
    ) -> _CommittedMutation:
        if operation_id == "declare_sector" and isinstance(prepared, SectorDefinition):
            register = service.declare_sector(prepared)
            actual = next(
                (item for item in register.sector_definitions if item.sector_id == prepared.sector_id),
                None,
            )
            if actual is None:
                raise RuntimeError("prorrata sector write returned no matching definition")
            return _CommittedMutation(register=register, sector_definition=actual)
        if operation_id in {"elect_especial", "elect_general", "revoke_especial"} and isinstance(
            prepared, ProrrataRegisterEntry
        ):
            register = (
                service.declare_especial_transition(prepared)
                if prepared.especial_transition is not None
                else service.declare(prepared)
            )
            actual = register.entry_for(prepared.ejercicio, sector_id=prepared.sector_id)
            if actual is None:
                raise RuntimeError("prorrata entry write returned no matching ejercicio/sector row")
            return _CommittedMutation(register=register, entry=actual)
        if operation_id == "seed" and isinstance(payload, ProrrataSeedRequest):
            if self._calculation_action_ports_factory is None:
                raise RuntimeError("whole-entity prorrata seed has no observation source capability")
            calculation_ports = self._calculation_action_ports_factory(
                bucket_id=str(payload.profile_id),
                operation=context.authority_operation,
            )
            observation_repository = calculation_ports.observation_repository
            if not callable(getattr(observation_repository, "load_prior_m303_settlement_snapshot", None)):
                raise RuntimeError("whole-entity prorrata seed has no source-snapshot capability")
            commit = service.seed_whole_carried(
                payload.ejercicio,
                observation_repository=cast(ProrrataPriorSettlementSnapshotRepositoryProtocol, observation_repository),
            )
            return _CommittedMutation(
                register=commit.register,
                entry=commit.seed.entry,
                seed=commit.seed,
                findings=commit.findings,
            )
        if operation_id == "seed_sector" and isinstance(payload, ProrrataSeedSectorRequest):
            register, entry = service.seed_sector_carried(payload.ejercicio, payload.sector_id)
            return _CommittedMutation(register=register, entry=entry, prior_ejercicio=payload.ejercicio - 1)
        if operation_id == "settle_sector" and isinstance(payload, ProrrataSettleSectorRequest):
            if not isinstance(prepared, RegistrySnapshotRef):
                raise RuntimeError("sector settlement preflight did not retain its pinned producing coordinate")
            register, entry = service.settle_sector(
                payload.ejercicio,
                payload.sector_id,
                con_derecho_volume=Decimal(payload.con_derecho_volume.decimal),
                sin_derecho_volume=Decimal(payload.sin_derecho_volume.decimal),
                producing_snapshot_ref=prepared,
            )
            return _CommittedMutation(register=register, entry=entry)
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    async def _store_refusal(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        operation_id: ProrrataOperationId,
        refusal: ProrrataRefusalProjection,
    ) -> OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            return await self._persist_refusal(
                context,
                profile_id=profile_id,
                operation_id=operation_id,
                refusal=refusal,
            )

    async def _persist_refusal(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        operation_id: ProrrataOperationId,
        refusal: ProrrataRefusalProjection,
    ) -> OperationRefusalEvidence:
        result = ProrrataOperationExecutionResult(
            operation_id=operation_id,
            profile_id=profile_id,
            outcome="refused",
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)


_OPERATION_ID_BY_DEFINITION: dict[str, ProrrataOperationId] = {
    PRORRATA_LIST_OPERATION_DEFINITION_ID: "list",
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID: "declare_sector",
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID: "elect_especial",
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID: "elect_general",
    PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID: "revoke_especial",
    PRORRATA_SEED_OPERATION_DEFINITION_ID: "seed",
    PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID: "seed_sector",
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID: "settle_sector",
}


def _copy_private_result(result: BaseModel) -> ProrrataOperationExecutionResult:
    if type(result) is not ProrrataOperationExecutionResult:
        raise ValueError("prorrata execution result has an incompatible type")
    return ProrrataOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def _receipt_matches(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    outcome: Literal["success", "refused"],
    operation_id: ProrrataOperationId,
    refusal_code: str | None = None,
) -> None:
    refused = outcome == "refused"
    expected_effect = OperationEffect.NONE if refused or operation_id == "list" else OperationEffect.UPDATED
    expected_condition = OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED
    expected_refusal = refusal_code if refused else None
    if (
        receipt.identity.definition_id != definition_id
        or receipt.identity.subject_ref != profile_operation_subject(str(profile_id))
        or receipt.condition is not expected_condition
        or receipt.effect is not expected_effect
        or receipt.refusal_ref != expected_refusal
        or (receipt.refusal_detail_ref is not None) != refused
        or (receipt.result_ref is not None) == refused
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("prorrata projection differs from its terminal receipt")


def project_prorrata_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> ProrrataListProjection:
    """Project every persisted entry and sector from an exact-profile list result."""
    private = _copy_private_result(result)
    profile_id = _profile_id_from_receipt(receipt, definition_id=PRORRATA_LIST_OPERATION_DEFINITION_ID)
    if (
        private.operation_id != "list"
        or private.profile_id != profile_id
        or private.outcome != "success"
        or private.register_snapshot is None
        or private.count != len(private.register_snapshot.entries)
        or private.entry is not None
        or private.sector_definition is not None
        or private.seed_source is not None
        or private.findings
        or private.refusal is not None
    ):
        raise ValueError("prorrata list result has an incompatible payload")
    _receipt_matches(
        receipt,
        definition_id=PRORRATA_LIST_OPERATION_DEFINITION_ID,
        profile_id=profile_id,
        outcome="success",
        operation_id="list",
    )
    return ProrrataListProjection(
        profile_id=profile_id,
        entries=tuple(ProrrataEntryProjection.from_entry(entry) for entry in private.register_snapshot.entries),
        sectors=tuple(
            ProrrataSectorDefinitionProjection.from_definition(sector)
            for sector in private.register_snapshot.sector_definitions
        ),
        count=len(private.register_snapshot.entries),
    )


def project_prorrata_mutation_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> ProrrataMutationProjection:
    """Project one complete mutation result or its accurate NONE-effect refusal."""
    private = _copy_private_result(result)
    definition_id = receipt.identity.definition_id
    operation_id = _OPERATION_ID_BY_DEFINITION.get(definition_id)
    if operation_id is None or operation_id == "list":
        raise ValueError("prorrata mutation result has an unknown operation definition")
    profile_id = _profile_id_from_receipt(receipt, definition_id=definition_id)
    if private.operation_id != operation_id or private.profile_id != profile_id:
        raise ValueError("prorrata mutation result crossed its profile or operation identity")
    if private.outcome == "refused":
        refusal = private.refusal
        if refusal is None or refusal.code not in _SHAPES[definition_id].refusal_codes:
            raise ValueError("prorrata refusal result has an unregistered code")
        _receipt_matches(
            receipt,
            definition_id=definition_id,
            profile_id=profile_id,
            outcome="refused",
            operation_id=operation_id,
            refusal_code=refusal.code,
        )
        return ProrrataMutationProjection(
            operation_id=operation_id,
            profile_id=profile_id,
            outcome="refused",
            refusal=refusal,
        )
    _receipt_matches(
        receipt,
        definition_id=definition_id,
        profile_id=profile_id,
        outcome=private.outcome,
        operation_id=operation_id,
    )
    register = private.register_snapshot
    if register is None or private.count is None:
        raise ValueError("prorrata success result omitted its committed register")
    if operation_id == "declare_sector":
        sector = private.sector_definition
        if (
            sector is None
            or private.entry is not None
            or private.count != len(register.sector_definitions)
            or not any(row == sector for row in register.sector_definitions)
        ):
            raise ValueError("prorrata sector result contradicts the committed register")
        return ProrrataMutationProjection(
            operation_id=operation_id,
            profile_id=profile_id,
            outcome="success",
            sector_definition=ProrrataSectorDefinitionProjection.from_definition(sector),
            count=private.count,
        )
    entry = private.entry
    if (
        entry is None
        or private.count != len(register.entries)
        or not any(row == entry for row in register.entries)
        or private.sector_definition is not None
    ):
        raise ValueError("prorrata entry result contradicts the committed register")
    if operation_id == "seed" and private.seed_source is None:
        raise ValueError("whole-entity prorrata seed omitted source identity")
    if operation_id != "seed" and private.seed_source is not None:
        raise ValueError("non-seed prorrata result contains source identity")
    return ProrrataMutationProjection(
        operation_id=operation_id,
        profile_id=profile_id,
        outcome="success",
        entry=ProrrataEntryProjection.from_entry(entry),
        seed_source=private.seed_source,
        findings=private.findings,
        prior_ejercicio=private.prior_ejercicio,
        count=private.count,
    )


def _shape_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    mutation: bool,
) -> ResolvedOperationAccess:
    shape = _SHAPES.get(definition_id)
    payload = request.payload
    if shape is None or type(payload) is not shape.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if request.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(payload, _ProfileRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())
    if not mutation:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}},
    )
    return replace(resolved, policy=policy)


def resolve_prorrata_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind each prorrata operation to complete all-period profile access."""
    shape = _SHAPES.get(request.definition_id)
    if shape is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _shape_access(request, context, definition_id=request.definition_id, mutation=shape.mutation)


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    repository_factory: ProrrataRegisterRepositoryFactory,
    *,
    calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
) -> OperationDefinition:
    shape = _SHAPES[definition_id]
    if shape.request_type is not request_type:
        raise ValueError("prorrata operation request differs from its closed registration schema")
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=ProrrataOperationExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=ProrrataOperationExecutor,
            build=lambda: ProrrataOperationExecutor(
                repository_factory,
                definition_id=definition_id,
                calculation_action_ports_factory=calculation_action_ports_factory,
            ),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP},
        ),
        refusal_detail_codes=shape.refusal_codes,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    projection_type: type[BaseModel],
    projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    shape = _SHAPES[definition.definition_id]
    if shape.request_type is not request_type or shape.projection_type is not projection_type:
        raise ValueError("prorrata registration does not match its closed public schema")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=projection_type,
        ),
        access_resolver=resolve_prorrata_operation_access,
        result_projector=projector,
    )


def build_prorrata_list_definition(repository_factory: ProrrataRegisterRepositoryFactory) -> OperationDefinition:
    """Build the complete profile prorrata-list definition."""
    return _definition(PRORRATA_LIST_OPERATION_DEFINITION_ID, ProrrataListRequest, repository_factory)


def build_prorrata_declare_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded differentiated-sector declaration definition."""
    return _definition(
        PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
        ProrrataDeclareSectorRequest,
        repository_factory,
    )


def build_prorrata_elect_especial_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded special-prorrata election definition."""
    return _definition(
        PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
        ProrrataElectEspecialRequest,
        repository_factory,
    )


def build_prorrata_elect_general_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded general-prorrata election definition."""
    return _definition(PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID, ProrrataElectGeneralRequest, repository_factory)


def build_prorrata_revoke_especial_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded evidence-backed special-prorrata revocation definition."""
    return _definition(
        PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
        ProrrataRevokeEspecialRequest,
        repository_factory,
    )


def build_prorrata_seed_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
    calculation_action_ports_factory: CalculationActionPortsFactory,
) -> OperationDefinition:
    """Build the source-fenced whole-entity carried-seed definition."""
    return _definition(
        PRORRATA_SEED_OPERATION_DEFINITION_ID,
        ProrrataSeedRequest,
        repository_factory,
        calculation_action_ports_factory=calculation_action_ports_factory,
    )


def build_prorrata_seed_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate per-sector carried-seed definition."""
    return _definition(
        PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
        ProrrataSeedSectorRequest,
        repository_factory,
    )


def build_prorrata_settle_sector_definition(
    repository_factory: ProrrataRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the latest-candidate year-end sector settlement definition."""
    return _definition(
        PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
        ProrrataSettleSectorRequest,
        repository_factory,
    )


def build_prorrata_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the list result to its complete all-period disclosure projection."""
    return _registration(
        definition,
        request_type=ProrrataListRequest,
        projection_type=ProrrataListProjection,
        projector=project_prorrata_list_result,
    )


def build_prorrata_mutation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind one complete mutation result and truthful refusal projection."""
    return _registration(
        definition,
        request_type=_SHAPES[definition.definition_id].request_type,
        projection_type=ProrrataMutationProjection,
        projector=project_prorrata_mutation_result,
    )


__all__ = [
    "PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID",
    "PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID",
    "PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID",
    "PRORRATA_LIST_OPERATION_DEFINITION_ID",
    "PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID",
    "PRORRATA_SEED_OPERATION_DEFINITION_ID",
    "PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID",
    "PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID",
    "PRORRATA_VALIDATION_REFUSAL_CODE",
    "ProrrataDeclareSectorRequest",
    "ProrrataElectEspecialRequest",
    "ProrrataElectGeneralRequest",
    "ProrrataEntryProjection",
    "ProrrataFindingProjection",
    "ProrrataListProjection",
    "ProrrataListRequest",
    "ProrrataMutationProjection",
    "ProrrataOperationExecutionResult",
    "ProrrataOperationExecutor",
    "ProrrataRefusalProjection",
    "ProrrataRevokeEspecialRequest",
    "ProrrataSectorDefinitionProjection",
    "ProrrataSeedRequest",
    "ProrrataSeedSectorRequest",
    "ProrrataSeedSourceProjection",
    "ProrrataSettleSectorRequest",
    "ProrrataSnapshotRefProjection",
    "build_prorrata_declare_sector_definition",
    "build_prorrata_elect_especial_definition",
    "build_prorrata_elect_general_definition",
    "build_prorrata_list_definition",
    "build_prorrata_list_registration",
    "build_prorrata_mutation_registration",
    "build_prorrata_revoke_especial_definition",
    "build_prorrata_seed_definition",
    "build_prorrata_seed_sector_definition",
    "build_prorrata_settle_sector_definition",
    "project_prorrata_list_result",
    "project_prorrata_mutation_result",
    "resolve_prorrata_operation_access",
]
