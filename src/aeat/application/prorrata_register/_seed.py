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
    :func:`~domain.calculations.registry.select_revision`
        Law-determined revision resolver used to re-confirm the stored
        ``stamped_revision_id`` before trusting the carry.
    :class:`~application.calculations.CrossPeriodCleanStateBlocker`
        Blocker vocabulary reused for revision-divergent seed findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from ...core import Modelo, ProrrataProvisionalProvenance, ProrrataRegisterRegime
from ...core.resources import resources
from ...domain.calculations.registry import CasillaId, select_revision, validated_casilla_id
from ...domain.prorrata_register import ProrrataRegisterEntry
from ..calculations import CalculationObservationRepository
from ..calculations._cross_period_models import CrossPeriodCleanStateBlocker

_PRORRATA_PORCENTAJE_CASILLA: Final[CasillaId] = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata register carried prior definitive seed casilla id",
)
_SETTLEMENT_PERIODS: Final[tuple[str, ...]] = ("4T", "0A")
_SETTLEMENT_PERIOD_ORDER: Final[dict[str, int]] = {period: index for index, period in enumerate(_SETTLEMENT_PERIODS)}
_MISSING_LEGACY_REVISION_STAMP = "missing_legacy_revision_stamp"
_REGULATED_OVERRIDE_DIFFERENCE = "regulated_prorrata_override_difference"


@dataclass(frozen=True, slots=True)
class ProrrataPriorDefinitivaSeed:
    """A re-confirmed prior-year definitive percentage ready to seed the register."""

    entry: ProrrataRegisterEntry
    source_modelo: str
    source_filing_year: int
    source_period: str
    source_casilla_id: CasillaId
    stamped_revision_id: str | None


@dataclass(frozen=True, slots=True)
class ProrrataSeedFinding:
    """Operator-visible seed/cross-check blocker or advisory."""

    code: str
    blocking: bool
    message: str
    source_modelo: str
    source_filing_year: int
    source_period: str
    stamped_revision_id: str | None
    selected_revision_id: str | None

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
    stamped_revision_id: str | None
    captured_at: datetime


def evaluate_carried_prior_definitiva_seed(
    *,
    ejercicio: int,
    observation_repository: CalculationObservationRepository | None = None,
    sector_id: str | None = None,
) -> ProrrataPriorDefinitivaSeedEvaluation:
    """Evaluate the carried-prior-definitive seed and surface blocker/advisory findings.

    Divergent or unreconfirmable revision stamps produce a blocking
    ``registry_revision_divergence`` finding and no seed. A missing legacy stamp
    is a non-blocking advisory: the prior observation can seed the register, but
    the operator-visible finding records that the legacy source could not be
    re-confirmed.
    """
    repository = observation_repository if observation_repository is not None else CalculationObservationRepository()
    prior_year = ejercicio - 1
    for source in _prior_settlement_observations(repository, prior_year=prior_year):
        try:
            selected_revision = select_revision(
                resources().modelos.get(Modelo.M303.value),
                filing_year=source.source_filing_year,
                period=source.source_period,
            )
        except Exception as exc:
            return ProrrataPriorDefinitivaSeedEvaluation(
                seed=None,
                findings=(
                    _registry_revision_divergence_finding(
                        source,
                        selected_revision_id=None,
                        detail=f"revision selection failed: {type(exc).__name__}",
                    ),
                ),
            )
        if source.stamped_revision_id is None or source.stamped_revision_id == "":
            return ProrrataPriorDefinitivaSeedEvaluation(
                seed=_seed_from_source(ejercicio=ejercicio, source=source, sector_id=sector_id),
                findings=(_missing_legacy_stamp_finding(source, selected_revision_id=selected_revision.id),),
            )
        if source.stamped_revision_id != selected_revision.id:
            return ProrrataPriorDefinitivaSeedEvaluation(
                seed=None,
                findings=(
                    _registry_revision_divergence_finding(
                        source,
                        selected_revision_id=selected_revision.id,
                        detail="stamped revision differs from the law-determined revision",
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
    fallback: str | None,
) -> str | None:
    for finding in findings:
        if finding.selected_revision_id is not None:
            return finding.selected_revision_id
    return fallback


def _carried_entry_contradiction_finding(
    seed: ProrrataPriorDefinitivaSeed,
    *,
    selected_revision_id: str | None,
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
    selected_revision_id: str | None,
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
    selected_revision_id: str | None,
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


def _missing_legacy_stamp_finding(
    source: _PriorSettlementObservation,
    *,
    selected_revision_id: str,
) -> ProrrataSeedFinding:
    return ProrrataSeedFinding(
        code=_MISSING_LEGACY_REVISION_STAMP,
        blocking=False,
        message=(
            "Prior Modelo 303 prorrata observation seeded carried_prior_definitiva but has no "
            "stamped_revision_id because it predates revision stamping. Re-capture the source "
            "period to clear this advisory."
        ),
        source_modelo=Modelo.M303.value,
        source_filing_year=source.source_filing_year,
        source_period=source.source_period,
        stamped_revision_id=None,
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
        source_period = _settlement_period_token(observation.period)
        if source_period is None:
            continue
        percentage = observation.casilla_values.get(_PRORRATA_PORCENTAJE_CASILLA)
        if percentage is None:
            continue
        observations.append(
            _PriorSettlementObservation(
                percentage=percentage,
                source_filing_year=observation.filing_year,
                source_period=source_period,
                stamped_revision_id=getattr(payload, "stamped_revision_id", None),
                captured_at=payload.captured_at,
            )
        )
    return tuple(
        sorted(
            observations,
            key=lambda item: (_SETTLEMENT_PERIOD_ORDER[item.source_period], item.captured_at),
        )
    )


def _settlement_period_token(period: str) -> str | None:
    token = period.upper()
    return token if token in _SETTLEMENT_PERIOD_ORDER else None


__all__ = [
    "ProrrataPriorDefinitivaSeed",
    "ProrrataPriorDefinitivaSeedEvaluation",
    "ProrrataSeedFinding",
    "cross_check_prorrata_entry_against_prior_observation",
    "evaluate_carried_prior_definitiva_seed",
    "seed_carried_prior_definitiva_entry",
]
