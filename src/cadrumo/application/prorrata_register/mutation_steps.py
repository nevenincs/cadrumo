"""Prorrata mutation preflight and persistence stages."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import cast

from pydantic import BaseModel, ValidationError

from ...core.errors.hierarchy import CadrumoError, InternalInvariantError
from ...core.prorrata_register import ProrrataProvisionalProvenance, ProrrataRegisterRegime
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
from ..modelo.calculation_action_ports import CalculationActionPortsFactory
from ..operations.owner import OperationExecutorContext
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from . import operation_requests as _requests
from .election import ProrrataElectionError
from .ports import ProrrataPriorSettlementSnapshotRepositoryProtocol
from .projection_contracts import (
    PRORRATA_VALIDATION_REFUSAL_CODE as _PRORRATA_VALIDATION_REFUSAL_CODE,
)
from .projection_contracts import (
    ProrrataFindingProjection as _ProrrataFindingProjection,
)
from .projection_contracts import ProrrataRefusalCode as _ProrrataRefusalCode
from .projection_contracts import (
    ProrrataRefusalProjection as _ProrrataRefusalProjection,
)
from .projection_contracts import (
    ProrrataRefusalReason as _ProrrataRefusalReason,
)
from .seed import ProrrataPriorDefinitivaSeed, ProrrataSeedFinding
from .service import (
    ProrrataRegisterService,
    ProrrataWholeSeedUnavailableReason,
)


@dataclass(frozen=True, slots=True)
class CommittedProrrataMutation:
    """Committed register snapshot and operation-specific result rows."""

    register: ProrrataRegister
    entry: ProrrataRegisterEntry | None = None
    sector_definition: SectorDefinition | None = None
    seed: ProrrataPriorDefinitivaSeed | None = None
    findings: tuple[ProrrataSeedFinding, ...] = ()
    prior_ejercicio: int | None = None


class ProrrataPreflightRefusalError(CadrumoError):
    """Known validation refusal raised before the mutation's write section."""

    reason: _ProrrataRefusalReason
    detail: str
    accepted_provenances: tuple[str, ...]

    def __init__(
        self,
        reason: _ProrrataRefusalReason,
        detail: str,
        *,
        accepted_provenances: tuple[str, ...] = (),
    ) -> None:
        """Retain the public refusal reason and accepted provenance set."""
        self.reason = reason
        self.detail = detail
        self.accepted_provenances = accepted_provenances
        super().__init__(detail)


def build_prorrata_refusal_projection(
    *,
    reason: _ProrrataRefusalReason,
    detail: str,
    ejercicio: int | None = None,
    sector_id: str | None = None,
    findings: tuple[ProrrataSeedFinding, ...] = (),
    accepted_provenances: tuple[str, ...] = (),
    existing_provenance: str | None = None,
    code: _ProrrataRefusalCode = _PRORRATA_VALIDATION_REFUSAL_CODE,
) -> _ProrrataRefusalProjection:
    """Create the typed refusal projection with its safe contextual evidence."""
    return _ProrrataRefusalProjection(
        code=code,
        reason=reason,
        detail=detail,
        ejercicio=ejercicio,
        sector_id=sector_id,
        findings=tuple(_ProrrataFindingProjection.from_finding(item) for item in findings),
        accepted_provenances=accepted_provenances,
        existing_provenance=existing_provenance,
    )


def _build_election_entry(
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataElectionRequest,
) -> ProrrataRegisterEntry:
    provenance, reference = _resolve_election_authority(payload)
    regime, transition = _election_regime_transition(operation_id, payload)
    return _create_election_entry(
        payload, provenance=provenance, reference=reference, regime=regime, transition=transition
    )


def _resolve_election_authority(
    payload: _requests.ProrrataElectionRequest,
) -> tuple[ProrrataProvisionalProvenance, str | None]:
    carried = carried_prior_definitiva_prorrata_provenance()
    accepted_provenances = tuple(item.value for item in prorrata_electable_provenances() if item != carried)
    if payload.provenance is None:
        raise ProrrataPreflightRefusalError(
            "provenance_required",
            "manual prorrata election requires evidence provenance",
            accepted_provenances=accepted_provenances,
        )
    try:
        provenance = require_prorrata_provenance(payload.provenance)
    except ProrrataRegisterValidationError as exc:
        raise ProrrataPreflightRefusalError(
            "provenance_not_electable",
            str(exc),
            accepted_provenances=accepted_provenances,
        ) from exc
    if provenance == carried:
        raise ProrrataPreflightRefusalError(
            "provenance_required",
            "carried prior definitive must use the seed operation",
            accepted_provenances=accepted_provenances,
        )
    try:
        from .election import validate_prorrata_election

        provenance, reference = validate_prorrata_election(provenance=provenance, reference=payload.reference)
    except ProrrataElectionError as exc:
        raise ProrrataPreflightRefusalError(
            exc.refusal.value,
            str(exc),
            accepted_provenances=accepted_provenances,
        ) from exc
    return provenance, reference


def _election_regime_transition(
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataElectionRequest,
) -> tuple[ProrrataRegisterRegime, ProrrataEspecialTransitionEvidence | None]:
    transition: ProrrataEspecialTransitionEvidence | None = None
    regime = general_prorrata_register_regime()
    if operation_id == "elect_especial":
        regime = especial_prorrata_register_regime()
        if not isinstance(payload, _requests.ProrrataElectEspecialRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.evidence_reference is not None:
            transition = ProrrataEspecialTransitionEvidence(
                kind=opcion_prorrata_transition(),
                evidence_reference=payload.evidence_reference,
            )
    elif operation_id == "revoke_especial":
        if not isinstance(payload, _requests.ProrrataRevokeEspecialRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        transition = ProrrataEspecialTransitionEvidence(
            kind=revocacion_prorrata_transition(),
            evidence_reference=payload.evidence_reference,
        )
    return regime, transition


def _create_election_entry(
    payload: _requests.ProrrataElectionRequest,
    *,
    provenance: ProrrataProvisionalProvenance,
    reference: str | None,
    regime: ProrrataRegisterRegime,
    transition: ProrrataEspecialTransitionEvidence | None,
) -> ProrrataRegisterEntry:
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
        raise ProrrataPreflightRefusalError("validation", str(exc)) from exc


def whole_seed_refusal_reason(reason: ProrrataWholeSeedUnavailableReason) -> _ProrrataRefusalReason:
    """Map service refusal reasons to the closed public result vocabulary."""
    mapping: dict[ProrrataWholeSeedUnavailableReason, _ProrrataRefusalReason] = {
        "source_absent": "seed_source_absent",
        "source_blocked": "seed_source_blocked",
        "existing_blocked": "seed_existing_blocked",
        "regulated_override_standing": "regulated_override_standing",
    }
    try:
        return mapping[reason]
    except KeyError:
        raise InternalInvariantError("whole-entity seed refusal returned an unknown finite reason") from None


def _preflight_sector_declaration(payload: BaseModel) -> SectorDefinition:
    if not isinstance(payload, _requests.ProrrataDeclareSectorRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    letter = next((item for item in prorrata_sector_letters() if item.value == payload.letra), None)
    if letter is None:
        raise ProrrataPreflightRefusalError(
            "validation",
            "sector letter is not present in the pinned prorrata authority",
        )
    return SectorDefinition(
        sector_id=payload.sector_id,
        letra=letter,
        member_activity_codes=payload.member_activity_codes,
    )


def _preflight_election(
    operation_id: _requests.ProrrataOperationId,
    payload: BaseModel,
) -> ProrrataRegisterEntry:
    if not isinstance(payload, _requests.ProrrataElectionRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _build_election_entry(operation_id, payload)


def _preflight_sector_settlement(
    payload: BaseModel,
    context: OperationExecutorContext,
) -> RegistrySnapshotRef:
    if not isinstance(payload, _requests.ProrrataSettleSectorRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    # Reject malformed volumes before UNKNOWN. The service still derives the
    # settled entry from the latest CAS candidate during COMMIT.
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


def _preflight_whole_seed(
    payload: BaseModel,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
) -> None:
    if not isinstance(payload, _requests.ProrrataSeedRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if calculation_action_ports_factory is None:
        raise InternalInvariantError("whole-entity prorrata seed has no observation source capability")
    return None


def _preflight_sector_seed(payload: BaseModel) -> None:
    if not isinstance(payload, _requests.ProrrataSeedSectorRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return None


def _perform_sector_declaration(
    definition: SectorDefinition,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    register = service.declare_sector(definition)
    actual = next(
        (item for item in register.sector_definitions if item.sector_id == definition.sector_id),
        None,
    )
    if actual is None:
        raise InternalInvariantError("prorrata sector write returned no matching definition")
    return CommittedProrrataMutation(register=register, sector_definition=actual)


def _perform_prepared_sector_declaration(
    prepared: object,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    if not isinstance(prepared, SectorDefinition):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _perform_sector_declaration(prepared, service)


def _perform_election(
    entry: ProrrataRegisterEntry,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    register = (
        service.declare_especial_transition(entry) if entry.especial_transition is not None else service.declare(entry)
    )
    actual = register.entry_for(entry.ejercicio, sector_id=entry.sector_id)
    if actual is None:
        raise InternalInvariantError("prorrata entry write returned no matching ejercicio/sector row")
    return CommittedProrrataMutation(register=register, entry=actual)


def _perform_prepared_election(
    prepared: object,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    if not isinstance(prepared, ProrrataRegisterEntry):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _perform_election(prepared, service)


def _perform_whole_seed(
    payload: _requests.ProrrataSeedRequest,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
    service: ProrrataRegisterService,
    context: OperationExecutorContext,
) -> CommittedProrrataMutation:
    if calculation_action_ports_factory is None:
        raise InternalInvariantError("whole-entity prorrata seed has no observation source capability")
    calculation_ports = calculation_action_ports_factory(
        bucket_id=str(payload.profile_id),
        operation=context.authority_operation,
    )
    observation_repository = calculation_ports.observation_repository
    if not callable(getattr(observation_repository, "load_prior_m303_settlement_snapshot", None)):
        raise InternalInvariantError("whole-entity prorrata seed has no source-snapshot capability")
    commit = service.seed_whole_carried(
        payload.ejercicio,
        observation_repository=cast(ProrrataPriorSettlementSnapshotRepositoryProtocol, observation_repository),
    )
    return CommittedProrrataMutation(
        register=commit.register,
        entry=commit.seed.entry,
        seed=commit.seed,
        findings=commit.findings,
    )


def _perform_whole_seed_request(
    payload: BaseModel,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
    service: ProrrataRegisterService,
    context: OperationExecutorContext,
) -> CommittedProrrataMutation:
    if not isinstance(payload, _requests.ProrrataSeedRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _perform_whole_seed(payload, calculation_action_ports_factory, service, context)


def _perform_sector_seed(
    payload: _requests.ProrrataSeedSectorRequest,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    register, entry = service.seed_sector_carried(payload.ejercicio, payload.sector_id)
    return CommittedProrrataMutation(register=register, entry=entry, prior_ejercicio=payload.ejercicio - 1)


def _perform_sector_seed_request(
    payload: BaseModel,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    if not isinstance(payload, _requests.ProrrataSeedSectorRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _perform_sector_seed(payload, service)


def _perform_sector_settlement(
    payload: _requests.ProrrataSettleSectorRequest,
    prepared: object,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    if not isinstance(prepared, RegistrySnapshotRef):
        raise InternalInvariantError("sector settlement preflight did not retain its pinned producing coordinate")
    register, entry = service.settle_sector(
        payload.ejercicio,
        payload.sector_id,
        con_derecho_volume=Decimal(payload.con_derecho_volume.decimal),
        sin_derecho_volume=Decimal(payload.sin_derecho_volume.decimal),
        producing_snapshot_ref=prepared,
    )
    return CommittedProrrataMutation(register=register, entry=entry)


def _perform_sector_settlement_request(
    payload: BaseModel,
    prepared: object,
    service: ProrrataRegisterService,
) -> CommittedProrrataMutation:
    if not isinstance(payload, _requests.ProrrataSettleSectorRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return _perform_sector_settlement(payload, prepared, service)


def preflight_prorrata_operation(
    operation_id: _requests.ProrrataOperationId,
    payload: BaseModel,
    context: OperationExecutorContext,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
) -> object:
    """Validate operation inputs and authority before any unknown effect."""
    if operation_id == "declare_sector":
        return _preflight_sector_declaration(payload)
    if operation_id in {"elect_especial", "elect_general", "revoke_especial"}:
        return _preflight_election(operation_id, payload)
    if operation_id == "settle_sector":
        return _preflight_sector_settlement(payload, context)
    if operation_id == "seed":
        return _preflight_whole_seed(payload, calculation_action_ports_factory)
    if operation_id == "seed_sector":
        return _preflight_sector_seed(payload)
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def perform_prorrata_mutation(
    operation_id: _requests.ProrrataOperationId,
    payload: BaseModel,
    prepared: object,
    service: ProrrataRegisterService,
    context: OperationExecutorContext,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
) -> CommittedProrrataMutation:
    """Apply one canonical mutation and capture its complete result arm."""
    if operation_id == "declare_sector":
        return _perform_prepared_sector_declaration(prepared, service)
    if operation_id in {"elect_especial", "elect_general", "revoke_especial"}:
        return _perform_prepared_election(prepared, service)
    if operation_id == "seed":
        return _perform_whole_seed_request(payload, calculation_action_ports_factory, service, context)
    if operation_id == "seed_sector":
        return _perform_sector_seed_request(payload, service)
    if operation_id == "settle_sector":
        return _perform_sector_settlement_request(payload, prepared, service)
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


__all__ = [
    "CommittedProrrataMutation",
    "ProrrataPreflightRefusalError",
    "build_prorrata_refusal_projection",
    "perform_prorrata_mutation",
    "preflight_prorrata_operation",
    "whole_seed_refusal_reason",
]
