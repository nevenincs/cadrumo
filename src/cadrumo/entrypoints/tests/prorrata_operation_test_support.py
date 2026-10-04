"""Canonical encrypted-profile fixtures for prorrata operation conformance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ...adapters.persistence.profile.tests.modelo_303_filed_disposition import modelo_303_filed_disposition
from ...application.calculations.observations_repository import CalculationObservationRepositoryProtocol
from ...application.operations.public_scalar import PublicDecimal
from ...application.prorrata_register.operation_requests import (
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
    PRORRATA_LIST_OPERATION_DEFINITION_ID,
    PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataElectGeneralRequest,
    ProrrataListRequest,
    ProrrataRevokeEspecialRequest,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSettleSectorRequest,
)
from ...application.prorrata_register.ports import ProrrataRegisterRepositoryFactory
from ...application.prorrata_register.projection_contracts import (
    ProrrataEntryProjection,
    ProrrataFindingProjection,
    ProrrataListProjection,
    ProrrataMutationProjection,
    ProrrataSectorDefinitionProjection,
    ProrrataSeedSourceProjection,
)
from ...application.prorrata_register.sector_lifecycle import (
    seed_sector_carried_definitive_from_register,
    settle_sector_definitive,
)
from ...application.prorrata_register.seed import (
    ProrrataPriorDefinitivaSeed,
    ProrrataSeedFinding,
    cross_check_prorrata_entry_against_observations,
    evaluate_carried_prior_definitiva_seed_from_observations,
)
from ...application.prorrata_register.service import ProrrataRegisterService
from ...application.prorrata_register.tests.provisional_override import record_aeat_autorizada
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.modelo import Modelo
from ...core.operations import OperationEffect
from ...core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.prorrata_register_catalogue import (
    aeat_autorizada_prorrata_provenance,
    carried_prior_definitiva_prorrata_provenance,
    especial_prorrata_register_regime,
    general_prorrata_register_regime,
    opcion_prorrata_transition,
    prorrata_sector_letters,
    revocacion_prorrata_transition,
)
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.calculations.registry.tests.registry_observations import registry_grounded_modelo_observation
from ...domain.prorrata_register.register import (
    ProrrataEspecialTransitionEvidence,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)

_CAPTURED_AT = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_SOURCE_KIND = "aeat_sede_justificante"
_SEED_TARGET_YEAR = 2026
_SEED_PRIOR_YEAR = _SEED_TARGET_YEAR - 1
_SEED_SETTLEMENT_PERIOD = "4T"
_SEED_PERCENTAGE = Decimal("87.25")
_PRORRATA_PERCENTAGE_ID: CasillaId = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="registered prorrata operation conformance seed",
)
_OPERATION_IDS: dict[
    str,
    tuple[
        Literal[
            "list",
            "declare_sector",
            "elect_especial",
            "elect_general",
            "revoke_especial",
            "seed",
            "seed_sector",
            "settle_sector",
        ],
        str,
    ],
] = {
    PRORRATA_LIST_OPERATION_DEFINITION_ID: ("list", "ledger.prorrata.list"),
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID: ("declare_sector", "ledger.prorrata.declare_sector"),
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID: ("elect_especial", "ledger.prorrata.elect_especial"),
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID: ("elect_general", "ledger.prorrata.elect_general"),
    PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID: ("revoke_especial", "ledger.prorrata.revoke_especial"),
    PRORRATA_SEED_OPERATION_DEFINITION_ID: ("seed", "ledger.prorrata.seed"),
    PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID: ("seed_sector", "ledger.prorrata.seed_sector"),
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID: ("settle_sector", "ledger.prorrata.settle_sector"),
}


@dataclass(frozen=True, slots=True)
class ProrrataOperationConformanceCase:
    """One typed request and its canonical projection and encrypted post-state."""

    definition_id: str
    operation_id: str
    request: BaseModel
    expected_effect: OperationEffect
    expected_count: int
    expected_register: ProrrataRegister
    expected_projection: ProrrataListProjection | ProrrataMutationProjection
    expected_entry: ProrrataRegisterEntry | None = None
    expected_sector_definition: SectorDefinition | None = None
    expected_seed: ProrrataPriorDefinitivaSeed | None = None


@dataclass(frozen=True, slots=True)
class ProrrataWholeSeedRefusalCase:
    """A source-backed pre-existing register state and its whole-seed refusal facts."""

    request: ProrrataSeedRequest
    expected_register: ProrrataRegister
    expected_reason: Literal["regulated_override_standing", "seed_existing_blocked"]
    expected_provenance: str | None
    expected_findings: tuple[ProrrataFindingProjection, ...]


def _service(
    profile_id: UUID,
    *,
    repository_factory: ProrrataRegisterRepositoryFactory,
    operation: PinnedAuthorityOperation,
) -> ProrrataRegisterService:
    return ProrrataRegisterService(
        repository=repository_factory(bucket_id=str(profile_id)),
        operation=operation,
    )


def _snapshot(operation: PinnedAuthorityOperation, year: int) -> RegistrySnapshotRef:
    return operation.snapshot(Modelo("303").value, filing_year=year, period="4T").snapshot_ref


def _sector_definition(sector_id: str = "sector-conformance") -> SectorDefinition:
    letters = prorrata_sector_letters()
    if not letters:
        raise AssertionError("published prorrata authority has no differentiated-sector letter")
    return SectorDefinition(
        sector_id=sector_id,
        letra=letters[0],
        member_activity_codes=("4711", "4719"),
    )


def _entry(
    *,
    year: int,
    regime: ProrrataRegisterRegime,
    provenance: ProrrataProvisionalProvenance,
    percentage: Decimal,
    authorisation_reference: str | None = None,
    sector_id: str | None = None,
    transition: ProrrataEspecialTransitionEvidence | None = None,
    source_observation_ref: str | None = None,
    source_registry_snapshot_refs: tuple[RegistrySnapshotRef, ...] = (),
) -> ProrrataRegisterEntry:
    return ProrrataRegisterEntry(
        ejercicio=year,
        regime=regime,
        especial_transition=transition,
        sector_id=sector_id,
        provisional_percentage=percentage,
        provisional_provenance=provenance,
        authorisation_reference=authorisation_reference,
        source_observation_ref=source_observation_ref,
        source_registry_snapshot_refs=source_registry_snapshot_refs,
    )


def _register_with_entry(register: ProrrataRegister, entry: ProrrataRegisterEntry) -> ProrrataRegister:
    key = (entry.ejercicio, entry.sector_id)
    retained = tuple(row for row in register.entries if (row.ejercicio, row.sector_id) != key)
    return ProrrataRegister(
        entries=(*retained, entry),
        sector_definitions=register.sector_definitions,
        activity_rows=register.activity_rows,
    )


def _register_with_sector(register: ProrrataRegister, definition: SectorDefinition) -> ProrrataRegister:
    retained = tuple(row for row in register.sector_definitions if row.sector_id != definition.sector_id)
    return ProrrataRegister(
        entries=register.entries,
        sector_definitions=(*retained, definition),
        activity_rows=register.activity_rows,
    )


def _list_projection(profile_id: UUID, register: ProrrataRegister) -> ProrrataListProjection:
    return ProrrataListProjection(
        profile_id=profile_id,
        entries=tuple(ProrrataEntryProjection.from_entry(entry) for entry in register.entries),
        sectors=tuple(
            ProrrataSectorDefinitionProjection.from_definition(definition) for definition in register.sector_definitions
        ),
        count=len(register.entries),
    )


def _mutation_projection(
    *,
    definition_id: str,
    profile_id: UUID,
    register: ProrrataRegister,
    entry: ProrrataRegisterEntry | None = None,
    sector_definition: SectorDefinition | None = None,
    seed: ProrrataPriorDefinitivaSeed | None = None,
    findings: tuple[ProrrataSeedFinding, ...] = (),
    prior_ejercicio: int | None = None,
) -> ProrrataMutationProjection:
    operation_id = _OPERATION_IDS[definition_id][0]
    return ProrrataMutationProjection(
        operation_id=operation_id,
        profile_id=profile_id,
        outcome="success",
        entry=ProrrataEntryProjection.from_entry(entry) if entry is not None else None,
        sector_definition=(
            ProrrataSectorDefinitionProjection.from_definition(sector_definition)
            if sector_definition is not None
            else None
        ),
        seed_source=ProrrataSeedSourceProjection.from_seed(seed) if seed is not None else None,
        findings=tuple(ProrrataFindingProjection.from_finding(finding) for finding in findings),
        prior_ejercicio=prior_ejercicio,
        count=(len(register.sector_definitions) if operation_id == "declare_sector" else len(register.entries)),
    )


def _save_prior_settlement_observation(
    profile_id: UUID,
    *,
    observation_repository: CalculationObservationRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> None:
    stamped_revision_id = str(_snapshot(operation, _SEED_PRIOR_YEAR).revision_id)
    values, headers = modelo_303_filed_disposition(
        {_PRORRATA_PERCENTAGE_ID: _SEED_PERCENTAGE},
        source_locator="registered-prorrata-conformance:prior-settlement",
    )
    observation = registry_grounded_modelo_observation(
        modelo=Modelo("303").value,
        filing_year=_SEED_PRIOR_YEAR,
        period=_SEED_SETTLEMENT_PERIOD,
        casilla_values=values,
    )
    if not isinstance(observation_repository, CalculationObservationRepository):
        raise TypeError("prorrata seed conformance requires the encrypted calculation-observation adapter")
    observation_repository.save(
        observation_repository.prepare_observation_envelope(
            observation,
            source_kind=_SOURCE_KIND,
            captured_at=_CAPTURED_AT,
            source_headers=headers,
            stamped_revision_id=stamped_revision_id,
        )
    )


def _prepare_case(
    definition_id: str,
    profile_id: UUID,
    *,
    repository_factory: ProrrataRegisterRepositoryFactory,
    operation: PinnedAuthorityOperation,
    observation_repository: CalculationObservationRepositoryProtocol | None,
) -> ProrrataOperationConformanceCase:
    operation_id, _ = _OPERATION_IDS[definition_id]
    service = _service(profile_id, repository_factory=repository_factory, operation=operation)
    request: BaseModel
    expected_entry: ProrrataRegisterEntry | None = None
    expected_sector: SectorDefinition | None = None
    expected_seed: ProrrataPriorDefinitivaSeed | None = None
    findings = ()
    prior_ejercicio = None

    if definition_id == PRORRATA_LIST_OPERATION_DEFINITION_ID:
        sector = _sector_definition()
        entry = _entry(
            year=2025,
            regime=general_prorrata_register_regime(),
            provenance=carried_prior_definitiva_prorrata_provenance(),
            percentage=Decimal("76.50"),
            source_observation_ref="303:2024:4T",
            source_registry_snapshot_refs=(_snapshot(operation, 2024),),
        )
        service.declare_sector(sector)
        service.declare(entry)
        register = service.list_all()
        request = ProrrataListRequest(profile_id=profile_id)
        projection: ProrrataListProjection | ProrrataMutationProjection = _list_projection(profile_id, register)
        expected_count = len(register.entries)
        return ProrrataOperationConformanceCase(
            definition_id=definition_id,
            operation_id=operation_id,
            request=request,
            expected_effect=OperationEffect.NONE,
            expected_count=expected_count,
            expected_register=register,
            expected_projection=projection,
        )

    register = service.list_all()
    if definition_id == PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID:
        expected_sector = _sector_definition()
        register = _register_with_sector(register, expected_sector)
        request = ProrrataDeclareSectorRequest(
            profile_id=profile_id,
            sector_id=expected_sector.sector_id,
            letra=expected_sector.letra.value,
            member_activity_codes=expected_sector.member_activity_codes,
        )
    elif definition_id == PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID:
        expected_entry = _entry(
            year=2026,
            regime=especial_prorrata_register_regime(),
            provenance=aeat_autorizada_prorrata_provenance(),
            percentage=Decimal("64.25"),
            authorisation_reference="AEAT-PRORRATA-CONFORMANCE-2026",
            transition=ProrrataEspecialTransitionEvidence(
                kind=opcion_prorrata_transition(),
                evidence_reference="option-evidence-conformance-2026",
            ),
        )
        request = ProrrataElectEspecialRequest(
            profile_id=profile_id,
            ejercicio=2026,
            percentage=PublicDecimal(decimal="64.25"),
            provenance=aeat_autorizada_prorrata_provenance().value,
            reference="AEAT-PRORRATA-CONFORMANCE-2026",
            evidence_reference="option-evidence-conformance-2026",
        )
        register = _register_with_entry(register, expected_entry)
    elif definition_id == PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID:
        expected_entry = _entry(
            year=2026,
            regime=general_prorrata_register_regime(),
            provenance=aeat_autorizada_prorrata_provenance(),
            percentage=Decimal("63.75"),
            authorisation_reference="AEAT-PRORRATA-CONFORMANCE-GENERAL-2026",
        )
        request = ProrrataElectGeneralRequest(
            profile_id=profile_id,
            ejercicio=2026,
            percentage=PublicDecimal(decimal="63.75"),
            provenance=aeat_autorizada_prorrata_provenance().value,
            reference="AEAT-PRORRATA-CONFORMANCE-GENERAL-2026",
        )
        register = _register_with_entry(register, expected_entry)
    elif definition_id == PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID:
        previous = _entry(
            year=2025,
            regime=especial_prorrata_register_regime(),
            provenance=aeat_autorizada_prorrata_provenance(),
            percentage=Decimal("60"),
            authorisation_reference="AEAT-PRORRATA-CONFORMANCE-SPECIAL-2025",
            transition=ProrrataEspecialTransitionEvidence(
                kind=opcion_prorrata_transition(),
                evidence_reference="option-evidence-conformance-2025",
            ),
        )
        service.declare_especial_transition(previous)
        register = service.list_all()
        expected_entry = _entry(
            year=2026,
            regime=general_prorrata_register_regime(),
            provenance=aeat_autorizada_prorrata_provenance(),
            percentage=Decimal("60"),
            authorisation_reference="AEAT-PRORRATA-CONFORMANCE-REVOKE-2026",
            transition=ProrrataEspecialTransitionEvidence(
                kind=revocacion_prorrata_transition(),
                evidence_reference="revocation-evidence-conformance-2026",
            ),
        )
        request = ProrrataRevokeEspecialRequest(
            profile_id=profile_id,
            ejercicio=2026,
            percentage=PublicDecimal(decimal="60"),
            provenance=aeat_autorizada_prorrata_provenance().value,
            reference="AEAT-PRORRATA-CONFORMANCE-REVOKE-2026",
            evidence_reference="revocation-evidence-conformance-2026",
        )
        register = _register_with_entry(register, expected_entry)
    elif definition_id == PRORRATA_SEED_OPERATION_DEFINITION_ID:
        observations = observation_repository or CalculationObservationRepository(bucket_id=str(profile_id))
        _save_prior_settlement_observation(
            profile_id,
            observation_repository=observations,
            operation=operation,
        )
        evaluation = evaluate_carried_prior_definitiva_seed_from_observations(
            ejercicio=_SEED_TARGET_YEAR,
            observations=tuple(observations.iter_modelo(Modelo("303").value)),
            operation=operation,
        )
        if evaluation.seed is None or evaluation.blocked:
            raise AssertionError("canonical conformance observation did not produce a whole-entity seed")
        expected_seed = evaluation.seed
        expected_entry = expected_seed.entry
        findings = evaluation.findings
        register = _register_with_entry(register, expected_entry)
        request = ProrrataSeedRequest(
            profile_id=profile_id,
            ejercicio=_SEED_TARGET_YEAR,
        )
    elif definition_id == PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID:
        sector = _sector_definition()
        service.declare_sector(sector)
        prior = _entry(
            year=2025,
            regime=general_prorrata_register_regime(),
            provenance=aeat_autorizada_prorrata_provenance(),
            percentage=Decimal("61"),
            authorisation_reference="AEAT-PRORRATA-SECTOR-2025",
            sector_id=sector.sector_id,
        )
        service.declare(prior)
        service.settle_sector(
            2025,
            sector.sector_id,
            con_derecho_volume=Decimal("125.00"),
            sin_derecho_volume=Decimal("75.00"),
            producing_snapshot_ref=_snapshot(operation, 2025),
        )
        register = service.list_all()
        expected_entry = seed_sector_carried_definitive_from_register(
            register,
            ejercicio=_SEED_TARGET_YEAR,
            sector_id=sector.sector_id,
        )
        if expected_entry is None:
            raise AssertionError("canonical sector settlement did not produce a prior definitive")
        prior_ejercicio = _SEED_PRIOR_YEAR
        register = _register_with_entry(register, expected_entry)
        request = ProrrataSeedSectorRequest(
            profile_id=profile_id,
            ejercicio=_SEED_TARGET_YEAR,
            sector_id=sector.sector_id,
        )
    elif definition_id == PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID:
        sector = _sector_definition()
        service.declare_sector(sector)
        provisional = _entry(
            year=_SEED_TARGET_YEAR,
            regime=general_prorrata_register_regime(),
            provenance=aeat_autorizada_prorrata_provenance(),
            percentage=Decimal("59.75"),
            authorisation_reference="AEAT-PRORRATA-SETTLE-2026",
            sector_id=sector.sector_id,
        )
        service.declare(provisional)
        con_derecho = Decimal("135.50")
        sin_derecho = Decimal("64.50")
        producing_snapshot = _snapshot(operation, _SEED_TARGET_YEAR)
        expected_entry = settle_sector_definitive(
            provisional,
            con_derecho_volume=con_derecho,
            sin_derecho_volume=sin_derecho,
            producing_snapshot_ref=producing_snapshot,
        )
        register = _register_with_entry(service.list_all(), expected_entry)
        request = ProrrataSettleSectorRequest(
            profile_id=profile_id,
            ejercicio=_SEED_TARGET_YEAR,
            sector_id=sector.sector_id,
            con_derecho_volume=PublicDecimal(decimal=str(con_derecho)),
            sin_derecho_volume=PublicDecimal(decimal=str(sin_derecho)),
        )
    else:
        raise ValueError(f"unsupported prorrata operation definition: {definition_id}")

    if definition_id == PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID:
        expected_count = len(register.sector_definitions)
    else:
        expected_count = len(register.entries)
    projection = _mutation_projection(
        definition_id=definition_id,
        profile_id=profile_id,
        register=register,
        entry=expected_entry,
        sector_definition=expected_sector,
        seed=expected_seed,
        findings=findings,
        prior_ejercicio=prior_ejercicio,
    )
    return ProrrataOperationConformanceCase(
        definition_id=definition_id,
        operation_id=operation_id,
        request=request,
        expected_effect=OperationEffect.UPDATED,
        expected_count=expected_count,
        expected_register=register,
        expected_projection=projection,
        expected_entry=expected_entry,
        expected_sector_definition=expected_sector,
        expected_seed=expected_seed,
    )


def prepare_prorrata_operation_conformance_case(
    definition_id: str,
    profile_id: UUID,
    *,
    repository_factory: ProrrataRegisterRepositoryFactory,
    operation: PinnedAuthorityOperation,
    observation_repository: CalculationObservationRepositoryProtocol | None = None,
) -> ProrrataOperationConformanceCase:
    """Prepare canonical requests, real prerequisites, and expected projections."""
    if definition_id not in _OPERATION_IDS:
        raise ValueError(f"unsupported prorrata operation definition: {definition_id}")
    with validating_governed_facts(operation):
        return _prepare_case(
            definition_id,
            profile_id,
            repository_factory=repository_factory,
            operation=operation,
            observation_repository=observation_repository,
        )


def prepare_prorrata_whole_seed_refusal_case(
    profile_id: UUID,
    *,
    repository_factory: ProrrataRegisterRepositoryFactory,
    operation: PinnedAuthorityOperation,
    observation_repository: CalculationObservationRepositoryProtocol | None = None,
    refusal_reason: Literal["regulated_override_standing", "seed_existing_blocked"],
) -> ProrrataWholeSeedRefusalCase:
    """Persist source and target facts that drive one exact whole-seed refusal."""
    observations = observation_repository or CalculationObservationRepository(bucket_id=str(profile_id))
    with validating_governed_facts(operation):
        _save_prior_settlement_observation(
            profile_id,
            observation_repository=observations,
            operation=operation,
        )
        service = _service(profile_id, repository_factory=repository_factory, operation=operation)
        expected_provenance: str | None = None
        if refusal_reason == "regulated_override_standing":
            register = record_aeat_autorizada(
                service,
                ejercicio=_SEED_TARGET_YEAR,
                provisional_percentage=Decimal("55.00"),
                authorisation_reference="AEAT-PRORRATA-STANDING-2026",
            )
            standing = register.entry_for(_SEED_TARGET_YEAR)
            if standing is None or standing.provisional_provenance is None:
                raise AssertionError("canonical AEAT override fixture did not persist its provenance")
            expected_provenance = standing.provisional_provenance.value
            expected_findings = cross_check_prorrata_entry_against_observations(
                standing,
                observations=tuple(observations.iter_modelo(Modelo("303").value)),
                operation=operation,
            )
        else:
            evaluation = evaluate_carried_prior_definitiva_seed_from_observations(
                ejercicio=_SEED_TARGET_YEAR,
                observations=tuple(observations.iter_modelo(Modelo("303").value)),
                operation=operation,
            )
            if evaluation.seed is None or evaluation.blocked:
                raise AssertionError("canonical conformance observation did not produce a whole-entity seed")
            contradictory = evaluation.seed.entry.model_copy(update={"provisional_percentage": Decimal("42.00")})
            register = service.declare(contradictory)
            expected_findings = cross_check_prorrata_entry_against_observations(
                contradictory,
                observations=tuple(observations.iter_modelo(Modelo("303").value)),
                operation=operation,
            )
            if not any(finding.blocking for finding in expected_findings):
                raise AssertionError("carried contradiction fixture did not produce a blocking finding")
        return ProrrataWholeSeedRefusalCase(
            request=ProrrataSeedRequest(profile_id=profile_id, ejercicio=_SEED_TARGET_YEAR),
            expected_register=register,
            expected_reason=refusal_reason,
            expected_provenance=expected_provenance,
            expected_findings=tuple(ProrrataFindingProjection.from_finding(item) for item in expected_findings),
        )


def read_prorrata_operation_conformance_register(
    profile_id: UUID,
    *,
    repository_factory: ProrrataRegisterRepositoryFactory,
    operation: PinnedAuthorityOperation,
) -> ProrrataRegister:
    """Read the complete post-state from the exact encrypted profile repository."""
    with validating_governed_facts(operation):
        return _service(profile_id, repository_factory=repository_factory, operation=operation).list_all()


__all__ = [
    "ProrrataOperationConformanceCase",
    "ProrrataWholeSeedRefusalCase",
    "prepare_prorrata_operation_conformance_case",
    "prepare_prorrata_whole_seed_refusal_case",
    "read_prorrata_operation_conformance_register",
]
