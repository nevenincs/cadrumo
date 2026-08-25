"""Closure-limb projection for exact filing layouts and verified official bytes.

Filing capability is stricter than a revision merely declaring a layout.  The
law-selected revision must admit a filing-grade snapshot, and each materialised
layout must retain a layout-authority source whose bundled bytes still match the
source catalogue.  The :class:`RegistryAuthorityGrade` boundary and this
module report those facts without creating a second export authoring path.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field, computed_field, model_validator

from ...core import REVIEWED_REVISION_REVIEW_STATUSES, STRICT_FROZEN_CONFIG, RegistryAuthorityGrade
from ...domain.calculations.registry import (
    RegistrySnapshotError,
    RegistryValidationError,
    SourceReference,
    ValidatedRegistryAuthority,
    coverage_assessment_horizon,
    revision_selection_coordinates,
    verify_source_file,
)
from ._closure import (
    RegistryClosureEvidence,
    RegistryClosureLimb,
    RegistryClosureOwnerDisposition,
    RegistryClosureRefusal,
    RegistryClosureRefusalReason,
)
from ._filing_export_authority import (
    FilingExportProof,
    FilingExportProofAuthority,
    FilingExportProofConflictError,
)

__all__ = [
    "FilingExportCoverageReport",
    "compose_filing_export_coverage",
]


class FilingExportCoverageReport(BaseModel):
    """Complete filing-layout projection for one validated registry authority."""

    model_config = STRICT_FROZEN_CONFIG

    limbs: tuple[RegistryClosureLimb, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_one_filing_limb_per_revision(self) -> FilingExportCoverageReport:
        coordinates = tuple((limb.modelo, limb.revision) for limb in self.limbs)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("filing-export coverage requires one limb per registry revision")
        if any(limb.name != "filing_export" for limb in self.limbs):
            raise ValueError("filing-export coverage may contain only filing-export limbs")
        return self

    @computed_field
    @property
    def fully_satisfied(self) -> bool:
        """Return whether every participating revision has filing-capable byte evidence."""
        return all(limb.outcome in {"satisfied", "not_applicable"} for limb in self.limbs)

    @computed_field
    @property
    def unsatisfied_limbs(self) -> tuple[RegistryClosureLimb, ...]:
        """Return every filing participant that lacks required export evidence."""
        return tuple(limb for limb in self.limbs if limb.outcome not in {"satisfied", "not_applicable"})


def compose_filing_export_coverage(
    *,
    authority: ValidatedRegistryAuthority,
    proof_authority: FilingExportProofAuthority | None = None,
) -> FilingExportCoverageReport:
    """Compose filing-layout evidence from validated law-selected snapshots.

    A revision below filing grade is a deliberate non-filing capability and is
    retained as such.  A filing-grade revision is selected without a revision-id
    override, admitted through the filing snapshot boundary, and then checked
    against the byte-exact official layout sources its materialised layouts cite.
    """
    authority.validate_registry()
    limbs = tuple(
        _compose_revision_limb(
            authority=authority,
            proof_authority=proof_authority,
            modelo_id=modelo.id,
            revision=revision,
        )
        for modelo in sorted(authority.modelos, key=lambda item: item.id)
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id)
    )
    return FilingExportCoverageReport(limbs=limbs)


def _compose_revision_limb(
    *,
    authority: ValidatedRegistryAuthority,
    proof_authority: FilingExportProofAuthority | None,
    modelo_id: str,
    revision,
) -> RegistryClosureLimb:
    """Build one retained filing-export limb from its declared revision scope."""
    if revision.authority_grade is not RegistryAuthorityGrade.FILING:
        return RegistryClosureLimb(
            modelo=modelo_id,
            revision=revision.id,
            name="filing_export",
            outcome="not_applicable",
        )
    if revision.review_status not in REVIEWED_REVISION_REVIEW_STATUSES:
        return _refused_limb(
            modelo_id=modelo_id,
            revision_id=revision.id,
            reason="unreviewed_evidence",
            detail="filing-grade snapshots require a reviewed revision",
            work_item="aeat-export-fragment-generator-authority:reviewed-layout",
            reconsideration_condition="Record a valid review for the exact revision and its official layout authority.",
        )
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    coordinates = revision_selection_coordinates(revision, assessment_horizon=assessment_horizon)
    snapshots = []
    evidence_by_locator: dict[tuple[str, str], RegistryClosureEvidence] = {}
    expected_layout_ids: tuple[str, ...] | None = None
    for filing_year, period in coordinates:
        try:
            snapshot = authority.snapshot(
                modelo_id,
                filing_year=filing_year,
                period=period,
                grade=RegistryAuthorityGrade.FILING,
            )
        except (RegistrySnapshotError, RegistryValidationError) as exc:
            return _refused_limb(
                modelo_id=modelo_id,
                revision_id=revision.id,
                reason="missing_evidence",
                detail=f"{filing_year}/{period}: {_failure_detail(exc)}",
                work_item="aeat-export-fragment-generator-authority:filing-layout",
                reconsideration_condition=(
                    "Supply the exact official layout evidence required by the filing snapshot boundary."
                ),
            )
        if snapshot.revision.id != revision.id:
            return _refused_limb(
                modelo_id=modelo_id,
                revision_id=revision.id,
                reason="cross_limb_disagreement",
                detail=(
                    f"{filing_year}/{period}: filing snapshot selected revision {snapshot.revision.id!r} instead "
                    f"of the registered revision {revision.id!r}"
                ),
                work_item="registry-temporal-coverage:law-selection",
                reconsideration_condition=(
                    "Reconcile the filing snapshot selection with the revision's declared temporal scope."
                ),
            )
        layout_ids = tuple(layout.id for layout in snapshot.revision.export_layouts)
        if expected_layout_ids is not None and layout_ids != expected_layout_ids:
            return _refused_limb(
                modelo_id=modelo_id,
                revision_id=revision.id,
                reason="cross_limb_disagreement",
                detail=f"{filing_year}/{period}: filing snapshot changed materialised export layout ids",
                work_item="registry-temporal-coverage:law-selection",
                reconsideration_condition=(
                    "Split the revision at the exact layout boundary before asserting one export proof."
                ),
            )
        expected_layout_ids = layout_ids
        evidence, evidence_failure = _layout_byte_evidence(authority=authority, snapshot=snapshot)
        if evidence_failure is not None:
            return _refused_limb(
                modelo_id=modelo_id,
                revision_id=revision.id,
                reason=evidence_failure.reason,
                detail=f"{filing_year}/{period}: {evidence_failure.detail}",
                work_item="aeat-export-fragment-generator-authority:official-layout-evidence",
                reconsideration_condition=(
                    "Restore byte-exact official layout evidence for every emitted filing layout."
                ),
            )
        evidence_by_locator.update({(item.authority, item.locator): item for item in evidence})
        snapshots.append(snapshot)
    snapshot = snapshots[0]
    evidence = tuple(evidence_by_locator.values())
    proof, proof_failure = _filing_export_proof(
        proof_authority=proof_authority,
        snapshot=snapshot,
    )
    if proof_failure is not None:
        return _refused_limb(
            modelo_id=modelo_id,
            revision_id=revision.id,
            reason=proof_failure.reason,
            detail=proof_failure.detail,
            work_item="aeat-export-fragment-generator-authority:production-emission-proof",
            reconsideration_condition=(
                "Verify the canonical generation manifest against the current semantic map and render profile, "
                "then record successful production emitted-byte evidence."
            ),
        )
    assert proof is not None
    evidence = (*evidence, *_proof_evidence(proof))
    return RegistryClosureLimb(
        modelo=modelo_id,
        revision=revision.id,
        name="filing_export",
        outcome="satisfied",
        evidence=evidence,
    )


def _layout_byte_evidence(
    *,
    authority: ValidatedRegistryAuthority,
    snapshot,
) -> tuple[tuple[RegistryClosureEvidence, ...], _LayoutEvidenceFailure | None]:
    """Recheck every materialised layout's official source bytes.

    Registry validation proves the declaration shape.  This live check proves
    the current corpus bytes still equal the immutable digest that declaration
    cites, so a cached registry authority cannot turn a later binary mismatch
    into a filing-capable closure result.
    """
    sources: list[SourceReference] = []
    for layout in snapshot.revision.export_layouts:
        layout_sources = tuple(
            snapshot.sources[source_ref]
            for source_ref in layout.source_refs
            if source_ref in snapshot.sources and snapshot.sources[source_ref].evidence_tier == "layout_authority"
        )
        if not layout_sources:
            return (), _LayoutEvidenceFailure(
                reason="missing_evidence",
                detail=f"materialised layout {layout.id!r} has no layout-authority source in the validated snapshot",
            )
        sources.extend(layout_sources)
    evidence: list[RegistryClosureEvidence] = []
    for source in sorted({source.id: source for source in sources}.values(), key=lambda item: item.id):
        try:
            verify_source_file(authority.source_root, source)
        except RegistryValidationError as exc:
            return (), _LayoutEvidenceFailure(reason="stale_evidence", detail=_failure_detail(exc))
        evidence.append(
            RegistryClosureEvidence(
                authority=f"{source.authority}:{source.kind}:{source.id}",
                locator=f"{source.corpus_path}#sha256={source.sha256}",
            ),
        )
    return tuple(evidence), None


def _filing_export_proof(
    *,
    proof_authority: FilingExportProofAuthority | None,
    snapshot,
) -> tuple[FilingExportProof | None, _LayoutEvidenceFailure | None]:
    """Require one exact canonical-generation and production-emission proof."""
    if proof_authority is None:
        return None, _LayoutEvidenceFailure(
            reason="missing_evidence",
            detail="no canonical generation and production emitted-byte proof authority was supplied",
        )
    layout_ids = tuple(layout.id for layout in snapshot.revision.export_layouts)
    try:
        proof = proof_authority.proof_for(
            modelo=snapshot.modelo.id,
            revision=snapshot.revision.id,
            layout_ids=layout_ids,
        )
    except FilingExportProofConflictError as exc:
        return None, _LayoutEvidenceFailure(reason="conflicting_evidence", detail=_failure_detail(exc))
    except (OSError, RuntimeError, ValueError) as exc:
        return None, _LayoutEvidenceFailure(reason="stale_evidence", detail=_failure_detail(exc))
    if proof is None:
        return None, _LayoutEvidenceFailure(
            reason="missing_evidence",
            detail="canonical generation or successful production emitted-byte evidence is absent",
        )
    if proof.modelo != snapshot.modelo.id or proof.revision != snapshot.revision.id or proof.layout_ids != layout_ids:
        return None, _LayoutEvidenceFailure(
            reason="conflicting_evidence",
            detail="filing export proof identity does not match the law-selected registry snapshot",
        )
    return proof, None


def _proof_evidence(proof: FilingExportProof) -> tuple[RegistryClosureEvidence, ...]:
    """Project both independent proof authorities into the closure evidence spine."""
    return (
        RegistryClosureEvidence(
            authority=proof.generation.authority,
            locator=(
                f"{proof.generation.manifest_locator}#sha256={proof.generation.manifest_sha256}"
                f";semantic={proof.generation.semantic_map_sha256}"
                f";render={proof.generation.render_profile_sha256}"
                f";loader={proof.generation.loader_semantic_sha256}"
            ),
        ),
        RegistryClosureEvidence(
            authority=proof.emission.authority,
            locator=(
                f"{proof.emission.evidence_locator}#payload-sha256={proof.emission.payload_sha256}"
                f";bytes={proof.emission.emitted_bytes}"
                f";checked-offsets={proof.emission.checked_official_offsets}"
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class _LayoutEvidenceFailure:
    """One typed internal failure while checking live layout-source bytes."""

    reason: RegistryClosureRefusalReason
    detail: str


def _refused_limb(
    *,
    modelo_id: str,
    revision_id: str,
    reason: RegistryClosureRefusalReason,
    detail: str,
    work_item: str,
    reconsideration_condition: str,
) -> RegistryClosureLimb:
    """Return one accountable filing-export refusal."""
    return RegistryClosureLimb(
        modelo=modelo_id,
        revision=revision_id,
        name="filing_export",
        outcome="refused",
        refusal=RegistryClosureRefusal(
            reason=reason,
            detail=detail,
            disposition=RegistryClosureOwnerDisposition(
                limb="filing_export",
                state="owned",
                owner="aeat-export-fragment-generator-authority",
                work_item=work_item,
                reconsideration_condition=reconsideration_condition,
            ),
        ),
    )


def _failure_detail(error: Exception) -> str:
    """Keep a source or snapshot refusal stable for report consumers."""
    return str(error).splitlines()[0][:500]
