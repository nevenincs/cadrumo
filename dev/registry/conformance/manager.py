"""Compose the shipped conformance fact libraries into rendered governance rows.

This module RENDERS; it does not compute conformance. Every fact below is read
off :class:`~application.registry.RegistryConformanceProfile`, the shipped
composer that already joined the evidence-tier coverage audit, the support
probe, the registry-scope validator, the authorization manifest, the
external-oracle grounding relation, the classification-coherence check, and the
declared governance stamp. The one axis added here is locale coverage, read
through :class:`~locales.ModeloLocaleManager`, because it lives in a different
shipped package and the composer does not reach for it.

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
    :class:`~locales.ModeloLocaleManager`
        Schema-local translation coverage the locale axis reads.
    :mod:`~dev.registry.conformance.cli`
        Typer surface that renders these payloads.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field

from cadrumo.application.registry import (
    RegistryConformanceProfile,
    RevisionConformanceRow,
    audit_bundled_registry_conformance,
)
from cadrumo.core import STRICT_FROZEN_CONFIG, RevisionReviewStatus
from cadrumo.core.external_constants import UTF_8_ENCODING, OutputLanguage
from cadrumo.domain.calculations.registry import (
    ExternalOracleInventory,
    UnattributedOraclePayload,
    load_bundled_external_oracle_inventory,
)
from cadrumo.locales import (
    ModeloLocaleCoverageRecord,
    ModeloLocaleDriftKind,
    ModeloLocaleError,
    ModeloLocaleManager,
)

#: Index of schema-local translation coverage, keyed by ``(modelo, revision)``.
LocaleCoverageIndex = Mapping[tuple[str, str], tuple[ModeloLocaleCoverageRecord, ...]]

__all__ = [
    "AUDITED_LOCALES",
    "NOT_MEASURED",
    "ConformanceAuditResult",
    "ConformanceBaseline",
    "ConformanceRatchetCeilings",
    "ConformanceReport",
    "ConformanceVacuityFloors",
    "CoverageAxisRow",
    "CoverageReport",
    "LocaleAxisSummary",
    "OraclePayloadGapRow",
    "RevisionConformancePayload",
    "RevisionLocaleCoverage",
    "baseline_path",
    "baseline_weakenings",
    "build_conformance_report",
    "build_coverage_report",
    "check_conformance_ratchet",
    "load_baseline",
    "load_conformance_report",
    "load_locale_coverage_index",
    "record_baseline",
    "render_audit",
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

#: Committed ratchet baseline, read only by this dev-side package.
_BASELINE_FILENAME: Final[str] = "conformance-baseline.json"

#: Command recorded on a captured baseline, so the artefact names its producer.
_RECORD_COMMAND: Final[str] = "python -m dev.registry.conformance audit --record"

#: Default cadence stamped on a captured baseline.
_DEFAULT_REVIEW_CADENCE: Final[str] = "revisit whenever a stamping or grounding campaign lands"


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
        required_coverage_gap_tiers: Mandatory evidence tiers left unbacked, or
            :data:`None` when evidence-tier coverage was not measured at all.
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
    modelo_authorization: str | None
    modelo_authorization_evidence_class: str | None
    modelo_calculation_class: str
    modelo_tax_domain: str
    modelo_scope_classification_findings: int = Field(ge=0)
    scope_diagnostics: int = Field(ge=0)
    latest_revision_probed: str | None
    support_probe_describes_this_revision: bool | None
    locale: RevisionLocaleCoverage | None


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

    @property
    def untranslated_locale_labels(self) -> int:
        """Required label leaves with no authored translation, across audited locales."""
        return sum(item.labels_required - item.labels_translated for item in self.locale_axis)

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


class ConformanceRatchetCeilings(ConformanceModel):
    """Shrink-only ceilings: each counter may stay flat or fall, never grow.

    Every field is a BACKLOG or DEFECT count. Lowering one requires editing the
    committed baseline, which is the point: the edit is the visible record that
    the backlog moved.

    Why the review backlog is TWO counters
    --------------------------------------

    ``unreviewed_revisions`` counts only the ``pending_review`` census, and the
    stamp verb is DESIGNED to move it: an agent may write ``agent_reviewed``
    freely, so a sweep across every revision drives that counter from the full
    registry to zero while this audit stays green throughout. The governing
    decision's whole rationale for a three-state vocabulary is that it makes the
    backlog visible instead of laundering it into prose, and one gated counter
    covering two of the three tiers reintroduces exactly that collapse at the
    only place anything is enforced.

    ``revisions_without_operator_review`` is therefore the counter CI protects.
    It counts every revision whose declared status is not
    :attr:`~cadrumo.core.RevisionReviewStatus.OPERATOR_REVIEWED`, so the stamp
    verb cannot move it at all — that value is outside the vocabulary this CLI
    will write, enforced at the writer's own boundary rather than by its type
    hints. Agent review remains a real, visible axis on the coverage screen; it
    is simply not progress against the operator backlog, because it is not the
    same backlog.
    """

    unreviewed_revisions: int = Field(ge=0)
    revisions_without_operator_review: int = Field(ge=0)
    revisions_without_engineered_by: int = Field(ge=0)
    grounding_findings: int = Field(ge=0)
    modelo_scope_classification_findings: int = Field(ge=0)
    required_coverage_gap_rows: int = Field(ge=0)
    unattributed_oracle_payloads: int = Field(ge=0)
    unmatched_oracle_evidence: int = Field(ge=0)
    unused_declared_axes: int = Field(ge=0)
    scope_diagnostics: int = Field(ge=0)
    locale_unavailable_modelos: int = Field(ge=0)
    untranslated_locale_labels: int = Field(ge=0)


class ConformanceVacuityFloors(ConformanceModel):
    """Minimums proving the run examined a real registry before reporting zeros.

    A profile composed from an empty or half-read tree reports no gaps, no
    findings, and no unreviewed revisions while having examined nothing. Each
    floor is a POPULATION the audit must have reached; falling below one means
    the measurement, not the registry, is what changed.
    """

    composed_revisions: int = Field(ge=1)
    composed_modelos: int = Field(ge=1)
    reconciled_casillas: int = Field(ge=1)
    declared_grounding_claims: int = Field(ge=1)
    bundled_oracle_payloads: int = Field(ge=1)
    audited_locale_leaves: int = Field(ge=1)


class ConformanceBaseline(ConformanceModel):
    """The committed conformance ratchet baseline.

    Attributes:
        recorded_at: When the baseline was captured.
        source: The command that produced it.
        review_cadence: When the ceilings are expected to be revisited.
        note: Why this capture happened and under what tree conditions.
            Mandatory and non-empty, because in a shared worktree a baseline is
            a snapshot of a MOVING tree: a capture taken while a peer's
            half-landed change is present records their state as everyone's
            ceiling, and a re-record with no stated reason is indistinguishable
            from silencing a real regression.
        ceilings: Shrink-only backlog and defect counters.
        floors: Anti-vacuity population minimums.
    """

    recorded_at: str = Field(min_length=1)
    source: str = Field(min_length=1)
    review_cadence: str = Field(min_length=1)
    note: str = Field(min_length=1)
    ceilings: ConformanceRatchetCeilings
    floors: ConformanceVacuityFloors


class ConformanceAuditResult(ConformanceModel):
    """The current report compared against the committed baseline.

    Attributes:
        report: The report the comparison was taken over.
        baseline: The committed baseline it was compared against.
        ratchet_violations: Counters that GREW past their ceiling.
        vacuity_violations: Populations that FELL below their floor, meaning the
            run examined less than the baseline proves it must.
    """

    report: ConformanceReport
    baseline: ConformanceBaseline
    ratchet_violations: tuple[str, ...]
    vacuity_violations: tuple[str, ...]

    @property
    def violations(self) -> tuple[str, ...]:
        """Every violation, vacuity first because it invalidates the ratchet reading."""
        return (*self.vacuity_violations, *self.ratchet_violations)

    @property
    def passed(self) -> bool:
        """Whether the audit found neither a grown backlog nor a shrunken measurement."""
        return not self.violations


def baseline_path() -> Path:
    """Return the committed ratchet baseline path.

    Lives beside this module under ``dev/`` and is read only by dev-side code:
    nothing shipped in the wheel may consume it.
    """
    return Path(__file__).resolve().parent / _BASELINE_FILENAME


def load_baseline(path: Path | None = None) -> ConformanceBaseline:
    """Load the committed conformance ratchet baseline.

    Args:
        path: Optional override for tests and staged reviews. Defaults to the
            committed baseline beside this module.

    Returns:
        The parsed :class:`ConformanceBaseline`.

    Raises:
        SystemExit: The baseline is missing or unreadable. A gate that silently
            invented a baseline would pass on any tree at all.
    """
    resolved = baseline_path() if path is None else path
    try:
        raw = json.loads(resolved.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise SystemExit(f"{resolved}: conformance baseline cannot be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{resolved}: conformance baseline is not valid JSON: {exc}") from exc
    return ConformanceBaseline.model_validate(raw)


def baseline_weakenings(candidate: ConformanceBaseline, committed: ConformanceBaseline) -> tuple[str, ...]:
    """Name every counter ``candidate`` would move in the WEAKENING direction.

    Weakening has two shapes and they are opposite movements. A CEILING that
    RISES permits more backlog than the committed one; a FLOOR that FALLS
    demands less measurement. Both make the gate accept a tree the committed
    baseline refuses, which is the whole content of "the ratchet moved the wrong
    way", and neither is visible in a capture that simply overwrites.

    The floor direction is the one that needs a guard. A raised ceiling
    self-heals loudly: the backlog it now permits shows up on the census and the
    coverage screen, and the next honest capture pulls it back down. A lowered
    floor is silent forever. A capture taken while a peer's half-landed change
    has removed revisions from the tree permanently lowers ``composed_revisions``,
    and from then on a genuinely half-read tree passes the anti-vacuity check
    that exists to catch exactly that.

    Args:
        candidate: The baseline a capture is about to write.
        committed: The baseline already on disk.

    Returns:
        One sentence per weakened counter, ceilings first, empty when the
        capture only strengthens or leaves every counter flat.
    """
    weakened: list[str] = []
    for field_name in ConformanceRatchetCeilings.model_fields:
        proposed = getattr(candidate.ceilings, field_name)
        allowed = getattr(committed.ceilings, field_name)
        if proposed > allowed:
            weakened.append(f"ceiling {field_name} would rise from {allowed} to {proposed}, permitting more backlog")
    for field_name in ConformanceVacuityFloors.model_fields:
        proposed = getattr(candidate.floors, field_name)
        required = getattr(committed.floors, field_name)
        if proposed < required:
            weakened.append(
                f"floor {field_name} would fall from {required} to {proposed}, demanding less measurement",
            )
    return tuple(weakened)


def record_baseline(
    report: ConformanceReport,
    *,
    note: str,
    recorded_at: str,
    review_cadence: str = _DEFAULT_REVIEW_CADENCE,
    source: str = _RECORD_COMMAND,
    path: Path | None = None,
    accept_weakening: bool = False,
) -> ConformanceBaseline:
    """Write a baseline captured from ``report`` and return it.

    Generated from a real run rather than hand-authored, so a committed ceiling
    is always a number the tool actually measured. Refuses a degraded report
    outright: three axes are unmeasured under the degraded read and would be
    frozen as clean zeros nothing established.

    A capture over an EXISTING baseline is also compared against it. The three
    prior guards — not degraded, non-empty rows, non-empty note — all describe
    the report in isolation, so a capture could raise a ceiling or lower a floor
    without anything saying so, and the note requirement only proves a sentence
    was typed, never that it describes the movement. Every weakened counter is
    now named, and accepting one is an explicit act.

    Args:
        report: The freshly composed report to capture.
        note: Why this capture happened and under what tree conditions.
        recorded_at: The capture date.
        review_cadence: When the ceilings should next be revisited.
        source: The command that produced the capture.
        path: Optional override for tests. Defaults to the committed baseline.
        accept_weakening: Take the weakened counters deliberately. Absent a
            prior baseline there is nothing to weaken and this has no effect.

    Returns:
        The written :class:`ConformanceBaseline`.

    Raises:
        SystemExit: The report is degraded, composed no rows at all, or would
            weaken a counter against the baseline already on disk without
            ``accept_weakening``.
    """
    if not report.registry_validated:
        raise SystemExit(
            "refusing to record a baseline from a degraded read: evidence-tier coverage, the "
            "support probe, and the derived authorization were never measured, and freezing them "
            "as zero would state a fact nobody established",
        )
    if not report.rows:
        raise SystemExit(
            "refusing to record a baseline from a report with zero revision rows; every ceiling "
            "would be zero and every floor unmeetable",
        )
    baseline = ConformanceBaseline(
        recorded_at=recorded_at,
        source=source,
        review_cadence=review_cadence,
        note=note,
        ceilings=_current_ceilings(report),
        floors=_current_floors(report),
    )
    resolved = baseline_path() if path is None else path
    if resolved.exists() and not accept_weakening:
        weakened = baseline_weakenings(baseline, load_baseline(resolved))
        if weakened:
            listed = "\n  ".join(weakened)
            raise SystemExit(
                "refusing to record a baseline that weakens the ratchet:\n  "
                f"{listed}\n"
                "A rising ceiling permits a backlog the committed baseline refuses; a falling floor "
                "lets a half-read tree pass the anti-vacuity check that exists to catch it, and that "
                "one never heals on its own. If the movement is real and intended, re-run with the "
                "acceptance flag and say in the note which counter moved and why.",
            )
    resolved.write_text(
        json.dumps(baseline.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding=UTF_8_ENCODING,
    )
    return baseline


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
    """Read schema-local translation coverage for every directory-mode modelo."""
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
    """Return schema-local translation coverage keyed by ``(modelo, revision)``.

    Returns:
        The coverage index, and the modelo ids the locale manager could not
        read. An unreadable modelo is REPORTED, never rendered as zero coverage:
        the two are different claims and only one of them is about translation.
    """
    return _cached_locale_index()


def _read_locale_coverage() -> tuple[LocaleCoverageIndex, tuple[str, ...]]:
    """Sweep every directory-mode modelo once, indexing its per-revision records."""
    manager = ModeloLocaleManager()
    index: dict[tuple[str, str], tuple[ModeloLocaleCoverageRecord, ...]] = {}
    unavailable: list[str] = []
    for modelo_id in manager.modelo_ids():
        try:
            records = manager.coverage_records(modelo_id, locales=AUDITED_LOCALES)
        except ModeloLocaleError:
            unavailable.append(modelo_id)
            continue
        grouped: dict[str, list[ModeloLocaleCoverageRecord]] = {}
        for record in records:
            grouped.setdefault(record.revision_id, []).append(record)
        for revision_id, items in grouped.items():
            index[(modelo_id, revision_id)] = tuple(items)
    return index, tuple(sorted(unavailable))


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
    return build_conformance_report(
        profile,
        locale_index=locale_index,
        locale_unavailable_modelos=unavailable,
        oracle_inventory=load_bundled_external_oracle_inventory(),
    )


def build_conformance_report(
    profile: RegistryConformanceProfile,
    *,
    locale_index: Mapping[tuple[str, str], Sequence[ModeloLocaleCoverageRecord]],
    locale_unavailable_modelos: Sequence[str],
    oracle_inventory: ExternalOracleInventory,
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


def check_conformance_ratchet(
    report: ConformanceReport,
    baseline: ConformanceBaseline,
) -> ConformanceAuditResult:
    """Compare a report against the committed baseline in both directions.

    Args:
        report: The freshly composed report.
        baseline: The committed ceilings and floors.

    Returns:
        A :class:`ConformanceAuditResult` naming every grown backlog counter and
        every shrunken measurement population.

    Raises:
        SystemExit: The report composed no rows at all. A ratchet over an empty
            input reports every counter clean while having examined nothing,
            which is worse than no gate.
    """
    if not report.rows:
        raise SystemExit(
            "conformance audit composed zero revision rows; every counter would read clean while "
            "nothing was examined, so the result would be meaningless",
        )

    current_ceilings = _current_ceilings(report)
    ratchet: list[str] = []
    for field_name in ConformanceRatchetCeilings.model_fields:
        current = getattr(current_ceilings, field_name)
        allowed = getattr(baseline.ceilings, field_name)
        if current > allowed:
            ratchet.append(f"{field_name} grew from {allowed} to {current}")

    current_floors = _current_floors(report)
    vacuity: list[str] = []
    for field_name in ConformanceVacuityFloors.model_fields:
        current = getattr(current_floors, field_name)
        required = getattr(baseline.floors, field_name)
        if current < required:
            vacuity.append(
                f"{field_name} fell from {required} to {current}; the measurement shrank, so the "
                "ratchet reading above cannot be trusted",
            )

    return ConformanceAuditResult(
        report=report,
        baseline=baseline,
        ratchet_violations=tuple(ratchet),
        vacuity_violations=tuple(vacuity),
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
            ),
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


def render_audit(result: ConformanceAuditResult) -> str:
    """Render the ratchet comparison, violations first."""
    current = _current_ceilings(result.report)
    floors = _current_floors(result.report)
    lines = [
        _kv_line(
            "audit",
            registry_validated=result.report.registry_validated,
            passed=result.passed,
            ratchet_violations=len(result.ratchet_violations),
            vacuity_violations=len(result.vacuity_violations),
            baseline_recorded_at=result.baseline.recorded_at,
        ),
    ]
    lines.extend(
        _kv_line(
            "ceiling",
            counter=field_name,
            current=getattr(current, field_name),
            allowed=getattr(result.baseline.ceilings, field_name),
        )
        for field_name in ConformanceRatchetCeilings.model_fields
    )
    lines.extend(
        _kv_line(
            "floor",
            population=field_name,
            current=getattr(floors, field_name),
            required=getattr(result.baseline.floors, field_name),
        )
        for field_name in ConformanceVacuityFloors.model_fields
    )
    lines.extend(_kv_line("violation", kind="vacuity", detail=item) for item in result.vacuity_violations)
    lines.extend(_kv_line("violation", kind="ratchet", detail=item) for item in result.ratchet_violations)
    return "\n".join(lines)


def _current_ceilings(report: ConformanceReport) -> ConformanceRatchetCeilings:
    """Project the report's shrink-only backlog and defect counters.

    Both review counters read the same census, and the subtraction rather than a
    second sum is deliberate: every revision the census does not record as
    operator-reviewed lacks operator review, whatever tier it does declare, so a
    fourth status added to the vocabulary tomorrow enrols itself in the operator
    backlog instead of silently escaping it.
    """
    return ConformanceRatchetCeilings(
        unreviewed_revisions=report.review_status_census.get(RevisionReviewStatus.PENDING_REVIEW.value, 0),
        revisions_without_operator_review=(
            report.revision_count - report.review_status_census.get(RevisionReviewStatus.OPERATOR_REVIEWED.value, 0)
        ),
        revisions_without_engineered_by=report.revision_count - report.engineered_by_declared_count,
        grounding_findings=report.grounding_finding_count,
        modelo_scope_classification_findings=report.modelo_scope_classification_finding_count,
        required_coverage_gap_rows=report.required_coverage_gap_row_count,
        unattributed_oracle_payloads=len(report.unattributed_oracle_payloads),
        unmatched_oracle_evidence=len(report.unmatched_oracle_evidence),
        unused_declared_axes=len(report.unused_declared_axes),
        scope_diagnostics=report.scope_diagnostic_count,
        locale_unavailable_modelos=len(report.locale_unavailable_modelos),
        untranslated_locale_labels=report.untranslated_locale_labels,
    )


def _current_floors(report: ConformanceReport) -> ConformanceVacuityFloors:
    """Project the populations the run must have reached to mean anything."""
    return ConformanceVacuityFloors(
        composed_revisions=report.revision_count,
        composed_modelos=report.modelo_count,
        reconciled_casillas=report.reconciled_casillas,
        declared_grounding_claims=report.declared_grounding_claims,
        bundled_oracle_payloads=report.bundled_oracle_payload_count,
        audited_locale_leaves=report.audited_locale_leaves,
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
    records: Sequence[ModeloLocaleCoverageRecord] | None,
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


def _stale_key_count(record: ModeloLocaleCoverageRecord) -> int:
    """Count locale leaves on disk that no registry key claims."""
    return sum(1 for drift in record.drift if drift.kind is ModeloLocaleDriftKind.STALE)


def _locale_axis_summary(
    locale_index: Mapping[tuple[str, str], Sequence[ModeloLocaleCoverageRecord]],
) -> tuple[LocaleAxisSummary, ...]:
    """Fold the locale index into one registry-wide summary per audited locale."""
    required: dict[str, int] = {}
    translated: dict[str, int] = {}
    complete: dict[str, int] = {}
    measured: dict[str, int] = {}
    stale: dict[str, int] = {}
    for records in locale_index.values():
        for record in records:
            code = record.locale.value
            required[code] = required.get(code, 0) + record.label_required
            translated[code] = translated.get(code, 0) + record.label_translated
            complete[code] = complete.get(code, 0) + (1 if record.complete else 0)
            measured[code] = measured.get(code, 0) + 1
            stale[code] = stale.get(code, 0) + _stale_key_count(record)
    return tuple(
        LocaleAxisSummary(
            locale=code,
            labels_required=required[code],
            labels_translated=translated.get(code, 0),
            complete_revisions=complete.get(code, 0),
            measured_revisions=measured.get(code, 0),
            stale_keys=stale.get(code, 0),
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
        return ",".join(str(item) for item in value) if value else "-"
    text = str(value)
    if not text or any(character in text for character in ' \t"='):
        return json.dumps(text)
    return text
