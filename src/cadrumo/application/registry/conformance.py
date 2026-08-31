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
AEAT's own published figures, NOT that it is correct. The quantity is derived
from the canonical registry grounding projection in
:mod:`~cadrumo.domain.calculations.registry.external_grounding`.

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
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ...core import NON_REGISTRY_MODELOS as _NON_REGISTRY_MODELOS
from ...core import REVIEWED_REVISION_REVIEW_STATUSES as _REVIEWED_REVISION_REVIEW_STATUSES
from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN_CONFIG
from ...core import ActionEvidenceProvenance, NoRecoveryOutcome
from ...core import CasillaId as _CasillaId
from ...core import ExportLayoutFormat as _ExportLayoutFormat
from ...core import Modelo as _Modelo
from ...core import RevisionReviewStatus as _RevisionReviewStatus
from ...core.access_gate import ModeloAuthorization as _ModeloAuthorization
from ...core.resources import bundled_path as _bundled_path
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority as _ValidatedRegistryAuthority
from ...domain.calculations.registry.classification_coherence import DeclaredAxisUsage as _DeclaredAxisUsage
from ...domain.calculations.registry.classification_coherence import ModeloClassificationRow as _ModeloClassificationRow
from ...domain.calculations.registry.classification_coherence import (
    RegistryClassificationAudit as _RegistryClassificationAudit,
)
from ...domain.calculations.registry.classification_coherence import (
    build_classification_coherence_audit as _build_classification_coherence_audit,
)
from ...domain.calculations.registry.coverage import REQUIRED_COVERAGE_TIERS as _REQUIRED_COVERAGE_TIERS
from ...domain.calculations.registry.coverage import ConstructEvidenceLedger as _ConstructEvidenceLedger
from ...domain.calculations.registry.coverage import ConstructEvidenceRow as _ConstructEvidenceRow
from ...domain.calculations.registry.coverage import EvidenceTierCoverageGate as _EvidenceTierCoverageGate
from ...domain.calculations.registry.coverage import ModelLawCoverageLedger as _ModelLawCoverageLedger
from ...domain.calculations.registry.coverage import RegistryConstructEvidenceAudit as _RegistryConstructEvidenceAudit
from ...domain.calculations.registry.coverage import RegistryCoverageAudit as _RegistryCoverageAudit
from ...domain.calculations.registry.coverage import RequiredCoverageTier as _RequiredCoverageTier
from ...domain.calculations.registry.coverage import (
    audit_registry_construct_evidence as _audit_registry_construct_evidence,
)
from ...domain.calculations.registry.coverage import (
    audit_registry_model_law_coverage as _audit_registry_model_law_coverage,
)
from ...domain.calculations.registry.errors import RegistryValidationError as _RegistryValidationError
from ...domain.calculations.registry.export import (
    derive_export_layouts_from_bindings as _derive_export_layouts_from_bindings,
)
from ...domain.calculations.registry.export_parse import xml_dictionary_entries as _xml_dictionary_entries
from ...domain.calculations.registry.external_grounding import (
    RegistryExternalGroundingAudit as _RegistryExternalGroundingAudit,
)
from ...domain.calculations.registry.external_grounding import (
    RevisionExternalGroundingRow as _RevisionExternalGroundingRow,
)
from ...domain.calculations.registry.external_grounding import UnattributedOraclePayload as _UnattributedOraclePayload
from ...domain.calculations.registry.external_grounding import (
    build_external_grounding_audit as _build_external_grounding_audit,
)
from ...domain.calculations.registry.external_grounding import (
    load_bundled_external_oracle_inventory as _load_bundled_external_oracle_inventory,
)
from ...domain.calculations.registry.ids import BindingId as _BindingId
from ...domain.calculations.registry.ids import FormulaId as _FormulaId
from ...domain.calculations.registry.ids import LegalRefId as _LegalRefId
from ...domain.calculations.registry.ids import ModeloId as _ModeloId
from ...domain.calculations.registry.ids import RelationId as _RelationId
from ...domain.calculations.registry.ids import RevisionId as _RevisionId
from ...domain.calculations.registry.ids import SourceRefId as _SourceRefId
from ...domain.calculations.registry.loader import load_registry_tree as _load_registry_tree
from ...domain.calculations.registry.schema import ModeloDefinition as _ModeloDefinition
from ...domain.calculations.registry.schema import ModeloRevision as _ModeloRevision
from ...domain.calculations.registry.schema import RegistrySnapshot as _RegistrySnapshot
from ...domain.calculations.registry.schema_base import EvidenceTier as _EvidenceTier
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition as _ExportLayoutDefinition
from ...domain.calculations.registry.schema_input_kind import InputKind as _InputKind
from ...domain.calculations.registry.schema_references import SourceReference as _SourceReference
from ...domain.calculations.registry.support_matrix import ModeloEntry as _ModeloEntry
from ...domain.calculations.registry.support_matrix import build_support_matrix as _build_support_matrix
from ...domain.calculations.registry.support_matrix import revision_capability_probe as _revision_capability_probe
from ...domain.calculations.registry.validate_registry_scope import validate_registry_scope as _validate_registry_scope
from .errors import RegistryPreconditionCondition, registry_terminal_refusal

__all__ = [
    "AnnualCasillaPopulationComparison",
    "CoverageAuthorityScope",
    "DictionaryLayoutCasillaComparison",
    "LatestRevisionSupportProbe",
    "RegistryConformanceProfile",
    "RevisionCapabilityFacts",
    "RevisionCasillaProducerTrace",
    "RevisionConformanceRow",
    "RevisionConstructEvidence",
    "RevisionGovernanceStamp",
    "RevisionModelLawCoverage",
    "audit_bundled_registry_conformance",
    "build_registry_conformance_profile",
    "compare_annual_casilla_population",
    "compare_annual_casilla_population_for_revision",
]


class ConformanceModel(BaseModel):
    """Strict frozen base for composed conformance facts."""

    model_config = _STRICT_FROZEN_CONFIG


type _MeasurementStatus = Literal["measured", "unsupported", "unmeasured"]

# The coverage audit can inspect every revision without giving every revision
# filing authority.  Keep that distinction on the application projection so a
# renderer cannot infer filing-grade scope merely because a ledger is present.
type CoverageAuthorityScope = Literal["filing", "inspection_only"]
type RevisionCoverageAuthorityScope = Literal["filing", "inspection_only", "mixed"]

_XML_DICTIONARY_PARSER_ATTRIBUTES = ("field_id", "path", "data_type", "casilla_id")
_UNMEASURED_DICTIONARY_ATTRIBUTES = ("label", "data_type", "number", "segmento")


class DictionaryLayoutCasillaComparison(ConformanceModel):
    """One year-specific comparison against one declared export layout.

    The measured population is the set of non-internal registry casilla
    identities versus the set of non-null ``casilla_id`` values returned by
    :func:`xml_dictionary_entries`.  It is deliberately named a dictionary
    comparison: those identities are not asserted to be the printed-form
    population.

    ``unsupported`` means the source kind is known but this bounded
    comparator has no parser for it. ``unmeasured`` means the source contract
    was not available to run (for example, an unresolved source or omitted
    source root). Neither status is a zero or a clean result.
    """

    layout_id: str
    layout_format: str
    identity_measurement: _MeasurementStatus
    registry_casilla_count: int = Field(ge=0)
    registry_internal_only_count: int = Field(ge=0)
    printed_form_membership: _MeasurementStatus
    xsd_only_attributes: _MeasurementStatus
    dictionary_source_ref: str | None = None
    dictionary_entry_count: int | None = Field(default=None, ge=0)
    dictionary_casilla_count: int | None = Field(default=None, ge=0)
    missing_casilla_ids: tuple[str, ...] = ()
    extra_casilla_ids: tuple[str, ...] = ()
    parser_exposed_attributes: tuple[str, ...] = ()
    unmeasured_attributes: tuple[str, ...] = ()
    diagnostic: str | None = None

    @property
    def identity_divergence_count(self) -> int:
        """Number of missing or extra identities for this layout."""
        return len(self.missing_casilla_ids) + len(self.extra_casilla_ids)


class AnnualCasillaPopulationComparison(ConformanceModel):
    """Year-specific casilla/layout evidence for one authority-selected read.

    The caller supplies a filing :class:`RegistrySnapshot`, or -- from a static
    compiler consumer, whose non-filing revision projection must not reach this
    boundary -- the coordinate and compiled revision as explicit values.  This
    function never selects a latest or largest revision and never compares two
    annual revisions to one another.

    ``printed_form_membership`` is intentionally not derived from dictionary
    identities.  A declared BOE/form source is visible as ``unsupported``
    until an existing form parser contract can measure it.  Likewise,
    ``xsd_only_attributes`` stays ``unsupported`` when an XSD source is
    declared because the XML dictionary parser exposes no XSD-attribute
    mapping contract.
    """

    modelo: _ModeloId
    filing_year: int = Field(ge=2000, le=2099)
    period: str
    law_selected_revision: _RevisionId
    identity_measurement: _MeasurementStatus
    printed_form_membership: _MeasurementStatus
    xsd_only_attributes: _MeasurementStatus
    layout_comparisons: tuple[DictionaryLayoutCasillaComparison, ...]
    printed_form_source_refs: tuple[str, ...] = ()
    xsd_source_refs: tuple[str, ...] = ()
    authority_scope: CoverageAuthorityScope = "filing"

    @property
    def missing_casilla_ids(self) -> tuple[str, ...]:
        """Union of missing identities across the measured layouts."""
        return tuple(
            sorted(
                {casilla_id for comparison in self.layout_comparisons for casilla_id in comparison.missing_casilla_ids},
            ),
        )

    @property
    def extra_casilla_ids(self) -> tuple[str, ...]:
        """Union of extra identities across the measured layouts."""
        return tuple(
            sorted(
                {casilla_id for comparison in self.layout_comparisons for casilla_id in comparison.extra_casilla_ids},
            ),
        )

    @property
    def identity_divergence_count(self) -> int:
        """Total per-layout missing/extra identity findings."""
        return sum(comparison.identity_divergence_count for comparison in self.layout_comparisons)


@dataclass(frozen=True)
class _AnnualPopulationContext:
    """Selected revision facts shared by filing and inspection comparisons."""

    revision: _ModeloRevision
    layouts: tuple[_ExportLayoutDefinition, ...]
    modelo: _ModeloId
    filing_year: int
    period: str
    sources: Mapping[str, _SourceReference]
    authority_scope: CoverageAuthorityScope


def compare_annual_casilla_population(
    snapshot: _RegistrySnapshot,
    *,
    source_root: Path | None = None,
) -> AnnualCasillaPopulationComparison:
    """Compare one law-selected filing snapshot to its declared XML dictionaries.

    A filing snapshot carries its temporal boundary, its selected revision and
    its declared export layouts directly, so nothing else need be supplied.

    Static compiler consumers, which read through a non-filing revision
    projection rather than a snapshot, call
    :func:`compare_annual_casilla_population_for_revision` and pass that
    projection's facts explicitly. That split is deliberate: inspection
    authority is static-only and must not reach an application boundary, so
    this module names no inspection type and the dependency direction is
    inverted rather than the boundary census being widened to admit one.

    The identity comparison delegates source reading to the existing
    :func:`xml_dictionary_entries` parser.  It compares unique non-null
    dictionary ``casilla_id`` values with non-internal registry casilla ids;
    dictionary rows without an id and duplicate field rows remain reflected
    by ``dictionary_entry_count`` but are not fabricated into identities.

    Args:
        snapshot: Validated filing snapshot for one ``modelo``/year/period.
        source_root: Repository root containing the bundled official source
            corpus.  Omitting it leaves dictionary measurement explicitly
            ``unmeasured`` because the parser cannot resolve its source.
    """
    return _compare_annual_population(
        _AnnualPopulationContext(
            revision=snapshot.revision,
            layouts=snapshot.revision.export_layouts,
            modelo=snapshot.modelo.id,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
            sources=snapshot.sources,
            authority_scope="filing",
        ),
        source_root=source_root,
    )


def compare_annual_casilla_population_for_revision(
    *,
    modelo: _ModeloId,
    revision: _ModeloRevision,
    filing_year: int,
    period: str,
    sources: Mapping[str, _SourceReference],
    source_root: Path | None = None,
) -> AnnualCasillaPopulationComparison:
    """Compare an explicitly-supplied revision read to its XML dictionaries.

    The entry point for static compiler consumers. Their revision projection
    retains no filing context and exposes no export layouts, so the coordinate
    and the already-selected compiled revision arrive as values from the same
    ``ValidatedRegistryAuthority``. Layouts are projected from the revision's
    bindings; no second selector or snapshot is constructed here.
    """
    return _compare_annual_population(
        _AnnualPopulationContext(
            revision=revision,
            layouts=_derive_export_layouts_from_bindings(revision),
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            sources=sources,
            authority_scope="inspection_only",
        ),
        source_root=source_root,
    )


def _compare_annual_population(
    selected: _AnnualPopulationContext,
    *,
    source_root: Path | None,
) -> AnnualCasillaPopulationComparison:

    registry_casillas = tuple(casilla for casilla in selected.revision.casillas if not casilla.internal_only)
    registry_ids = frozenset(str(casilla.id) for casilla in registry_casillas)
    form_source_refs = _source_refs_of_kind(selected.revision.source_refs, selected.sources, "form_spec")
    xsd_source_refs = _source_refs_of_kind(selected.revision.source_refs, selected.sources, "xsd")
    printed_form_status = _source_status(form_source_refs)
    xsd_status = _source_status(xsd_source_refs)

    comparisons = tuple(
        _compare_dictionary_layout(
            layout,
            registry_ids=registry_ids,
            registry_internal_only_count=len(selected.revision.casillas) - len(registry_casillas),
            printed_form_status=printed_form_status,
            xsd_status=xsd_status,
            sources=selected.sources,
            source_root=source_root,
        )
        for layout in selected.layouts
    )
    return AnnualCasillaPopulationComparison(
        modelo=selected.modelo,
        filing_year=selected.filing_year,
        period=selected.period,
        law_selected_revision=selected.revision.id,
        identity_measurement=_fold_measurement_status(
            tuple(comparison.identity_measurement for comparison in comparisons),
        ),
        printed_form_membership=printed_form_status,
        xsd_only_attributes=xsd_status,
        layout_comparisons=comparisons,
        printed_form_source_refs=form_source_refs,
        xsd_source_refs=xsd_source_refs,
        authority_scope=selected.authority_scope,
    )


def _compare_dictionary_layout(
    layout: _ExportLayoutDefinition,
    *,
    registry_ids: frozenset[str],
    registry_internal_only_count: int,
    printed_form_status: _MeasurementStatus,
    xsd_status: _MeasurementStatus,
    sources: Mapping[str, _SourceReference],
    source_root: Path | None,
) -> DictionaryLayoutCasillaComparison:
    """Measure one layout, keeping unsupported and unavailable sources visible."""
    source_ref = None if layout.dictionary_source_ref is None else str(layout.dictionary_source_ref)
    base: dict[str, object] = {
        "layout_id": str(layout.id),
        "layout_format": layout.format.value,
        "registry_casilla_count": len(registry_ids),
        "registry_internal_only_count": registry_internal_only_count,
        "printed_form_membership": printed_form_status,
        "xsd_only_attributes": xsd_status,
        "dictionary_source_ref": source_ref,
    }

    def measured(**fields: object) -> DictionaryLayoutCasillaComparison:
        return DictionaryLayoutCasillaComparison.model_validate({**base, **fields})

    if layout.format is not _ExportLayoutFormat.XML_DICTIONARY:
        return measured(
            identity_measurement="unsupported",
            diagnostic="dictionary comparator supports only xml_dictionary layouts",
        )
    if layout.dictionary_source_ref is None:
        return measured(
            identity_measurement="unmeasured",
            diagnostic="xml_dictionary layout has no dictionary source reference",
        )
    try:
        entries = _xml_dictionary_entries(
            layout,
            source_root=source_root,
            sources=sources,
        )
    except (_RegistryValidationError, OSError) as exc:
        return measured(
            identity_measurement="unmeasured",
            parser_exposed_attributes=_XML_DICTIONARY_PARSER_ATTRIBUTES,
            unmeasured_attributes=_UNMEASURED_DICTIONARY_ATTRIBUTES,
            diagnostic=f"{type(exc).__name__}: {exc}",
        )

    dictionary_ids = frozenset(str(entry.casilla_id) for entry in entries if entry.casilla_id is not None)
    return measured(
        identity_measurement="measured",
        dictionary_entry_count=len(entries),
        dictionary_casilla_count=len(dictionary_ids),
        missing_casilla_ids=tuple(sorted(registry_ids - dictionary_ids)),
        extra_casilla_ids=tuple(sorted(dictionary_ids - registry_ids)),
        parser_exposed_attributes=_XML_DICTIONARY_PARSER_ATTRIBUTES,
        unmeasured_attributes=_UNMEASURED_DICTIONARY_ATTRIBUTES,
    )


def _source_refs_of_kind(
    source_refs: Sequence[str],
    sources: Mapping[str, _SourceReference],
    kind: str,
) -> tuple[str, ...]:
    """Return resolved source ids of one declared kind in declaration order."""
    return tuple(
        source_ref
        for source_ref in (str(item) for item in source_refs)
        if (source := sources.get(source_ref)) is not None and source.kind == kind
    )


def _source_status(source_refs: Sequence[str]) -> _MeasurementStatus:
    """Classify a declared-but-unparsed official surface explicitly."""
    return "unsupported" if source_refs else "unmeasured"


def _fold_measurement_status(statuses: Sequence[_MeasurementStatus]) -> _MeasurementStatus:
    """Fold per-layout status without treating an empty set as measured."""
    if "measured" in statuses:
        return "measured"
    if "unsupported" in statuses:
        return "unsupported"
    return "unmeasured"


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
        portal_compatibility_ref_count: Declared AEAT-portal cross-references.
    """

    probed_revision: _RevisionId
    describes_this_revision: bool
    calc_grade: bool
    has_completeness_manifest: bool
    has_fixed_width_export: bool
    has_xml_dictionary_export: bool
    has_extractor: bool
    rename_count: int = Field(ge=0)
    portal_compatibility_ref_count: int = Field(ge=0)


class RevisionModelLawCoverage(ConformanceModel):
    """Evidence-tier coverage for one revision, split by whether the tier is mandatory.

    Legal authority, official source guidance, and layout authority are
    mandatory for a filing-scope ledger: the registry cannot be filing-grade
    without them, so a gap on one is a failure. Inspection-only ledgers retain
    every measured gate and gap for discovery, but their gaps are not filing-
    grade failures. Executable parity is reported rather than required,
    because no official safe calculator or formula workbook exists for many
    revisions. Collapsing the two kinds of gap into one count would make an
    expected absence look like a defect.

    Attributes:
        satisfied_tiers: Evidence tiers backed by at least one registry
            reference.
        gap_tiers: Evidence tiers with no supporting reference at all.
        required_tier_gaps: Filing-grade mandatory gaps. Empty for an
            inspection-only ledger even when ``gap_tiers`` remains non-empty.
        authority_scope: Whether the ledger was built from filing authority or
            from a non-filing inspection projection.
    """

    satisfied_tiers: tuple[_EvidenceTier, ...]
    gap_tiers: tuple[_EvidenceTier, ...]
    required_tier_gaps: tuple[_RequiredCoverageTier, ...]
    authority_scope: RevisionCoverageAuthorityScope = "filing"
    coordinates: tuple[tuple[int, str], ...] = Field(min_length=1)

    @property
    def filing_eligible(self) -> bool:
        """Whether this coverage ledger may contribute filing-grade gaps."""
        return self.authority_scope == "filing"

    @property
    def has_required_gap(self) -> bool:
        """Whether a filing-scope ledger has an unbacked mandatory tier."""
        return self.filing_eligible and bool(self.required_tier_gaps)


class RevisionConstructEvidence(ConformanceModel):
    """Construct-level evidence, kept separate from revision evidence floors.

    Inspection-only rows deliberately retain their incomplete construct rows so
    the ledger remains a real, non-vacuous discovery surface.  Consumers that
    need filing-grade defects must use :attr:`filing_gaps`; :attr:`gaps` keeps
    the complete measured population visible.
    """

    ledger: _ConstructEvidenceLedger

    @property
    def authority_scope(self) -> RevisionCoverageAuthorityScope:
        """Return the authority scope declared by the underlying ledger."""
        return self.ledger.authority_scope

    @property
    def filing_eligible(self) -> bool:
        """Whether this construct ledger may contribute filing-grade gaps."""
        return self.ledger.filing_eligible

    @property
    def rows(self) -> tuple[_ConstructEvidenceRow, ...]:
        """Return the exact formula/parameter/binding/relation/selector rows."""
        return self.ledger.rows

    @property
    def gaps(self) -> tuple[_ConstructEvidenceRow, ...]:
        """Return every unresolved or unmeasured construct row.

        This intentionally includes inspection-only rows.  Use
        :attr:`filing_gaps` for the strict filing-grade subset.
        """
        return self.ledger.gaps

    @property
    def filing_gaps(self) -> tuple[_ConstructEvidenceRow, ...]:
        """Return construct gaps from filing-scope ledgers only."""
        return self.ledger.filing_gaps

    @property
    def inspection_gaps(self) -> tuple[_ConstructEvidenceRow, ...]:
        """Return incomplete construct rows retained for inspection only."""
        return self.ledger.gaps if not self.filing_eligible else ()


class RevisionCasillaProducerTrace(ConformanceModel):
    """Compact per-casilla producer trace projected from the validated schema."""

    casilla_id: _CasillaId
    input_kind: _InputKind
    producer_kind: Literal["formula", "manual", "upstream", "relation", "informational", "projection_only"]
    reason: str = Field(min_length=1, max_length=1024)
    formula_id: _FormulaId | None = None
    binding_id: _BindingId | None = None
    relation_id: _RelationId | None = None
    casilla_legal_refs: tuple[_LegalRefId, ...]
    casilla_source_refs: tuple[_SourceRefId, ...]
    producer_legal_refs: tuple[_LegalRefId, ...]
    producer_source_refs: tuple[_SourceRefId, ...]


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
        construct_evidence: Construct-level legal/source evidence, or
            :data:`None` when the degraded read could not build validated
            construct ledgers.
        casilla_provenance: Per-casilla producer traces projected from the
            revision schema. The row remains stamped by ``registry_validated``.
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
    construct_evidence: RevisionConstructEvidence | None = None
    casilla_provenance: tuple[RevisionCasillaProducerTrace, ...] = ()
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
        counts: dict[_RevisionReviewStatus, int] = {status: 0 for status in _RevisionReviewStatus}
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
    def construct_evidence_gap_rows(self) -> tuple[RevisionConformanceRow, ...]:
        """Rows with filing-grade construct evidence gaps.

        Inspection-only gaps stay available through each row's
        ``construct_evidence.gaps`` and through
        :attr:`construct_evidence_inspection_gap_rows`; they do not contribute
        to this filing-grade counter.
        """
        return tuple(
            row for row in self.rows if row.construct_evidence is not None and row.construct_evidence.filing_gaps
        )

    @property
    def construct_evidence_inspection_gap_rows(self) -> tuple[RevisionConformanceRow, ...]:
        """Rows retaining incomplete construct evidence for inspection only."""
        return tuple(
            row for row in self.rows if row.construct_evidence is not None and row.construct_evidence.inspection_gaps
        )

    @property
    def construct_evidence_unmeasured_rows(self) -> tuple[RevisionConformanceRow, ...]:
        """Rows whose validated construct evidence axis was not measured."""
        return tuple(row for row in self.rows if row.construct_evidence is None)

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
    coverage_ledgers: Mapping[tuple[_ModeloId, _RevisionId], tuple[_ModelLawCoverageLedger, ...]]
    construct_evidence_ledgers: Mapping[tuple[_ModeloId, _RevisionId], _ConstructEvidenceLedger]
    support_entries: Mapping[_ModeloId, _ModeloEntry]

    @classmethod
    def build(
        cls,
        *,
        external_grounding: _RegistryExternalGroundingAudit,
        classification: _RegistryClassificationAudit,
        model_law_coverage: _RegistryCoverageAudit | None,
        construct_evidence: _RegistryConstructEvidenceAudit | None,
        support_matrix: Sequence[_ModeloEntry] | None,
    ) -> _AxisIndex:
        """Key each supplied axis by the identity the row fold joins on."""
        return cls(
            grounding_rows={(row.modelo, row.revision): row for row in external_grounding.rows},
            classification_rows={row.modelo: row for row in classification.rows},
            coverage_ledgers=({} if model_law_coverage is None else model_law_coverage.ledgers_by_revision),
            construct_evidence_ledgers=(
                {}
                if construct_evidence is None
                else {(ledger.modelo, ledger.revision): ledger for ledger in construct_evidence.ledgers}
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
            raise registry_terminal_refusal(
                condition=RegistryPreconditionCondition.CONFORMANCE_CLASSIFICATION_ROW_PRESENT,
                context={"modelo": modelo_id},
                facts={"modelo": str(modelo_id), "classification_row_present": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.SAFETY,
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
            raise registry_terminal_refusal(
                condition=RegistryPreconditionCondition.CONFORMANCE_GROUNDING_ROW_PRESENT,
                context={"modelo": modelo_id, "revision_id": revision_id},
                facts={
                    "modelo": str(modelo_id),
                    "revision_id": str(revision_id),
                    "grounding_row_present": False,
                },
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                outcome=NoRecoveryOutcome.SAFETY,
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
    construct_evidence_ledgers: Mapping[tuple[_ModeloId, _RevisionId], _ConstructEvidenceLedger],
) -> RevisionConformanceRow:
    """Compose one revision's row from every axis.

    An axis the caller could not supply lands as :data:`None` rather than a
    zeroed value, so a row distinguishes "measured absent" from "not measured".

    The grounding row is resolved FIRST so a revision the audit omits is
    refused before any other axis is computed for it.
    """
    grounding_row = index.require_grounding_row(modelo_id, revision.id)
    ledgers = index.coverage_ledgers.get((modelo_id, revision.id))
    construct_ledger = construct_evidence_ledgers.get((modelo_id, revision.id))
    return RevisionConformanceRow(
        modelo=modelo_id,
        revision=revision.id,
        registry_validated=registry_validated,
        governance=_governance_stamp(revision),
        capabilities=_capability_facts(revision, modelo_id=modelo_id),
        latest_revision_support=(
            None if support_entry is None else _support_probe(support_entry, revision_id=revision.id)
        ),
        model_law_coverage=None if ledgers is None else _model_law_coverage(ledgers),
        construct_evidence=None if construct_ledger is None else RevisionConstructEvidence(ledger=construct_ledger),
        casilla_provenance=_casilla_producer_traces(revision),
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
    construct_evidence: _RegistryConstructEvidenceAudit | None = None,
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
        construct_evidence: Validated construct-level legal/source audit, or
            :data:`None` when the caller could not build validated snapshots.
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
        construct_evidence=construct_evidence,
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
                construct_evidence_ledgers=index.construct_evidence_ledgers,
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
        model_law_coverage=_audit_registry_model_law_coverage(authority),
        construct_evidence=_audit_registry_construct_evidence(authority),
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
        live_cross_reference_count=len(revision.live_cross_references),
        casilla_continuidad_evolution_count=len(revision.casilla_continuidad_evolutions),
    )


def _support_probe(entry: _ModeloEntry, *, revision_id: _RevisionId) -> LatestRevisionSupportProbe:
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
        portal_compatibility_ref_count=len(entry.portal_compatibility_refs),
    )


def _casilla_producer_traces(revision: _ModeloRevision) -> tuple[RevisionCasillaProducerTrace, ...]:
    """Project the revision's typed producer inventory without flattening traces."""
    inventory = revision.producer_inventory()
    projected: list[RevisionCasillaProducerTrace] = []
    for casilla in sorted(revision.casillas, key=lambda item: item.id):
        for trace in inventory.producer_provenance_by_casilla[casilla.id]:
            projected.append(
                RevisionCasillaProducerTrace(
                    casilla_id=trace.casilla.id,
                    input_kind=trace.casilla.input_kind,
                    producer_kind=trace.producer_kind,
                    reason=trace.reason,
                    formula_id=None if trace.formula is None else trace.formula.id,
                    binding_id=None if trace.binding is None else trace.binding.id,
                    relation_id=None if trace.relation is None else trace.relation.id,
                    casilla_legal_refs=trace.casilla.legal_refs,
                    casilla_source_refs=trace.casilla.source_refs,
                    producer_legal_refs=trace.producer_legal_refs,
                    producer_source_refs=trace.producer_source_refs,
                ),
            )
    return tuple(projected)


def _model_law_coverage(ledgers: tuple[_ModelLawCoverageLedger, ...]) -> RevisionModelLawCoverage:
    """Aggregate every coverage cell into one visible revision projection.

    The three locals are annotated because a generator comprehension widens the
    tier ``Literal`` back to ``str``, and the strict row models would then refuse
    a value the ledger already typed exactly.

    Inspection-only ledgers keep their complete ``gap_tiers`` population, but
    mandatory gaps are only projected into ``required_tier_gaps`` for a
    filing-scope ledger.  This leaves discovery evidence visible without turning
    a non-filing inspection read into a filing-grade defect.
    """
    if not ledgers:
        raise _RegistryValidationError("revision model-law coverage requires at least one selector coordinate")
    gates_by_tier: dict[_EvidenceTier, tuple[_EvidenceTierCoverageGate, ...]] = {
        tier: tuple(next(gate for gate in ledger.gates if gate.tier == tier) for ledger in ledgers)
        for tier in (*_REQUIRED_COVERAGE_TIERS, "executable_parity_evidence")
    }
    satisfied: tuple[_EvidenceTier, ...] = tuple(
        tier for tier, gates in gates_by_tier.items() if all(gate.status == "satisfied" for gate in gates)
    )
    gaps: tuple[_EvidenceTier, ...] = tuple(
        tier for tier, gates in gates_by_tier.items() if any(gate.status == "gap" for gate in gates)
    )
    required_gaps: tuple[_RequiredCoverageTier, ...] = tuple(
        tier
        for tier in _REQUIRED_COVERAGE_TIERS
        if any(
            ledger.filing_eligible and next(gate for gate in ledger.gates if gate.tier == tier).status == "gap"
            for ledger in ledgers
        )
    )
    scopes: set[RevisionCoverageAuthorityScope] = {ledger.authority_scope for ledger in ledgers}
    authority_scope: RevisionCoverageAuthorityScope = next(iter(scopes)) if len(scopes) == 1 else "mixed"
    return RevisionModelLawCoverage(
        satisfied_tiers=satisfied,
        gap_tiers=gaps,
        required_tier_gaps=required_gaps,
        authority_scope=authority_scope,
        coordinates=tuple((ledger.filing_year, ledger.period) for ledger in ledgers),
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
