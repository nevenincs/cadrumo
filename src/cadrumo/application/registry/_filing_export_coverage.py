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
    verify_source_file,
)
from ._closure import (
    RegistryClosureEvidence,
    RegistryClosureLimb,
    RegistryClosureOwnerDisposition,
    RegistryClosureRefusal,
    RegistryClosureRefusalReason,
)
from ._temporal_coverage import _law_selection_coordinate

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
        """Return whether every registered revision has filing-capable byte evidence."""
        return all(limb.outcome == "satisfied" for limb in self.limbs)

    @computed_field
    @property
    def unsatisfied_limbs(self) -> tuple[RegistryClosureLimb, ...]:
        """Return every visible non-filing-capable revision."""
        return tuple(limb for limb in self.limbs if limb.outcome != "satisfied")


def compose_filing_export_coverage(*, authority: ValidatedRegistryAuthority) -> FilingExportCoverageReport:
    """Compose filing-layout evidence from validated law-selected snapshots.

    A revision below filing grade is a deliberate non-filing capability and is
    retained as such.  A filing-grade revision is selected without a revision-id
    override, admitted through the filing snapshot boundary, and then checked
    against the byte-exact official layout sources its materialised layouts cite.
    """
    authority.validate_registry()
    limbs = tuple(
        _compose_revision_limb(authority=authority, modelo_id=modelo.id, revision=revision)
        for modelo in sorted(authority.modelos, key=lambda item: item.id)
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id)
    )
    return FilingExportCoverageReport(limbs=limbs)


def _compose_revision_limb(
    *,
    authority: ValidatedRegistryAuthority,
    modelo_id: str,
    revision,
) -> RegistryClosureLimb:
    """Build one retained filing-export limb from its declared revision scope."""
    if revision.authority_grade is not RegistryAuthorityGrade.FILING:
        return _refused_limb(
            modelo_id=modelo_id,
            revision_id=revision.id,
            reason="below_filing_grade",
            detail=(
                f"revision declares {revision.authority_grade.value if revision.authority_grade else 'no'} "
                "filing authority grade"
            ),
            work_item="registry-temporal-coverage:authority-grade",
            reconsideration_condition=(
                "Validate the revision at filing authority grade before claiming export capability."
            ),
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
    filing_year, period = _law_selection_coordinate(revision)
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
            detail=_failure_detail(exc),
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
                f"filing snapshot selected revision {snapshot.revision.id!r} instead of "
                f"the registered revision {revision.id!r}"
            ),
            work_item="registry-temporal-coverage:law-selection",
            reconsideration_condition=(
                "Reconcile the filing snapshot selection with the revision's declared temporal scope."
            ),
        )
    evidence, evidence_failure = _layout_byte_evidence(authority=authority, snapshot=snapshot)
    if evidence_failure is not None:
        return _refused_limb(
            modelo_id=modelo_id,
            revision_id=revision.id,
            reason=evidence_failure.reason,
            detail=evidence_failure.detail,
            work_item="aeat-export-fragment-generator-authority:official-layout-evidence",
            reconsideration_condition="Restore byte-exact official layout evidence for every emitted filing layout.",
        )
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


def _failure_detail(error: RegistrySnapshotError | RegistryValidationError) -> str:
    """Keep a source or snapshot refusal stable for report consumers."""
    return str(error).splitlines()[0][:1024]
