"""Multi-year prior-filing resolver.

Annual modelos and multi-year regimes need access to prior filings'
casilla outputs:

- Modelo 200 (IS) consults modelo 202 1P/2P/3P pago fraccionado
  filings of the SAME year and prior years' base imponible negativa
  carryforwards (LIS arts. 25-26, unlimited carryforward subject to
  acquisition caps).
- Modelo 303 (IVA) prorrata deducción provisional (LIVA art. 105) is
  the mean of the four prior years' definitive prorrata.
- Modelo 303 regularización inversiones (LIVA art. 93) applies a
  five-year (ten-year for inmuebles) straight-line schedule against
  the prior-year deduction history.
- Modelo 180 / 190 / 193 / 390 sum the same year's quarterly source
  modelo for an annual roll-up.

This resolver is the application-layer consumer that the engine /
relation_resolver / binding pre-resolution call into. It reads
observations from the local `CalculationObservationRepository` and
returns them as the `RegistryModeloObservation` records the runtime
expects.

The resolver does NOT silently invent missing prior years.  When a
caller requests `years_back=4` and only 2 are persisted, the
returned tuple is shorter; callers decide whether to refuse, prompt
the operator, fall back to AEAT live state, or zero-fill.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ...domain.calculations.registry._bindings import RegistryModeloObservation
from ...domain.calculations.registry._schema import RegistrySnapshot
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ._observations_repository import CalculationObservationRepository

_STRICT_FROZEN: Final = ConfigDict(strict=True, frozen=True, extra="forbid")


class MultiYearResolutionRequest(BaseModel):
    """A request to scan the local observation store for prior filings."""

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    current_year: int = Field(ge=2000, le=2099)
    years_back: int = Field(ge=1, le=20)
    periods: tuple[str, ...] | None = None


class MultiYearResolutionReport(BaseModel):
    """Outcome of one resolver scan with provenance for downstream gating."""

    model_config = _STRICT_FROZEN

    request: MultiYearResolutionRequest
    observations: tuple[RegistryModeloObservation, ...]
    requested_years: tuple[int, ...]
    found_years: tuple[int, ...]
    missing_years: tuple[int, ...]


class MultiYearResolver:
    """Reads from `CalculationObservationRepository`, returns prior observations.

    Construct with `MultiYearResolver()` for default repository
    binding; inject a custom repository in tests by passing
    `repository=...` (the resolver does no construction beyond the
    repository it's handed).
    """

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
    ) -> None:
        self._repository = repository if repository is not None else CalculationObservationRepository()

    def resolve(self, request: MultiYearResolutionRequest) -> MultiYearResolutionReport:
        """Scan persisted observations matching `request` and report findings.

        The returned `MultiYearResolutionReport.observations` is
        sorted by `(filing_year, period)` ascending so callers that
        expect chronological order (e.g. quarter 1T → 4T summing
        for an annual modelo) can iterate directly.
        """

        requested_years = tuple(request.current_year - offset for offset in range(1, request.years_back + 1))
        observations: list[RegistryModeloObservation] = []
        for payload in self._repository.iter_modelo(request.modelo):
            obs = payload.observation
            if obs.filing_year not in requested_years:
                continue
            if request.periods is not None and obs.period not in request.periods:
                continue
            observations.append(obs)
        observations.sort(key=lambda o: (o.filing_year, o.period))
        found_years = tuple(sorted({obs.filing_year for obs in observations}))
        missing_years = tuple(year for year in requested_years if year not in found_years)
        return MultiYearResolutionReport(
            request=request,
            observations=tuple(observations),
            requested_years=requested_years,
            found_years=found_years,
            missing_years=missing_years,
        )


class PreviousFilingSourceResolver:
    """Resolve ``source = "previous_filing"`` bindings through the source mesh."""

    resolver_id = "previous_filing"
    owned_sources = ("previous_filing",)

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
    ) -> None:
        self._repository = repository
        self._registry_snapshot = registry_snapshot

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        snapshot = self._registry_snapshot
        if snapshot is None:
            from ...core.resources import resources

            snapshot = resources().modelos.authority.snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period,
            )
        from ._binding_prefill import resolve_bindings_from_local_store

        report = resolve_bindings_from_local_store(snapshot, repository=self._repository)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=report.binding_values,
            provenance=tuple(
                CalculationSourceProvenance(
                    source_kind="previous_filing",
                    source_ref=(
                        f"{item.source_modelo}:{item.source_filing_year}:"
                        f"{','.join(item.source_periods)}:{item.binding_id}"
                    ),
                )
                for item in report.prefilled
            ),
        )


def resolve_prior_year_observations(
    modelo: str,
    current_year: int,
    years_back: int,
    *,
    periods: Iterable[str] | None = None,
    repository: CalculationObservationRepository | None = None,
) -> MultiYearResolutionReport:
    """Functional entry point for one-shot scans without constructing a resolver.

    Equivalent to constructing `MultiYearResolver(repository=...)`
    and calling `resolve(MultiYearResolutionRequest(...))`.
    """

    resolver = MultiYearResolver(repository=repository)
    request = MultiYearResolutionRequest(
        modelo=modelo,
        current_year=current_year,
        years_back=years_back,
        periods=tuple(periods) if periods is not None else None,
    )
    return resolver.resolve(request)


__all__ = [
    "MultiYearResolutionReport",
    "MultiYearResolutionRequest",
    "MultiYearResolver",
    "PreviousFilingSourceResolver",
    "resolve_prior_year_observations",
]
