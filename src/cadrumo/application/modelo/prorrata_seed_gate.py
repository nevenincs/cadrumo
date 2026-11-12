"""Verify-time gate on the provisional prorrata a Modelo 303 deducts under.

LIVA art. 105.Uno sets the provisional percentage of an ejercicio to the prior
ejercicio's definitive one (art. 104.Dos.1), which the prorrata register holds
once seeded from the prior Modelo 390 box [118], the prior final-period
Modelo 303, or the taxpayer's own statement. The register is the one figure
the deduction reads, so this gate never defaults a percentage. It refuses a
draft when the register holds an apportioning whole-entity entry with no
provisional percentage, or when a held prior return contradicts the carried
or stated figure; both are settled by seeding the ejercicio again. It also
refuses a draft that left exempt output without the right to deduct to the
prorrata (LIVA art. 102.Uno) while the register holds no entry at all for the
ejercicio, since that deduction ran unapportioned; seeding settles it. It
discloses, without blocking, a figure the taxpayer stated because no prior
return is held. A draft calculated under another figure than the register now
holds is sent to be calculated again, as the ledger drift gate does; a filed
revision calculated under a superseded figure is refused on re-verification
with the amendment door.

A register partitioned into differentiated sectors carries a percentage per
sector through its own lifecycle and is outside this whole-entity gate.

See Also:
    :func:`~application.prorrata_register.seed.cross_check_prorrata_entry_against_observations`
        The canonical comparison of a register entry with the held prior returns.
    :func:`~application.aggregation.iva_ledger.sector_scoped_apportionment`
        The apportionment the IVA ledger aggregation deducts under.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.prorrata_register_catalogue import (
    carried_prior_definitiva_prorrata_provenance,
    operator_stated_prior_definitiva_prorrata_provenance,
    regime_apportions_deduction,
)
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.errors import ModeloError
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..aggregation.iva_ledger import sector_scoped_apportionment
from ..aggregation.modelo_bindings_iva import (
    RecordedProrrataApportionment,
    recorded_prorrata_apportionment,
    recorded_prorrata_only_exempt_output,
)
from ..prorrata_register.seed import (
    cross_check_prorrata_entry_against_observations,
    prior_definitiva_source_coordinates,
)
from ..prorrata_register.service import require_prorrata_register_coordinates_current
from .action_errors import ModeloPreconditionErrorMixin
from .preconditions import ModeloPreconditionFailure, build_modelo_precondition_failure_for_scenario

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.calculation_revision import CalculationRevision
    from ...domain.modelos.work_unit import WorkUnit
    from ...domain.prorrata_register.protocols import ProrrataRegisterRepositoryProtocol
    from ...domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry
    from ..aggregation.iva_ledger import IvaLedgerProrrataApportionment
    from ..calculations.observations_repository import (
        CalculationObservationRepositoryProtocol,
        ObservationEnvelopePayload,
    )

_VERIFY_LEAF: Final = "modelo.work.verify"
_EVIDENCE_ID: Final = "modelo.work.verify.prorrata_seed"
_PRORRATA_SEED_LEGAL_REFS: Final[tuple[str, ...]] = ("ley-37-1992:art-104", "ley-37-1992:art-105")
_PRORRATA_UNSEEDED_LEGAL_REFS: Final[tuple[str, ...]] = ("ley-37-1992:art-102", *_PRORRATA_SEED_LEGAL_REFS)


class ModeloProrrataSeedSupersededError(ModeloPreconditionErrorMixin, ModeloError):
    """Raised when a filed revision deducted under a provisional prorrata the register no longer holds."""


@dataclass(frozen=True, slots=True)
class ProrrataSeedVerificationFinding:
    """One gate finding and, when it blocks, the verdict that names its door."""

    finding: ModeloVerificationFinding
    failure: ModeloPreconditionFailure | None


def prorrata_seed_verification_findings(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    observation_repository: CalculationObservationRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> tuple[ProrrataSeedVerificationFinding, ...]:
    """Return the prorrata seed findings for a Modelo 303 draft, or none where the gate does not apply."""
    if target.state is not CalculationRevisionState.BORRADOR or not _gate_applies(work_unit):
        return ()
    register = require_prorrata_register_coordinates_current(prorrata_register_repository.load(), operation=operation)
    if register.sector_definitions:
        return ()
    return _whole_entity_findings(work_unit, target, register, observation_repository, operation=operation)


def _whole_entity_findings(
    work_unit: WorkUnit,
    target: CalculationRevision,
    register: ProrrataRegister,
    observation_repository: CalculationObservationRepositoryProtocol,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ProrrataSeedVerificationFinding, ...]:
    ejercicio = work_unit.filing_year
    unseeded = _unseeded_finding(work_unit, target, register)
    if unseeded is not None:
        return (unseeded,)
    entry = _apportioning_whole_entity_entry(register, ejercicio, operation=operation)
    if entry is not None and register.resolve_provisional(ejercicio, sector_id=None).percentage is None:
        return (_unsourced_finding(work_unit, target),)
    findings: list[ProrrataSeedVerificationFinding] = []
    if entry is not None:
        findings.extend(_source_findings(work_unit, target, entry, observation_repository, operation=operation))
    if any(item.failure is not None for item in findings):
        return tuple(findings)
    recorded, current = _recorded_and_current(target, register, ejercicio, operation=operation)
    if _apportionment_changed(recorded, current):
        findings.append(_changed_finding(work_unit, target, recorded=recorded, current=current))
    return tuple(findings)


def require_filed_prorrata_seed_current(
    *,
    work_unit: WorkUnit,
    target: CalculationRevision,
    prorrata_register_repository: ProrrataRegisterRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> None:
    """Refuse re-verifying a filed Modelo 303 whose provisional prorrata the register has since replaced."""
    if target.state is not CalculationRevisionState.PRESENTADO or not _gate_applies(work_unit):
        return
    register = require_prorrata_register_coordinates_current(prorrata_register_repository.load(), operation=operation)
    if register.sector_definitions:
        return
    recorded, current = _recorded_and_current(target, register, work_unit.filing_year, operation=operation)
    if not _apportionment_changed(recorded, current):
        return
    raise ModeloProrrataSeedSupersededError(
        translated_message="errors.refused.refused_modelo_prorrata_seed_superseded",
        context={
            "modelo": str(work_unit.modelo),
            "filing_year": str(work_unit.filing_year),
            "period": work_unit.period.registry_token,
        },
        precondition_failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=_VERIFY_LEAF,
            scenario_id=f"{_VERIFY_LEAF}.prorrata_seed.superseded",
            evidence_id=_EVIDENCE_ID,
            evidence_values={
                "calculation_revision_id": target.calculation_revision_id,
                **_apportionment_evidence(work_unit, recorded=recorded, current=current),
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
            action_argument_values={"work_unit_id": work_unit.work_unit_id},
        ),
    )


def _gate_applies(work_unit: WorkUnit) -> bool:
    return work_unit.modelo == form_for_role("iva.periodic")


def _apportioning_whole_entity_entry(
    register: ProrrataRegister,
    ejercicio: int,
    *,
    operation: PinnedAuthorityOperation,
) -> ProrrataRegisterEntry | None:
    entry = register.entry_for(ejercicio, sector_id=None)
    if entry is None or entry.interrupted or not regime_apportions_deduction(entry.regime, authority=operation):
        return None
    return entry


def _prior_source_observations(
    observation_repository: CalculationObservationRepositoryProtocol,
    ejercicio: int,
) -> tuple[ObservationEnvelopePayload, ...]:
    observations: list[ObservationEnvelopePayload] = []
    for modelo, token in prior_definitiva_source_coordinates():
        payload = observation_repository.load_observation(modelo, Period.from_year_and_code(ejercicio - 1, token))
        if payload is not None:
            observations.append(payload)
    return tuple(observations)


def _source_findings(
    work_unit: WorkUnit,
    target: CalculationRevision,
    entry: ProrrataRegisterEntry,
    observation_repository: CalculationObservationRepositoryProtocol,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ProrrataSeedVerificationFinding, ...]:
    """Check a carried or stated figure against the held prior returns."""
    stated = operator_stated_prior_definitiva_prorrata_provenance()
    if entry.provisional_provenance not in (carried_prior_definitiva_prorrata_provenance(), stated):
        return ()
    cross_findings = cross_check_prorrata_entry_against_observations(
        entry,
        observations=_prior_source_observations(observation_repository, work_unit.filing_year),
        operation=operation,
    )
    contradiction = next((item for item in cross_findings if item.blocking), None)
    if contradiction is not None:
        facts: dict[str, str | int] = {
            "filing_year": work_unit.filing_year,
            "source_modelo": contradiction.source_modelo,
            "source_filing_year": contradiction.source_filing_year,
        }
        return (
            ProrrataSeedVerificationFinding(
                finding=ModeloVerificationFinding(
                    kind=ModeloVerificationFindingKind.BLOCKING_RULE,
                    severity=ModeloVerificationFindingSeverity.BLOCKING,
                    message_locale_key="application.modelo.findings.prorrata_seed_contradicted",
                    message_facts=facts,
                    legal_refs=_PRORRATA_SEED_LEGAL_REFS,
                ),
                failure=_seed_door_failure(
                    work_unit,
                    target,
                    scenario="contradicted",
                    evidence_values={
                        "finding_code": contradiction.code,
                        "source_modelo": contradiction.source_modelo,
                        "source_filing_year": contradiction.source_filing_year,
                        "source_period": contradiction.source_period,
                    },
                ),
            ),
        )
    if entry.provisional_provenance != stated or entry.provisional_percentage is None:
        return ()
    return (
        ProrrataSeedVerificationFinding(
            finding=ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message_locale_key="application.modelo.findings.prorrata_seed_operator_stated",
                message_facts={
                    "filing_year": work_unit.filing_year,
                    "prior_filing_year": work_unit.filing_year - 1,
                    "percentage": entry.provisional_percentage,
                },
                legal_refs=_PRORRATA_SEED_LEGAL_REFS,
            ),
            failure=None,
        ),
    )


def _unsourced_finding(work_unit: WorkUnit, target: CalculationRevision) -> ProrrataSeedVerificationFinding:
    return ProrrataSeedVerificationFinding(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.prorrata_seed_unsourced",
            message_facts={"filing_year": work_unit.filing_year},
            legal_refs=_PRORRATA_SEED_LEGAL_REFS,
        ),
        failure=_seed_door_failure(work_unit, target, scenario="unsourced", evidence_values={}),
    )


def _unseeded_finding(
    work_unit: WorkUnit,
    target: CalculationRevision,
    register: ProrrataRegister,
) -> ProrrataSeedVerificationFinding | None:
    """Refuse a draft that left exempt output to a prorrata the register holds nothing for.

    Operations exempt without the right to deduct make the taxpayer apply the
    prorrata (LIVA art. 102.Uno); with no register entry for the ejercicio the
    deduction ran unapportioned, which is a full deduction.
    """
    if register.entry_for(work_unit.filing_year, sector_id=None) is not None:
        return None
    row_count = recorded_prorrata_only_exempt_output(item.source_ref for item in target.source_provenance)
    if row_count is None:
        return None
    return ProrrataSeedVerificationFinding(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.prorrata_seed_unseeded",
            message_facts={"filing_year": work_unit.filing_year},
            legal_refs=_PRORRATA_UNSEEDED_LEGAL_REFS,
        ),
        failure=_seed_door_failure(
            work_unit,
            target,
            scenario="unseeded",
            evidence_values={"exempt_output_record_count": row_count},
        ),
    )


def _seed_door_failure(
    work_unit: WorkUnit,
    target: CalculationRevision,
    *,
    scenario: str,
    evidence_values: dict[str, str | int],
) -> ModeloPreconditionFailure:
    return build_modelo_precondition_failure_for_scenario(
        subject_leaf_key=_VERIFY_LEAF,
        scenario_id=f"{_VERIFY_LEAF}.prorrata_seed.{scenario}",
        evidence_id=_EVIDENCE_ID,
        evidence_values={
            "calculation_revision_id": target.calculation_revision_id,
            "work_unit_id": work_unit.work_unit_id,
            "ejercicio": work_unit.filing_year,
            **evidence_values,
        },
        provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        action_argument_values={"ejercicio": work_unit.filing_year},
    )


def _recorded_and_current(
    target: CalculationRevision,
    register: ProrrataRegister,
    ejercicio: int,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[RecordedProrrataApportionment | None, IvaLedgerProrrataApportionment | None]:
    recorded = recorded_prorrata_apportionment(item.source_ref for item in target.source_provenance)
    current = sector_scoped_apportionment(register, ejercicio, sector_id=None, operation=operation)
    return recorded, current


def _apportionment_changed(
    recorded: RecordedProrrataApportionment | None,
    current: IvaLedgerProrrataApportionment | None,
) -> bool:
    if recorded is None or current is None:
        return (recorded is None) != (current is None)
    return (recorded.percentage, recorded.provenance) != (current.percentage, current.provenance.value)


def _apportionment_evidence(
    work_unit: WorkUnit,
    *,
    recorded: RecordedProrrataApportionment | None,
    current: IvaLedgerProrrataApportionment | None,
) -> dict[str, str | int | bool]:
    return {
        "work_unit_id": work_unit.work_unit_id,
        "ejercicio": work_unit.filing_year,
        "recorded_applied": recorded is not None,
        "recorded_percentage": "" if recorded is None else str(recorded.percentage),
        "recorded_provenance": "" if recorded is None else recorded.provenance,
        "current_applied": current is not None,
        "current_percentage": "" if current is None else str(current.percentage),
        "current_provenance": "" if current is None else current.provenance.value,
    }


def _changed_finding(
    work_unit: WorkUnit,
    target: CalculationRevision,
    *,
    recorded: RecordedProrrataApportionment | None,
    current: IvaLedgerProrrataApportionment | None,
) -> ProrrataSeedVerificationFinding:
    return ProrrataSeedVerificationFinding(
        finding=ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.STALE_CALCULATION,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            message_locale_key="application.modelo.findings.prorrata_seed_changed",
            message_facts={
                "modelo": str(work_unit.modelo),
                "filing_year": work_unit.filing_year,
                "period": work_unit.period.registry_token,
            },
            legal_refs=_PRORRATA_SEED_LEGAL_REFS,
        ),
        failure=build_modelo_precondition_failure_for_scenario(
            subject_leaf_key=_VERIFY_LEAF,
            scenario_id=f"{_VERIFY_LEAF}.prorrata_seed.changed",
            evidence_id=_EVIDENCE_ID,
            evidence_values={
                "calculation_revision_id": target.calculation_revision_id,
                **_apportionment_evidence(work_unit, recorded=recorded, current=current),
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        ),
    )


__all__ = [
    "ModeloProrrataSeedSupersededError",
    "ProrrataSeedVerificationFinding",
    "prorrata_seed_verification_findings",
    "require_filed_prorrata_seed_current",
]
