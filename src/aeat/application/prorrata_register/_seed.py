"""Seed the cross-period prorrata register from stamped prior observations.

The LIVA art. 105.Uno normal provisional percentage is the prior ejercicio's
definitive prorrata. This module locates that percentage in the prior Modelo 303
settlement observation and trusts it only after the observation's registry
revision stamp re-confirms against the law-determined revision for the source
period.
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

_PRORRATA_PORCENTAJE_CASILLA: Final[CasillaId] = validated_casilla_id(
    "iva.prorrata-porcentaje",
    surface="prorrata register carried prior definitive seed casilla id",
)
_SETTLEMENT_PERIODS: Final[tuple[str, ...]] = ("4T", "0A")
_SETTLEMENT_PERIOD_ORDER: Final[dict[str, int]] = {period: index for index, period in enumerate(_SETTLEMENT_PERIODS)}


@dataclass(frozen=True, slots=True)
class ProrrataPriorDefinitivaSeed:
    """A re-confirmed prior-year definitive percentage ready to seed the register."""

    entry: ProrrataRegisterEntry
    source_modelo: str
    source_filing_year: int
    source_period: str
    source_casilla_id: CasillaId
    stamped_revision_id: str


@dataclass(frozen=True, slots=True)
class _PriorSettlementObservation:
    percentage: Decimal
    source_filing_year: int
    source_period: str
    stamped_revision_id: str
    captured_at: datetime


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
    Divergent or unreconfirmable observations are not trusted by this first seed
    builder; the following plan rows add the operator-facing blocker/advisory
    surfaces for those cases.

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
    repository = observation_repository if observation_repository is not None else CalculationObservationRepository()
    prior_year = ejercicio - 1
    for source in _prior_settlement_observations(repository, prior_year=prior_year):
        selected_revision = select_revision(
            resources().modelos.get(Modelo.M303.value),
            filing_year=source.source_filing_year,
            period=source.source_period,
        )
        if source.stamped_revision_id != selected_revision.id:
            continue
        entry = ProrrataRegisterEntry(
            ejercicio=ejercicio,
            regime=ProrrataRegisterRegime.GENERAL,
            sector_id=sector_id,
            provisional_percentage=source.percentage,
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        )
        return ProrrataPriorDefinitivaSeed(
            entry=entry,
            source_modelo=Modelo.M303.value,
            source_filing_year=source.source_filing_year,
            source_period=source.source_period,
            source_casilla_id=_PRORRATA_PORCENTAJE_CASILLA,
            stamped_revision_id=source.stamped_revision_id,
        )
    return None


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
                stamped_revision_id=payload.stamped_revision_id,
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
    "seed_carried_prior_definitiva_entry",
]
