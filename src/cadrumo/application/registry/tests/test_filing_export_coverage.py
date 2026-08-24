"""Focused closure projection tests for filing layouts and official byte evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from ....core import Modelo, RegistryAuthorityGrade, RevisionReviewStatus
from .. import (
    FilingExportEmissionProof,
    FilingExportGenerationProof,
    GeneratedExportFileDigest,
    compose_filing_export_coverage,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "0" * 64


def test_generation_proof_refuses_a_manifest_without_generated_fragments() -> None:
    """A manifest digest alone cannot stand in for verified generated output files."""
    with pytest.raises(ValidationError, match="at least one emitted TOML fragment"):
        FilingExportGenerationProof(
            authority="dev.registry.pipeline.verify_export_fragment_provenance_manifest",
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
            checked_official_offsets=0,
        )


def test_application_registry_exports_no_passive_proof_catalogue() -> None:
    """A caller-authored tuple of hashes is no longer a shipped proof authority."""
    from .. import __all__ as registry_exports

    assert "FilingExportProofCatalogue" not in registry_exports


def test_filing_export_coverage_retains_every_revision_and_below_grade_refusal(registry_authority) -> None:
    """Registered models without filing authority remain visible, not inferred fileable."""
    report = compose_filing_export_coverage(authority=registry_authority)

    assert {(limb.modelo, limb.revision) for limb in report.limbs} == {
        (modelo.id, revision.id) for modelo in registry_authority.modelos for revision in modelo.revisions.values()
    }
    limb = next(limb for limb in report.limbs if (limb.modelo, limb.revision) == ("036", "2025-02-03-y-siguientes"))

    assert (limb.name, limb.outcome, limb.refusal.reason) == (
        "filing_export",
        "refused",
        "below_filing_grade",
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

    assert (limb.outcome, limb.refusal.reason) == ("refused", "stale_evidence")


def test_modelo_111_layout_cannot_satisfy_without_generation_and_emission_proof(registry_authority) -> None:
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
    assert "generation" in limb.refusal.detail
    assert "emitted-byte" in limb.refusal.detail


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
