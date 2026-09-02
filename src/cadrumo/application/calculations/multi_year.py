"""Enrollment evidence and the previous-filing source-mesh adapter.

The enrollment surface records the real renta years exercised by continuity
tests through :class:`EnrollmentRecorder`, emits :class:`EnrollmentEvidence`,
and checks those observations against the
:class:`~core.access_gate.ModeloAuthorizationEntry` claimed by the bundled
authorization manifest.

The calculation surface is :class:`PreviousFilingSourceResolver`, the source
mesh adapter for :attr:`~core.BindingSourceKind.PREVIOUS_FILING`. It
selects the caller's :class:`RegistrySnapshot`, delegates local observation
reading to :func:`~._binding_prefill.resolve_bindings_from_local_store`, and
returns a :class:`~application.aggregation.CalculationSourceResolution`
for the aggregation mesh.

The direct value-resolution contract lives in
:mod:`~application.calculations._binding_prefill`; this module records
enrollment proof and adapts its :class:`~._binding_prefill.BindingPrefillReport`
into source-mesh output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from pydantic import BaseModel, Field

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.errors.hierarchy import CoreValidationError
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...domain.calculations.registry.authority import bundled_authority

if TYPE_CHECKING:
    from pathlib import Path

from ...adapters.persistence.storage.errors import ClassificationError, DecryptionError, EnvelopeVersionError
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ..aggregation import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..aggregation.source_resolution_operations import storage_degradation_resolution
from .observations_repository import CalculationObservationRepository

STORAGE_DEGRADATION_ERRORS = (ClassificationError, DecryptionError, EnvelopeVersionError)


# ---------------------------------------------------------------------------
# Multi-year-renta authorization enrollment recorder
#
# Every modelo's calculation backend is NON-FUNCTIONAL until an enrolling
# end-to-end persona test proves it across at least two distinct renta
# (annual) years. The manifest entry is a *claim*; the recorder below is
# the independent *verifier* the enrolling test drives.
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


class EnrollmentEvidenceError(CoreValidationError):
    """Raised when an enrollment recording is missing its un-fakeable evidence.

    Calculation-mode recordings require a strictly-positive produced-value
    count (a real calculation emitted casillas); non-calculation-mode
    recordings require both a non-empty context label AND a strictly-positive
    persisted-observation count (at least one real
    :class:`~domain.calculations.registry.RegistryModeloObservation` was
    saved to the real
    :class:`~.observations_repository.CalculationObservationRepository` for
    that year). A recording that supplies a label alone — without a persisted
    observation count — is label-only and therefore fakeable; the recorder
    refuses it.
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
            :class:`~domain.calculations.registry.RegistryModeloObservation`
            records the test actually persisted to the real
            :class:`~.observations_repository.CalculationObservationRepository`
            for this year — must be strictly positive, the evidence a real
            repository interaction occurred. Zero for calculation mode. Mirrors the role of
            ``produced_value_count`` in calculation mode: a context-mode year
            claimed with zero persisted observations is label-only and therefore
            fakeable; the recorder refuses it.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
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
    :class:`~core.access_gate.ModeloAuthorizationEntry`.
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
        from ...core.access_gate.authorization import MIN_DISTINCT_RENTA_YEARS

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
    manifest claim. The recorder is the un-fakeable home for the enrollment
    contract.
    """

    def __init__(self, modelo: str) -> None:
        """Initialize the recorder for the given modelo with no observations yet."""
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
        :class:`~domain.calculations.registry.RegistryModeloObservation`
        records actually saved to the real
        :class:`~.observations_repository.CalculationObservationRepository` for
        this year. A label alone is not sufficient evidence: any string can be
        passed without touching the real adapters. The observation count proves
        a real repository interaction happened; it mirrors the role of
        ``produced_value_count`` in :meth:`record_calculation_year`.

        Args:
            filing_year: The renta year the test exercised.
            context_label: A non-empty label naming the real two-year context
                (e.g. ``"347-fidelity-year-over-year"``).
            persisted_observation_count: The number of
                :class:`~domain.calculations.registry.RegistryModeloObservation`
                records the test saved to the real
                :class:`~.observations_repository.CalculationObservationRepository`
                for this year. MUST be strictly positive — it is the evidence a
                real adapter interaction occurred.

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
        from ...core.access_gate.authorization import MIN_DISTINCT_RENTA_YEARS

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
    manifest entry's declared ``renta_years`` on
    :class:`~core.access_gate.ModeloAuthorizationEntry`. A mismatch (the
    test exercised different years than the manifest claims) raises, turning
    the enrolling test RED.

    Args:
        evidence: The verified evidence from :meth:`EnrollmentRecorder.evidence`.
        repository_root: Optional registry root override (tests). When
            ``None`` the bundled registry authority's manifest is used.

    Raises:
        EnrollmentEvidenceError: When no manifest entry enrolls the modelo, or
            the recorded distinct-year set differs from the claimed ``renta_years``.
    """
    if repository_root is None:
        manifest = bundled_authority().authorization_manifest
    else:
        from ...core.access_gate.authorization import load_authorization_manifest

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


class PreviousFilingSourceResolver:
    """Source mesh resolver for ``source = "previous_filing"`` calculation bindings.

    Registered under ``resolver_id = "previous_filing"`` in the source mesh and
    claiming :attr:`~core.BindingSourceKind.PREVIOUS_FILING`.
    When the calculation engine encounters a binding whose source is
    ``"previous_filing"``, this resolver reads the relevant prior-year
    :class:`~domain.calculations.registry.RegistryModeloObservation`
    records from the local :class:`~.observations_repository.CalculationObservationRepository`
    through :func:`~._binding_prefill.resolve_bindings_from_local_store`, then
    maps them into the :class:`~application.aggregation.CalculationSourceResolution`
    binding channel. Storage-degradation errors (classification, decryption,
    version) are caught and returned as a
    :func:`~application.aggregation.storage_degradation_resolution` rather
    than propagated.
    """

    resolver_id: ClassVar[str] = "previous_filing"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.PREVIOUS_FILING,)

    def __init__(
        self,
        *,
        repository: CalculationObservationRepository | None = None,
        registry_snapshot: RegistrySnapshot | None = None,
        excluded_binding_ids: frozenset[BindingId] | None = None,
    ) -> None:
        """Initialize the resolver with the optional repository, snapshot, and excluded bindings."""
        self._repository = repository
        self._registry_snapshot = registry_snapshot
        self._excluded_binding_ids = excluded_binding_ids or frozenset()

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve ``source = "previous_filing"`` bindings from the prior-year local store.

        Returns:
            The resolved :class:`~application.aggregation.CalculationSourceResolution`,
            or a degraded resolution when storage classification, decryption,
            or version errors occur while reading prior-year observations.
        """
        snapshot = self._registry_snapshot
        if snapshot is None:
            snapshot = bundled_authority().snapshot(
                context.modelo,
                filing_year=context.filing_year,
                period=context.period.registry_token,
            )
        from .binding_prefill import resolve_bindings_from_local_store
        from .relation_prefill import activity_start_date_for_bucket

        try:
            report = resolve_bindings_from_local_store(
                snapshot,
                repository=self._repository,
                activity_start_date=activity_start_date_for_bucket(str(context.bucket_id)),
                excluded_binding_ids=self._excluded_binding_ids,
            )
        except STORAGE_DEGRADATION_ERRORS as exc:
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
            unresolved_binding_ids=tuple(item.binding_id for item in report.unsatisfied),
            diagnostics=tuple(
                CalculationSourceDiagnostic(
                    reason="unresolved_binding",
                    source_kind="previous_filing",
                    resolver_id=self.resolver_id,
                    binding_id=item.binding_id,
                    message=(
                        f"Modelo {context.modelo} declares previous-filing binding "
                        f"{item.binding_id!r}, but no observation for modelo "
                        f"{item.source_modelo} {item.source_filing_year} "
                        f"{'+'.join(item.source_periods) if item.source_periods else '(any period)'} "
                        "is in the local store, so the carry contributes nothing. Every "
                        "previous-filing carry reduces the amount owed, so an absent one "
                        "over-declares. File or capture the prior filing, or enter the value "
                        "by hand, before filing."
                    ),
                )
                for item in report.unsatisfied
            ),
            provenance=tuple(
                CalculationSourceProvenance(
                    resolver_id=self.resolver_id,
                    resolved_binding_source=BindingSourceKind.PREVIOUS_FILING,
                    contributor_source_kind="previous_filing",
                    contributor_binding_source=BindingSourceKind.PREVIOUS_FILING,
                    lineage_role=CalculationSourceLineageRole.PRIMARY,
                    source_ref=(
                        f"{item.source_modelo}:{item.source_filing_year}:"
                        f"{','.join(item.source_periods)}:{item.binding_id}"
                    ),
                    parent_source_ref=None,
                    dependency_treatment=item.dependency_treatment,
                )
                for item in report.prefilled
            ),
        )


__all__ = [
    "EnrollmentEvidence",
    "EnrollmentEvidenceError",
    "EnrollmentRecorder",
    "EnrollmentYearObservation",
    "PreviousFilingSourceResolver",
    "assert_enrollment_matches_manifest",
]
