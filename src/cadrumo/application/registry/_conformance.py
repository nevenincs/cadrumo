"""Per-revision conformance profile: one composed governance row per modelo revision.

Nothing in the registry declares "how conformant is modelo X". Conformance is
deduced today by a handful of independent folds — an evidence-tier coverage
audit, a support-capability probe, a registry-scope validator, an authorization
manifest, an external-oracle grounding relation, a classification-coherence
check — each answering one question about one axis, none of them joined. This
module performs the join: it emits exactly one
:class:`RevisionConformanceRow` per modelo revision in the loaded tree,
carrying every axis side by side plus the one axis that cannot be derived at
all, the revision's declared governance stamp.

Discovery evidence, not authority
---------------------------------

A composed row is DISCOVERY EVIDENCE. It tells a reader where to look; it never
authorises an action, and no gate should grant or refuse on the strength of one.
Two consequences follow and are load-bearing:

* **Status is derived, never declared.** No per-modelo status scalar exists in
  the registry and this module does not invent one — not in the tree, and not as
  a synthesised grade on the row either. A single letter or number would be read
  as a verdict this data cannot support, so the row exposes the individual
  signals (coverage gaps, scope diagnostics, grounding findings, review status)
  and leaves the reading to the reader. The one DECLARED axis is provenance:
  who engineered a revision and how far its review has progressed are facts
  about people and agents that nothing in the tree can compute.
* **Absence is not zero.** A revision that reconciles no casillas at all makes
  no grounding claim; a revision that reconciles two hundred and independently
  checks none of them makes a claim and fails it. Both would read ``0.0`` if
  collapsed, so an axis that was not measured is :data:`None` here, never a
  fabricated zero or a fabricated default. This is why a degraded read reports
  :attr:`RevisionConformanceRow.modelo_authorization` as :data:`None` rather
  than as ``UNAUTHORIZED`` — the latter is the default-deny VALUE, and emitting
  it for an axis nobody checked would state a fact the composer never
  established.

Coverage, not correctness
-------------------------

:attr:`RevisionConformanceRow.independent_check_coverage` measures COVERAGE OF
INDEPENDENT CHECKING and nothing else. A low value means most of a revision's
reconciliation is the engine agreeing with itself, NOT that the revision
computes a wrong number; a high value means more of it is cross-checked against
AEAT's own published figures, NOT that it is correct. The quantity is the same
one :class:`~cadrumo.application.verification.VerificationVerdict` reports per
filing, lifted to registry scope by
:mod:`~cadrumo.domain.calculations.registry._external_grounding`.

Scope of each composed axis
---------------------------

Axes disagree about what they describe, and silently attributing a coarse fact
to a fine row is how a governance report starts lying. Each axis therefore
carries its scope in its own field name and model:

* :attr:`RevisionConformanceRow.capabilities` is resolved from THIS revision.
* :attr:`RevisionConformanceRow.latest_revision_support` projects the
  support matrix, which probes the modelo's LATEST revision only. It names the
  revision it probed and states outright whether that is this row, so a
  latest-revision capability is never read as a fact about an older one.
* :attr:`RevisionConformanceRow.modelo_classification` and
  :attr:`RevisionConformanceRow.modelo_authorization` are modelo-level and are
  named so.
* Registry-scope diagnostics are registry-wide. A diagnostic that names its
  modelo and revision is attributed to that row; the remainder stay on
  :attr:`RegistryConformanceProfile.unattributed_scope_diagnostics` rather than
  being dropped, because a diagnostic nothing renders is a diagnostic nobody
  reads.

Reading the registry
--------------------

Every fact is read from COMPILED :class:`ModeloDefinition` records, never from a
listing of fragment subdirectories: a subdirectory-blind read of this registry
has twice produced wrong "parse-only" verdicts.

:func:`audit_bundled_registry_conformance` reads through the validating
authority by default. Passing ``validate=False`` selects the degraded read: the
non-validating tree loader, so a governance read survives a concurrently-edited
registry the validating authority would refuse outright. Every row emitted that
way is stamped ``registry_validated=False`` individually — the label rides on
the row and not on a global flag a renderer could drop — and the three axes that
require the validating authority (model-law coverage, the support probe, the
derived authorization) are absent rather than guessed.

See Also:
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority`
        Registry authority the validated read composes every axis from.
    :class:`~domain.calculations.registry.ModeloRevision`
        The versioned ruleset one composed row describes.
    :class:`~domain.calculations.registry.RegistryExternalGroundingAudit`
        External-oracle grounding fold nested onto each row.
    :class:`~domain.calculations.registry.RegistryClassificationAudit`
        Classification-coherence fold nested onto each row.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field

from ...core import NON_REGISTRY_MODELOS as _NON_REGISTRY_MODELOS
from ...core import REVIEWED_REVISION_REVIEW_STATUSES as _REVIEWED_REVISION_REVIEW_STATUSES
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ...core import Modelo as _Modelo
from ...core import RevisionReviewStatus as _RevisionReviewStatus
from ...core.access_gate import ModeloAuthorization as _ModeloAuthorization
from ...core.resources import bundled_path as _bundled_path
from ...domain.calculations.registry import REQUIRED_COVERAGE_TIERS as _REQUIRED_COVERAGE_TIERS
from ...domain.calculations.registry import DeclaredAxisUsage as _DeclaredAxisUsage
from ...domain.calculations.registry import EvidenceTier as _EvidenceTier
from ...domain.calculations.registry import ModelLawCoverageLedger as _ModelLawCoverageLedger
from ...domain.calculations.registry import ModeloClassificationRow as _ModeloClassificationRow
from ...domain.calculations.registry import ModeloDefinition as _ModeloDefinition
from ...domain.calculations.registry import ModeloEntry as _ModeloEntry
from ...domain.calculations.registry import ModeloId as _ModeloId
from ...domain.calculations.registry import ModeloRevision as _ModeloRevision
from ...domain.calculations.registry import RegistryClassificationAudit as _RegistryClassificationAudit
from ...domain.calculations.registry import RegistryCoverageAudit as _RegistryCoverageAudit
from ...domain.calculations.registry import RegistryExternalGroundingAudit as _RegistryExternalGroundingAudit
from ...domain.calculations.registry import RequiredCoverageTier as _RequiredCoverageTier
from ...domain.calculations.registry import RevisionExternalGroundingRow as _RevisionExternalGroundingRow
from ...domain.calculations.registry import RevisionId as _RevisionId
from ...domain.calculations.registry import UnattributedOraclePayload as _UnattributedOraclePayload
from ...domain.calculations.registry import (
    ValidatedRegistryAuthority as _ValidatedRegistryAuthority,
)
from ...domain.calculations.registry import (
    audit_registry_model_law_coverage as _audit_registry_model_law_coverage,
)
from ...domain.calculations.registry import (
    build_classification_coherence_audit as _build_classification_coherence_audit,
)
from ...domain.calculations.registry import (
    build_external_grounding_audit as _build_external_grounding_audit,
)
from ...domain.calculations.registry import build_support_matrix as _build_support_matrix
from ...domain.calculations.registry import (
    load_bundled_external_oracle_inventory as _load_bundled_external_oracle_inventory,
)
from ...domain.calculations.registry import load_registry_tree as _load_registry_tree
from ...domain.calculations.registry import (
    revision_capability_probe as _revision_capability_probe,
)
from ...domain.calculations.registry import validate_registry_scope as _validate_registry_scope
from ._errors import RegistryApplicationInputError

__all__ = [
    "LatestRevisionSupportProbe",
    "RegistryConformanceProfile",
    "RevisionCapabilityFacts",
    "RevisionConformanceRow",
    "RevisionGovernanceStamp",
    "RevisionModelLawCoverage",
    "audit_bundled_registry_conformance",
    "build_registry_conformance_profile",
]


class ConformanceModel(BaseModel):
    """Strict frozen base for composed conformance facts."""

    model_config = _STRICT_FROZEN_CONFIG


class RevisionGovernanceStamp(ConformanceModel):
    """The revision's DECLARED review and engineering provenance.

    The only axis on a conformance row that is declared rather than derived.
    Authorship and signoff are facts about the people and agents who built a
    revision, so nothing in the tree can compute them. Absence of the stamp
    block on ``revision.toml`` reads as
    :attr:`~cadrumo.core.RevisionReviewStatus.PENDING_REVIEW`, the fail-closed
    default, so an unstamped revision is a visible backlog entry rather than a
    silent pass.

    Attributes:
        review_status: How far the review of this revision has progressed.
        engineered_by: Who built the revision, or :data:`None` when undeclared.
        reviewed_by: Who reviewed it. Present exactly when ``review_status`` is
            beyond ``PENDING_REVIEW``; the schema refuses any other combination.
        reviewed_at: The date of that review, under the same pairing rule.
    """

    review_status: _RevisionReviewStatus
    engineered_by: str | None = None
    reviewed_by: str | None = None
    reviewed_at: date | None = None

    @property
    def is_reviewed(self) -> bool:
        """Whether the revision asserts a completed review of any kind."""
        return self.review_status in _REVIEWED_REVISION_REVIEW_STATUSES

    @property
    def declares_engineer(self) -> bool:
        """Whether the revision names who engineered it."""
        return self.engineered_by is not None


class RevisionCapabilityFacts(ConformanceModel):
    """What THIS revision declares, read from this revision alone.

    Distinct from :class:`LatestRevisionSupportProbe`, which describes the
    modelo's latest revision whatever row it is attached to. Every field here is
    a direct read or fold over the revision named on the owning row.

    Attributes:
        calc_grade: Whether the revision's calculation closure is non-empty —
            at least one formula, binding, or verification wiring the engine
            traverses.
        has_completeness_manifest: Whether the revision declares a
            calculation-completeness manifest.
        has_fixed_width_export: Whether it registers a fichero-BOE export layout.
        has_xml_dictionary_export: Whether it registers an XML-dictionary layout.
        extraction_profile_count: Extraction profiles declared on the revision.
        casilla_count: Casillas declared on the revision.
        formula_count: Formulas declared on the revision.
        binding_count: Data bindings declared on the revision.
        verification_expectation_count: Verification contracts declared on the
            revision. Zero means the revision reconciles nothing at all, which
            is why a grounding coverage of ``0.0`` and an absent coverage are
            different answers.
        support_removal_decision_count: Declared deprecation decisions.
        live_cross_reference_count: Declared AEAT-portal cross-references.
        casilla_continuidad_evolution_count: Declared per-ejercicio casilla
            continuity evolutions.
    """

    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    extraction_profile_count: int = Field(ge=0)
    casilla_count: int = Field(ge=0)
    formula_count: int = Field(ge=0)
    binding_count: int = Field(ge=0)
    verification_expectation_count: int = Field(ge=0)
    support_removal_decision_count: int = Field(ge=0)
    live_cross_reference_count: int = Field(ge=0)
    casilla_continuidad_evolution_count: int = Field(ge=0)


class LatestRevisionSupportProbe(ConformanceModel):
    """The support matrix's modelo-level capability probe, and what it probed.

    The support matrix answers "what does modelo X support" by probing the
    modelo's LATEST revision only. Attaching that answer to every revision row
    unlabelled would silently attribute a current capability to a superseded
    revision, so the probe travels with the revision it actually examined and
    states outright whether that is the row it is attached to.

    Attributes:
        probed_revision: The revision the support matrix examined — the one with
            the most recent ``valid_from``.
        describes_this_revision: Whether ``probed_revision`` is the revision on
            the owning row. When :data:`False`, every other field here is a fact
            about a DIFFERENT revision of the same modelo.
        calc_grade: Probed revision's calculation-closure state.
        has_completeness_manifest: Probed revision's manifest presence.
        has_fixed_width_export: Probed revision's fichero-BOE layout presence.
        has_xml_dictionary_export: Probed revision's XML-dictionary presence.
        has_extractor: Whether the probed revision registers any extractor.
        rename_count: Declared casilla continuity evolutions on the probed
            revision.
        deprecation_count: Declared support-removal decisions on it.
        portal_compatibility_ref_count: Declared AEAT-portal cross-references.
        is_deprecated: The support matrix's own deprecation verdict for the
            modelo, which is :data:`False` by construction while no revision in
            the tree declares a support-removal decision.
    """

    probed_revision: _RevisionId
    describes_this_revision: bool
    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    has_extractor: bool
    rename_count: int = Field(ge=0)
    deprecation_count: int = Field(ge=0)
    portal_compatibility_ref_count: int = Field(ge=0)
    is_deprecated: bool


class RevisionModelLawCoverage(ConformanceModel):
    """Evidence-tier coverage for one revision, split by whether the tier is mandatory.

    Legal authority, official source guidance, and layout authority are
    mandatory: the registry cannot be filing-grade without them, so a gap on one
    is a failure. Executable parity is reported rather than required, because no
    official safe calculator or formula workbook exists for many revisions.
    Collapsing the two kinds of gap into one count would make an expected
    absence look like a defect.

    Attributes:
        satisfied_tiers: Evidence tiers backed by at least one registry
            reference.
        gap_tiers: Evidence tiers with no supporting reference at all.
        required_tier_gaps: The subset of ``gap_tiers`` that is mandatory.
    """

    satisfied_tiers: tuple[_EvidenceTier, ...]
    gap_tiers: tuple[_EvidenceTier, ...]
    required_tier_gaps: tuple[_RequiredCoverageTier, ...]

    @property
    def has_required_gap(self) -> bool:
        """Whether any mandatory evidence tier is unbacked."""
        return bool(self.required_tier_gaps)


class RevisionConformanceRow(ConformanceModel):
    """Every conformance axis for one modelo revision, side by side.

    Emitted for EVERY revision in the loaded tree, including revisions with no
    verification contract, no oracle evidence, and no governance stamp, so a
    revision with nothing to report is a visible row rather than an absent one.

    Attributes:
        modelo: The modelo this revision belongs to.
        revision: The revision id this row describes.
        registry_validated: Whether the facts on THIS row were read through the
            validating authority. Stamped per row rather than only on the
            envelope so a renderer cannot drop the label and present a degraded
            row as validated authority.
        governance: The declared review and engineering provenance.
        capabilities: What this revision itself declares.
        latest_revision_support: The modelo-level support probe, or :data:`None`
            when the degraded read could not build it.
        model_law_coverage: Evidence-tier coverage, or :data:`None` when the
            degraded read could not build validated snapshots for it.
        external_grounding: The external-oracle grounding row for this revision.
        modelo_classification: Modelo-level classification coherence facts.
        modelo_authorization: The derived modelo-level authorization capability,
            or :data:`None` when the degraded read did not consult the
            authority. :data:`None` means UNCHECKED and is deliberately not the
            ``UNAUTHORIZED`` value, which would assert a default-deny verdict
            nobody established.
        scope_diagnostics: Registry-scope diagnostics naming this exact
            modelo and revision.
    """

    modelo: _ModeloId
    revision: _RevisionId
    registry_validated: bool
    governance: RevisionGovernanceStamp
    capabilities: RevisionCapabilityFacts
    latest_revision_support: LatestRevisionSupportProbe | None = None
    model_law_coverage: RevisionModelLawCoverage | None = None
    external_grounding: _RevisionExternalGroundingRow
    modelo_classification: _ModeloClassificationRow
    modelo_authorization: _ModeloAuthorization | None = None
    scope_diagnostics: tuple[str, ...] = ()

    @property
    def reconciles_nothing(self) -> bool:
        """Whether the revision enrols no casilla in any verification contract.

        The distinction that keeps an absent grounding claim apart from a failed
        one: a revision reconciling nothing makes no claim about independent
        checking at all.
        """
        return not self.external_grounding.reconciled_casilla_ids

    @property
    def independent_check_coverage(self) -> float | None:
        """Fraction of this revision's reconciled casillas that are independently checked.

        COVERAGE OF INDEPENDENT CHECKING, never a correctness score. A low value
        means most reconciliation here is the engine agreeing with itself; it is
        not a statement that any number is wrong. :data:`None` — not ``0.0`` —
        when the revision reconciles nothing, because no coverage claim exists
        to report.
        """
        if self.reconciles_nothing:
            return None
        return self.external_grounding.independent_check_coverage

    @property
    def has_required_coverage_gap(self) -> bool | None:
        """Whether a mandatory evidence tier is unbacked, or :data:`None` when uncomputed."""
        if self.model_law_coverage is None:
            return None
        return self.model_law_coverage.has_required_gap

    @property
    def grounding_finding_count(self) -> int:
        """Breaches of the external-grounding honesty relation on this revision."""
        return len(self.external_grounding.findings)

    @property
    def modelo_classification_finding_count(self) -> int:
        """Classification-coherence findings carried by this row's MODELO.

        Named for its scope because it is a modelo-level count repeated on every
        revision row of that modelo. Summing it across rows multiplies each
        finding by the modelo's revision count; count the findings on the
        classification audit itself instead.
        """
        return len(self.modelo_classification.findings)


class RegistryConformanceProfile(ConformanceModel):
    """Registry-wide conformance profile: one row per modelo revision.

    Attributes:
        rows: One :class:`RevisionConformanceRow` per revision in the loaded
            tree, ordered by modelo then revision id.
        registry_validated: Whether the profile was composed through the
            validating authority. Every row repeats this, so the envelope value
            is a summary of the rows and never the only place it is recorded.
        scope_diagnostics: Every registry-scope diagnostic the tree produced.
        unattributed_scope_diagnostics: The diagnostics that name no single
            modelo and revision, kept here rather than dropped.
        declared_axis_usage: Per-axis census of schema surfaces the tree may or
            may not exercise, so a dead vocabulary member reports as unused
            rather than as silently passing.
        unattributed_oracle_payloads: Bundled oracle payloads whose evidence
            could not be attributed to any modelo and filing year.
        unmatched_oracle_evidence: Attributed oracle evidence that reaches no
            registry revision.
    """

    rows: tuple[RevisionConformanceRow, ...]
    registry_validated: bool
    scope_diagnostics: tuple[str, ...] = ()
    unattributed_scope_diagnostics: tuple[str, ...] = ()
    declared_axis_usage: tuple[_DeclaredAxisUsage, ...] = ()
    unattributed_oracle_payloads: tuple[_UnattributedOraclePayload, ...] = ()
    unmatched_oracle_evidence: tuple[_UnattributedOraclePayload, ...] = ()

    @property
    def composed_revision_count(self) -> int:
        """Revisions this profile composed a row for.

        The anti-vacuity floor: a profile composed from an empty tree would
        report no gaps, no findings, and no unreviewed revisions while having
        examined nothing at all.
        """
        return len(self.rows)

    @property
    def composed_modelo_count(self) -> int:
        """Distinct modelos represented in :attr:`rows`."""
        return len({row.modelo for row in self.rows})

    def review_status_census(self) -> Mapping[_RevisionReviewStatus, int]:
        """Count rows by declared review status, including statuses nothing declares.

        Every member is present with an explicit count so a status no revision
        holds reads as a real zero rather than as an absent key a renderer would
        silently omit.
        """
        counts = dict.fromkeys(_RevisionReviewStatus, 0)
        for row in self.rows:
            counts[row.governance.review_status] += 1
        return counts

    @property
    def reviewed_revision_count(self) -> int:
        """Revisions asserting a completed review of any kind."""
        return sum(1 for row in self.rows if row.governance.is_reviewed)

    @property
    def engineered_by_declared_count(self) -> int:
        """Revisions naming who engineered them."""
        return sum(1 for row in self.rows if row.governance.declares_engineer)

    @property
    def required_coverage_gap_rows(self) -> tuple[RevisionConformanceRow, ...]:
        """Rows whose evidence-tier coverage leaves a mandatory tier unbacked.

        Read this together with :attr:`coverage_unmeasured_rows`. A degraded
        profile has no coverage on any row, so this is empty there — and an
        empty gap list means "nothing was measured", not "nothing is missing".
        Rendering the two counts side by side is what keeps those apart.
        """
        return tuple(row for row in self.rows if row.has_required_coverage_gap)

    @property
    def coverage_unmeasured_rows(self) -> tuple[RevisionConformanceRow, ...]:
        """Rows whose evidence-tier coverage was not computed at all.

        The denominator that stops an empty
        :attr:`required_coverage_gap_rows` from reading as a clean bill of
        health on a profile that never measured coverage in the first place.
        """
        return tuple(row for row in self.rows if row.model_law_coverage is None)

    @property
    def independent_check_coverage(self) -> float | None:
        """Registry-wide fraction of reconciled casillas that are independently checked.

        COVERAGE OF INDEPENDENT CHECKING, never a correctness score and never a
        quality ranking between modelos. :data:`None` — not ``0.0`` — when no
        row reconciles anything, because the ratio has no denominator and no
        claim is being made.
        """
        reconciled = sum(len(row.external_grounding.reconciled_casilla_ids) for row in self.rows)
        if not reconciled:
            return None
        checked = sum(len(row.external_grounding.independently_checked_casilla_ids) for row in self.rows)
        return checked / reconciled

    @property
    def grounding_finding_count(self) -> int:
        """Breaches of the external-grounding honesty relation across every row."""
        return sum(row.grounding_finding_count for row in self.rows)


@dataclass(frozen=True, slots=True)
class _AxisIndex:
    """The per-axis lookup maps the row fold reads, keyed for O(1) joins.

    An axis the caller could not build is an EMPTY map rather than a sentinel,
    so a missing entry means the same thing everywhere: absent, reported as
    :data:`None` on the row. The two axes that must be complete
    (classification, external grounding) are read through the ``require_*``
    accessors, which refuse instead of returning ``None``.
    """

    grounding_rows: Mapping[tuple[_ModeloId, _RevisionId], _RevisionExternalGroundingRow]
    classification_rows: Mapping[_ModeloId, _ModeloClassificationRow]
    coverage_ledgers: Mapping[tuple[_ModeloId, _RevisionId], _ModelLawCoverageLedger]
    support_entries: Mapping[_ModeloId, _ModeloEntry]

    @classmethod
    def build(
        cls,
        *,
        external_grounding: _RegistryExternalGroundingAudit,
        classification: _RegistryClassificationAudit,
        model_law_coverage: _RegistryCoverageAudit | None,
        support_matrix: Sequence[_ModeloEntry] | None,
    ) -> _AxisIndex:
        """Key each supplied axis by the identity the row fold joins on."""
        return cls(
            grounding_rows={(row.modelo, row.revision): row for row in external_grounding.rows},
            classification_rows={row.modelo: row for row in classification.rows},
            coverage_ledgers=(
                {}
                if model_law_coverage is None
                else {(ledger.modelo, ledger.revision): ledger for ledger in model_law_coverage.ledgers}
            ),
            support_entries={} if support_matrix is None else {entry.modelo_id: entry for entry in support_matrix},
        )

    def require_classification_row(self, modelo_id: _ModeloId) -> _ModeloClassificationRow:
        """Return the modelo's classification row, refusing when the axis omits it.

        Raises:
            RegistryApplicationInputError: When the audit carries no row for
                ``modelo_id``. Dropping the modelo would hide it from the
                census that exists to count it.
        """
        row = self.classification_rows.get(modelo_id)
        if row is None:
            raise RegistryApplicationInputError(
                f"registry conformance: classification audit carries no row for modelo {modelo_id!r}",
                context={"modelo": modelo_id},
            )
        return row

    def require_grounding_row(
        self,
        modelo_id: _ModeloId,
        revision_id: _RevisionId,
    ) -> _RevisionExternalGroundingRow:
        """Return the revision's external-grounding row, refusing when absent.

        Raises:
            RegistryApplicationInputError: When the audit carries no row for
                this revision.
        """
        row = self.grounding_rows.get((modelo_id, revision_id))
        if row is None:
            raise RegistryApplicationInputError(
                f"registry conformance: external-grounding audit carries no row for modelo "
                f"{modelo_id!r} revision {revision_id!r}",
                context={"modelo": modelo_id, "revision_id": revision_id},
            )
        return row


def _revision_conformance_row(
    revision: _ModeloRevision,
    *,
    modelo_id: _ModeloId,
    index: _AxisIndex,
    classification_row: _ModeloClassificationRow,
    support_entry: _ModeloEntry | None,
    authorization: _ModeloAuthorization | None,
    registry_validated: bool,
    scope_diagnostics: Sequence[str],
) -> RevisionConformanceRow:
    """Compose one revision's row from every axis.

    An axis the caller could not supply lands as :data:`None` rather than a
    zeroed value, so a row distinguishes "measured absent" from "not measured".

    The grounding row is resolved FIRST so a revision the audit omits is
    refused before any other axis is computed for it.
    """
    grounding_row = index.require_grounding_row(modelo_id, revision.id)
    ledger = index.coverage_ledgers.get((modelo_id, revision.id))
    return RevisionConformanceRow(
        modelo=modelo_id,
        revision=revision.id,
        registry_validated=registry_validated,
        governance=_governance_stamp(revision),
        capabilities=_capability_facts(revision, modelo_id=modelo_id),
        latest_revision_support=(
            None if support_entry is None else _support_probe(support_entry, revision_id=revision.id)
        ),
        model_law_coverage=None if ledger is None else _model_law_coverage(ledger),
        external_grounding=grounding_row,
        modelo_classification=classification_row,
        modelo_authorization=authorization,
        scope_diagnostics=_diagnostics_for(scope_diagnostics, modelo=modelo_id, revision=revision.id),
    )


def build_registry_conformance_profile(
    modelos: Iterable[_ModeloDefinition],
    *,
    external_grounding: _RegistryExternalGroundingAudit,
    classification: _RegistryClassificationAudit,
    scope_diagnostics: Sequence[str],
    registry_validated: bool,
    model_law_coverage: _RegistryCoverageAudit | None = None,
    support_matrix: Sequence[_ModeloEntry] | None = None,
    authorizations: Mapping[str, _ModeloAuthorization] | None = None,
) -> RegistryConformanceProfile:
    """Join every conformance axis into one row per modelo revision.

    A pure fold: the caller owns loading and validation, so the same composition
    serves the validating authority and the degraded tree read, and a test can
    inject a mutated axis and observe exactly which row changes.

    Args:
        modelos: Compiled :class:`ModeloDefinition` records, taken from the
            loaded tree and never from a fragment-directory listing. One row is
            emitted for every revision of every modelo given.
        external_grounding: The registry-wide external-oracle grounding audit.
            Must carry a row for each revision in ``modelos``.
        classification: The registry-wide classification-coherence audit. Must
            carry a row for each modelo in ``modelos``.
        scope_diagnostics: Registry-scope diagnostics for the same tree.
        registry_validated: Whether ``modelos`` came from the validating
            authority. Stamped onto every emitted row, not only the envelope.
        model_law_coverage: Evidence-tier coverage audit, or :data:`None` when
            the caller could not build validated snapshots. Absent rather than
            zeroed on every row.
        support_matrix: The modelo-level support-capability probe, or
            :data:`None` when unavailable.
        authorizations: Derived per-modelo authorization capabilities keyed by
            modelo id, or :data:`None` when unavailable. A modelo absent from a
            supplied mapping reports :data:`None`, which means UNCHECKED and is
            deliberately distinct from the ``UNAUTHORIZED`` verdict.

    Returns:
        The composed :class:`RegistryConformanceProfile`.

    Raises:
        RegistryApplicationInputError: When a supplied axis is missing a row for
            a modelo or revision present in ``modelos``. Dropping the revision
            instead would hide it from the census that exists to count it.
    """
    modelo_tuple = tuple(sorted(modelos, key=lambda item: item.id))
    index = _AxisIndex.build(
        external_grounding=external_grounding,
        classification=classification,
        model_law_coverage=model_law_coverage,
        support_matrix=support_matrix,
    )

    rows: list[RevisionConformanceRow] = []
    attributed_diagnostics: set[str] = set()
    for modelo in modelo_tuple:
        classification_row = index.require_classification_row(modelo.id)
        support_entry = index.support_entries.get(modelo.id)
        authorization = None if authorizations is None else authorizations.get(modelo.id)
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            row = _revision_conformance_row(
                revision,
                modelo_id=modelo.id,
                index=index,
                classification_row=classification_row,
                support_entry=support_entry,
                authorization=authorization,
                registry_validated=registry_validated,
                scope_diagnostics=scope_diagnostics,
            )
            attributed_diagnostics.update(row.scope_diagnostics)
            rows.append(row)

    return RegistryConformanceProfile(
        rows=tuple(rows),
        registry_validated=registry_validated,
        scope_diagnostics=tuple(scope_diagnostics),
        unattributed_scope_diagnostics=tuple(
            diagnostic for diagnostic in scope_diagnostics if diagnostic not in attributed_diagnostics
        ),
        declared_axis_usage=classification.axis_usage,
        unattributed_oracle_payloads=external_grounding.inventory.unattributed_payloads,
        unmatched_oracle_evidence=external_grounding.unmatched_evidence,
    )


def audit_bundled_registry_conformance(*, validate: bool = True) -> RegistryConformanceProfile:
    """Compose the conformance profile for the bundled registry tree.

    Args:
        validate: When :data:`True` (the default) every axis is read through the
            :class:`~domain.calculations.registry.ValidatedRegistryAuthority`.
            When :data:`False` the degraded read is used: the non-validating
            tree loader, so the profile still composes while a peer's mid-edit
            registry would make the authority refuse to load. Every row is then
            stamped ``registry_validated=False``, and the three axes that
            require the authority — model-law coverage, the support probe, and
            the derived authorization — are absent rather than guessed.

    Returns:
        The composed :class:`RegistryConformanceProfile`.

    Raises:
        RegistryValidationError: When ``validate`` is :data:`True` and the tree
            fails validation. The coverage audit re-runs registry validation
            itself, so it can refuse a tree the authority accepted on a cached
            verdict — a validated read that reports rather than hides that is
            the intended behaviour, and ``validate=False`` is the way past it.
    """
    registry_root = _bundled_path("registry", "aeat")
    inventory = _load_bundled_external_oracle_inventory()
    non_registry_codes = frozenset(item.value for item in _NON_REGISTRY_MODELOS)
    known_codes = frozenset(item.value for item in _Modelo)

    if not validate:
        modelos, _catalogues = _load_registry_tree(registry_root)
        return build_registry_conformance_profile(
            modelos,
            external_grounding=_build_external_grounding_audit(
                modelos,
                inventory=inventory,
                registry_validated=False,
            ),
            classification=_build_classification_coherence_audit(
                modelos,
                non_registry_modelo_codes=non_registry_codes,
                known_modelo_codes=known_codes,
                registry_validated=False,
            ),
            scope_diagnostics=_validate_registry_scope(modelos),
            registry_validated=False,
        )

    authority = _ValidatedRegistryAuthority.load(registry_root, source_root=_bundled_path())
    return build_registry_conformance_profile(
        authority.modelos,
        external_grounding=_build_external_grounding_audit(
            authority.modelos,
            inventory=inventory,
            registry_validated=True,
        ),
        classification=_build_classification_coherence_audit(
            authority.modelos,
            non_registry_modelo_codes=non_registry_codes,
            known_modelo_codes=known_codes,
            registry_validated=True,
        ),
        scope_diagnostics=_validate_registry_scope(authority.modelos),
        registry_validated=True,
        model_law_coverage=_audit_registry_model_law_coverage(
            authority.modelos,
            authority.catalogues,
            source_root=authority.source_root,
        ),
        support_matrix=_build_support_matrix(authority),
        authorizations={modelo.id: authority.authorization(modelo.id) for modelo in authority.modelos},
    )


def _governance_stamp(revision: _ModeloRevision) -> RevisionGovernanceStamp:
    """Project the revision's declared governance scalars."""
    return RevisionGovernanceStamp(
        review_status=revision.review_status,
        engineered_by=revision.engineered_by,
        reviewed_by=revision.reviewed_by,
        reviewed_at=revision.reviewed_at,
    )


def _capability_facts(revision: _ModeloRevision, *, modelo_id: str) -> RevisionCapabilityFacts:
    """Fold what THIS revision declares, through the support authority's own probe.

    The capability predicates come from
    :func:`~domain.calculations.registry.revision_capability_probe` rather than
    being recomputed here, so a conformance row and the canonical support row
    cannot disagree about the same revision. Only the declaration counts below
    are conformance-local.
    """
    capabilities = _revision_capability_probe(revision, modelo_id=modelo_id)
    return RevisionCapabilityFacts(
        calc_grade=capabilities.calc_grade,
        has_completeness_manifest=capabilities.has_completeness_manifest,
        has_fixed_width_export=capabilities.has_fixed_width_export,
        has_xml_dictionary_export=capabilities.has_xml_dictionary_export,
        extraction_profile_count=capabilities.extraction_profile_count,
        casilla_count=len(revision.casillas),
        formula_count=len(revision.formulas),
        binding_count=len(revision.bindings),
        verification_expectation_count=len(revision.verification_expectations),
        support_removal_decision_count=len(revision.support_removal_decisions),
        live_cross_reference_count=len(revision.live_cross_references),
        casilla_continuidad_evolution_count=len(revision.casilla_continuidad_evolutions),
    )


def _support_probe(entry: _ModeloEntry, *, revision_id: str) -> LatestRevisionSupportProbe:
    """Project the modelo-level support entry, naming the revision it probed."""
    return LatestRevisionSupportProbe(
        probed_revision=entry.latest_revision_id,
        describes_this_revision=entry.latest_revision_id == revision_id,
        calc_grade=entry.calc_grade,
        has_completeness_manifest=entry.has_completeness_manifest,
        has_fixed_width_export=entry.has_fixed_width_export,
        has_xml_dictionary_export=entry.has_xml_dictionary_export,
        has_extractor=entry.has_extractor,
        rename_count=len(entry.renames),
        deprecation_count=len(entry.deprecations),
        portal_compatibility_ref_count=len(entry.portal_compatibility_refs),
        is_deprecated=entry.is_deprecated,
    )


def _model_law_coverage(ledger: _ModelLawCoverageLedger) -> RevisionModelLawCoverage:
    """Split one coverage ledger's gates into satisfied, gap, and mandatory-gap tiers.

    The three locals are annotated because a generator comprehension widens the
    tier ``Literal`` back to ``str``, and the strict row models would then refuse
    a value the ledger already typed exactly.
    """
    satisfied: tuple[_EvidenceTier, ...] = tuple(gate.tier for gate in ledger.gates if gate.status == "satisfied")
    gaps: tuple[_EvidenceTier, ...] = tuple(gate.tier for gate in ledger.gates if gate.status == "gap")
    required_gaps: tuple[_RequiredCoverageTier, ...] = tuple(tier for tier in _REQUIRED_COVERAGE_TIERS if tier in gaps)
    return RevisionModelLawCoverage(
        satisfied_tiers=satisfied,
        gap_tiers=gaps,
        required_tier_gaps=required_gaps,
    )


def _diagnostics_for(diagnostics: Sequence[str], *, modelo: str, revision: str) -> tuple[str, ...]:
    """Select the registry-scope diagnostics that name this exact modelo and revision.

    The scope validator prefixes a per-revision diagnostic with
    ``modelo <id> revision <id>: ``. A diagnostic that carries no such prefix
    belongs to no single row and is preserved on the envelope instead, because a
    dropped diagnostic is indistinguishable from a clean tree.
    """
    prefix = f"modelo {modelo} revision {revision}: "
    return tuple(diagnostic for diagnostic in diagnostics if diagnostic.startswith(prefix))
