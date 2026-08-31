"""Closure-limb projection for exact filing layouts and two-channel proof.

Filing capability is stricter than a revision merely declaring a layout.  The
law-selected revision must admit a filing-grade snapshot, each materialised
layout must retain byte-matching official authority, and both public conformance
and encrypted source-owned replay must attest the canonical writer.  The
:class:`RegistryAuthorityGrade` boundary and this module report those facts
without creating a second export authoring path or projecting secret payloads.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field, computed_field, model_validator

from ...core import REVIEWED_REVISION_REVIEW_STATUSES
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time import UtcInstant, now
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.corpus_catalogue import verify_source_file
from ...domain.calculations.registry.errors import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_references import SourceReference
from ...domain.calculations.registry.temporal import (
    coverage_assessment_horizon,
    revision_selection_coordinates,
)
from ..filing import (
    FilingExportProof,
    FilingExportProofAuthority,
    FilingExportProofChannel,
    FilingExportProofCoordinate,
    FilingExportProofRefusalReason,
)
from .closure import (
    RegistryClosureEvidence,
    RegistryClosureFilingChannelRefusal,
    RegistryClosureLimb,
    RegistryClosureOwnerDisposition,
    RegistryClosureRefusal,
    RegistryClosureRefusalReason,
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
    assessment_at: UtcInstant | None = None,
) -> FilingExportCoverageReport:
    """Compose filing-layout evidence from validated law-selected snapshots.

    A revision below filing grade is a deliberate non-filing capability and is
    retained as such.  A filing-grade revision is selected without a revision-id
    override, admitted through the filing snapshot boundary, and then checked
    against the byte-exact official layout sources its materialised layouts cite.
    """
    authority.validate_registry()
    current_assessment_at = now() if assessment_at is None else assessment_at
    limbs = tuple(
        _compose_revision_limb(
            authority=authority,
            proof_authority=proof_authority,
            assessment_at=current_assessment_at,
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
    assessment_at: UtcInstant,
    modelo_id: str,
    revision: ModeloRevision,
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
    snapshots: list[RegistrySnapshot] = []
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
        assessment_at=assessment_at,
    )
    if proof_failure is not None:
        return _refused_limb(
            modelo_id=modelo_id,
            revision_id=revision.id,
            reason=proof_failure.reason,
            detail=proof_failure.detail,
            work_item="aeat-export-fragment-generator-authority:production-emission-proof",
            reconsideration_condition=(
                "Verify public conformance through the canonical writer and provide a current encrypted "
                "source-owned replay receipt for the same law-selected provenance."
            ),
            filing_channels=proof_failure.filing_channels,
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
    snapshot: RegistrySnapshot,
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


class _FilingExportSnapshotLayout(Protocol):
    """The one export-layout fact :func:`_filing_export_proof` reads."""

    @property
    def id(self) -> str: ...


class _FilingExportSnapshotRevision(Protocol):
    """The revision facts :func:`_filing_export_proof` reads."""

    @property
    def id(self) -> str: ...

    @property
    def export_layouts(self) -> Iterable[_FilingExportSnapshotLayout]: ...


class _FilingExportSnapshotModelo(Protocol):
    """The modelo fact :func:`_filing_export_proof` reads."""

    @property
    def id(self) -> str: ...


class _FilingExportSnapshotLike(Protocol):
    """Narrow structural need :func:`_filing_export_proof` has of a registry snapshot.

    Deliberately narrower than :class:`~domain.calculations.registry.RegistrySnapshot`:
    this coordinate-derivation step reads only the modelo/revision identity and the
    declared export layouts, and ``FilingExportProofCoordinate`` performs the real
    typed validation of the values this function passes through. Read-only
    ``@property`` accessors keep every attribute covariant, so a concrete
    :class:`~domain.calculations.registry.RegistrySnapshot` (whose ids are
    ``Annotated[str, ...]`` registry alias types) satisfies this Protocol
    structurally.
    """

    @property
    def modelo(self) -> _FilingExportSnapshotModelo: ...

    @property
    def revision(self) -> _FilingExportSnapshotRevision: ...


def _filing_export_proof(
    *,
    proof_authority: FilingExportProofAuthority | None,
    snapshot: _FilingExportSnapshotLike,
    assessment_at: UtcInstant,
) -> tuple[FilingExportProof | None, _LayoutEvidenceFailure | None]:
    """Require one exact two-channel assessment at the law-selected coordinate."""
    if proof_authority is None:
        return None, _LayoutEvidenceFailure(
            reason="missing_evidence",
            detail="no canonical two-channel filing-export proof authority was supplied",
        )
    layout_ids = tuple(layout.id for layout in snapshot.revision.export_layouts)
    coordinate = FilingExportProofCoordinate(
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        layout_ids=layout_ids,
    )
    try:
        assessment = proof_authority.assess_for(coordinate)
    except (OSError, RuntimeError, ValueError) as exc:
        return None, _LayoutEvidenceFailure(reason="stale_evidence", detail=_failure_detail(exc))
    if assessment.coordinate != coordinate:
        return None, _LayoutEvidenceFailure(
            reason="conflicting_evidence",
            detail="filing export assessment identity does not match the law-selected registry snapshot",
        )
    if assessment.proof is None:
        channel_refusals = tuple(
            RegistryClosureFilingChannelRefusal(
                channel=refusal.channel.value,
                reason=refusal.reason.value,
                authority_id=refusal.authority_id,
            )
            for refusal in assessment.refusals
        )
        conflicting_reasons = {"identity_mismatch", "provenance_mismatch"}
        reason = (
            "conflicting_evidence"
            if any(item.reason in conflicting_reasons for item in channel_refusals)
            else "missing_evidence"
        )
        detail = "; ".join(f"{item.channel}:{item.reason}" for item in channel_refusals)
        return None, _LayoutEvidenceFailure(
            reason=reason,
            detail=f"two-channel filing export assessment refused: {detail}",
            filing_channels=channel_refusals,
        )
    proof = assessment.proof
    if not proof.secure_replay.attested_at <= assessment_at < proof.secure_replay.valid_until:
        return None, _LayoutEvidenceFailure(
            reason="stale_evidence",
            detail="secure replay receipt is not current at the closure assessment instant",
            filing_channels=(
                RegistryClosureFilingChannelRefusal(
                    channel=FilingExportProofChannel.SECURE_REPLAY.value,
                    reason=FilingExportProofRefusalReason.PROOF_VALIDATION_FAILED.value,
                ),
            ),
        )
    return proof, None


def _proof_evidence(proof: FilingExportProof) -> tuple[RegistryClosureEvidence, ...]:
    """Project only public receipt metadata into the closure evidence spine."""
    provenance = proof.conformance.provenance
    return (
        RegistryClosureEvidence(
            authority=proof.conformance.authority_id,
            locator=(
                f"{provenance.official_source_ref}#sha256={provenance.official_source_sha256}"
                f";manifest={provenance.generation_manifest_sha256}"
                f";semantic={provenance.semantic_map_sha256}"
                f";render={provenance.render_profile_sha256}"
                f";loader={provenance.loader_semantic_sha256}"
                f";writer={proof.conformance.canonical_writer}"
                f";bytes={proof.conformance.emitted_bytes}"
                f";checked-offsets={proof.conformance.checked_official_offsets}"
            ),
        ),
        RegistryClosureEvidence(
            authority=(f"{proof.secure_replay.source_authority_id}+{proof.secure_replay.custody_authority_id}"),
            locator=(
                f"secure-replay-receipt:{proof.secure_replay.receipt_id}"
                f";writer={proof.secure_replay.canonical_writer}"
                f";schema={proof.secure_replay.proof_schema_version}"
                f";attested={proof.secure_replay.attested_at.isoformat()}"
                f";valid-until={proof.secure_replay.valid_until.isoformat()}"
                ";replay-passed=true;payload-digest-exposed=false"
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class _LayoutEvidenceFailure:
    """One typed internal failure while checking live layout-source bytes."""

    reason: RegistryClosureRefusalReason
    detail: str
    filing_channels: tuple[RegistryClosureFilingChannelRefusal, ...] = ()


def _refused_limb(
    *,
    modelo_id: str,
    revision_id: str,
    reason: RegistryClosureRefusalReason,
    detail: str,
    work_item: str,
    reconsideration_condition: str,
    filing_channels: tuple[RegistryClosureFilingChannelRefusal, ...] = (),
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
            filing_channels=filing_channels,
        ),
    )


def _failure_detail(error: Exception) -> str:
    """Keep a source or snapshot refusal stable for report consumers."""
    return str(error).splitlines()[0][:500]
