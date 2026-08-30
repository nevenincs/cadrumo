"""Seed the cross-period prorrata register from stamped prior observations.

The LIVA art. 105.Uno normal provisional percentage is the prior ejercicio's
definitive prorrata. This module locates that percentage in the prior Modelo 303
settlement observation and trusts it only after the observation's registry
revision stamp re-confirms against the law-determined revision for the source
period.

See Also:
    :class:`~domain.prorrata_register.ProrrataRegisterEntry`
        Register record populated with the carried-prior-definitive percentage,
        provenance, and source-observation identity.
    :class:`~core.ProrrataProvisionalProvenance`
        Closed provenance axis whose ``CARRIED_PRIOR_DEFINITIVA`` member marks
        the normal LIVA art. 105.Uno seed path.
    :class:`~application.calculations.CalculationObservationRepository`
        Local observation catalogue scanned for prior Modelo 303 settlement
        observations.
    :func:`~application.calculations.revision_carry_outcome`
        Shared law-determined gate used to re-confirm the stored
        ``stamped_revision_id`` before trusting the carry.
    :class:`~application.calculations.CrossPeriodCleanStateBlocker`
        Blocker vocabulary reused for revision-divergent seed findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from ...core import ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ...core.modelo import Modelo
from ...core.period import Period
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...domain.calculations.registry.ids import RevisionId
from ...domain.iva.m303_settlement import m303_annual_settlement_order_key
from ...domain.prorrata_register import ProrrataRegisterEntry
from ..calculations import CalculationObservationRepository, CrossPeriodCleanStateBlocker, revision_carry_outcome

_PRORRATA_PORCENTAJE_CASILLA: Final[CasillaId] = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata register carried prior definitive seed casilla id",
)
_REGULATED_OVERRIDE_DIFFERENCE = "regulated_prorrata_override_difference"


@dataclass(frozen=True, slots=True)
class ProrrataPriorDefinitivaSeed:
    """A re-confirmed prior-year definitive percentage ready to seed the register."""

    entry: ProrrataRegisterEntry
    source_modelo: str
    source_filing_year: int
    source_period: str
    source_casilla_id: CasillaId
    stamped_revision_id: RevisionId


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


def evaluate_carried_prior_definitiva_seed(
    *,
    ejercicio: int,
    observation_repository: CalculationObservationRepository | None = None,
    sector_id: str | None = None,
) -> ProrrataPriorDefinitivaSeedEvaluation:
    """Evaluate the carried-prior-definitive seed and surface findings.

    Divergent or unreconfirmable revision stamps produce a blocking
    ``registry_revision_divergence`` finding and no seed.
    """
    repository = observation_repository if observation_repository is not None else CalculationObservationRepository()
    prior_year = ejercicio - 1
    for source in _prior_settlement_observations(repository, prior_year=prior_year):
        revision_outcome = revision_carry_outcome(
            source.stamped_revision_id,
            source_modelo=Modelo.M303.value,
            source_filing_year=source.source_filing_year,
            source_period=source.source_period,
        )
        if revision_outcome.refused:
            return ProrrataPriorDefinitivaSeedEvaluation(
                seed=None,
                findings=(
                    _registry_revision_divergence_finding(
                        source,
                        selected_revision_id=revision_outcome.selected_revision_id,
                        detail=revision_outcome.detail or "revision stamp cannot be re-confirmed",
                    ),
                ),
            )
        return ProrrataPriorDefinitivaSeedEvaluation(
            seed=_seed_from_source(ejercicio=ejercicio, source=source, sector_id=sector_id),
            findings=(),
        )
    return ProrrataPriorDefinitivaSeedEvaluation(seed=None, findings=())


def seed_carried_prior_definitiva_entry(
    *,
    ejercicio: int,
    observation_repository: CalculationObservationRepository | None = None,
    sector_id: str | None = None,
) -> ProrrataPriorDefinitivaSeed | None:
    """Build a carried-prior-definitive register entry from a stamped prior observation.

    The seed is available only when the prior ejercicio has a Modelo 303
    settlement-period observation carrying ``iva.prorrata-porcentaje`` and that
    observation's ``stamped_revision_id`` still matches the law-determined
    revision selected for its source ``(M303, ejercicio - 1, settlement period)``.
    Divergent or unreconfirmable observations are not trusted. Call
    :func:`evaluate_carried_prior_definitiva_seed` when the caller needs the
    operator-facing blocker/advisory findings that explain why a seed did or did
    not resolve.

    Args:
        ejercicio: Ejercicio whose provisional prorrata entry is being seeded.
        observation_repository: Observation repository to scan. Defaults to the
            active runtime repository.
        sector_id: Optional sector axis for future sectores-diferenciados
            entries. ``None`` seeds the whole-entity register entry.

    Returns:
        A :class:`ProrrataPriorDefinitivaSeed` when a stamped prior settlement
        observation re-confirms, otherwise ``None``.
    """
    return evaluate_carried_prior_definitiva_seed(
        ejercicio=ejercicio,
        observation_repository=observation_repository,
        sector_id=sector_id,
    ).seed


def cross_check_prorrata_entry_against_prior_observation(
    entry: ProrrataRegisterEntry,
    *,
    observation_repository: CalculationObservationRepository | None = None,
) -> tuple[ProrrataSeedFinding, ...]:
    """Cross-check a register entry against the prior definitive observation.

    A carried-prior-definitive entry must match the prior Modelo 303 settlement
    observation because art. 105.Uno is the normal carry rule. AEAT-authorised
    and inicio-de-actividades entries are regulated alternatives: when they
    differ from the prior definitive, the difference is surfaced as a
    non-blocking notice that names the provenance rather than being silenced.
    """
    if entry.provisional_percentage is None or entry.provisional_provenance is None:
        return ()

    evaluation = evaluate_carried_prior_definitiva_seed(
        ejercicio=entry.ejercicio,
        observation_repository=observation_repository,
        sector_id=entry.sector_id,
    )
    seed = evaluation.seed
    if seed is None:
        return evaluation.findings

    selected_revision_id = _selected_revision_id_from_findings(
        evaluation.findings,
        fallback=seed.stamped_revision_id,
    )
    if entry.provisional_provenance is ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA:
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

    if (
        entry.provisional_provenance
        in {ProrrataProvisionalProvenance.AEAT_AUTORIZADA, ProrrataProvisionalProvenance.INICIO_ACTIVIDAD}
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


def _seed_from_source(
    *,
    ejercicio: int,
    source: _PriorSettlementObservation,
    sector_id: str | None,
) -> ProrrataPriorDefinitivaSeed:
    entry = ProrrataRegisterEntry(
        ejercicio=ejercicio,
        regime=ProrrataRegisterRegime.GENERAL,
        especial_transition=None,
        sector_id=sector_id,
        provisional_percentage=source.percentage,
        provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        source_observation_ref=_source_observation_ref(source),
    )
    return ProrrataPriorDefinitivaSeed(
        entry=entry,
        source_modelo=Modelo.M303.value,
        source_filing_year=source.source_filing_year,
        source_period=source.source_period,
        source_casilla_id=_PRORRATA_PORCENTAJE_CASILLA,
        stamped_revision_id=source.stamped_revision_id,
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
            "carried_prior_definitiva register entry contradicts the prior Modelo 303 "
            f"settlement observation: {detail}. Reconcile the register entry with "
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
    assert provenance is not None
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
            "Prior Modelo 303 prorrata observation cannot seed carried_prior_definitiva: "
            f"{detail}. Re-file or re-capture {source.source_filing_year} {source.source_period} "
            "so the observation is stamped under the law-determined registry revision."
        ),
        source_modelo=Modelo.M303.value,
        source_filing_year=source.source_filing_year,
        source_period=source.source_period,
        stamped_revision_id=source.stamped_revision_id,
        selected_revision_id=selected_revision_id,
    )


def _source_observation_ref(source: _PriorSettlementObservation) -> str:
    return f"{Modelo.M303.value}:{source.source_filing_year}:{source.source_period}"


def _prior_settlement_observations(
    repository: CalculationObservationRepository,
    *,
    prior_year: int,
) -> tuple[_PriorSettlementObservation, ...]:
    observations: list[_PriorSettlementObservation] = []
    for payload in repository.iter_modelo(Modelo.M303.value):
        observation = payload.observation
        if observation.filing_year != prior_year:
            continue
        period = Period.from_year_and_code(observation.filing_year, observation.period)
        settlement_key = m303_annual_settlement_order_key(period, payload.captured_at)
        if settlement_key is None:
            continue
        percentage = observation.casilla_values.get(_PRORRATA_PORCENTAJE_CASILLA)
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
                )
                or (0, item.captured_at),
            ),
            reverse=True,
        )
    )


__all__ = [
    "ProrrataPriorDefinitivaSeed",
    "ProrrataPriorDefinitivaSeedEvaluation",
    "ProrrataSeedFinding",
    "cross_check_prorrata_entry_against_prior_observation",
    "evaluate_carried_prior_definitiva_seed",
    "seed_carried_prior_definitiva_entry",
]
