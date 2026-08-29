"""Coverage ledgers for registry authority, verification tiers and schema families.

Audits every :class:`ModeloDefinition` and :class:`ModeloRevision` in the
registry for the four mandatory evidence tiers (legal authority, official
source guidance, executable parity, and layout authority). Each revision is
examined through the typed authority projection appropriate to its canonical
review state: filing-grade revisions use a :class:`RegistrySnapshot`, while
review-ineligible revisions use :class:`RegistryRevisionInspection` so
static/audit evidence remains available without claiming filing authority.

Three axes, deliberately not one
---------------------------------

This module now answers three different questions about a revision, and they
are easy to mistake for each other because all three sound like "is it
complete".

* **Evidence tier** — what BACKS the content. Is there a legal authority, an
  official source, a parity artefact, a layout authority. Governed by
  :data:`REQUIRED_COVERAGE_TIERS` and reported per tier.
* **Authority scope** — which PROJECTION the ledger was built from, filing or
  inspection-only. A property of how the audit reached the revision, not of the
  revision's content.
* **Schema family disposition** — whether the CONTENT ITSELF is there, and if
  not, whether anybody said why. Reported per family by
  :class:`RevisionCoverageManifest`.

A revision can hold a full casilla family with no legal authority backing it,
and it can carry impeccable legal authority over an empty formula family. The
first is an evidence-tier gap; the second is a family disposition. Collapsing
them would let either mask the other, which is the specific failure the family
axis exists to remove — a revision reads complete because nothing distinguishes
"this modelo computes nothing" from "nobody built the formulas yet".

The family manifest is deliberately narrower than the tier audit in what it
touches: it projects one :class:`ModeloRevision` and nothing else. It does not
build a snapshot, does not consult review state, and does not reduce a revision
to a representative filing year. That independence is why it reports on every
revision in the corpus rather than on the empty set of review-eligible ones, and
it is why the manifest lives in its own module: this one builds validated
snapshots and so sits ABOVE registry-build validation, while the manifest is
consumed BY that validation. Housing both here inverted the dependency.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Literal

from pydantic import Field, PrivateAttr, computed_field, model_validator

from ....core import RegistryAuthorityGrade, RegistrySelectorPeriodCode, RevisionReviewStatus
from ....core.filing_year import FilingYear
from ._schema_family_coverage import (
    CoverageModel,
)
from ._snapshot_internals import check_snapshot_filing_review_tier
from .authority import ValidatedRegistryAuthority
from .errors import AmbiguousRevisionSelectionError, RegistryValidationError
from .ids import BindingId, CrossReferenceId, LegalRefId, SourceRefId, WorkbookParityRefId
from .schema import (
    DataBindingDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistrySnapshot,
)
from .schema_base import EvidenceTier
from .schema_formula import ParameterDefinition
from .schema_references import SourceReference
from .schema_surfaces import RelationDefinition
from .schema_verification import LiveCrossReferenceDecision, WorkbookParityReference
from .static_inspection import RegistryRevisionInspection
from .temporal import coverage_assessment_horizon, revision_selection_coordinates

CoverageGateStatus = Literal["satisfied", "gap"]
CoverageAuthorityScope = Literal["filing", "inspection_only", "mixed"]
RequiredCoverageTier = Literal["legal_authority", "official_source_guidance", "layout_authority"]

REQUIRED_COVERAGE_TIERS: tuple[RequiredCoverageTier, ...] = (
    "legal_authority",
    "official_source_guidance",
    "layout_authority",
)
"""The evidence tiers a revision cannot be filing-grade without.

Public because the distinction is load-bearing outside this module too: a gap on
one of these is a failure, while a gap on ``executable_parity_evidence`` is a
reported absence, and a consumer that cannot tell them apart reports an expected
absence as a defect.
"""


class EvidenceTierCoverageGate(CoverageModel):
    """Coverage state for one evidence tier."""

    tier: EvidenceTier
    status: CoverageGateStatus
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    workbook_refs: tuple[WorkbookParityRefId, ...] = ()
    cross_reference_refs: tuple[CrossReferenceId, ...] = ()
    detail: str

    @model_validator(mode="after")
    def _validate_status_matches_evidence(self) -> EvidenceTierCoverageGate:
        has_evidence = bool(
            self.legal_refs or self.source_refs or self.workbook_refs or self.cross_reference_refs,
        )
        if self.status == "satisfied" and not has_evidence:
            raise RegistryValidationError(f"{self.tier} coverage cannot be satisfied without evidence refs")
        if self.status == "gap" and has_evidence:
            raise RegistryValidationError(f"{self.tier} coverage gap cannot carry evidence refs")
        return self


class ModelLawCoverageLedger(CoverageModel):
    """One law-selected coverage cell for legal, source, parity, and layout evidence."""

    modelo: str
    revision: str
    filing_year: FilingYear
    period: RegistrySelectorPeriodCode
    gates: tuple[EvidenceTierCoverageGate, ...]
    authority_scope: CoverageAuthorityScope = "filing"
    authority_fallback_reason: str | None = Field(default=None, min_length=1, max_length=512)
    """Why a REVIEW-eligible revision was still measured through inspection.

    Review state and filing capability are different conditions, and the fold
    tests only the first. A reviewed revision can still be unable to produce a
    filing-grade snapshot, and without this field that outcome is indistinguishable
    from a revision nobody reviewed: both read ``inspection_only``.
    """

    authority_review_tier: RevisionReviewStatus | None = None
    """Which review standard established a ``filing`` scope, or None when inspection-only.

    Agent review is sufficient to reach the filing fold, so ``authority_scope``
    alone no longer says what backs the ledger. A reader who sees ``filing``
    without this field would infer a human signoff that may never have happened.
    It is the WEAKEST tier in the chain: the revision's own status, downgraded to
    agent review if any legal reference it cites rests on agent review.
    """

    @property
    def filing_eligible(self) -> bool:
        """Whether this ledger was built from filing-grade snapshot authority."""
        return self.authority_scope == "filing"

    @property
    def gaps(self) -> tuple[EvidenceTierCoverageGate, ...]:
        """Return :class:`EvidenceTierCoverageGate` entries that have no supporting registry evidence."""
        return tuple(gate for gate in self.gates if gate.status == "gap")


class RegistryCoverageAudit(CoverageModel):
    """Audit result for model-law coverage across the committed registry."""

    ledgers: tuple[ModelLawCoverageLedger, ...]
    required_gate_failures: tuple[str, ...]
    executable_parity_gaps: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether every mandatory model-law evidence tier is covered."""
        return not self.required_gate_failures

    @property
    def ledgers_by_revision(self) -> Mapping[tuple[str, str], tuple[ModelLawCoverageLedger, ...]]:
        """Group the full cell matrix without discarding later selector coordinates.

        Callers that render one revision row must consume this aggregate rather
        than indexing :attr:`ledgers` by ``(modelo, revision)`` directly.  The
        latter would retain an arbitrary final coordinate and recreate the
        representative-coordinate defect this matrix removes.
        """
        grouped: dict[tuple[str, str], list[ModelLawCoverageLedger]] = {}
        for ledger in self.ledgers:
            grouped.setdefault((ledger.modelo, ledger.revision), []).append(ledger)
        return {
            key: tuple(sorted(value, key=lambda ledger: (ledger.filing_year, ledger.period)))
            for key, value in grouped.items()
        }


ConstructEvidenceKind = Literal["formula", "parameter", "binding", "relation", "selector"]
ConstructEvidenceStatus = Literal["grounded", "inherited", "unresolved", "unmeasured", "unvalidated"]

_COMPLETE_REFS_REQUIRED_BY_STATUS: Mapping[ConstructEvidenceStatus, str] = {
    "grounded": "grounded construct evidence requires legal and source refs",
    "inherited": "inherited selector evidence requires owning binding refs",
    "unvalidated": "unvalidated construct evidence requires declared legal and source refs",
}
"""Statuses that claim complete evidence, mapped to their refusal when it is absent.

A status absent from this mapping makes no completeness claim, so its refs are
governed by the forbidding checks instead.
"""

_AUTHORITY_CHECKED_STATUSES: frozenset[ConstructEvidenceStatus] = frozenset({"grounded", "inherited"})
"""Statuses that may only be reached through the validated audit fold."""


class _AuthorityCheckProof:
    """Proof held only by the validated audit fold, naming the tier that backs it.

    The instances are module-private and enumerated in
    :data:`_AUTHORITY_CHECK_PROOFS`; membership is tested by identity, so no
    caller outside this module can forge one. Carrying ``review_tier`` is what
    keeps the claim honest now that agent review suffices to reach the fold: a
    reader of the ledger learns which standard established the authority rather
    than inferring a human signoff that may not have happened.
    """

    __slots__ = ("review_tier",)

    def __init__(self, review_tier: RevisionReviewStatus) -> None:
        self.review_tier = review_tier


_AGENT_REVIEWED_PROOF = _AuthorityCheckProof(RevisionReviewStatus.AGENT_REVIEWED)
_OPERATOR_REVIEWED_PROOF = _AuthorityCheckProof(RevisionReviewStatus.OPERATOR_REVIEWED)

#: Every proof this module may issue. Identity membership is the forgery guard.
_AUTHORITY_CHECK_PROOFS: frozenset[_AuthorityCheckProof] = frozenset(
    {_AGENT_REVIEWED_PROOF, _OPERATOR_REVIEWED_PROOF},
)

_PROOF_BY_TIER: dict[RevisionReviewStatus, _AuthorityCheckProof] = {
    RevisionReviewStatus.AGENT_REVIEWED: _AGENT_REVIEWED_PROOF,
    RevisionReviewStatus.OPERATOR_REVIEWED: _OPERATOR_REVIEWED_PROOF,
}


class ConstructEvidenceRow(CoverageModel):
    """Legal/source evidence for one revision-level calculation construct.

    A selector is a typed child of a binding and has no independent legal/source
    fields in the registry schema. Its row therefore carries the owning binding
    references with ``status='inherited'`` and says so in ``reason``. This keeps
    the selector visible without turning binding evidence into an independent
    selector claim.
    """

    kind: ConstructEvidenceKind
    construct_id: str = Field(min_length=1, max_length=160)
    binding_id: BindingId | None = None
    status: ConstructEvidenceStatus
    legal_refs: tuple[LegalRefId, ...] = ()
    source_refs: tuple[SourceRefId, ...] = ()
    reason: str = Field(min_length=1, max_length=1024)
    _authority_proof: _AuthorityCheckProof | None = PrivateAttr(default=None)

    @computed_field
    @property
    def authority_checked(self) -> bool:
        """Return whether this row was created through the validated audit fold."""
        return self._authority_proof in _AUTHORITY_CHECK_PROOFS

    @model_validator(mode="after")
    def _validate_evidence_shape(self) -> ConstructEvidenceRow:
        self._validate_binding_identity()
        has_legal = bool(self.legal_refs)
        has_source = bool(self.source_refs)
        self._validate_claimed_evidence(complete_refs=has_legal and has_source)
        self._validate_withheld_evidence(has_legal=has_legal, has_source=has_source)
        return self

    def _validate_binding_identity(self) -> None:
        """Refuse a row whose ``binding_id`` does not match its selector kind."""
        if self.kind != "selector":
            if self.binding_id is not None:
                raise RegistryValidationError("only selector evidence rows may declare binding_id")
            return
        if self.binding_id is None:
            raise RegistryValidationError("selector evidence rows must identify their owning binding")
        if self.construct_id != self.binding_id:
            raise RegistryValidationError("selector evidence construct_id must equal binding_id")

    def _validate_claimed_evidence(self, *, complete_refs: bool) -> None:
        """Refuse a status claiming evidence it does not carry or was not authorised to claim."""
        if self.status == "inherited" and self.kind != "selector":
            raise RegistryValidationError("only selector evidence may be inherited")
        incomplete_refusal = _COMPLETE_REFS_REQUIRED_BY_STATUS.get(self.status)
        if incomplete_refusal is not None and not complete_refs:
            raise RegistryValidationError(incomplete_refusal)
        if self.status in _AUTHORITY_CHECKED_STATUSES and not self.authority_checked:
            raise RegistryValidationError(
                "complete construct evidence requires an authority-checked registry validation boundary",
            )

    def _validate_withheld_evidence(self, *, has_legal: bool, has_source: bool) -> None:
        """Refuse a status disclaiming evidence while carrying more refs than it may."""
        if self.status == "unresolved" and has_legal and has_source:
            raise RegistryValidationError("unresolved construct evidence cannot carry complete refs")
        if self.status == "unmeasured" and (has_legal or has_source):
            raise RegistryValidationError("unmeasured construct evidence cannot carry refs")


class ConstructEvidenceLedger(CoverageModel):
    """Per-modelo/revision construct evidence rows, separate from casilla floors."""

    modelo: str
    revision: str
    rows: tuple[ConstructEvidenceRow, ...]
    authority_scope: CoverageAuthorityScope = "filing"
    authority_fallback_reason: str | None = Field(default=None, min_length=1, max_length=512)

    @property
    def filing_eligible(self) -> bool:
        """Whether this ledger was built from filing-grade snapshot authority."""
        return self.authority_scope == "filing"

    @property
    def reviewed_but_not_filing_capable(self) -> bool:
        """Whether a reviewed revision fell back because it cannot produce a filing.

        Distinguishes a revision whose review passed but whose filing capability
        refused from one nobody reviewed. Both read ``inspection_only`` scope, and
        without this the two are indistinguishable.
        """
        return self.authority_fallback_reason is not None

    @model_validator(mode="after")
    def _rows_are_unique(self) -> ConstructEvidenceLedger:
        coordinates = [(row.kind, row.construct_id) for row in self.rows]
        if len(coordinates) != len(set(coordinates)):
            raise RegistryValidationError("construct evidence rows must have unique kind/id coordinates")
        return self

    @property
    def gaps(self) -> tuple[ConstructEvidenceRow, ...]:
        """Return construct rows whose own or inherited evidence is incomplete."""
        return tuple(row for row in self.rows if row.status in {"unresolved", "unmeasured", "unvalidated"})

    @property
    def filing_gaps(self) -> tuple[ConstructEvidenceRow, ...]:
        """Return construct gaps that belong to a filing-grade ledger."""
        return self.gaps if self.filing_eligible else ()


class RegistryConstructEvidenceAudit(CoverageModel):
    """Registry-wide construct evidence audit with an explicit finite denominator."""

    ledgers: tuple[ConstructEvidenceLedger, ...]

    @property
    def gaps(self) -> tuple[ConstructEvidenceRow, ...]:
        """Return all unresolved, unmeasured, or unvalidated construct rows."""
        return tuple(row for ledger in self.ledgers for row in ledger.gaps)

    @property
    def filing_gaps(self) -> tuple[ConstructEvidenceRow, ...]:
        """Return only construct gaps from filing-grade ledgers."""
        return tuple(row for ledger in self.ledgers for row in ledger.filing_gaps)

    @property
    def inspection_gaps(self) -> tuple[ConstructEvidenceRow, ...]:
        """Return incomplete construct evidence retained from inspection ledgers."""
        return tuple(row for ledger in self.ledgers if not ledger.filing_eligible for row in ledger.gaps)

    @property
    def ok(self) -> bool:
        """Return whether every filing-grade construct has complete evidence."""
        return not self.filing_gaps


def audit_registry_model_law_coverage(
    authority: ValidatedRegistryAuthority,
) -> RegistryCoverageAudit:
    """Return the full derived coverage matrix from validated authority.

    Every ledger is one ``(modelo, revision, filing_year, period)`` cell. The
    canonical selector is re-run without an injected revision id for every
    declared coordinate through the registry's supported-year horizon. An old
    source or layout therefore cannot make an open selector's later years
    invisible behind a revision-level summary.
    """
    authority.validate_registry()
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    ledgers: list[ModelLawCoverageLedger] = []
    required_gate_failures: list[str] = []
    executable_parity_gaps: list[str] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            for filing_year, period in revision_selection_coordinates(
                revision,
                assessment_horizon=assessment_horizon,
            ):
                ledger = _model_law_coverage_for_coordinate(
                    authority=authority,
                    modelo=modelo,
                    revision=revision,
                    filing_year=filing_year,
                    period=period,
                )
                ledgers.append(ledger)
                required_failures, parity_gaps = _model_law_coverage_findings(modelo, revision, ledger)
                required_gate_failures.extend(required_failures)
                executable_parity_gaps.extend(parity_gaps)
    return RegistryCoverageAudit(
        ledgers=tuple(ledgers),
        required_gate_failures=tuple(required_gate_failures),
        executable_parity_gaps=tuple(executable_parity_gaps),
    )


def _inspect_declared_revision(
    authority: ValidatedRegistryAuthority,
    *,
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    filing_year: int,
    period: RegistrySelectorPeriodCode,
) -> RegistryRevisionInspection:
    """Inspect the revision an audit is iterating, dating the ask where a year is shared.

    A revision whose validity starts or ends INSIDE a filing year shares that
    year with its neighbour, and where both declare the same period token the
    undated question genuinely has two right answers. Modelo 308 is the live
    case: its January-to-June and July-to-December eras both declare AD-HOC, and
    refusing an undated 2011 request is the ADJUDICATED behaviour, asserted by
    that modelo's own selector regression -- not a defect for an audit to report.

    An audit's real question is narrower than the one it asks, being "does THIS
    revision cover this coordinate", so it re-asks with a date the revision
    itself owns. A revision spanning the whole filing year has no such
    neighbour and the ambiguity stays a hard failure.
    """
    try:
        return authority.inspect_revision(modelo.id, filing_year=filing_year, period=period)
    except AmbiguousRevisionSelectionError:
        year_start, year_end = date(filing_year, 1, 1), date(filing_year, 12, 31)
        spans_whole_year = revision.valid_from <= year_start and (
            revision.valid_to is None or revision.valid_to >= year_end
        )
        if spans_whole_year:
            raise
        on = max(revision.valid_from, year_start)
        if revision.valid_to is not None:
            on = min(on, revision.valid_to)
        return authority.inspect_revision(
            modelo.id,
            filing_year=filing_year,
            period=period,
            on=on,
        )


def _model_law_coverage_for_coordinate(
    *,
    authority: ValidatedRegistryAuthority,
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    filing_year: int,
    period: RegistrySelectorPeriodCode,
) -> ModelLawCoverageLedger:
    """Build one cell from the law-selected inspection or filing snapshot."""
    inspection = _inspect_declared_revision(
        authority,
        modelo=modelo,
        revision=revision,
        filing_year=filing_year,
        period=period,
    )
    if inspection.revision_id != revision.id:
        raise RegistryValidationError(
            f"coverage coordinate {modelo.id}/{filing_year}/{period} selected revision "
            f"{inspection.revision_id!r} instead of declared revision {revision.id!r}",
        )
    proof = _snapshot_filing_review_proof(modelo, revision, authority, inspection)
    if proof is not None and revision.effective_authority_grade is RegistryAuthorityGrade.FILING:
        try:
            snapshot = authority.snapshot(
                modelo.id,
                filing_year=filing_year,
                period=period,
                grade=revision.effective_authority_grade,
            )
        except RegistryValidationError as capability_refusal:
            return build_model_law_coverage_ledger(
                inspection,
                filing_year=filing_year,
                period=period,
                _fallback_reason=str(capability_refusal).splitlines()[0][:512],
            )
        return build_model_law_coverage_ledger(
            snapshot,
            filing_year=filing_year,
            period=period,
            _authority_proof=proof,
        )
    return build_model_law_coverage_ledger(inspection, filing_year=filing_year, period=period)


def _model_law_coverage_findings(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    ledger: ModelLawCoverageLedger,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Project mandatory and executable-parity findings for one ledger."""
    gates = {gate.tier: gate for gate in ledger.gates}
    required_failures = tuple(
        f"modelo {modelo.id} revision {revision.id}: {tier} coverage gap"
        for tier in REQUIRED_COVERAGE_TIERS
        if gates[tier].status == "gap"
    )
    parity_gaps = (
        (f"modelo {modelo.id} revision {revision.id}: executable_parity_evidence coverage gap",)
        if gates["executable_parity_evidence"].status == "gap" and revision.formulas
        else ()
    )
    return required_failures, parity_gaps


def audit_registry_construct_evidence(
    authority: ValidatedRegistryAuthority,
) -> RegistryConstructEvidenceAudit:
    """Build construct evidence ledgers from the validated registry authority.

    Construct declarations are revision-level, so this report retains one row
    per revision.  Its filing-capability probe nevertheless traverses every
    law-selected coordinate through the same coverage horizon: no first
    coordinate may bless an open selector's later cells.
    """
    authority.validate_registry()
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    ledgers: list[ConstructEvidenceLedger] = []
    for modelo in sorted(authority.modelos, key=lambda item: item.id):
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id):
            coordinates = revision_selection_coordinates(revision, assessment_horizon=assessment_horizon)
            inspections = tuple(
                _inspect_declared_revision(
                    authority,
                    modelo=modelo,
                    revision=revision,
                    filing_year=filing_year,
                    period=period,
                )
                for filing_year, period in coordinates
            )
            for (filing_year, period), inspection in zip(coordinates, inspections, strict=True):
                if inspection.revision_id != revision.id:
                    raise RegistryValidationError(
                        f"construct-evidence coordinate {modelo.id}/{filing_year}/{period} selected revision "
                        f"{inspection.revision_id!r} instead of declared revision {revision.id!r}",
                    )
            inspection = inspections[0]
            proof = _snapshot_filing_review_proof(modelo, revision, authority, inspection)
            if proof is not None and revision.effective_authority_grade is RegistryAuthorityGrade.FILING:
                try:
                    snapshots = tuple(
                        authority.snapshot(
                            modelo.id,
                            filing_year=filing_year,
                            period=period,
                            grade=revision.effective_authority_grade,
                        )
                        for filing_year, period in coordinates
                    )
                except RegistryValidationError as capability_refusal:
                    # Reviewed, but not filing-CAPABLE -- exactly the condition the
                    # sibling model-law audit above already catches and records.
                    # This call site made the same request unguarded, so reviewing a
                    # revision that declares no export layout aborted the whole
                    # corpus audit with a filing-capability refusal. An
                    # applicability-grade revision could therefore never be
                    # reviewed: stamping it broke the registry load rather than
                    # producing a ledger. Review state and filing capability are
                    # different conditions, and the proof above tests only the
                    # first.
                    ledgers.append(
                        _build_construct_evidence_ledger(
                            inspection,
                            authority_proof=None,
                            fallback_reason=str(capability_refusal).splitlines()[0][:512],
                        ),
                    )
                else:
                    ledgers.append(
                        _build_construct_evidence_ledger(
                            snapshots[0],
                            authority_proof=proof,
                        ),
                    )
            else:
                ledgers.append(_build_construct_evidence_ledger(inspection, authority_proof=None))
    return RegistryConstructEvidenceAudit(ledgers=tuple(ledgers))


def build_model_law_coverage_ledger(
    authority: RegistrySnapshot | RegistryRevisionInspection,
    *,
    filing_year: int | None = None,
    period: RegistrySelectorPeriodCode | None = None,
    _authority_proof: _AuthorityCheckProof | None = None,
    _fallback_reason: str | None = None,
) -> ModelLawCoverageLedger:
    """Build the four-tier coverage ledger for one typed registry authority.

    Args:
        authority: Filing-grade :class:`RegistrySnapshot` or non-filing
            :class:`RegistryRevisionInspection` to assess for model-law coverage.
        filing_year: The law-selected filing year for an inspection projection.
            A snapshot supplies its own coordinate and rejects a conflict.
        period: The canonical selector token for an inspection projection.
            A snapshot supplies its own coordinate and rejects a conflict.
        _authority_proof: Private marker supplied only by the validated
            registry-wide audit. A hand-built or otherwise unproven snapshot
            remains inspection-only even though its shape is a
            :class:`RegistrySnapshot`.

    Returns:
        A :class:`ModelLawCoverageLedger` summarising coverage across all evidence tiers.
    """
    if isinstance(authority, RegistrySnapshot):
        modelo_id = authority.modelo.id
        revision_id = authority.revision.id
        if filing_year is not None and filing_year != authority.filing_year:
            raise RegistryValidationError("coverage ledger filing_year must match its snapshot")
        if period is not None and period != authority.period:
            raise RegistryValidationError("coverage ledger period must match its snapshot")
        resolved_filing_year = authority.filing_year
        resolved_period = authority.period
        legal_refs: Iterable[LegalRefId] = authority.legal
        sources: Mapping[SourceRefId, SourceReference] = authority.sources
        workbook_parity_refs: Iterable[WorkbookParityReference] = authority.workbook_parity_refs.values()
        live_cross_references: Iterable[LiveCrossReferenceDecision] = authority.live_cross_references.values()
        proven = _authority_proof if _authority_proof in _AUTHORITY_CHECK_PROOFS else None
        authority_scope: CoverageAuthorityScope = "filing" if proven is not None else "inspection_only"
        review_tier = proven.review_tier if proven is not None else None
    else:
        modelo_id = authority.modelo_id
        revision_id = authority.revision_id
        if filing_year is None or period is None:
            raise RegistryValidationError("inspection coverage ledger requires its law-selected filing coordinate")
        resolved_filing_year = filing_year
        resolved_period = period
        legal_refs = authority.legal_ref_ids
        sources = authority.sources
        workbook_parity_refs = authority.workbook_parity_refs
        live_cross_references = authority.live_cross_references
        authority_scope = "inspection_only"
        review_tier = None

    return ModelLawCoverageLedger(
        modelo=modelo_id,
        revision=revision_id,
        filing_year=resolved_filing_year,
        period=resolved_period,
        gates=(
            _legal_authority_gate(legal_refs),
            _source_guidance_gate(
                sources,
                live_cross_references,
            ),
            _executable_parity_gate(
                sources,
                workbook_parity_refs,
                live_cross_references,
            ),
            _layout_authority_gate(
                sources,
                workbook_parity_refs,
                live_cross_references,
            ),
        ),
        authority_scope=authority_scope,
        authority_review_tier=review_tier,
        authority_fallback_reason=_fallback_reason,
    )


def build_construct_evidence_ledger(
    snapshot: RegistrySnapshot,
) -> ConstructEvidenceLedger:
    """Build declared legal/source rows from a :class:`RegistrySnapshot`.

    Reads the snapshot's declarations as given, claiming no registry validation.
    """
    return _build_construct_evidence_ledger(snapshot, authority_proof=None)


def _construct_evidence_context(
    authority: RegistrySnapshot | RegistryRevisionInspection,
) -> tuple[str, str, ModeloRevision | RegistryRevisionInspection, CoverageAuthorityScope]:
    """Project the shared identity, declarations, and scope for one authority."""
    if isinstance(authority, RegistrySnapshot):
        return authority.modelo.id, authority.revision.id, authority.revision, "filing"
    return authority.modelo_id, authority.revision_id, authority, "inspection_only"


def _build_construct_evidence_ledger(
    authority: RegistrySnapshot | RegistryRevisionInspection,
    *,
    authority_proof: _AuthorityCheckProof | None,
    fallback_reason: str | None = None,
) -> ConstructEvidenceLedger:
    """Build construct rows, optionally under the private validated-audit proof.

    ``fallback_reason`` is set only when a REVIEWED revision was demoted to
    inspection scope because its filing capability refused, so the ledger keeps
    that apart from a revision nobody reviewed.
    """
    modelo_id, revision_id, revision, authority_scope = _construct_evidence_context(authority)
    rows: list[ConstructEvidenceRow] = []
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="formula", authority_proof=authority_proof)
        for declaration in revision.formulas
    )
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="parameter", authority_proof=authority_proof)
        for declaration in revision.parameters
    )
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="binding", authority_proof=authority_proof)
        for declaration in revision.bindings
    )
    rows.extend(
        _declared_construct_evidence_row(declaration, kind="relation", authority_proof=authority_proof)
        for declaration in revision.relations
    )

    for binding in revision.bindings:
        declared_status = _status_for_declared_refs(binding.legal_refs, binding.source_refs)
        authority_checked = authority_proof in _AUTHORITY_CHECK_PROOFS
        if declared_status == "grounded" and authority_checked:
            selector_status: ConstructEvidenceStatus = "inherited"
            reason = f"selector evidence is inherited from binding {binding.id!r}"
        elif declared_status == "grounded":
            selector_status = "unvalidated"
            reason = f"selector evidence has refs but no validated registry authority for binding {binding.id!r}"
        else:
            selector_status = declared_status
            reason = f"selector evidence cannot inherit complete refs from binding {binding.id!r}"
        rows.append(
            _construct_evidence_row(
                kind="selector",
                construct_id=binding.id,
                binding_id=binding.id,
                status=selector_status,
                legal_refs=tuple(binding.legal_refs),
                source_refs=tuple(binding.source_refs),
                reason=(f"authority-checked {reason}" if authority_checked else reason),
                authority_proof=authority_proof,
            ),
        )

    rows.sort(key=lambda row: (row.kind, row.construct_id))
    return ConstructEvidenceLedger(
        modelo=modelo_id,
        revision=revision_id,
        rows=tuple(rows),
        authority_scope=authority_scope,
        authority_fallback_reason=fallback_reason,
    )


def _declared_construct_evidence_row(
    declaration: FormulaDefinition | ParameterDefinition | DataBindingDefinition | RelationDefinition,
    *,
    kind: ConstructEvidenceKind,
    authority_proof: _AuthorityCheckProof | None,
) -> ConstructEvidenceRow:
    declared_status = _status_for_declared_refs(declaration.legal_refs, declaration.source_refs)
    authority_checked = authority_proof in _AUTHORITY_CHECK_PROOFS
    status: ConstructEvidenceStatus = (
        declared_status if authority_checked or declared_status != "grounded" else "unvalidated"
    )
    return _construct_evidence_row(
        kind=kind,
        construct_id=declaration.id,
        status=status,
        legal_refs=tuple(declaration.legal_refs),
        source_refs=tuple(declaration.source_refs),
        reason=(
            f"authority-checked {kind} declaration {declaration.id!r} carries its own legal/source refs"
            if authority_checked
            else f"{kind} declaration {declaration.id!r} carries its own legal/source refs"
        ),
        authority_proof=authority_proof,
    )


def _construct_evidence_row(
    *,
    kind: ConstructEvidenceKind,
    construct_id: str,
    binding_id: BindingId | None = None,
    status: ConstructEvidenceStatus,
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
    reason: str,
    authority_proof: _AuthorityCheckProof | None,
) -> ConstructEvidenceRow:
    """Create a row and attach the private proof only after shape validation."""
    if authority_proof not in _AUTHORITY_CHECK_PROOFS or status not in _AUTHORITY_CHECKED_STATUSES:
        return ConstructEvidenceRow(
            kind=kind,
            construct_id=construct_id,
            binding_id=binding_id,
            status=status,
            legal_refs=legal_refs,
            source_refs=source_refs,
            reason=reason,
        )

    unvalidated_row = ConstructEvidenceRow(
        kind=kind,
        construct_id=construct_id,
        binding_id=binding_id,
        status="unvalidated",
        legal_refs=legal_refs,
        source_refs=source_refs,
        reason=reason,
    )
    object.__setattr__(unvalidated_row, "status", status)
    object.__setattr__(unvalidated_row, "_authority_proof", authority_proof)
    return unvalidated_row


def _status_for_declared_refs(
    legal_refs: tuple[LegalRefId, ...],
    source_refs: tuple[SourceRefId, ...],
) -> Literal["grounded", "unresolved", "unmeasured"]:
    if legal_refs and source_refs:
        return "grounded"
    if legal_refs or source_refs:
        return "unresolved"
    return "unmeasured"


def _legal_authority_gate(legal_refs: Iterable[LegalRefId]) -> EvidenceTierCoverageGate:
    refs = tuple(sorted(legal_refs))
    return EvidenceTierCoverageGate(
        tier="legal_authority",
        status=_status(refs),
        legal_refs=refs,
        detail="BOE or other binding legal references for filing-grade calculation",
    )


def _source_guidance_gate(
    sources: Mapping[SourceRefId, SourceReference],
    live_cross_references: Iterable[LiveCrossReferenceDecision],
) -> EvidenceTierCoverageGate:
    source_refs = _sources_for_tier(sources, "official_source_guidance")
    cross_refs = _cross_refs_for_tier(live_cross_references, "official_source_guidance")
    return EvidenceTierCoverageGate(
        tier="official_source_guidance",
        status=_status(source_refs, cross_refs),
        source_refs=source_refs,
        cross_reference_refs=cross_refs,
        detail="AEAT instructions, manuals, or static official guidance that explain model behaviour",
    )


def _executable_parity_gate(
    sources: Mapping[SourceRefId, SourceReference],
    workbook_parity_refs: Iterable[WorkbookParityReference],
    live_cross_references: Iterable[LiveCrossReferenceDecision],
) -> EvidenceTierCoverageGate:
    source_refs = _sources_for_tier(sources, "executable_parity_evidence")
    workbook_refs = _workbook_refs_for_tier(
        sources,
        workbook_parity_refs,
        coverage_kinds=("formula_form",),
        tier="executable_parity_evidence",
    )
    cross_refs = _cross_refs_for_tier(live_cross_references, "executable_parity_evidence")
    return EvidenceTierCoverageGate(
        tier="executable_parity_evidence",
        status=_status(source_refs, workbook_refs, cross_refs),
        source_refs=source_refs,
        workbook_refs=workbook_refs,
        cross_reference_refs=cross_refs,
        detail="Safe executable parity from true formula workbooks or guarded AEAT live/help surfaces",
    )


def _layout_authority_gate(
    sources: Mapping[SourceRefId, SourceReference],
    workbook_parity_refs: Iterable[WorkbookParityReference],
    live_cross_references: Iterable[LiveCrossReferenceDecision],
) -> EvidenceTierCoverageGate:
    source_refs = _sources_for_tier(sources, "layout_authority")
    workbook_refs = _workbook_refs_for_tier(
        sources,
        workbook_parity_refs,
        coverage_kinds=("record_design_layout", "unsupported_binary_xls", "static_layout"),
        tier="layout_authority",
    )
    cross_refs = _cross_refs_for_tier(live_cross_references, "layout_authority")
    return EvidenceTierCoverageGate(
        tier="layout_authority",
        status=_status(source_refs, workbook_refs, cross_refs),
        source_refs=source_refs,
        workbook_refs=workbook_refs,
        cross_reference_refs=cross_refs,
        detail="AEAT record designs and file-layout artefacts for import/export verification",
    )


def _sources_for_tier(
    sources: Mapping[SourceRefId, SourceReference],
    tier: EvidenceTier,
) -> tuple[SourceRefId, ...]:
    return tuple(sorted(ref for ref, item in sources.items() if item.evidence_tier == tier))


def _cross_refs_for_tier(
    live_cross_references: Iterable[LiveCrossReferenceDecision],
    tier: EvidenceTier,
) -> tuple[CrossReferenceId, ...]:
    return tuple(sorted(ref.id for ref in live_cross_references if ref.evidence_tier == tier))


def _workbook_refs_for_tier(
    sources: Mapping[SourceRefId, SourceReference],
    workbook_parity_refs: Iterable[WorkbookParityReference],
    *,
    coverage_kinds: tuple[str, ...],
    tier: EvidenceTier,
) -> tuple[WorkbookParityRefId, ...]:
    return tuple(
        sorted(
            ref.id
            for ref in workbook_parity_refs
            if ref.formula_coverage in coverage_kinds and sources[ref.workbook_source].evidence_tier == tier
        ),
    )


def _status(*values: tuple[object, ...]) -> CoverageGateStatus:
    return "satisfied" if any(values) else "gap"


def _snapshot_filing_review_proof(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    authority: ValidatedRegistryAuthority,
    inspection: RegistryRevisionInspection,
) -> _AuthorityCheckProof | None:
    """Return snapshot-owned filing-review proof, or None when the check refuses."""
    try:
        tier = check_snapshot_filing_review_tier(
            modelo,
            revision,
            authority.catalogues,
            set(inspection.legal_ref_ids),
        )
    except RegistryValidationError:
        return None
    return _PROOF_BY_TIER[tier]
