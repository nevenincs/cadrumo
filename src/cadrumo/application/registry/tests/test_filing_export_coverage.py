"""Focused closure projection tests for filing layouts and official byte evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ....core import RegistryAuthorityGrade, RevisionReviewStatus
from .. import compose_filing_export_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_filing_export_coverage_retains_every_revision_and_below_grade_refusal(registry_authority) -> None:
    """Registered models without filing authority remain visible, not inferred fileable."""
    report = compose_filing_export_coverage(authority=registry_authority)

    assert {(limb.modelo, limb.revision) for limb in report.limbs} == {
        (modelo.id, revision.id)
        for modelo in registry_authority.modelos
        for revision in modelo.revisions.values()
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
