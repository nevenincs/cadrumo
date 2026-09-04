"""Compose the shipped conformance fact libraries into rendered governance rows.

This module RENDERS; it does not compute conformance. Every fact below is read
off :class:`~application.registry.RegistryConformanceProfile`, the shipped
composer that already joined the evidence-tier coverage audit, the support
probe, the registry-scope validator, the authorization manifest, the
external-oracle grounding relation, the classification-coherence check, and the
declared governance stamp. The one axis added here is locale coverage, read
from the shared locale-key catalogue because it lives in a different shipped
package and the composer does not reach for it.

Why the arrow points this way
-----------------------------

``dev/`` consumes ``src/cadrumo`` through public top-level facades and nothing
under ``src/cadrumo`` may import or read anything under ``dev/``. Fact logic
therefore lives in the shipped tree where the product and its gates can reach
it; only rendering, ratcheting, and the governance write path live here. A fact
recomputed on this side would be unreachable by the product forever.

Reading the rendered rows
-------------------------

Four reading rules are load-bearing, and every renderer below preserves them.

* **Absence is not zero.** The composer deliberately returns :data:`None` where
  an axis was not measured or where a revision makes no claim at all: a revision
  reconciling nothing has no independent-check coverage, and a degraded read has
  no evidence-tier coverage, no support probe, and no authorization verdict.
  Both would read ``0`` if collapsed, so :data:`None` renders as
  :data:`NOT_MEASURED` (``n/a``) in text and stays ``null`` in JSON. ``n/a`` and
  ``0`` are different answers and must never be conflated.
* **Coverage, not correctness.** Every independent-check figure measures
  COVERAGE OF INDEPENDENT CHECKING. A low value means most of a revision's
  reconciliation is the engine agreeing with itself; it is not a statement that
  any number is wrong, and a high value is not a statement that any number is
  right. The caveat rides on :attr:`CoverageAxisRow.caveat` so a JSON consumer
  reads it too, not only someone looking at the text header.
* **Status is derived, and no grade is synthesised.** The rows carry the
  individual signals. No composite score, letter, or percentage-of-conformance
  is computed anywhere here: a single number would be read as a verdict this
  data cannot support.
* **The degraded label rides on every row.** ``registry_validated`` is emitted
  per row, never only on the envelope, so a filtered or re-sorted rendering
  cannot present a degraded row as validated authority.
* **A reviewer never renders without its tier, under ONE key name.**
  ``reviewed_by`` is free text by necessity — reviewer identity cannot be
  constrained to a vocabulary — so
  ``--review-status agent_reviewed --reviewed-by "<a person's name>"`` writes
  cleanly and is a legitimate stamp. The status column is honest about it and
  the reviewer column is not, and a reader scanning ninety rows reads the name.
  Both surfaces therefore carry ``reviewed_by_attribution``, the reviewer joined
  to the tier that claimed them, and it carries the SAME value in each.

  The first attempt at this rendered the joined form in text under the key
  ``reviewed_by`` while JSON's ``reviewed_by`` stayed the raw name, so one key
  name carried two different values depending on which surface you read — and
  the surface a program reads was the bare one, which is the reading the join
  exists to prevent. Text now names the joined field exactly as the payload does
  and does not emit a bare reviewer column at all; the payload still carries the
  raw ``reviewed_by``, because it is the datum the manifest declares, documented
  as a field to read beside its attribution rather than alone.

  The attribution is parseable at its FIRST separator whatever the name
  contains, so ``agent:opus-executor`` is unambiguous and stays legal. What the
  writer refuses is a reviewer whose own leading segment is a status token: such
  a value, read raw, is indistinguishable from an already-qualified attribution.
  This closes the PRESENTATION half only. Nothing here can make an attribution
  TRUE, and no gate should pretend otherwise.

One double-count is worth naming because the shipped composer warns about it:
``modelo_scope_classification_findings`` is a MODELO-level count repeated on
every revision row of that modelo. Summing it across rows multiplies each
finding by the modelo's revision count, so the registry-wide total is folded at
modelo scope in :func:`build_conformance_report` and the field name says so.

See Also:
    :func:`~application.registry.audit_bundled_registry_conformance`
        Shipped composer every fact here is read from.
    :class:`~application.registry.RevisionConformanceRow`
        Per-revision row the payload models project.
    :func:`~core.i18n.lookup_translation_entry`
        Shared locale-key catalogue membership the locale axis reads.
    :mod:`~dev.registry.conformance.cli`
        Typer surface that renders these payloads.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Literal, cast

from pydantic import BaseModel, Field, model_serializer, model_validator
from pydantic_core.core_schema import SerializerFunctionWrapHandler

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n import lookup_translation_entry
from cadrumo.core.models import STRICT_FROZEN_CONFIG
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.external_grounding import (
    ExternalOracleInventory,
    UnattributedOraclePayload,
    load_bundled_external_oracle_inventory,
)
from cadrumo.tests.registry_conformance import (
    AnnualCasillaPopulationComparison,
    CoverageAuthorityScope,
    RegistryConformanceProfile,
    RevisionCasillaProducerTrace,
    RevisionConformanceRow,
    RevisionConstructEvidence,
    audit_bundled_registry_conformance,
    compare_annual_casilla_population_for_revision,
)


@dataclass(frozen=True, slots=True)
class _SharedModeloLocaleCoverageRecord:
    """Shared-catalogue coverage for one Modelo revision and locale."""

    locale: OutputLanguage
    modelo_id: str
    revision_id: str
    label_required: int
    label_translated: int
    help_required: int
    help_translated: int

    @property
    def complete(self) -> bool:
        """Return whether every required label has an authored value."""
        return self.label_translated == self.label_required


#: Index of shared-catalogue translation coverage, keyed by ``(modelo, revision)``.
LocaleCoverageIndex = Mapping[tuple[str, str], tuple[_SharedModeloLocaleCoverageRecord, ...]]

__all__ = [
    "AUDITED_LOCALES",
    "COORDINATE_CLASSIFICATIONS",
    "NOT_MEASURED",
    "ConformanceCoordinate",
    "ConformanceCoordinateClassification",
    "ConformanceCoordinateMatrix",
    "ConformanceReport",
    "CoverageAxisRow",
    "CoverageReport",
    "LocaleAxisSummary",
    "OraclePayloadGapRow",
    "RevisionConformancePayload",
    "RevisionLocaleCoverage",
    "build_annual_coordinate_matrix",
    "build_conformance_report",
    "build_coverage_report",
    "load_conformance_report",
    "load_locale_coverage_index",
    "render_coverage",
    "render_report",
    "reset_conformance_cache",
    "reviewer_attribution",
    "vacuity_warning",
]

NOT_MEASURED: Final[str] = "n/a"
"""Text rendering for an axis that was NOT MEASURED or makes NO CLAIM.

Never a synonym for zero. A revision reconciling nothing has no
independent-check coverage to report, and a degraded read never consulted the
validating authority for evidence-tier coverage; rendering either as ``0``
would state a fact nobody established.
"""

type ConformanceCoordinateClassification = Literal[
    "unsupported",
    "open_ended",
    "manual",
    "upstream",
    "deferred",
    "not_yet_measured",
]
"""Allowed dispositions for finite annual-matrix coordinates.

The matrix is an evidence ledger, not a completion score. A coordinate remains
visible when it is unsupported, belongs to an open-ended revision, is manual or
upstream by declaration, is deferred by an accepted decision, or has not yet
been measured. The vocabulary is intentionally closed so a new disposition
cannot disappear from the census by omission.
"""

COORDINATE_CLASSIFICATIONS: Final[tuple[ConformanceCoordinateClassification, ...]] = (
    "unsupported",
    "open_ended",
    "manual",
    "upstream",
    "deferred",
    "not_yet_measured",
)

# The annual matrix is deliberately finite. D2025 is a provisional label only
# for this one exact coordinate; it is not a repository-wide revision class or
# an open-ended claim about any other modelo or year.
_PROVISIONAL_ANNUAL_COORDINATE_SPECS: Final[tuple[tuple[str, int, str], ...]] = (("100", 2025, "0A"),)

AUDITED_LOCALES: Final[tuple[OutputLanguage, ...]] = tuple(
    language for language in OutputLanguage if language is not OutputLanguage.ES
)
"""Locales the coverage axis audits: every output language except Spanish.

Spanish is excluded because it needs no schema-local translation file at all —
the official ``CasillaDefinition.label`` compiled from the registry IS the
Spanish authority, and schema-local Spanish TOML is deliberately absent. An
``es`` row would therefore report zero translated leaves forever for a locale
that is fully covered.
"""


class ConformanceModel(BaseModel):
    """Strict frozen base for rendered conformance payloads."""

    model_config = STRICT_FROZEN_CONFIG


class RevisionLocaleCoverage(ConformanceModel):
    """Schema-local translation coverage for one revision, folded across locales.

    Attributes:
        audited_locales: The locale codes measured, in audit order.
        labels_required_per_locale: Required label leaves for ONE locale. Every
            audited locale shares the same key set, so this is deliberately not
            multiplied by the locale count — and it is named for that scope,
            because ``labels_translated`` IS summed across locales and the two
            would otherwise read as a fraction that can exceed one.
        labels_translated: Authored label leaves summed across audited locales.
            A key-echo placeholder and a mirrored help value never count here.
        complete_locales: Audited locales whose labels are fully authored with
            no stale keys left behind.
        stale_keys: Locale leaves on disk that no registry key claims.
    """

    audited_locales: tuple[str, ...]
    labels_required_per_locale: int = Field(ge=0)
    labels_translated: int = Field(ge=0)
    complete_locales: int = Field(ge=0)
    stale_keys: int = Field(ge=0)

    @property
    def labels_required_across_locales(self) -> int:
        """Required label leaves summed over every audited locale."""
        return self.labels_required_per_locale * len(self.audited_locales)

    @property
    def labels_untranslated(self) -> int:
        """Required label leaves with no authored translation, across audited locales."""
        return self.labels_required_across_locales - self.labels_translated


class ConformanceCoordinate(ConformanceModel):
    """One exact finite annual-matrix coordinate selected by registry law.

    ``authority_scope`` is explicit because the static matrix is allowed to
    inspect a law-selected revision without granting filing authority.
    """

    modelo: str = Field(min_length=1)
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=32)
    law_selected_revision: str = Field(min_length=1)
    schema_comparison: AnnualCasillaPopulationComparison
    classification: ConformanceCoordinateClassification
    provisional: bool
    authority_scope: CoverageAuthorityScope = "filing"

    @model_validator(mode="after")
    def _schema_comparison_matches_coordinate(self) -> ConformanceCoordinate:
        """Keep the nested schema evidence on the same exact law coordinate."""
        enclosing = (
            self.modelo,
            self.filing_year,
            self.period,
            self.law_selected_revision,
            self.authority_scope,
        )
        comparison = self.schema_comparison
        nested = (
            comparison.modelo,
            comparison.filing_year,
            comparison.period,
            comparison.law_selected_revision,
            comparison.authority_scope,
        )
        if nested != enclosing:
            raise ValueError(
                "annual schema comparison coordinate does not match enclosing coordinate",
            )
        return self

    @model_serializer(mode="wrap")
    def _serialize_schema_comparison_properties(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        """Expose computed divergence properties in the JSON projection."""
        payload: dict[str, object] = handler(self)
        comparison = self.schema_comparison
        comparison_payload = comparison.model_dump(mode="json")
        comparison_payload.update(
            missing_casilla_ids=list(comparison.missing_casilla_ids),
            extra_casilla_ids=list(comparison.extra_casilla_ids),
            identity_divergence_count=comparison.identity_divergence_count,
        )
        comparison_payload["layout_comparisons"] = [
            {
                **layout.model_dump(mode="json"),
                "identity_divergence_count": layout.identity_divergence_count,
            }
            for layout in comparison.layout_comparisons
        ]
        payload["schema_comparison"] = comparison_payload
        return payload


class ConformanceCoordinateMatrix(ConformanceModel):
    """Finite annual coordinates and an explicit census of every disposition."""

    coordinates: tuple[ConformanceCoordinate, ...]
    classification_census: dict[str, int]

    @model_validator(mode="after")
    def _classification_census_is_complete(self) -> ConformanceCoordinateMatrix:
        expected = set(COORDINATE_CLASSIFICATIONS)
        if set(self.classification_census) != expected:
            raise ValueError(
                "annual coordinate classification census must name every supported disposition exactly once",
            )
        actual = {classification: 0 for classification in COORDINATE_CLASSIFICATIONS}
        coordinate_keys: set[tuple[str, int, str]] = set()
        for coordinate in self.coordinates:
            key = (coordinate.modelo, coordinate.filing_year, coordinate.period)
            if key in coordinate_keys:
                raise ValueError(f"annual coordinate is duplicated: {key!r}")
            coordinate_keys.add(key)
            actual[coordinate.classification] += 1
        if self.classification_census != actual:
            raise ValueError(
                "annual coordinate classification census does not match the enumerated coordinates",
            )
        return self


class RevisionConformancePayload(ConformanceModel):
    """One modelo revision's conformance signals, flattened for rendering.

    A projection of :class:`~application.registry.RevisionConformanceRow`, not a
    second computation of it. Optional fields are :data:`None` exactly where the
    composer left the axis unmeasured or the revision makes no claim.

    Attributes:
        modelo: The modelo this revision belongs to.
        revision: The revision id.
        registry_validated: Whether THIS row was read through the validating
            authority. Repeated per row so a renderer cannot drop the label.
        review_status: Declared review progress; ``pending_review`` on absence.
        engineered_by: Declared author, or :data:`None` when undeclared.
        reviewed_by: Declared reviewer, RAW, or :data:`None`. Read it beside
            ``reviewed_by_attribution``, never alone: an agent-tier review may
            legitimately name a person, and this field cannot tell you which
            tier claimed them.
        reviewed_by_attribution: The reviewer joined to the tier that claimed
            them, or :data:`None` when no review is declared. The form the text
            renderer prints, carried in the payload so a JSON consumer reading
            only the reviewer column reaches the same qualified answer.
        reviewed_at: ISO date of the declared review, or :data:`None`.
        calc_grade: Whether the revision's calculation closure is non-empty.
        casillas: Casillas declared on the revision.
        formulas: Formulas declared on the revision.
        bindings: Data bindings declared on the revision.
        verification_expectations: Verification contracts declared. Zero means
            the revision reconciles nothing, which is why an absent coverage and
            a zero coverage are different answers.
        extraction_profiles: Extraction profiles declared.
        completeness_manifest: Whether a completeness manifest is declared.
        fixed_width_export: Whether a fichero-BOE layout is registered.
        xml_dictionary_export: Whether an XML-dictionary layout is registered.
        reconciled_casillas: Casillas enrolled in a verification contract.
        declared_grounded_casillas: Casillas the revision declares externally
            grounded.
        independently_checked_casillas: Reconciled casillas backed by a bundled
            AEAT oracle figure.
        independent_check_coverage: COVERAGE OF INDEPENDENT CHECKING, never a
            correctness score. :data:`None` — not ``0.0`` — when the revision
            reconciles nothing and therefore makes no claim.
        grounding_findings: Breaches of the grounding honesty relation here.
        required_coverage_gap_tiers: Filing-grade mandatory evidence tiers left
            unbacked, or :data:`None` when evidence-tier coverage was not
            measured at all. Inspection-only gaps remain visible in the
            application row's ``gap_tiers`` but do not enter this field.
        model_law_authority_scope: Authority scope of the evidence-tier ledger,
            or :data:`None` when that axis was not measured.
        modelo_authorization: Derived modelo-level authorization state, or
            :data:`None` meaning UNCHECKED — deliberately NOT the
            ``unauthorized`` default-deny verdict.
        modelo_authorization_evidence_class: Enrollment-evidence shape behind an
            authorization, or :data:`None`.
        modelo_calculation_class: The modelo's enforcement posture.
        modelo_tax_domain: The modelo's taxonomy label.
        modelo_scope_classification_findings: Classification-coherence findings
            carried by this row's MODELO. Named for its scope because it repeats
            across the modelo's revision rows; summing it across rows
            multiplies each finding by the revision count.
        scope_diagnostics: Registry-scope diagnostics naming this exact revision.
        latest_revision_probed: The revision the modelo-level support matrix
            examined, or :data:`None` when the degraded read could not build it.
        support_probe_describes_this_revision: Whether that probe describes this
            row, or :data:`None` when no probe was built.
        locale: Schema-local translation coverage, or :data:`None` when the
            locale manager could not read this modelo.
        construct_evidence: Full construct-level legal/source ledger, or
            :data:`None` when the validating authority was not consulted.
        construct_evidence_authority_scope: Authority scope of the construct
            ledger, or :data:`None` when that axis was not measured.
        casilla_provenance: Lossless per-casilla producer traces, including
            relation multiplicity and producer-specific provenance.
    """

    modelo: str
    revision: str
    registry_validated: bool
    review_status: str
    engineered_by: str | None
    reviewed_by: str | None
    reviewed_by_attribution: str | None
    reviewed_at: str | None
    calc_grade: bool
    casillas: int = Field(ge=0)
    formulas: int = Field(ge=0)
    bindings: int = Field(ge=0)
    verification_expectations: int = Field(ge=0)
    extraction_profiles: int = Field(ge=0)
    completeness_manifest: bool
    fixed_width_export: bool
    xml_dictionary_export: bool
    reconciled_casillas: int = Field(ge=0)
    declared_grounded_casillas: int = Field(ge=0)
    independently_checked_casillas: int = Field(ge=0)
    independent_check_coverage: float | None
    grounding_findings: int = Field(ge=0)
    required_coverage_gap_tiers: tuple[str, ...] | None
    model_law_authority_scope: CoverageAuthorityScope | None
    modelo_authorization: str | None
    modelo_authorization_evidence_class: str | None
    modelo_calculation_class: str
    modelo_tax_domain: str
    modelo_scope_classification_findings: int = Field(ge=0)
    scope_diagnostics: int = Field(ge=0)
    latest_revision_probed: str | None
    support_probe_describes_this_revision: bool | None
    locale: RevisionLocaleCoverage | None
    construct_evidence: RevisionConstructEvidence | None
    construct_evidence_authority_scope: CoverageAuthorityScope | None
    casilla_provenance: tuple[RevisionCasillaProducerTrace, ...]


class OraclePayloadGapRow(ConformanceModel):
    """One bundled oracle payload whose figures reach no registry revision.

    Surfaced as a rendered row rather than left as a typed field nothing
    consumes: a payload the fold recorded but no screen printed is
    indistinguishable to a reader from one it checked and found clean, and a
    second such payload landing tomorrow would move no number anybody sees.

    Attributes:
        corpus: Which bundled oracle corpus the payload belongs to.
        payload_name: The payload file name.
        gap: Why its evidence could not be attributed to a revision.
        detail: The fold's own sentence explaining the gap.
    """

    corpus: str
    payload_name: str
    gap: str
    detail: str


class LocaleAxisSummary(ConformanceModel):
    """Registry-wide schema-local translation coverage, per audited locale.

    Attributes:
        locale: The audited locale code.
        labels_required: Required label leaves across every measured revision.
        labels_translated: Authored label leaves across the same revisions.
        complete_revisions: Revisions whose labels are fully authored with no
            stale keys.
        measured_revisions: Revisions the locale manager could read.
        stale_keys: Locale leaves on disk that no registry key claims.
    """

    locale: str
    labels_required: int = Field(ge=0)
    labels_translated: int = Field(ge=0)
    complete_revisions: int = Field(ge=0)
    measured_revisions: int = Field(ge=0)
    stale_keys: int = Field(ge=0)
    help_required: int = Field(ge=0)
    help_translated: int = Field(ge=0)


class ConformanceReport(ConformanceModel):
    """Registry-wide conformance report: one payload row per modelo revision.

    Attributes:
        rows: One row per revision in the loaded tree.
        registry_validated: Whether the profile was read through the validating
            authority. Every row repeats it.
        revision_count: Rows composed — the anti-vacuity denominator.
        modelo_count: Distinct modelos represented.
        review_status_census: Count of rows per declared review status, with
            every status member present so a status nobody declares reads as a
            real zero.
        engineered_by_declared_count: Revisions naming who engineered them.
        independent_check_coverage: Registry-wide COVERAGE OF INDEPENDENT
            CHECKING, never a correctness score. :data:`None` when no row
            reconciles anything.
        reconciled_casillas: Casillas enrolled in a verification contract.
        independently_checked_casillas: Of those, the ones an AEAT oracle backs.
        reconciles_nothing_row_count: Revisions enrolling no casilla at all.
        grounding_finding_count: Breaches of the grounding honesty relation.
        modelo_scope_classification_finding_count: Classification-coherence
            findings folded at MODELO scope, never summed across revision rows.
        required_coverage_gap_row_count: Rows leaving a mandatory evidence tier
            unbacked. Read beside ``coverage_unmeasured_row_count``: an empty
            gap list on a profile that measured nothing is not a clean bill of
            health.
        coverage_unmeasured_row_count: Rows whose evidence-tier coverage was not
            computed at all.
        unused_declared_axes: Schema surfaces no TOML in the tree exercises.
        declared_axis_declarations: Declarations found per tracked axis.
        declared_axis_population: Candidate declaration sites per tracked axis,
            so ``0 of 43`` and ``0 of 0`` stay distinguishable.
        unattributed_oracle_payloads: Bundled payloads whose evidence could not
            be attributed to any modelo and filing year.
        unmatched_oracle_evidence: Attributed evidence reaching no revision.
        bundled_oracle_payload_count: Total bundled payloads — the honest
            denominator for both gap counts.
        scope_diagnostic_count: Registry-scope diagnostics the tree produced.
        unattributed_scope_diagnostic_count: Of those, the ones naming no single
            revision.
        locale_axis: Per-locale registry-wide translation coverage.
        locale_unavailable_modelos: Modelos the locale manager could not read.
            Recorded rather than counted as zero coverage.
        annual_matrix: The finite annual coordinate matrix, or :data:`None` on
            a degraded read where law-selected coordinates were not validated.
            This is deliberately separate from the portfolio's revision rows.
    """

    rows: tuple[RevisionConformancePayload, ...]
    registry_validated: bool
    revision_count: int = Field(ge=0)
    modelo_count: int = Field(ge=0)
    review_status_census: dict[str, int]
    engineered_by_declared_count: int = Field(ge=0)
    independent_check_coverage: float | None
    reconciled_casillas: int = Field(ge=0)
    independently_checked_casillas: int = Field(ge=0)
    reconciles_nothing_row_count: int = Field(ge=0)
    grounding_finding_count: int = Field(ge=0)
    modelo_scope_classification_finding_count: int = Field(ge=0)
    required_coverage_gap_row_count: int = Field(ge=0)
    coverage_unmeasured_row_count: int = Field(ge=0)
    unused_declared_axes: tuple[str, ...]
    declared_axis_declarations: dict[str, int]
    declared_axis_population: dict[str, int]
    unattributed_oracle_payloads: tuple[OraclePayloadGapRow, ...]
    unmatched_oracle_evidence: tuple[OraclePayloadGapRow, ...]
    bundled_oracle_payload_count: int = Field(ge=0)
    scope_diagnostic_count: int = Field(ge=0)
    unattributed_scope_diagnostic_count: int = Field(ge=0)
    locale_axis: tuple[LocaleAxisSummary, ...]
    locale_unavailable_modelos: tuple[str, ...]
    annual_matrix: ConformanceCoordinateMatrix | None = None

    @property
    def translated_locale_labels(self) -> int:
        """Authored label leaves across audited locales — translation already achieved.

        The complement, "leaves left untranslated", was what the ratchet used to
        cap, and it is the wrong quantity to cap: every new casilla adds one
        required leaf per audited locale, so the untranslated count rises on an
        honest registry addition that translates nothing away. What must not
        happen is a translation being LOST, and that is this number falling.
        """
        return sum(item.labels_translated for item in self.locale_axis)

    @property
    def audited_locale_leaves(self) -> int:
        """Required label leaves the locale sweep examined — its anti-vacuity floor."""
        return sum(item.labels_required for item in self.locale_axis)

    @property
    def declared_grounding_claims(self) -> int:
        """Casilla-level grounding claims declared across the registry."""
        return sum(row.declared_grounded_casillas for row in self.rows)


class CoverageAxisRow(ConformanceModel):
    """One conformance axis's measured count against its candidate population.

    Attributes:
        axis: Dotted axis name, stable enough to grep for.
        scope: What the population counts — ``revision``, ``modelo``,
            ``casilla``, ``payload``, or ``locale_leaf``.
        measured: The count the axis records, or :data:`None` when the axis was
            NOT MEASURED. :data:`None` is never a zero.
        population: Candidate sites the measurement was taken over. Zero
            population makes a zero measurement uninformative rather than bad.
        caveat: The honest reading of this axis where its plain name would
            mislead, carried in JSON as well as text so no consumer sees the
            number without it.
    """

    axis: str
    scope: str
    measured: int | None
    population: int = Field(ge=0)
    caveat: str | None = None

    @property
    def fraction(self) -> float | None:
        """Measured over population, or :data:`None` when either is unavailable."""
        if self.measured is None or not self.population:
            return None
        return self.measured / self.population


class CoverageReport(ConformanceModel):
    """Per-axis conformance coverage across the whole registry.

    Attributes:
        rows: One row per tracked axis.
        registry_validated: Whether the underlying profile was validated. Axes
            requiring the validating authority report :data:`None` when it was
            not consulted.
        revision_count: Revisions the profile composed.
        modelo_count: Modelos the profile composed.
    """

    rows: tuple[CoverageAxisRow, ...]
    registry_validated: bool
    revision_count: int = Field(ge=0)
    modelo_count: int = Field(ge=0)


@lru_cache(maxsize=2)
def _cached_profile(validate: bool) -> RegistryConformanceProfile:
    """Compose the profile once per process per read mode.

    The registry fold costs seconds; a CLI process reads it once, and a test
    module invoking several verbs would otherwise pay for it on each. Invalidated
    by :func:`reset_conformance_cache`, which the governance writer calls after
    every successful stamp so a re-read never serves a pre-write tree.
    """
    return audit_bundled_registry_conformance(validate=validate)


@lru_cache(maxsize=1)
def _cached_locale_index() -> tuple[LocaleCoverageIndex, tuple[str, ...]]:
    """Read shared-catalogue translation coverage for every bundled Modelo."""
    return _read_locale_coverage()


def reset_conformance_cache() -> None:
    """Drop the memoised registry and locale reads.

    Called by the governance writer after a successful stamp: a report rendered
    from a pre-write profile inside the same process would show the operator the
    state their own command just replaced.
    """
    _cached_profile.cache_clear()
    _cached_locale_index.cache_clear()


def load_locale_coverage_index() -> tuple[LocaleCoverageIndex, tuple[str, ...]]:
    """Return shared-catalogue translation coverage keyed by ``(modelo, revision)``.

    Returns:
        The coverage index and modelo ids that could not be read. An unreadable
        Modelo is reported, never rendered as zero coverage.
    """
    return _cached_locale_index()


def _read_locale_coverage() -> tuple[LocaleCoverageIndex, tuple[str, ...]]:
    """Sweep every bundled Modelo and index its shared locale-key coverage."""
    index: dict[tuple[str, str], tuple[_SharedModeloLocaleCoverageRecord, ...]] = {}
    unavailable: list[str] = []
    try:
        modelos = bundled_authority().modelos
    except Exception:
        return {}, ("<bundled-registry>",)
    for modelo in modelos:
        modelo_id = str(modelo.id)
        for revision_id, revision in modelo.revisions.items():
            records = tuple(
                _shared_locale_coverage_record(
                    locale=locale,
                    modelo_id=modelo_id,
                    revision_id=str(revision_id),
                    casillas=revision.casillas,
                )
                for locale in AUDITED_LOCALES
            )
            index[(modelo_id, str(revision_id))] = records
    return index, tuple(sorted(unavailable))


def _shared_locale_coverage_record(
    *,
    locale: OutputLanguage,
    modelo_id: str,
    revision_id: str,
    casillas: Sequence[object],
) -> _SharedModeloLocaleCoverageRecord:
    """Count authored values across exact and continuity candidate keys."""
    label_required = len(casillas)
    label_translated = sum(1 for casilla in casillas if _has_authored_locale_value(casilla, locale, field="label"))
    help_required = len(casillas)
    help_translated = sum(1 for casilla in casillas if _has_authored_locale_value(casilla, locale, field="help"))
    return _SharedModeloLocaleCoverageRecord(
        locale=locale,
        modelo_id=modelo_id,
        revision_id=revision_id,
        label_required=label_required,
        label_translated=label_translated,
        help_required=help_required,
        help_translated=help_translated,
    )


def _has_authored_locale_value(casilla: object, locale: OutputLanguage, *, field: str) -> bool:
    """Return whether a casilla has an authored value in the requested locale."""
    keys = getattr(casilla, "localization_keys", ())
    if field == "help":
        keys = tuple(f"{key.removesuffix('.label')}.help" for key in keys)
    return any(
        (present and value is not None)
        for key in keys
        for present, value in (lookup_translation_entry(key, locale=locale.value),)
    )


def load_conformance_report(*, validate: bool = True) -> ConformanceReport:
    """Compose and project the bundled registry's conformance report.

    Args:
        validate: When :data:`True` every axis is read through the validating
            registry authority. When :data:`False` the degraded read is used —
            the non-validating tree loader, so a governance read survives a
            concurrently-edited registry the authority would refuse outright.
            Every emitted row is then stamped ``registry_validated=false`` and
            the axes requiring the authority report ``n/a`` rather than zero.

    Returns:
        The projected :class:`ConformanceReport`.
    """
    profile = _cached_profile(validate)
    locale_index, unavailable = _cached_locale_index()
    annual_matrix = build_annual_coordinate_matrix() if validate else None
    return build_conformance_report(
        profile,
        locale_index=locale_index,
        locale_unavailable_modelos=unavailable,
        oracle_inventory=load_bundled_external_oracle_inventory(),
        annual_matrix=annual_matrix,
    )


def build_annual_coordinate_matrix() -> ConformanceCoordinateMatrix:
    """Enumerate finite annual coordinates through typed inspection authority.

    The portfolio conformance rows remain one row per validated modelo revision
    (currently 73 modelos and 90 revisions). This function owns the separate,
    finite behavioral denominator. Its only current coordinate is the
    provisional D2025 interpretation: Modelo 100, ejercicio 2025, period ``0A``,
    revision selected by the law-determined registry authority.  The matrix is
    a static schema comparison, so it uses the authority's non-filing
    inspection projection and never constructs a filing snapshot.

    Returns:
        A typed matrix whose classification census names every supported
        disposition, including zero populations that must remain visible.

    Raises:
        RegistrySnapshotError: If the accepted coordinate cannot be resolved by
            the validated registry authority.
    """
    authority = bundled_authority()
    coordinate_items: list[ConformanceCoordinate] = []
    for modelo, filing_year, period in _PROVISIONAL_ANNUAL_COORDINATE_SPECS:
        inspection = authority.inspect_revision(modelo, filing_year=filing_year, period=period)
        selected_revision = authority.modelo(modelo).revisions[inspection.revision_id]
        schema_comparison = compare_annual_casilla_population_for_revision(
            modelo=inspection.modelo_id,
            revision=selected_revision,
            filing_year=filing_year,
            period=period,
            sources=inspection.sources,
            source_root=authority.source_root,
        )
        coordinate_items.append(
            ConformanceCoordinate(
                modelo=modelo,
                filing_year=filing_year,
                period=period,
                law_selected_revision=inspection.revision_id,
                schema_comparison=schema_comparison,
                classification="not_yet_measured",
                provisional=True,
                authority_scope=schema_comparison.authority_scope,
            ),
        )
    coordinates = tuple(coordinate_items)
    classification_census = {classification: 0 for classification in COORDINATE_CLASSIFICATIONS}
    for coordinate in coordinates:
        classification_census[coordinate.classification] += 1
    return ConformanceCoordinateMatrix(
        coordinates=coordinates,
        classification_census=classification_census,
    )


def build_conformance_report(
    profile: RegistryConformanceProfile,
    *,
    locale_index: Mapping[tuple[str, str], Sequence[_SharedModeloLocaleCoverageRecord]],
    locale_unavailable_modelos: Sequence[str],
    oracle_inventory: ExternalOracleInventory,
    annual_matrix: ConformanceCoordinateMatrix | None = None,
) -> ConformanceReport:
    """Project a composed profile plus the locale axis into rendered payload rows.

    A pure fold: the caller owns loading, so a test can inject a mutated profile
    and observe exactly which rendered number moves.

    Args:
        profile: The shipped composer's output.
        locale_index: Schema-local coverage records keyed by
            ``(modelo, revision)``. A revision absent from the index reports
            :data:`None` locale facts, never zero coverage.
        locale_unavailable_modelos: Modelos the locale manager could not read.
        oracle_inventory: The bundled oracle inventory, supplying the honest
            denominator for the attribution-gap counts.
        annual_matrix: The finite annual coordinate matrix from the validated
            authority, or :data:`None` for a synthetic/degraded projection.

    Returns:
        The projected :class:`ConformanceReport`.
    """
    rows = tuple(
        _payload_row(row, locale=_locale_coverage(locale_index.get((row.modelo, row.revision)))) for row in profile.rows
    )
    classification_by_modelo = {row.modelo: row.modelo_classification_finding_count for row in profile.rows}
    # Annotated because the axis name is a ``Literal`` union on the audit and a
    # dict comprehension keeps that narrow key type, which the ``str``-keyed
    # payload field then refuses.
    axis_population: dict[str, int] = {item.axis: item.population for item in profile.declared_axis_usage}
    axis_declarations: dict[str, int] = {item.axis: item.declaration_count for item in profile.declared_axis_usage}
    unused_axes = tuple(item.axis for item in profile.declared_axis_usage if item.status == "unused")

    return ConformanceReport(
        rows=rows,
        registry_validated=profile.registry_validated,
        revision_count=profile.composed_revision_count,
        modelo_count=profile.composed_modelo_count,
        review_status_census={status.value: count for status, count in profile.review_status_census().items()},
        engineered_by_declared_count=profile.engineered_by_declared_count,
        independent_check_coverage=profile.independent_check_coverage,
        reconciled_casillas=sum(row.reconciled_casillas for row in rows),
        independently_checked_casillas=sum(row.independently_checked_casillas for row in rows),
        reconciles_nothing_row_count=sum(1 for row in profile.rows if row.reconciles_nothing),
        grounding_finding_count=profile.grounding_finding_count,
        modelo_scope_classification_finding_count=sum(classification_by_modelo.values()),
        required_coverage_gap_row_count=len(profile.required_coverage_gap_rows),
        coverage_unmeasured_row_count=len(profile.coverage_unmeasured_rows),
        unused_declared_axes=unused_axes,
        declared_axis_declarations=axis_declarations,
        declared_axis_population=axis_population,
        unattributed_oracle_payloads=tuple(_gap_row(item) for item in profile.unattributed_oracle_payloads),
        unmatched_oracle_evidence=tuple(_gap_row(item) for item in profile.unmatched_oracle_evidence),
        bundled_oracle_payload_count=(len(oracle_inventory.evidence) + len(oracle_inventory.unattributed_payloads)),
        scope_diagnostic_count=len(profile.scope_diagnostics),
        unattributed_scope_diagnostic_count=len(profile.unattributed_scope_diagnostics),
        locale_axis=_locale_axis_summary(locale_index),
        locale_unavailable_modelos=tuple(locale_unavailable_modelos),
        annual_matrix=annual_matrix,
    )


def build_coverage_report(report: ConformanceReport) -> CoverageReport:
    """Fold a conformance report into one row per tracked conformance axis.

    Axes requiring the validating authority report ``measured=None`` on a
    degraded read rather than a zero, because nothing measured them.
    """
    validated = report.registry_validated
    rows = report.rows
    revisions = report.revision_count
    modelos = report.modelo_count

    axes: list[CoverageAxisRow] = [
        _axis("revision.calc_grade", "revision", sum(1 for row in rows if row.calc_grade), revisions),
        _axis(
            "revision.verification_expectations",
            "revision",
            sum(1 for row in rows if row.verification_expectations),
            revisions,
        ),
        _axis(
            "revision.completeness_manifest",
            "revision",
            sum(1 for row in rows if row.completeness_manifest),
            revisions,
        ),
        _axis(
            "revision.extraction_profiles",
            "revision",
            sum(1 for row in rows if row.extraction_profiles),
            revisions,
        ),
        _axis(
            "revision.fixed_width_export",
            "revision",
            sum(1 for row in rows if row.fixed_width_export),
            revisions,
        ),
        _axis(
            "revision.xml_dictionary_export",
            "revision",
            sum(1 for row in rows if row.xml_dictionary_export),
            revisions,
        ),
        _axis(
            "external_grounding.independently_checked_casillas",
            "casilla",
            report.independently_checked_casillas,
            report.reconciled_casillas,
            caveat=(
                "coverage of independent checking, never correctness: a low value means most "
                "reconciliation here is the engine agreeing with itself, not that any number is wrong"
            ),
        ),
        _axis(
            "external_grounding.declared_grounding_claims",
            "casilla",
            report.declared_grounding_claims,
            report.reconciled_casillas,
            caveat="a declaration that a casilla is externally grounded, not evidence that it is",
        ),
        _axis(
            "external_grounding.revisions_reconciling_nothing",
            "revision",
            report.reconciles_nothing_row_count,
            revisions,
            caveat="these revisions make no independent-check claim at all, which is not a claim of zero",
        ),
        _axis(
            "oracle_payloads.unattributed",
            "payload",
            len(report.unattributed_oracle_payloads),
            report.bundled_oracle_payload_count,
            caveat="bundled AEAT figures sitting outside the grounding relation entirely",
        ),
        _axis(
            "oracle_evidence.unmatched",
            "payload",
            len(report.unmatched_oracle_evidence),
            report.bundled_oracle_payload_count,
            caveat="attributed oracle evidence that reaches no registry revision",
        ),
        _axis(
            "governance.engineered_by",
            "revision",
            report.engineered_by_declared_count,
            revisions,
        ),
    ]
    axes.extend(
        _axis(f"governance.review_status.{status}", "revision", count, revisions)
        for status, count in sorted(report.review_status_census.items())
    )
    axes.append(
        _axis(
            "authorization.authorized",
            "modelo",
            _authorized_modelo_count(rows) if validated else None,
            modelos,
            caveat=(
                None
                if validated
                else "not measured on a degraded read; absent is not the unauthorized default-deny verdict"
            ),
        ),
    )
    axes.append(
        _axis(
            "model_law_coverage.rows_without_required_gap",
            "revision",
            (revisions - report.required_coverage_gap_row_count) if validated else None,
            revisions,
            caveat=(
                None
                if validated
                else "evidence-tier coverage needs the validating authority; a degraded read measures none of it"
            ),
        ),
    )
    axes.extend(
        _axis(
            f"declared_axis.{axis}",
            "declaration_site",
            declarations,
            report.declared_axis_population.get(axis, 0),
            caveat=(
                "a schema surface no TOML in the tree declares is UNUSED, never passing: zero "
                "declarations produce zero failures, which is indistinguishable from always correct"
                if axis in report.unused_declared_axes
                else None
            ),
        )
        for axis, declarations in sorted(report.declared_axis_declarations.items())
    )
    axes.extend(
        _axis(
            f"locale.{item.locale}.labels_translated",
            "locale_leaf",
            item.labels_translated,
            item.labels_required,
            caveat="Spanish is excluded: the official registry casilla label IS the Spanish authority",
        )
        for item in report.locale_axis
    )
    axes.append(_axis("registry_scope.diagnostics", "revision", report.scope_diagnostic_count, revisions))

    return CoverageReport(
        rows=tuple(axes),
        registry_validated=validated,
        revision_count=revisions,
        modelo_count=modelos,
    )


def render_report(report: ConformanceReport) -> str:
    """Render the conformance report as greppable ``key=value`` rows."""
    lines = [
        _kv_line(
            "summary",
            registry_validated=report.registry_validated,
            revisions=report.revision_count,
            modelos=report.modelo_count,
            engineered_by_declared=report.engineered_by_declared_count,
            independent_check_coverage=report.independent_check_coverage,
            reconciled_casillas=report.reconciled_casillas,
            independently_checked_casillas=report.independently_checked_casillas,
            reconciles_nothing_rows=report.reconciles_nothing_row_count,
            grounding_findings=report.grounding_finding_count,
            modelo_scope_classification_findings=report.modelo_scope_classification_finding_count,
            required_coverage_gap_rows=report.required_coverage_gap_row_count,
            coverage_unmeasured_rows=report.coverage_unmeasured_row_count,
            unattributed_oracle_payloads=len(report.unattributed_oracle_payloads),
            unmatched_oracle_evidence=len(report.unmatched_oracle_evidence),
            bundled_oracle_payloads=report.bundled_oracle_payload_count,
            scope_diagnostics=report.scope_diagnostic_count,
            unattributed_scope_diagnostics=report.unattributed_scope_diagnostic_count,
            locale_unavailable_modelos=len(report.locale_unavailable_modelos),
        ),
    ]
    lines.extend(
        _kv_line("census", review_status=status, revisions=count)
        for status, count in sorted(report.review_status_census.items())
    )
    for row in report.rows:
        lines.append(
            _kv_line(
                "row",
                modelo=row.modelo,
                revision=row.revision,
                registry_validated=row.registry_validated,
                review_status=row.review_status,
                engineered_by=row.engineered_by,
                # Named EXACTLY as the payload names it, and carrying exactly
                # what the payload carries. Rendering the joined form under the
                # key ``reviewed_by`` — while the payload's ``reviewed_by`` held
                # the raw name — made one key name mean two different things
                # across two surfaces, and the surface a program reads was the
                # bare one. No bare reviewer column is emitted here: the joined
                # form contains the name, so nothing is lost by omitting it.
                reviewed_by_attribution=row.reviewed_by_attribution,
                reviewed_at=row.reviewed_at,
                calc_grade=row.calc_grade,
                casillas=row.casillas,
                formulas=row.formulas,
                bindings=row.bindings,
                verification_expectations=row.verification_expectations,
                extraction_profiles=row.extraction_profiles,
                completeness_manifest=row.completeness_manifest,
                fixed_width_export=row.fixed_width_export,
                xml_dictionary_export=row.xml_dictionary_export,
                reconciled_casillas=row.reconciled_casillas,
                declared_grounded_casillas=row.declared_grounded_casillas,
                independently_checked_casillas=row.independently_checked_casillas,
                independent_check_coverage=row.independent_check_coverage,
                grounding_findings=row.grounding_findings,
                required_coverage_gap_tiers=row.required_coverage_gap_tiers,
                model_law_authority_scope=row.model_law_authority_scope,
                modelo_authorization=row.modelo_authorization,
                modelo_authorization_evidence_class=row.modelo_authorization_evidence_class,
                modelo_calculation_class=row.modelo_calculation_class,
                modelo_tax_domain=row.modelo_tax_domain,
                modelo_scope_classification_findings=row.modelo_scope_classification_findings,
                scope_diagnostics=row.scope_diagnostics,
                latest_revision_probed=row.latest_revision_probed,
                support_probe_describes_this_revision=row.support_probe_describes_this_revision,
                locale_audited_locales=None if row.locale is None else len(row.locale.audited_locales),
                locale_labels_required_per_locale=(
                    None if row.locale is None else row.locale.labels_required_per_locale
                ),
                locale_labels_translated=None if row.locale is None else row.locale.labels_translated,
                locale_complete_locales=None if row.locale is None else row.locale.complete_locales,
                locale_stale_keys=None if row.locale is None else row.locale.stale_keys,
                construct_evidence_rows=(None if row.construct_evidence is None else len(row.construct_evidence.rows)),
                construct_evidence_gaps=(None if row.construct_evidence is None else len(row.construct_evidence.gaps)),
                construct_evidence_filing_gaps=(
                    None if row.construct_evidence is None else len(row.construct_evidence.filing_gaps)
                ),
                construct_evidence_inspection_gaps=(
                    None if row.construct_evidence is None else len(row.construct_evidence.inspection_gaps)
                ),
                construct_evidence_authority_scope=row.construct_evidence_authority_scope,
                casilla_provenance_traces=len(row.casilla_provenance),
            ),
        )
    lines.append(
        _kv_line(
            "annual_matrix",
            registry_validated=report.registry_validated,
            measured=report.annual_matrix is not None,
            coordinates=None if report.annual_matrix is None else len(report.annual_matrix.coordinates),
        ),
    )
    if report.annual_matrix is not None:
        lines.extend(
            _kv_line(
                "annual_coordinate",
                modelo=coordinate.modelo,
                filing_year=coordinate.filing_year,
                period=coordinate.period,
                law_selected_revision=coordinate.law_selected_revision,
                authority_scope=coordinate.authority_scope,
                classification=coordinate.classification,
                provisional=coordinate.provisional,
                schema_identity_measurement=coordinate.schema_comparison.identity_measurement,
                schema_printed_form_membership=coordinate.schema_comparison.printed_form_membership,
                schema_xsd_only_attributes=coordinate.schema_comparison.xsd_only_attributes,
                schema_identity_divergence_count=coordinate.schema_comparison.identity_divergence_count,
            )
            for coordinate in report.annual_matrix.coordinates
        )
        lines.extend(
            _kv_line(
                "annual_schema_layout",
                modelo=coordinate.modelo,
                filing_year=coordinate.filing_year,
                period=coordinate.period,
                law_selected_revision=coordinate.law_selected_revision,
                authority_scope=coordinate.authority_scope,
                layout_id=layout.layout_id,
                layout_format=layout.layout_format,
                identity_measurement=layout.identity_measurement,
                registry_casilla_count=layout.registry_casilla_count,
                dictionary_entry_count=layout.dictionary_entry_count,
                dictionary_casilla_count=layout.dictionary_casilla_count,
                identity_divergence_count=layout.identity_divergence_count,
                missing_casilla_ids=layout.missing_casilla_ids,
                extra_casilla_ids=layout.extra_casilla_ids,
                printed_form_membership=layout.printed_form_membership,
                xsd_only_attributes=layout.xsd_only_attributes,
                dictionary_source_ref=layout.dictionary_source_ref,
                parser_exposed_attributes=layout.parser_exposed_attributes,
                unmeasured_attributes=layout.unmeasured_attributes,
                diagnostic=layout.diagnostic,
            )
            for coordinate in report.annual_matrix.coordinates
            for layout in coordinate.schema_comparison.layout_comparisons
        )
        lines.extend(
            _kv_line(
                "annual_coordinate_classification",
                classification=classification,
                count=report.annual_matrix.classification_census[classification],
            )
            for classification in COORDINATE_CLASSIFICATIONS
        )
    lines.extend(
        _kv_line("oracle_gap", kind="unattributed_payload", corpus=item.corpus, payload=item.payload_name, gap=item.gap)
        for item in report.unattributed_oracle_payloads
    )
    lines.extend(
        _kv_line("oracle_gap", kind="unmatched_evidence", corpus=item.corpus, payload=item.payload_name, gap=item.gap)
        for item in report.unmatched_oracle_evidence
    )
    lines.extend(
        _kv_line("unused_axis", axis=axis, population=report.declared_axis_population.get(axis, 0))
        for axis in report.unused_declared_axes
    )
    lines.extend(_kv_line("locale_unavailable", modelo=modelo) for modelo in report.locale_unavailable_modelos)
    lines.append(_reading_note(report))
    return "\n".join(lines)


def render_coverage(coverage: CoverageReport) -> str:
    """Render the per-axis coverage report as greppable ``key=value`` rows."""
    lines = [
        _kv_line(
            "summary",
            registry_validated=coverage.registry_validated,
            revisions=coverage.revision_count,
            modelos=coverage.modelo_count,
            axes=len(coverage.rows),
        ),
    ]
    for row in coverage.rows:
        # The caveat key is OMITTED when absent rather than rendered as n/a: an
        # axis needing no caveat has not "failed to measure" one, and n/a is
        # reserved for a measurement nobody took.
        fields: dict[str, object] = {
            "axis": row.axis,
            "scope": row.scope,
            "measured": row.measured,
            "population": row.population,
            "fraction": row.fraction,
        }
        if row.caveat is not None:
            fields["caveat"] = row.caveat
        lines.append(_kv_line("axis", **fields))
    lines.append(
        f"note {NOT_MEASURED} means NOT MEASURED or NO CLAIM MADE, never zero; "
        "every independent-check figure is coverage of independent checking, never correctness",
    )
    return "\n".join(lines)


def vacuity_warning(report: ConformanceReport) -> str | None:
    """Return the warning record for a screen that composed nothing, or :data:`None`.

    The screens keep their zero exit — refusal belongs to ``audit`` — but an
    empty render that said nothing would be indistinguishable from a clean
    registry, which is the false-green shape this whole surface exists to
    remove. A record line rather than prose, so a caller greps it.
    """
    if report.rows:
        return None
    return (
        'warning rows=0 detail="composed no revision rows at all; every count above is vacuous '
        'and describes the read, not the registry"'
    )


def reviewer_attribution(review_status: str, reviewed_by: str | None) -> str | None:
    """Join a declared reviewer to the review tier that claimed them.

    Returns :data:`None` when no reviewer is declared, which is exactly when no
    review is claimed: the registry schema pairs the reviewer identity with a
    status beyond ``pending_review`` and refuses either alone. Absence therefore
    stays absence and is never joined to a tier nobody asserted.

    Applied to EVERY tier rather than only to ``agent_reviewed``. Qualifying one
    tier and leaving the other bare would make a bare name mean
    ``operator_reviewed`` by convention, which is a rule a reader has to know
    before the column is safe — and the reader who does not know it is the one
    this join exists to protect.

    The result is parseable at its FIRST separator, whatever the reviewer name
    contains: no status value carries a colon, so everything before the first
    one is the tier and everything after it is the name. A reviewer such as
    ``agent:opus-executor`` is therefore unambiguous and stays legal. The
    hazard the writer refuses is narrower and is about the RAW field, not this
    one: a reviewer whose own leading segment is a status token reads, on its
    own, as an already-qualified attribution.
    """
    if reviewed_by is None:
        return None
    return f"{review_status}:{reviewed_by}"


def _authorized_modelo_count(rows: Sequence[RevisionConformancePayload]) -> int:
    """Count distinct modelos whose derived authorization is granted."""
    return len({row.modelo for row in rows if row.modelo_authorization == "authorized"})


def _axis(
    axis: str,
    scope: str,
    measured: int | None,
    population: int,
    *,
    caveat: str | None = None,
) -> CoverageAxisRow:
    """Build one coverage axis row."""
    return CoverageAxisRow(axis=axis, scope=scope, measured=measured, population=population, caveat=caveat)


def _gap_row(payload: UnattributedOraclePayload) -> OraclePayloadGapRow:
    """Project one attribution gap, keeping the fold's own explanatory sentence."""
    return OraclePayloadGapRow(
        corpus=payload.corpus.value,
        payload_name=payload.payload_name,
        gap=payload.gap,
        detail=payload.detail,
    )


def _locale_coverage(
    records: Sequence[_SharedModeloLocaleCoverageRecord] | None,
) -> RevisionLocaleCoverage | None:
    """Fold one revision's per-locale records, or report absence as absence."""
    if not records:
        return None
    first = records[0]
    return RevisionLocaleCoverage(
        audited_locales=tuple(record.locale.value for record in records),
        labels_required_per_locale=first.label_required,
        labels_translated=sum(record.label_translated for record in records),
        complete_locales=sum(1 for record in records if record.complete),
        stale_keys=sum(_stale_key_count(record) for record in records),
    )


def _stale_key_count(record: _SharedModeloLocaleCoverageRecord) -> int:
    """Return zero; shared-catalogue stale keys are audited globally."""
    return 0


def _locale_axis_summary(
    locale_index: Mapping[tuple[str, str], Sequence[_SharedModeloLocaleCoverageRecord]],
) -> tuple[LocaleAxisSummary, ...]:
    """Fold the locale index into one registry-wide summary per audited locale."""
    required: dict[str, int] = {}
    translated: dict[str, int] = {}
    complete: dict[str, int] = {}
    measured: dict[str, int] = {}
    stale: dict[str, int] = {}
    help_required: dict[str, int] = {}
    help_translated: dict[str, int] = {}
    for records in locale_index.values():
        for record in records:
            code = record.locale.value
            required[code] = required.get(code, 0) + record.label_required
            translated[code] = translated.get(code, 0) + record.label_translated
            complete[code] = complete.get(code, 0) + (1 if record.complete else 0)
            measured[code] = measured.get(code, 0) + 1
            stale[code] = stale.get(code, 0) + _stale_key_count(record)
            help_required[code] = help_required.get(code, 0) + record.help_required
            help_translated[code] = help_translated.get(code, 0) + record.help_translated
    return tuple(
        LocaleAxisSummary(
            locale=code,
            labels_required=required[code],
            labels_translated=translated.get(code, 0),
            complete_revisions=complete.get(code, 0),
            measured_revisions=measured.get(code, 0),
            stale_keys=stale.get(code, 0),
            help_required=help_required.get(code, 0),
            help_translated=help_translated.get(code, 0),
        )
        for code in sorted(required)
    )


def _payload_row(
    row: RevisionConformanceRow,
    *,
    locale: RevisionLocaleCoverage | None,
) -> RevisionConformancePayload:
    """Flatten one composed conformance row for rendering."""
    governance = row.governance
    capabilities = row.capabilities
    grounding = row.external_grounding
    classification = row.modelo_classification
    coverage = row.model_law_coverage
    support = row.latest_revision_support
    authorization = row.modelo_authorization
    return RevisionConformancePayload(
        modelo=row.modelo,
        revision=row.revision,
        registry_validated=row.registry_validated,
        review_status=governance.review_status.value,
        engineered_by=governance.engineered_by,
        reviewed_by=governance.reviewed_by,
        reviewed_by_attribution=reviewer_attribution(governance.review_status.value, governance.reviewed_by),
        reviewed_at=None if governance.reviewed_at is None else governance.reviewed_at.isoformat(),
        calc_grade=capabilities.calc_grade,
        casillas=capabilities.casilla_count,
        formulas=capabilities.formula_count,
        bindings=capabilities.binding_count,
        verification_expectations=capabilities.verification_expectation_count,
        extraction_profiles=capabilities.extraction_profile_count,
        completeness_manifest=capabilities.has_completeness_manifest,
        fixed_width_export=capabilities.has_fixed_width_export,
        xml_dictionary_export=capabilities.has_xml_dictionary_export,
        reconciled_casillas=len(grounding.reconciled_casilla_ids),
        declared_grounded_casillas=len(grounding.declared_grounded_casilla_ids),
        independently_checked_casillas=len(grounding.independently_checked_casilla_ids),
        independent_check_coverage=row.independent_check_coverage,
        grounding_findings=len(grounding.findings),
        required_coverage_gap_tiers=None if coverage is None else tuple(coverage.required_tier_gaps),
        model_law_authority_scope=None if coverage is None else coverage.authority_scope,
        modelo_authorization=None if authorization is None else authorization.state.value,
        modelo_authorization_evidence_class=(
            None if authorization is None or authorization.entry is None else authorization.entry.evidence_class.value
        ),
        modelo_calculation_class=classification.calculation_class,
        modelo_tax_domain=classification.tax_domain.value,
        modelo_scope_classification_findings=len(classification.findings),
        scope_diagnostics=len(row.scope_diagnostics),
        latest_revision_probed=None if support is None else support.probed_revision,
        support_probe_describes_this_revision=None if support is None else support.describes_this_revision,
        locale=locale,
        construct_evidence=row.construct_evidence,
        construct_evidence_authority_scope=(
            None if row.construct_evidence is None else row.construct_evidence.authority_scope
        ),
        casilla_provenance=row.casilla_provenance,
    )


def _reading_note(report: ConformanceReport) -> str:
    """Return the standing reading note every rendered report ends with."""
    degraded = (
        ""
        if report.registry_validated
        else (
            " DEGRADED READ: rows are stamped registry_validated=false and the evidence-tier coverage, "
            "support-probe, and authorization axes were not consulted at all."
        )
    )
    return (
        f"note {NOT_MEASURED} means NOT MEASURED or NO CLAIM MADE, never zero, while '-' is a real "
        "empty list; independent_check_coverage is coverage of independent checking, never "
        "correctness; modelo_scope_classification_findings repeats across a modelo's revision rows "
        f"and must not be summed over rows.{degraded}"
    )


def _kv_line(record: str, **fields: object) -> str:
    """Render one greppable ``record key=value ...`` line."""
    parts = [record]
    parts.extend(f"{key}={_render_value(value)}" for key, value in fields.items())
    return " ".join(parts)


def _render_value(value: object) -> str:
    """Render one field value, keeping absence distinct from zero."""
    if value is None:
        return NOT_MEASURED
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, tuple):
        items = cast(tuple[object, ...], value)
        return ",".join(str(item) for item in items) if items else "-"
    text = str(value)
    if not text or any(character in text for character in ' \t"='):
        return json.dumps(text)
    return text
