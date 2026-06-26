"""Multi-year prior-filing resolver.

Annual modelos and multi-year regimes need access to prior filings'
casilla outputs. The resolver selects available observations through a
:class:`RegistrySnapshot` that fixes the revision the caller is targeting.

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
from typing import TYPE_CHECKING, override

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import BindingSourceKind

if TYPE_CHECKING:
    from pathlib import Path

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...domain.calculations.registry import RegistryModeloObservation, RegistrySnapshot
from ..aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    storage_degradation_resolution,
)
from ._binding_prefill import _revision_prefill_divergence
from ._observations_repository import CalculationObservationRepository

_STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)


# ---------------------------------------------------------------------------
# Multi-year-renta authorization enrollment recorder
#
# The ``modelo-multiyear-renta`` ADR makes every modelo's calculation backend
# NON-FUNCTIONAL until an enrolling end-to-end persona test proves it across at
# least two distinct renta (annual) years. The manifest entry is a *claim*; the
# recorder below is the independent *verifier* the enrolling test drives.
#
# An enrolling test runs the REAL backend for two or more distinct
# ``filing_year`` values and records each year it exercised through the
# recorder. The recorder is un-fakeable in two ways: it admits a year only with
# an evidence token the caller cannot fabricate from nothing (calculation mode:
# a non-empty produced-value count from a real ``calculate_modelo_revision`` /
# registry calculation; non-calculation mode: an explicit, named two-year
# context the test had to construct from real adapters), and the resulting
# :class:`EnrollmentEvidence` enforces the ``>=2 distinct renta years``
# invariant at its own type boundary. A stub records nothing and a single-period
# test records one year — both fail the invariant, turning the gate RED.
# ---------------------------------------------------------------------------


class EnrollmentEvidenceError(ValueError):
    """Raised when an enrollment recording is missing its un-fakeable evidence.

    Calculation-mode recordings require a strictly-positive produced-value
    count (a real calculation emitted casillas); non-calculation-mode
    recordings require both a non-empty context label AND a strictly-positive
    persisted-observation count (at least one real
    :class:`RegistryModeloObservation` was saved to the real
    ``CalculationObservationRepository`` for that year). A recording that
    supplies a label alone — without a persisted observation count — is
    label-only and therefore fakeable; the recorder refuses it.
    """


class EnrollmentYearObservation(BaseModel):
    """One renta year an enrolling test proved the backend exercised.

    Attributes:
        modelo: The modelo id whose backend was exercised.
        filing_year: The distinct renta (annual) year exercised.
        calculation_mode: ``True`` when the year was produced by a real
            calculation (``calculate_modelo_revision`` / registry calculate);
            ``False`` for the non-calculation two-year-context registration
            used by informativa / reconciliation / structural modelos.
        produced_value_count: For calculation mode, the number of casilla
            values the real calculation produced — strictly positive, the
            evidence a calculation actually ran. Zero for non-calculation mode.
        context_label: For non-calculation mode, the named real two-year
            context the test constructed (e.g. a fidelity-comparison label).
            Empty for calculation mode.
        persisted_observation_count: For non-calculation mode, the number of
            :class:`RegistryModeloObservation` records the test actually persisted
            to the real ``CalculationObservationRepository`` for this year — must
            be strictly positive, the evidence a real repository interaction
            occurred. Zero for calculation mode. Mirrors the role of
            ``produced_value_count`` in calculation mode: a context-mode year
            claimed with zero persisted observations is label-only and therefore
            fakeable; the recorder refuses it.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    calculation_mode: bool
    produced_value_count: int = Field(ge=0, default=0)
    context_label: str = Field(max_length=128, default="")
    persisted_observation_count: int = Field(ge=0, default=0)

    @property
    def has_evidence(self) -> bool:
        """Return whether this observation carries its mode's required evidence."""
        if self.calculation_mode:
            return self.produced_value_count > 0
        # Context mode requires both a non-blank label AND at least one persisted
        # observation — a label alone is fakeable; the observation count proves a
        # real CalculationObservationRepository interaction happened.
        return bool(self.context_label.strip()) and self.persisted_observation_count > 0


class EnrollmentEvidence(BaseModel):
    """The verified cross-year evidence an enrolling test produced for one modelo.

    Constructed by :meth:`EnrollmentRecorder.evidence`. The ``>=2 distinct
    renta years`` invariant is enforced here so an enrollment that did not
    actually span two distinct years cannot construct — the contract is
    unconstructable to violate, mirroring
    :class:`aeat.core.access_gate.ModeloAuthorizationEntry`.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    observations: tuple[EnrollmentYearObservation, ...]

    @property
    def distinct_renta_years(self) -> tuple[int, ...]:
        """Return the distinct renta years exercised, sorted ascending."""
        return tuple(sorted({obs.filing_year for obs in self.observations}))

    @override
    def model_post_init(self, _context: object) -> None:
        """Enforce the >=2-distinct-years and per-observation-evidence contract."""
        from ...core.access_gate import MIN_DISTINCT_RENTA_YEARS

        if any(obs.modelo != self.modelo for obs in self.observations):
            mismatched = sorted({obs.modelo for obs in self.observations if obs.modelo != self.modelo})
            raise EnrollmentEvidenceError(
                f"enrollment evidence for modelo {self.modelo!r} mixes other modelos {mismatched!r}",
            )
        if any(not obs.has_evidence for obs in self.observations):
            raise EnrollmentEvidenceError(
                f"enrollment evidence for modelo {self.modelo!r} contains an observation with no "
                f"un-fakeable evidence (a calculation-mode year with zero produced values, or a "
                f"non-calculation-mode year with no context label)",
            )
        distinct = self.distinct_renta_years
        if len(distinct) < MIN_DISTINCT_RENTA_YEARS:
            raise EnrollmentEvidenceError(
                f"enrollment evidence for modelo {self.modelo!r} spans only {len(distinct)} distinct "
                f"renta year(s) {distinct!r}; the authorization gate requires at least "
                f"{MIN_DISTINCT_RENTA_YEARS}",
            )


class EnrollmentRecorder:
    """Accumulates the renta years an enrolling test proves the backend exercised.

    The enrolling test constructs one recorder per modelo, records each year it
    drives through the real backend, then calls :meth:`evidence` to obtain the
    verified :class:`EnrollmentEvidence` and assert it against the modelo's
    manifest claim. The recorder is the natural home named by the
    ``modelo-multiyear-renta`` ADR for the un-fakeable enrollment contract.
    """

    def __init__(self, modelo: str) -> None:
        self._modelo = modelo
        self._observations: list[EnrollmentYearObservation] = []

    @property
    def modelo(self) -> str:
        """Return the modelo id this recorder enrolls."""
        return self._modelo

    def record_calculation_year(self, *, filing_year: int, produced_value_count: int) -> None:
        """Record a renta year produced by a real calculation.

        Args:
            filing_year: The renta year the test calculated.
            produced_value_count: The number of casilla values the real
                calculation emitted. MUST be strictly positive — it is the
                evidence a calculation actually ran for this year.

        Raises:
            EnrollmentEvidenceError: When ``produced_value_count`` is not
                strictly positive (no real calculation output to evidence the
                year).
        """
        if produced_value_count <= 0:
            raise EnrollmentEvidenceError(
                f"modelo {self._modelo!r} calculation-mode recording for {filing_year} produced "
                f"{produced_value_count} values; a real calculation must emit at least one casilla",
            )
        self._observations.append(
            EnrollmentYearObservation(
                modelo=self._modelo,
                filing_year=filing_year,
                calculation_mode=True,
                produced_value_count=produced_value_count,
            ),
        )

    def record_context_year(
        self,
        *,
        filing_year: int,
        context_label: str,
        persisted_observation_count: int,
    ) -> None:
        """Record a renta year exercised through a real non-calculation context.

        For informativa / reconciliation / structural modelos that do not run a
        numeric calculation, the enrolling test still drives the real adapters
        for the year and names the context it constructed. To be un-fakeable the
        call must supply both a non-blank ``context_label`` AND a strictly
        positive ``persisted_observation_count`` — the number of
        :class:`RegistryModeloObservation` records actually saved to the real
        ``CalculationObservationRepository`` for this year. A label alone is not
        sufficient evidence: any string can be passed without touching the real
        adapters. The observation count proves a real repository interaction
        happened; it mirrors the role of ``produced_value_count`` in
        :meth:`record_calculation_year`.

        Args:
            filing_year: The renta year the test exercised.
            context_label: A non-empty label naming the real two-year context
                (e.g. ``"347-fidelity-year-over-year"``).
            persisted_observation_count: The number of
                :class:`~aeat.domain.calculations.registry.RegistryModeloObservation`
                records the test saved to the real
                ``CalculationObservationRepository`` for this year. MUST be
                strictly positive — it is the evidence a real adapter interaction
                occurred.

        Raises:
            EnrollmentEvidenceError: When ``context_label`` is blank or when
                ``persisted_observation_count`` is not strictly positive.
        """
        if not context_label.strip():
            raise EnrollmentEvidenceError(
                f"modelo {self._modelo!r} non-calculation recording for {filing_year} carries no "
                f"context label; name the real two-year context the test constructed",
            )
        if persisted_observation_count <= 0:
            raise EnrollmentEvidenceError(
                f"modelo {self._modelo!r} context-mode recording for {filing_year} has "
                f"persisted_observation_count={persisted_observation_count}; at least one real "
                f"RegistryModeloObservation must be saved to the CalculationObservationRepository "
                f"to prove the real adapters were exercised (a label alone is fakeable)",
            )
        self._observations.append(
            EnrollmentYearObservation(
                modelo=self._modelo,
                filing_year=filing_year,
                calculation_mode=False,
                context_label=context_label,
                persisted_observation_count=persisted_observation_count,
            ),
        )

    def evidence(self) -> EnrollmentEvidence:
        """Return the verified cross-year evidence accumulated so far.

        The recorder validates the ``>=2 distinct renta years`` floor here so
        the public API raises the documented :class:`EnrollmentEvidenceError`
        directly; :class:`EnrollmentEvidence` re-enforces the same invariant at
        its own type boundary as an unconstructable-to-violate backstop (a
        pydantic ``ValidationError`` there would wrap this error type).

        Returns:
            The verified :class:`EnrollmentEvidence`.

        Raises:
            EnrollmentEvidenceError: When fewer than two distinct renta years
                were recorded.
        """
        from ...core.access_gate import MIN_DISTINCT_RENTA_YEARS

        distinct = sorted({obs.filing_year for obs in self._observations})
        if len(distinct) < MIN_DISTINCT_RENTA_YEARS:
            raise EnrollmentEvidenceError(
                f"modelo {self._modelo!r} recorded only {len(distinct)} distinct renta year(s) "
                f"{tuple(distinct)!r}; the authorization gate requires at least "
                f"{MIN_DISTINCT_RENTA_YEARS} distinct years driven through the real backend",
            )
        return EnrollmentEvidence(modelo=self._modelo, observations=tuple(self._observations))


def assert_enrollment_matches_manifest(
    evidence: EnrollmentEvidence,
    *,
    repository_root: Path | None = None,
) -> None:
    """Assert recorded enrollment evidence matches the modelo's manifest claim.

    The enrolling end-to-end test calls this after recording its years. It is
    the load-bearing cross-check that converts the manifest from an honour
    claim into a verified one: the recorded distinct-year set MUST equal the
    manifest entry's declared ``renta_years``. A mismatch (the test exercised
    different years than the manifest claims) raises, turning the enrolling
    test RED.

    Args:
        evidence: The verified evidence from :meth:`EnrollmentRecorder.evidence`.
        repository_root: Optional registry root override (tests). When
            ``None`` the bundled registry authority's manifest is used.

    Raises:
        EnrollmentEvidenceError: When no manifest entry enrolls the modelo, or
            the recorded distinct-year set differs from the claimed ``renta_years``.
    """
    from ...core.resources import resources

    if repository_root is None:
        manifest = resources().modelos.authority.authorization_manifest
    else:
        from ...core.access_gate import load_authorization_manifest

        manifest = load_authorization_manifest(repository_root)
    entry = manifest.entry_for(evidence.modelo)
    if entry is None:
        raise EnrollmentEvidenceError(
            f"modelo {evidence.modelo!r} recorded enrollment evidence but the authorization manifest "
            f"declares no entry enrolling it; add the [[modelo]] entry in the same commit as the test",
        )
    recorded = evidence.distinct_renta_years
    claimed = entry.distinct_renta_years
    if recorded != claimed:
        raise EnrollmentEvidenceError(
            f"modelo {evidence.modelo!r} enrollment mismatch: the test exercised renta years "
            f"{recorded!r} but the manifest claims {claimed!r}; the recorded year-set must equal the claim",
        )


class MultiYearResolutionRequest(BaseModel):
    """Parameters for one prior-filing observation scan.

    Passed to :meth:`MultiYearResolver.resolve`. ``modelo`` and
    ``current_year`` identify the filing being calculated;
    ``years_back`` controls how many prior renta years the resolver
    walks back; ``periods`` optionally restricts the scan to specific
    period tokens (e.g. ``("1P", "2P", "3P")`` for Modelo 202 pagos
    fraccionados).
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    current_year: int = Field(ge=2000, le=2099)
    years_back: int = Field(ge=1, le=20)
    periods: tuple[str, ...] | None = None


class MultiYearResolutionReport(BaseModel):
    """Outcome of one :meth:`MultiYearResolver.resolve` scan.

    Carries the original ``request``, the matched
    :class:`RegistryModeloObservation` records, and three derived
    year-sets (``requested_years``, ``found_years``, ``missing_years``)
    that let callers decide whether to refuse, prompt the operator, or
    zero-fill for absent prior years without re-scanning the store.
    """

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

    .. rubric:: Deferral note (W02.P04.S25)

    This class has no live production caller in the current calculate path
    (``calculate_modelo_revision_from_bucket_aggregation_with_diagnostics``).
    :class:`PreviousFilingSourceResolver` covers the ``previous_filing``
    source mesh for the live path by calling
    :func:`~aeat.application.calculations.resolve_bindings_from_local_store`
    directly.

    ``MultiYearResolver`` is the *explicit multi-year scan API* intended for
    modelos that need structured year-set coverage reports:

    - Modelo 200 IS — BIN unlimited carryforward (LIS arts. 25-26) and M202
      pago fraccionado roll-up across prior years.
    - Modelo 303 IVA — prorrata four-year average (LIVA art. 105) and
      regularización inversiones five-year straight-line (LIVA art. 93).

    It returns a :class:`MultiYearResolutionReport` with explicit
    ``requested_years``, ``found_years``, and ``missing_years`` sets that
    :class:`PreviousFilingSourceResolver` does not expose — callers can
    decide whether to refuse, prompt the operator, or zero-fill absent years.

    **Why not wired yet:** the modelos above are in DORMANT aggregation state
    per the calculation-engine-foundations audit F6 matrix (no enrolled source
    resolver for their multi-year inputs). This class will be wired when those
    modelos are enrolled in W02.P06 / W03.P08.

    **Follow-up:** wire ``MultiYearResolver`` as the multi-year scan back-end
    for M200 BIN carry and M303 prorrata when the respective modelo resolvers
    are enrolled. Reference: calculation-engine-foundations plan W02.P06 /
    W03.P08, audit F6.
    """

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
    ) -> None:
        self._repository = repository if repository is not None else CalculationObservationRepository()

    def resolve(self, request: MultiYearResolutionRequest) -> MultiYearResolutionReport:
        """Scan persisted observations matching ``request`` and return a :class:`MultiYearResolutionReport`.

        The returned report's ``observations`` are sorted by
        ``(filing_year, period)`` ascending so callers that expect
        chronological order (e.g. quarter 1T - 4T summing for an annual
        modelo) can iterate directly.
        """
        requested_years = tuple(request.current_year - offset for offset in range(1, request.years_back + 1))
        observations: list[RegistryModeloObservation] = []
        for payload in self._repository.iter_modelo(request.modelo):
            obs = payload.observation
            if obs.filing_year not in requested_years:
                continue
            if request.periods is not None and obs.period not in request.periods:
                continue
            # R2 carry gate: divergent stamp → refuse (skip); missing stamp → carry proceeds.
            # (ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2)
            if _revision_prefill_divergence(payload):
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
    """Source mesh resolver for ``source = "previous_filing"`` calculation bindings.

    Registered under ``resolver_id = "previous_filing"`` in the source mesh.
    When the calculation engine encounters a binding whose source is
    ``"previous_filing"``, this resolver reads the relevant prior-year
    :class:`RegistryModeloObservation` records from the local
    :class:`CalculationObservationRepository` and maps them to the binding
    values the engine expects. Storage-degradation errors
    (classification, decryption, version) are caught and returned as a
    :func:`storage_degradation_resolution` rather than propagated.
    """

    resolver_id = "previous_filing"
    owned_sources: tuple[BindingSourceKind, ...] = (BindingSourceKind.PREVIOUS_FILING,)

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
                period=context.period.registry_token,
            )
        from ._binding_prefill import resolve_bindings_from_local_store

        try:
            report = resolve_bindings_from_local_store(snapshot, repository=self._repository)
        except _STORAGE_DEGRADATION_ERRORS as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
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

    Returns a :class:`MultiYearResolutionReport`.
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
    "EnrollmentEvidence",
    "EnrollmentEvidenceError",
    "EnrollmentRecorder",
    "EnrollmentYearObservation",
    "MultiYearResolutionReport",
    "MultiYearResolutionRequest",
    "MultiYearResolver",
    "PreviousFilingSourceResolver",
    "assert_enrollment_matches_manifest",
    "resolve_prior_year_observations",
]
