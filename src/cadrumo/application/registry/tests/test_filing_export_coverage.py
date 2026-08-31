"""Focused closure projection tests for filing layouts and official byte evidence."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....core import RevisionReviewStatus
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.modelo import Modelo
from ...filing import (
    FilingExportConformanceReceipt,
    FilingExportGeneratedOutput,
    FilingExportOfficialProbe,
    FilingExportProof,
    FilingExportProofAssessment,
    FilingExportProofChannel,
    FilingExportProofCoordinate,
    FilingExportProofRefusal,
    FilingExportProofRefusalReason,
    FilingExportPublicProvenance,
    FilingExportSecureReplayReceipt,
)
from ..filing_export_authority import FilingExportEmissionProof, FilingExportGenerationProof, GeneratedExportFileDigest
from ..filing_export_coverage import _filing_export_proof, compose_filing_export_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "0" * 64
_ATTESTED_AT = datetime(2026, 8, 26, 10, 0, tzinfo=UTC)


def test_generation_proof_refuses_a_manifest_without_generated_fragments() -> None:
    """A manifest digest alone cannot stand in for verified generated output files."""
    with pytest.raises(ValidationError, match="at least one emitted TOML fragment"):
        FilingExportGenerationProof(
            authority="generated_export_fragment_provenance_manifest",
            manifest_locator="registry/aeat/modelos/111/revisions/2019-y-siguientes/export/_generation.provenance.json",
            manifest_sha256=_DIGEST,
            semantic_map_sha256=_DIGEST,
            render_profile_sha256=_DIGEST,
            loader_semantic_sha256=_DIGEST,
            output_files=(GeneratedExportFileDigest(relative_path="README.md", sha256=_DIGEST),),
        )


def test_emission_proof_refuses_zero_checked_official_offsets() -> None:
    """Payload bytes without an official-offset assertion are not emission proof."""
    with pytest.raises(ValidationError, match="greater than 0"):
        FilingExportEmissionProof(
            authority="cadrumo.application.filing.export_draft",
            evidence_locator="src/cadrumo/application/filing/tests/test_filing_emitted_byte_acceptance.py",
            payload_sha256=_DIGEST,
            emitted_bytes=1,
            checked_official_offsets=int("0"),
        )


def test_application_registry_exports_no_passive_proof_catalogue() -> None:
    """A caller-authored tuple of hashes is no longer a shipped proof authority."""
    from .. import __all__ as registry_exports

    assert "FilingExportProofCatalogue" not in registry_exports
    assert "FilingExportProofAuthority" not in registry_exports


def test_filing_export_coverage_retains_every_revision_and_below_grade_non_participation(registry_authority) -> None:
    """Registered models below filing grade remain visible without becoming filing participants."""
    report = compose_filing_export_coverage(authority=registry_authority)

    assert {(limb.modelo, limb.revision) for limb in report.limbs} == {
        (modelo.id, revision.id) for modelo in registry_authority.modelos for revision in modelo.revisions.values()
    }
    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("036", "2025-02-03-y-siguientes"))

    assert (limb.name, limb.outcome, limb.evidence, limb.refusal) == (
        "filing_export",
        "not_applicable",
        (),
        None,
    )


def test_filing_export_coverage_refuses_unreviewed_filing_revision(registry_authority) -> None:
    """A filing grade does not bypass the revision-review evidence boundary."""
    modelo = registry_authority.modelo("100")
    revision = modelo.revisions["2025"]
    assert revision.authority_grade is RegistryAuthorityGrade.FILING
    unreviewed = revision.model_copy(update={"review_status": RevisionReviewStatus.PENDING_REVIEW})
    authority = _authority_with_single_revision(registry_authority, modelo=modelo, revision=unreviewed)

    report = compose_filing_export_coverage(authority=authority)
    limb = report.limbs[0]

    assert limb.refusal is not None
    assert (limb.outcome, limb.refusal.reason) == ("refused", "unreviewed_evidence")


def test_filing_export_coverage_refuses_layout_source_byte_drift(registry_authority) -> None:
    """A changed official source digest cannot retain a satisfied export limb."""
    modelo = registry_authority.modelo("100")
    revision = modelo.revisions["2025"]
    source_id = next(
        source_ref
        for layout in revision.export_layouts
        for source_ref in layout.source_refs
        if registry_authority.catalogues.sources[source_ref].evidence_tier == "layout_authority"
    )
    source = registry_authority.catalogues.sources[source_id]
    mutated_source = source.model_copy(update={"sha256": "0" * 64})
    catalogues = registry_authority.catalogues.model_copy(
        update={"sources": {**registry_authority.catalogues.sources, source_id: mutated_source}},
    )
    authority = _authority_with_single_revision(
        registry_authority,
        modelo=modelo,
        revision=revision,
        catalogues=catalogues,
    )

    report = compose_filing_export_coverage(authority=authority)
    limb = report.limbs[0]

    assert limb.refusal is not None
    assert (limb.outcome, limb.refusal.reason) == ("refused", "stale_evidence")


def test_modelo_111_layout_cannot_satisfy_without_two_channel_proof(registry_authority) -> None:
    """A loadable fixed-width declaration is not evidence that production can emit it."""
    modelo = registry_authority.modelo(Modelo.M111)
    revision = modelo.revisions["2019-y-siguientes"]
    assert revision.authority_grade is RegistryAuthorityGrade.FILING
    assert revision.export_layouts
    authority = _authority_with_single_revision(
        registry_authority,
        modelo=modelo,
        revision=revision,
    )

    report = compose_filing_export_coverage(authority=authority)
    limb = report.limbs[0]

    assert (limb.modelo, limb.revision, limb.outcome) == (
        Modelo.M111,
        revision.id,
        "refused",
    )
    assert limb.refusal is not None
    assert limb.refusal.reason == "missing_evidence"
    assert "two-channel" in limb.refusal.detail


def test_two_channel_public_receipts_satisfy_without_projecting_a_payload_digest(registry_authority) -> None:
    """Synthetic strict receipts prove only the application bridge, never taxpayer acceptance."""
    modelo = registry_authority.modelo(Modelo.M100)
    revision = modelo.revisions["2025"]
    authority = _authority_with_single_revision(registry_authority, modelo=modelo, revision=revision)
    coordinate = FilingExportProofCoordinate(
        modelo=modelo.id,
        revision=revision.id,
        layout_ids=tuple(layout.id for layout in revision.export_layouts),
    )
    provenance = _synthetic_public_provenance()
    proof = FilingExportProof(
        coordinate=coordinate,
        conformance=FilingExportConformanceReceipt(
            coordinate=coordinate,
            provenance=provenance,
            authority_id="test.public-conformance",
            emitted_bytes=100,
            checked_official_offsets=1,
        ),
        secure_replay=FilingExportSecureReplayReceipt(
            receipt_id=UUID("00000000-0000-4000-8000-000000000001"),
            coordinate=coordinate,
            provenance=provenance,
            source_authority_id="test.secure-source",
            custody_authority_id="test.encrypted-custody",
            attested_at=_ATTESTED_AT,
            valid_until=_ATTESTED_AT + timedelta(days=1),
        ),
    )

    limb = compose_filing_export_coverage(
        authority=authority,
        proof_authority=_StrictAssessmentAuthority(FilingExportProofAssessment(coordinate=coordinate, proof=proof)),
        assessment_at=_ATTESTED_AT + timedelta(hours=1),
    ).limbs[0]

    assert limb.outcome == "satisfied"
    assert len(limb.evidence) >= 2
    projected = "\n".join(item.locator for item in limb.evidence)
    assert "writer=cadrumo.application.filing.export_draft" in projected
    assert "payload-sha256=" not in projected
    assert "00000000-0000-4000-8000-000000000001" in projected


def test_generic_proof_boundary_refuses_an_expired_secure_replay_receipt() -> None:
    """A complete substitute assessment cannot make an expired custody receipt eligible."""
    coordinate = FilingExportProofCoordinate(
        modelo=Modelo.M100,
        revision="2025",
        layout_ids=("test-layout",),
    )
    provenance = _synthetic_public_provenance()
    proof = FilingExportProof(
        coordinate=coordinate,
        conformance=FilingExportConformanceReceipt(
            coordinate=coordinate,
            provenance=provenance,
            authority_id="test.public-conformance",
            emitted_bytes=100,
            checked_official_offsets=1,
        ),
        secure_replay=FilingExportSecureReplayReceipt(
            receipt_id=UUID("00000000-0000-4000-8000-000000000002"),
            coordinate=coordinate,
            provenance=provenance,
            source_authority_id="test.secure-source",
            custody_authority_id="test.encrypted-custody",
            attested_at=_ATTESTED_AT,
            valid_until=_ATTESTED_AT + timedelta(days=1),
        ),
    )

    resolved_proof, failure = _filing_export_proof(
        proof_authority=_StrictAssessmentAuthority(FilingExportProofAssessment(coordinate=coordinate, proof=proof)),
        snapshot=SimpleNamespace(
            modelo=SimpleNamespace(id=Modelo.M100),
            revision=SimpleNamespace(id="2025", export_layouts=(SimpleNamespace(id="test-layout"),)),
        ),
        assessment_at=_ATTESTED_AT + timedelta(days=1),
    )

    assert resolved_proof is None
    assert failure is not None
    assert failure.reason == "stale_evidence"
    assert tuple((item.channel, item.reason) for item in failure.filing_channels) == (
        ("secure_replay", "proof_validation_failed"),
    )


def test_two_channel_refusals_remain_typed_per_channel(registry_authority) -> None:
    """Unavailable secure replay and missing conformance remain distinct public refusals."""
    modelo = registry_authority.modelo(Modelo.M100)
    revision = modelo.revisions["2025"]
    authority = _authority_with_single_revision(registry_authority, modelo=modelo, revision=revision)
    coordinate = FilingExportProofCoordinate(
        modelo=modelo.id,
        revision=revision.id,
        layout_ids=tuple(layout.id for layout in revision.export_layouts),
    )
    assessment = FilingExportProofAssessment(
        coordinate=coordinate,
        refusals=(
            FilingExportProofRefusal(
                coordinate=coordinate,
                channel=FilingExportProofChannel.CONFORMANCE,
                reason=FilingExportProofRefusalReason.EVIDENCE_MISSING,
                authority_id="test.public-conformance",
            ),
            FilingExportProofRefusal(
                coordinate=coordinate,
                channel=FilingExportProofChannel.SECURE_REPLAY,
                reason=FilingExportProofRefusalReason.AUTHORITY_UNAVAILABLE,
            ),
        ),
    )

    limb = compose_filing_export_coverage(
        authority=authority,
        proof_authority=_StrictAssessmentAuthority(assessment),
    ).limbs[0]

    assert limb.refusal is not None
    assert tuple((item.channel, item.reason) for item in limb.refusal.filing_channels) == (
        ("conformance", "evidence_missing"),
        ("secure_replay", "authority_unavailable"),
    )


class _StrictAssessmentAuthority:
    """Return one already-validated assessment without fabricating writer execution."""

    def __init__(self, assessment: FilingExportProofAssessment) -> None:
        self._assessment = assessment

    def assess_for(self, coordinate: FilingExportProofCoordinate) -> FilingExportProofAssessment:
        assert coordinate == self._assessment.coordinate
        return self._assessment


def _synthetic_public_provenance() -> FilingExportPublicProvenance:
    """Build non-sensitive strict metadata solely for bridge-contract coverage."""
    return FilingExportPublicProvenance(
        official_source_ref="test.official-layout",
        official_source_sha256="1" * 64,
        design_epoch="2025",
        generation_manifest_sha256="2" * 64,
        semantic_map_sha256="3" * 64,
        render_profile_sha256="4" * 64,
        loader_semantic_sha256="5" * 64,
        generated_outputs=(FilingExportGeneratedOutput(relative_path="generated/layout.toml", sha256="6" * 64),),
        probes=(
            FilingExportOfficialProbe(
                record_id="record-1",
                field_id="field-1",
                emitted_offset=0,
                length=1,
            ),
        ),
    )


def _authority_with_single_revision(
    authority,
    *,
    modelo,
    revision,
    catalogues=None,
):
    """Return a real authority narrowed to one independently mutated revision."""
    composed_modelo = modelo.model_copy(update={"revisions": {revision.id: revision}})
    return replace(
        authority,
        modelos=(composed_modelo,),
        catalogues=authority.catalogues if catalogues is None else catalogues,
        _modelos_by_id={composed_modelo.id: composed_modelo},
        _snapshots={},
    )
