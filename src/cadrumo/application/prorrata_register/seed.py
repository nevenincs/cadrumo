"""Seed the cross-period prorrata register from stamped prior observations.

The LIVA art. 105.Uno normal provisional percentage is the prior ejercicio's
definitive prorrata (art. 104.Dos.1). A Modelo 390 filer states it in the annual
summary's box [118], found through the registry binding that reads the first
activity row's percentage; a filer exempt from the 390 states it in the final
period's Modelo 303 prorrata section. This module reads the 390 first and the
303 second, trusting either only after the observation's registry revision
stamp re-confirms against the law-determined revision for the source period.
With neither return held, the taxpayer may state the figure: it is carried
under its own registry-declared provenance and disclosed as operator-stated.
A prior 390 declaring more than one activity row leaves the percentage not
computed, because the activity rows' own percentages are not one figure.

See Also:
    :class:`~domain.prorrata_register.register.ProrrataRegisterEntry`
        Register record populated with the carried-prior-definitive percentage,
        provenance, and source-observation identity.
    :class:`~core.prorrata_register.ProrrataProvisionalProvenance`
        Closed provenance axis whose ``CARRIED_PRIOR_DEFINITIVA`` member marks
        the normal LIVA art. 105.Uno seed path.
    :class:`~application.calculations.observations_repository.CalculationObservationRepositoryProtocol`
        Local observation catalogue holding the prior Modelo 390 and Modelo 303
        observations.
    :func:`~application.calculations.revision_carry_gate.revision_carry_outcome`
        Shared law-determined gate used to re-confirm the stored
        ``stamped_revision_id`` before trusting the carry.
    :class:`~application.calculations.cross_period_models.CrossPeriodCleanStateBlocker`
        Blocker vocabulary reused for revision-divergent seed findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Final

from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.period import Period, StandardPeriodCode
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_targets import casillas_by_binding
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.prorrata_register_activity_bindings import (
    PRORRATA_ACTIVITY_FIELD_CHANNEL,
    ProrrataActivityField,
    ProrrataRegisterActivityProvider,
)
from ...domain.calculations.registry.prorrata_register_catalogue import (
    carried_prior_definitiva_prorrata_provenance,
    general_prorrata_register_regime,
    operator_stated_prior_definitiva_prorrata_provenance,
    prorrata_referenced_provenances,
)
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.iva.m303_settlement import m303_annual_settlement_order_key
from ...domain.prorrata_register.register import ProrrataRegisterEntry
from ..calculations.cross_period_models import CrossPeriodCleanStateBlocker
from ..calculations.observations_repository import (
    ObservationEnvelopePayload,
)
from ..calculations.revision_carry_gate import revision_carry_outcome
from .settlement import PRORRATA_PORCENTAJE_CASILLA

_REGULATED_OVERRIDE_DIFFERENCE = "regulated_prorrata_override_difference"
#: The prior 390 declares more than one activity row, so no single definitive percentage carries.
PRORRATA_SEVERAL_ACTIVITIES: Final = "prorrata_several_activities"
#: The register is partitioned into differentiated sectors, so no whole-entity percentage carries.
PRORRATA_DIFFERENTIATED_SECTOR: Final = "prorrata_differentiated_sector"
#: The taxpayer stated the prior definitive because no prior return is held.
PRORRATA_OPERATOR_STATED: Final = "prorrata_prior_definitiva_operator_stated"
#: A held prior return states another definitive percentage than the taxpayer's statement or the register.
PRORRATA_RETURN_CONTRADICTS_FIGURE: Final = "prorrata_prior_return_contradicts_figure"


@dataclass(frozen=True, slots=True)
class ProrrataPriorDefinitivaSeed:
    """A re-confirmed prior-year definitive percentage ready to seed the register.

    ``operator_stated`` marks the taxpayer's statement; its source coordinate is
    then the annual summary box the statement stands in for, not a held return.
    """

    entry: ProrrataRegisterEntry
    source_modelo: str
    source_filing_year: int
    source_period: str
    source_casilla_id: CasillaId
    stamped_revision_id: RevisionId
    operator_stated: bool = False


@dataclass(frozen=True, slots=True)
class ProrrataSeedFinding:
    """Operator-visible seed/cross-check blocker or advisory."""

    code: str
    blocking: bool
    message: str
    source_modelo: str
    source_filing_year: int
    source_period: str
    stamped_revision_id: RevisionId
    selected_revision_id: RevisionId | None

    @property
    def advisory(self) -> bool:
        """Whether this finding is a non-blocking advisory."""
        return not self.blocking


@dataclass(frozen=True, slots=True)
class ProrrataPriorDefinitivaSeedEvaluation:
    """Seed resolution plus any blockers or advisories surfaced while resolving it."""

    seed: ProrrataPriorDefinitivaSeed | None
    findings: tuple[ProrrataSeedFinding, ...] = ()

    @property
    def blocked(self) -> bool:
        """Whether any finding blocks trusting the seed."""
        return any(finding.blocking for finding in self.findings)


@dataclass(frozen=True, slots=True)
class _PriorSettlementObservation:
    percentage: Decimal
    source_filing_year: int
    source_period: str
    stamped_revision_id: RevisionId
    captured_at: datetime
    source_modelo: str = field(default_factory=lambda: form_for_role("iva.periodic"))
    source_casilla_id: CasillaId = PRORRATA_PORCENTAJE_CASILLA


@dataclass(frozen=True, slots=True)
class _OfficialPriorDefinitiva:
    """The held prior return's definitive percentage, or the findings that withhold it."""

    source: _PriorSettlementObservation | None
    findings: tuple[ProrrataSeedFinding, ...] = ()


def prior_definitiva_source_coordinates() -> tuple[tuple[str, str], ...]:
    """Return every ``(modelo, period)`` coordinate a prior definitive can be read from.

    The prior annual summary comes first, then the final-period self-assessments;
    a seed fences all of them, including absence, so a newly captured source
    invalidates an evaluated seed rather than escaping its fence.
    """
    periodic = form_for_role("iva.periodic")
    return (
        (form_for_role("iva.annual_summary"), StandardPeriodCode.ANNUAL.value),
        (periodic, StandardPeriodCode.Q4.value),
        (periodic, StandardPeriodCode.DEC.value),
    )


def evaluate_carried_prior_definitiva_seed_from_observations(
    *,
    ejercicio: int,
    observations: tuple[ObservationEnvelopePayload, ...],
    operation: PinnedAuthorityOperation,
    sector_id: str | None = None,
    stated_percentage: Decimal | None = None,
) -> ProrrataPriorDefinitivaSeedEvaluation:
    """Evaluate the canonical carry rule against one revision-pinned source snapshot.

    ``observations`` may hold the prior Modelo 390 and the prior Modelo 303
    rows together: the 390's box [118] is read first, the 303's final-period
    percentage second. ``stated_percentage`` is the taxpayer's statement; it
    seeds only when neither return is held, and a held return stating another
    figure blocks rather than letting either win silently.
    """
    official = _official_prior_definitiva(observations, prior_year=ejercicio - 1, operation=operation)
    if official.findings:
        return ProrrataPriorDefinitivaSeedEvaluation(seed=None, findings=official.findings)
    source = official.source
    if source is not None:
        if stated_percentage is not None and stated_percentage != source.percentage:
            return ProrrataPriorDefinitivaSeedEvaluation(
                seed=None,
                findings=(
                    _return_contradicts_figure_finding(
                        source,
                        figure=stated_percentage,
                        figure_label="the stated percentage",
                    ),
                ),
            )
        return ProrrataPriorDefinitivaSeedEvaluation(
            seed=_seed_from_source(ejercicio=ejercicio, source=source, sector_id=sector_id),
            findings=(),
        )
    if stated_percentage is None:
        return ProrrataPriorDefinitivaSeedEvaluation(seed=None, findings=())
    seed = _operator_stated_seed(
        ejercicio=ejercicio,
        percentage=stated_percentage,
        sector_id=sector_id,
        operation=operation,
    )
    if seed is None:
        return ProrrataPriorDefinitivaSeedEvaluation(seed=None, findings=())
    return ProrrataPriorDefinitivaSeedEvaluation(seed=seed, findings=(operator_stated_seed_finding(seed),))


def cross_check_prorrata_entry_against_observations(
    entry: ProrrataRegisterEntry,
    *,
    observations: tuple[ObservationEnvelopePayload, ...],
    operation: PinnedAuthorityOperation,
) -> tuple[ProrrataSeedFinding, ...]:
    """Cross-check one entry using the same source snapshot as a proposed seed."""
    if entry.provisional_percentage is None or entry.provisional_provenance is None:
        return ()
    evaluation = evaluate_carried_prior_definitiva_seed_from_observations(
        ejercicio=entry.ejercicio,
        observations=observations,
        operation=operation,
        sector_id=entry.sector_id,
    )
    seed = evaluation.seed
    if seed is None:
        return evaluation.findings

    selected_revision_id = _selected_revision_id_from_findings(
        evaluation.findings,
        fallback=seed.stamped_revision_id,
    )
    if entry.provisional_provenance == carried_prior_definitiva_prorrata_provenance():
        contradiction_detail = _carried_entry_contradiction_detail(entry, seed.entry)
        if contradiction_detail is None:
            return evaluation.findings
        return (
            *evaluation.findings,
            _carried_entry_contradiction_finding(
                seed,
                selected_revision_id=selected_revision_id,
                detail=contradiction_detail,
            ),
        )
    if entry.provisional_provenance == operator_stated_prior_definitiva_prorrata_provenance():
        if entry.provisional_percentage == seed.entry.provisional_percentage:
            return evaluation.findings
        return (
            *evaluation.findings,
            _return_contradicts_figure_finding(
                _seed_source(seed),
                figure=entry.provisional_percentage,
                figure_label="the stated percentage held in the register",
            ),
        )
    if (
        entry.provisional_provenance in prorrata_referenced_provenances()
        and entry.provisional_percentage != seed.entry.provisional_percentage
    ):
        return (
            *evaluation.findings,
            _regulated_override_difference_finding(
                entry,
                seed,
                selected_revision_id=selected_revision_id,
            ),
        )
    return evaluation.findings


def operator_stated_seed_finding(seed: ProrrataPriorDefinitivaSeed) -> ProrrataSeedFinding:
    """Disclose, without blocking, that the carried percentage is the taxpayer's own statement."""
    return ProrrataSeedFinding(
        code=PRORRATA_OPERATOR_STATED,
        blocking=False,
        message=(
            f"The provisional prorrata {seed.entry.provisional_percentage} for {seed.entry.ejercicio} is the "
            f"taxpayer's statement of the {seed.source_filing_year} definitive percentage: neither the "
            f"{seed.source_filing_year} Modelo {seed.source_modelo} nor the final-period Modelo "
            f"{form_for_role('iva.periodic')} is held."
        ),
        source_modelo=seed.source_modelo,
        source_filing_year=seed.source_filing_year,
        source_period=seed.source_period,
        stamped_revision_id=seed.stamped_revision_id,
        selected_revision_id=None,
    )


def differentiated_sector_seed_finding(*, ejercicio: int, sector_ids: tuple[str, ...]) -> ProrrataSeedFinding:
    """Withhold a whole-entity carry from a register partitioned into differentiated sectors.

    The finding names the prior annual summary coordinate, the return a
    whole-entity carry would have read.
    """
    return ProrrataSeedFinding(
        code=PRORRATA_DIFFERENTIATED_SECTOR,
        blocking=True,
        message=(
            f"The prorrata register for {ejercicio} is partitioned into differentiated sectors "
            f"({', '.join(sector_ids)}); each sector carries its own percentage, so no whole-entity "
            "percentage is computed."
        ),
        source_modelo=form_for_role("iva.annual_summary"),
        source_filing_year=ejercicio - 1,
        source_period=StandardPeriodCode.ANNUAL.value,
        stamped_revision_id="",
        selected_revision_id=None,
    )


def _official_prior_definitiva(
    observations: tuple[ObservationEnvelopePayload, ...],
    *,
    prior_year: int,
    operation: PinnedAuthorityOperation,
) -> _OfficialPriorDefinitiva:
    """Read the prior 390 first and the prior final-period 303 second."""
    annual = _prior_annual_summary_definitiva(observations, prior_year=prior_year, operation=operation)
    if annual.source is not None or annual.findings:
        return annual
    for source in _prior_settlement_observations(observations, prior_year=prior_year, operation=operation):
        refusal = _revision_divergence(source, operation=operation)
        if refusal is not None:
            return _OfficialPriorDefinitiva(source=None, findings=(refusal,))
        return _OfficialPriorDefinitiva(source=source)
    return _OfficialPriorDefinitiva(source=None)


def _revision_divergence(
    source: _PriorSettlementObservation,
    *,
    operation: PinnedAuthorityOperation,
) -> ProrrataSeedFinding | None:
    revision_outcome = revision_carry_outcome(
        RegistrySnapshotRef(
            modelo=source.source_modelo,
            revision_id=source.stamped_revision_id,
            modelo_year=source.source_filing_year,
            period=source.source_period,
        ),
        operation=operation,
    )
    if not revision_outcome.refused:
        return None
    return _registry_revision_divergence_finding(
        source,
        selected_revision_id=revision_outcome.selected_revision_id,
        detail=revision_outcome.detail or "revision stamp cannot be re-confirmed",
    )


def _latest_whole_entity_annual_summary(
    observations: tuple[ObservationEnvelopePayload, ...],
    *,
    annual_modelo: str,
    annual_period: str,
    prior_year: int,
) -> ObservationEnvelopePayload | None:
    candidates = [
        payload
        for payload in observations
        if payload.observation.modelo == annual_modelo
        and payload.observation.filing_year == prior_year
        and payload.observation.period == annual_period
        and payload.member_nif is None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda payload: payload.captured_at)


def _prior_annual_summary_definitiva(
    observations: tuple[ObservationEnvelopePayload, ...],
    *,
    prior_year: int,
    operation: PinnedAuthorityOperation,
) -> _OfficialPriorDefinitiva:
    """Read box [118] of the prior whole-entity Modelo 390, refusing a several-activity summary."""
    annual_modelo = form_for_role("iva.annual_summary")
    annual_period = StandardPeriodCode.ANNUAL.value
    payload = _latest_whole_entity_annual_summary(
        observations, annual_modelo=annual_modelo, annual_period=annual_period, prior_year=prior_year
    )
    if payload is None:
        return _OfficialPriorDefinitiva(source=None)
    refusal = _revision_divergence(
        _PriorSettlementObservation(
            percentage=Decimal(0),
            source_filing_year=prior_year,
            source_period=annual_period,
            stamped_revision_id=payload.stamped_revision_id,
            captured_at=payload.captured_at,
            source_modelo=annual_modelo,
        ),
        operation=operation,
    )
    if refusal is not None:
        return _OfficialPriorDefinitiva(source=None, findings=(refusal,))
    rows = _activity_row_casillas(operation.revision(annual_modelo, payload.stamped_revision_id))
    return _definitiva_from_activity_rows(
        payload, rows, prior_year=prior_year, annual_modelo=annual_modelo, annual_period=annual_period
    )


def _definitiva_from_activity_rows(
    payload: ObservationEnvelopePayload,
    rows: dict[int, dict[ProrrataActivityField, CasillaId]],
    *,
    prior_year: int,
    annual_modelo: str,
    annual_period: str,
) -> _OfficialPriorDefinitiva:
    """Take the first activity row's percentage, refusing a summary that declares further activities."""
    percentage_id = rows.get(1, {}).get(ProrrataActivityField.PORCENTAJE)
    values = payload.observation.casilla_values
    percentage = None if percentage_id is None else values.get(percentage_id)
    if percentage is None or percentage_id is None:
        return _OfficialPriorDefinitiva(source=None)
    source = _PriorSettlementObservation(
        percentage=percentage,
        source_filing_year=prior_year,
        source_period=annual_period,
        stamped_revision_id=payload.stamped_revision_id,
        captured_at=payload.captured_at,
        source_modelo=annual_modelo,
        source_casilla_id=percentage_id,
    )
    further_rows = [
        slot
        for slot, row in rows.items()
        if slot != 1 and any(values.get(casilla_id) is not None for casilla_id in row.values())
    ]
    if further_rows:
        return _OfficialPriorDefinitiva(
            source=None,
            findings=(_several_activities_finding(source, declared_rows=len(further_rows) + 1),),
        )
    return _OfficialPriorDefinitiva(source=source)


def _activity_row_casillas(revision: ModeloRevision) -> dict[int, dict[ProrrataActivityField, CasillaId]]:
    """Map each activity row slot to the decimal casillas the registry binds to that register row."""
    targets = casillas_by_binding(revision)
    rows: dict[int, dict[ProrrataActivityField, CasillaId]] = {}
    for binding in revision.bindings:
        provider = binding.provider
        if not isinstance(provider, ProrrataRegisterActivityProvider):
            continue
        if PRORRATA_ACTIVITY_FIELD_CHANNEL[provider.field] is not BindingValueChannel.DECIMAL:
            continue
        for casilla_id in targets.get(binding.id, ()):
            rows.setdefault(provider.slot, {})[provider.field] = casilla_id
    return rows


def _operator_stated_seed(
    *,
    ejercicio: int,
    percentage: Decimal,
    sector_id: str | None,
    operation: PinnedAuthorityOperation,
) -> ProrrataPriorDefinitivaSeed | None:
    """Carry the taxpayer's statement, naming the annual summary box it stands in for."""
    annual_modelo = form_for_role("iva.annual_summary")
    prior_year = ejercicio - 1
    try:
        revision = operation.snapshot(
            annual_modelo,
            filing_year=prior_year,
            period=StandardPeriodCode.ANNUAL.value,
            grade=RegistryAuthorityGrade.CALCULATION,
        ).revision
    except RegistrySnapshotError:
        return None
    percentage_id = _activity_row_casillas(revision).get(1, {}).get(ProrrataActivityField.PORCENTAJE)
    if percentage_id is None:
        return None
    entry = ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=general_prorrata_register_regime(),
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=percentage,
        provisional_provenance=operator_stated_prior_definitiva_prorrata_provenance(),
        source_registry_snapshot_refs=(),
    )
    return ProrrataPriorDefinitivaSeed(
        entry=entry,
        source_modelo=annual_modelo,
        source_filing_year=prior_year,
        source_period=StandardPeriodCode.ANNUAL.value,
        source_casilla_id=percentage_id,
        stamped_revision_id=revision.id,
        operator_stated=True,
    )


def _seed_from_source(
    *,
    ejercicio: int,
    source: _PriorSettlementObservation,
    sector_id: str | None,
) -> ProrrataPriorDefinitivaSeed:
    entry = ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=general_prorrata_register_regime(),
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=source.percentage,
        provisional_provenance=carried_prior_definitiva_prorrata_provenance(),
        source_observation_ref=_source_observation_ref(source),
        source_registry_snapshot_refs=(
            RegistrySnapshotRef(
                modelo=source.source_modelo,
                revision_id=source.stamped_revision_id,
                modelo_year=source.source_filing_year,
                period=source.source_period,
            ),
        ),
    )
    return ProrrataPriorDefinitivaSeed(
        entry=entry,
        source_modelo=source.source_modelo,
        source_filing_year=source.source_filing_year,
        source_period=source.source_period,
        source_casilla_id=source.source_casilla_id,
        stamped_revision_id=source.stamped_revision_id,
    )


def _seed_source(seed: ProrrataPriorDefinitivaSeed) -> _PriorSettlementObservation:
    """Recover the source coordinate a carried seed names, for a finding about it."""
    percentage = seed.entry.provisional_percentage
    if percentage is None:
        raise ValueError("a carried prorrata seed always carries its percentage")
    return _PriorSettlementObservation(
        percentage=percentage,
        source_filing_year=seed.source_filing_year,
        source_period=seed.source_period,
        stamped_revision_id=seed.stamped_revision_id,
        captured_at=datetime.min,
        source_modelo=seed.source_modelo,
        source_casilla_id=seed.source_casilla_id,
    )


def _carried_entry_contradiction_detail(
    entry: ProrrataRegisterEntry,
    seed_entry: ProrrataRegisterEntry,
) -> str | None:
    details: list[str] = []
    if entry.provisional_percentage != seed_entry.provisional_percentage:
        details.append(
            f"entry percentage {entry.provisional_percentage} differs from prior observation "
            f"{seed_entry.provisional_percentage}"
        )
    if entry.source_observation_ref != seed_entry.source_observation_ref:
        details.append(
            f"entry source_observation_ref {entry.source_observation_ref!r} differs from "
            f"prior observation {seed_entry.source_observation_ref!r}"
        )
    return "; ".join(details) if details else None


def _selected_revision_id_from_findings(
    findings: tuple[ProrrataSeedFinding, ...],
    *,
    fallback: str,
) -> str:
    for finding in findings:
        if finding.selected_revision_id is not None:
            return finding.selected_revision_id
    return fallback


def _carried_entry_contradiction_finding(
    seed: ProrrataPriorDefinitivaSeed,
    *,
    selected_revision_id: RevisionId,
    detail: str,
) -> ProrrataSeedFinding:
    return ProrrataSeedFinding(
        code=CrossPeriodCleanStateBlocker.OBSERVATION_REVISION_VALUE_DIVERGENCE.value,
        blocking=True,
        message=(
            f"carried_prior_definitiva register entry contradicts the prior Modelo {seed.source_modelo} "
            f"observation: {detail}. Seed {seed.entry.ejercicio} again from "
            f"{seed.source_filing_year} {seed.source_period} before carrying the provisional percentage."
        ),
        source_modelo=seed.source_modelo,
        source_filing_year=seed.source_filing_year,
        source_period=seed.source_period,
        stamped_revision_id=seed.stamped_revision_id,
        selected_revision_id=selected_revision_id,
    )


def _regulated_override_difference_finding(
    entry: ProrrataRegisterEntry,
    seed: ProrrataPriorDefinitivaSeed,
    *,
    selected_revision_id: RevisionId,
) -> ProrrataSeedFinding:
    provenance = entry.provisional_provenance
    if provenance is None:
        raise ValueError("a regulated-override seed finding requires the entry's provisional provenance")
    return ProrrataSeedFinding(
        code=_REGULATED_OVERRIDE_DIFFERENCE,
        blocking=False,
        message=(
            f"{provenance.value} provisional prorrata {entry.provisional_percentage} differs from "
            f"prior definitive {seed.entry.provisional_percentage}; this is the regulated art. 105 "
            "override case and is recorded for operator visibility."
        ),
        source_modelo=seed.source_modelo,
        source_filing_year=seed.source_filing_year,
        source_period=seed.source_period,
        stamped_revision_id=seed.stamped_revision_id,
        selected_revision_id=selected_revision_id,
    )


def _registry_revision_divergence_finding(
    source: _PriorSettlementObservation,
    *,
    selected_revision_id: RevisionId | None,
    detail: str,
) -> ProrrataSeedFinding:
    return ProrrataSeedFinding(
        code=CrossPeriodCleanStateBlocker.REGISTRY_REVISION_DIVERGENCE.value,
        blocking=True,
        message=(
            f"Prior Modelo {source.source_modelo} prorrata observation cannot seed carried_prior_definitiva: "
            f"{detail}. Re-file or re-capture {source.source_filing_year} {source.source_period} "
            "so the observation is stamped under the law-determined registry revision."
        ),
        source_modelo=source.source_modelo,
        source_filing_year=source.source_filing_year,
        source_period=source.source_period,
        stamped_revision_id=source.stamped_revision_id,
        selected_revision_id=selected_revision_id,
    )


def _several_activities_finding(source: _PriorSettlementObservation, *, declared_rows: int) -> ProrrataSeedFinding:
    return ProrrataSeedFinding(
        code=PRORRATA_SEVERAL_ACTIVITIES,
        blocking=True,
        message=(
            f"The {source.source_filing_year} Modelo {source.source_modelo} declares {declared_rows} prorrata "
            "activity rows; one provisional percentage for the whole entity is not computed from them."
        ),
        source_modelo=source.source_modelo,
        source_filing_year=source.source_filing_year,
        source_period=source.source_period,
        stamped_revision_id=source.stamped_revision_id,
        selected_revision_id=source.stamped_revision_id,
    )


def _return_contradicts_figure_finding(
    source: _PriorSettlementObservation,
    *,
    figure: Decimal | None,
    figure_label: str,
) -> ProrrataSeedFinding:
    return ProrrataSeedFinding(
        code=PRORRATA_RETURN_CONTRADICTS_FIGURE,
        blocking=True,
        message=(
            f"The {source.source_filing_year} Modelo {source.source_modelo} states a definitive prorrata of "
            f"{source.percentage}, which contradicts {figure_label} ({figure}). Seed the ejercicio again "
            "from the held return."
        ),
        source_modelo=source.source_modelo,
        source_filing_year=source.source_filing_year,
        source_period=source.source_period,
        stamped_revision_id=source.stamped_revision_id,
        selected_revision_id=source.stamped_revision_id,
    )


def _source_observation_ref(source: _PriorSettlementObservation) -> str:
    return f"{source.source_modelo}:{source.source_filing_year}:{source.source_period}"


def _prior_settlement_observations(
    source_observations: tuple[ObservationEnvelopePayload, ...],
    *,
    prior_year: int,
    operation: PinnedAuthorityOperation,
) -> tuple[_PriorSettlementObservation, ...]:
    periodic_modelo = form_for_role("iva.periodic")
    observations: list[_PriorSettlementObservation] = []
    for payload in source_observations:
        observation = payload.observation
        if (
            observation.modelo != periodic_modelo
            or observation.filing_year != prior_year
            or payload.member_nif is not None
        ):
            continue
        period = Period.from_year_and_code(observation.filing_year, observation.period)
        settlement_key = m303_annual_settlement_order_key(period, payload.captured_at, authority=operation)
        if settlement_key is None:
            continue
        percentage = observation.casilla_values.get(PRORRATA_PORCENTAJE_CASILLA)
        if percentage is None:
            continue
        observations.append(
            _PriorSettlementObservation(
                percentage=percentage,
                source_filing_year=observation.filing_year,
                source_period=period.registry_token,
                stamped_revision_id=payload.stamped_revision_id,
                captured_at=payload.captured_at,
            )
        )
    return tuple(
        sorted(
            observations,
            key=lambda item: (
                m303_annual_settlement_order_key(
                    Period.from_year_and_code(item.source_filing_year, item.source_period),
                    item.captured_at,
                    authority=operation,
                )
                or (0, item.captured_at),
            ),
            reverse=True,
        )
    )


__all__ = [
    "PRORRATA_DIFFERENTIATED_SECTOR",
    "PRORRATA_OPERATOR_STATED",
    "PRORRATA_RETURN_CONTRADICTS_FIGURE",
    "PRORRATA_SEVERAL_ACTIVITIES",
    "ProrrataPriorDefinitivaSeed",
    "ProrrataPriorDefinitivaSeedEvaluation",
    "ProrrataSeedFinding",
    "cross_check_prorrata_entry_against_observations",
    "differentiated_sector_seed_finding",
    "evaluate_carried_prior_definitiva_seed_from_observations",
    "operator_stated_seed_finding",
    "prior_definitiva_source_coordinates",
]
