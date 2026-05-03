"""Central legal calculation registry.

This module is the domain entry point for tax-calculation registration.
It binds modelo metadata, legal basis, filing cadence, and formula
rulesets into one audited registry. The committed casilla corpus is a
materialized catalogue view; it is not a second calculation authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core.errors import AmbiguousPeriodError, MissingRulesetError, RulesetValidationError
from ..formulas import FiscalPeriod, Quarter, Ruleset, RulesetRegistry
from ..formulas._rulesets import ALL_RULESETS
from ..modelos import MODELO_REGISTRY, ModeloCadence, ModeloCode, ModeloMetadata


@dataclass(frozen=True, slots=True)
class CalculationCatalogueTarget:
    """One corpus catalogue target backed by a registered calculation slot."""

    modelo: ModeloCode
    period: str
    fiscal_period: FiscalPeriod
    variant: str = "default"


class CalculationRegistry(BaseModel):
    """Audited registry for modelo calculation rules and legal provenance.

    Args:
        rulesets: Approved formula rulesets.
        modelos: Authoritative modelo metadata keyed by :class:`ModeloCode`.

    The registry is intentionally configurable for tests and downstream
    deployments, but strict by default: formula IDs must be scoped to
    their owning ruleset, every ruleset must have legal citations, and
    every ruleset modelo must exist in the modelo metadata registry.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    rulesets: tuple[Ruleset, ...] = Field(default_factory=tuple)
    modelos: Mapping[ModeloCode, ModeloMetadata] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> CalculationRegistry:
        known_modelos = set(self.modelos)
        failures: list[str] = []
        for ruleset in self.rulesets:
            if ruleset.modelo not in known_modelos:
                failures.append(f"{ruleset.ruleset_id}: modelo {ruleset.modelo.value} missing from modelo registry")
            if not ruleset.legal_citations:
                failures.append(f"{ruleset.ruleset_id}: missing legal citations")
            prefix = f"{ruleset.ruleset_id}."
            for formula in ruleset.formulas:
                if not formula.formula_id.startswith(prefix):
                    failures.append(
                        f"{ruleset.ruleset_id}: formula {formula.formula_id!r} is outside owning ruleset scope"
                    )
        if failures:
            raise RulesetValidationError("calculation registry invalid:\n" + "\n".join(f" - {f}" for f in failures))
        # Reuse the lower-level overlap / duplicate checks.
        RulesetRegistry(rulesets=self.rulesets)
        return self

    @property
    def formula_registry(self) -> RulesetRegistry:
        """Return the formula resolver view over this registry."""
        return RulesetRegistry(rulesets=self.rulesets)

    def metadata_for(self, modelo: ModeloCode | str) -> ModeloMetadata:
        """Return authoritative metadata for ``modelo``."""
        code = modelo if isinstance(modelo, ModeloCode) else ModeloCode(modelo)
        return self.modelos[code]

    def resolve_ruleset(
        self,
        *,
        modelo: ModeloCode | str,
        period: FiscalPeriod,
        variant: str = "default",
    ) -> Ruleset:
        """Resolve the approved ruleset for one modelo / period slot."""
        code = modelo if isinstance(modelo, ModeloCode) else ModeloCode(modelo)
        return self.formula_registry.resolve(modelo=code, period=period, variant=variant)

    def catalogue_targets(
        self,
        *,
        modelo: ModeloCode | str | None = None,
        year: int | None = None,
        period: str | None = None,
        variant: str = "default",
    ) -> tuple[CalculationCatalogueTarget, ...]:
        """Return materializable catalogue targets from registry metadata.

        Args:
            modelo: Optional modelo filter.
            year: Optional fiscal year filter.
            period: Optional exact canonical period filter, e.g. ``2026Q1``.
            variant: Ruleset variant, defaulting to the canonical slot.

        Returns:
            A deterministic tuple of targets that have a registered
            ruleset for the requested slot.
        """
        modelo_filter = modelo if isinstance(modelo, ModeloCode) or modelo is None else ModeloCode(modelo)
        years = (year,) if year is not None else tuple(sorted({rs.effective_from.year for rs in self.rulesets}))
        out: list[CalculationCatalogueTarget] = []
        for code in sorted(self.modelos, key=lambda c: c.value):
            if modelo_filter is not None and code != modelo_filter:
                continue
            for y in years:
                for target_period, fiscal_period in self._periods_for_metadata(code, y):
                    if period is not None and target_period != period:
                        continue
                    try:
                        self.resolve_ruleset(modelo=code, period=fiscal_period, variant=variant)
                    except (AmbiguousPeriodError, MissingRulesetError):
                        continue
                    out.append(
                        CalculationCatalogueTarget(
                            modelo=code,
                            period=target_period,
                            fiscal_period=fiscal_period,
                            variant=variant,
                        )
                    )
        return tuple(out)

    def _periods_for_metadata(self, modelo: ModeloCode, year: int) -> tuple[tuple[str, FiscalPeriod], ...]:
        cadence = self.modelos[modelo].cadence
        if cadence == ModeloCadence.QUARTERLY:
            return tuple(
                (f"{year}Q{idx}", FiscalPeriod(year=year, quarter=quarter))
                for idx, quarter in enumerate((Quarter.Q1, Quarter.Q2, Quarter.Q3, Quarter.Q4), start=1)
            )
        if cadence == ModeloCadence.MONTHLY:
            return tuple((f"{year}-{month:02d}", FiscalPeriod(year=year)) for month in range(1, 13))
        return ((str(year), FiscalPeriod(year=year)),)


_cached_registry: CalculationRegistry | None = None


def get_calculation_registry() -> CalculationRegistry:
    """Return the shared approved calculation registry."""
    global _cached_registry
    if _cached_registry is None:
        _cached_registry = CalculationRegistry(
            rulesets=ALL_RULESETS,
            modelos=MappingProxyType(dict(MODELO_REGISTRY)),
        )
    return _cached_registry
