"""Derived filing-grade export proof gate over the shipped authority.

This is deliberately a status gate rather than a second export implementation.
The denominator comes from :class:`ValidatedRegistryAuthority`, the law
selection coordinate comes from the closure authority, and the canonical live
proof authority is the only route that can attest semantic-map ownership,
generated fragments, and bytes written by ``export_draft``.

Consequently an unproven layout is a visible refusal, not an invitation to
invent a draft, output payload, offset, or a plan-row table in Python. Exact
successor-plan routes remain in the Vault records; this executable gate retains
only the application-owned generic disposition.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from dev.registry.filing_export_proof import (
    CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES,
    canonical_live_filing_export_proof_authority,
)

from ....application.registry import compose_filing_export_coverage
from ....core import Modelo, RegistryAuthorityGrade
from ....core.resources import bundled_path
from ....domain.calculations.registry import (
    ValidatedRegistryAuthority,
    bundled_authority,
    coverage_assessment_horizon,
    revision_selection_coordinates,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_EXPORT_OWNER = "aeat-export-fragment-generator-authority"


def _canonical_filing_authority():
    """Bind the one live filing proof authority without opening source proof."""
    authority = bundled_authority()
    return authority, canonical_live_filing_export_proof_authority(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=authority,
    )


def _filing_revisions(authority: ValidatedRegistryAuthority):
    """Derive every filing-capable revision from the validated authority."""
    return tuple(
        (modelo, revision)
        for modelo in sorted(authority.modelos, key=lambda item: item.id)
        for revision in sorted(modelo.revisions.values(), key=lambda item: item.id)
        if revision.authority_grade is RegistryAuthorityGrade.FILING
    )


def _narrow_authority(
    authority: ValidatedRegistryAuthority,
    *,
    modelo,
    revision,
) -> ValidatedRegistryAuthority:
    """Keep one real revision while exercising the normal closure composer."""
    narrowed_modelo = modelo.model_copy(update={"revisions": {revision.id: revision}})
    return replace(
        authority,
        modelos=(narrowed_modelo,),
        _modelos_by_id={narrowed_modelo.id: narrowed_modelo},
        _snapshots={},
    )


def _limbs_by_coordinate(report) -> dict[tuple[str, str], object]:
    return {(str(limb.modelo), str(limb.revision)): limb for limb in report.limbs}


def test_every_filing_grade_revision_has_one_law_selected_export_limb_and_an_honest_proof_outcome() -> None:
    """Selection, semantic ownership, and emitted bytes all stay proof-gated.

    A satisfied limb carries the only admissible live evidence: its canonical
    generator verification records semantic-map, render-profile, and loader
    identities; the production ``export_draft`` evidence records payload bytes
    and checked official offsets. A refused limb must name the generic export
    authority rather than disappearing from the denominator.
    """
    authority, proof_authority = _canonical_filing_authority()
    filing_revisions = _filing_revisions(authority)
    assert filing_revisions, "the filing-grade inventory is empty; this gate would pass vacuously"

    report = compose_filing_export_coverage(
        authority=authority,
        proof_authority=proof_authority,
    )
    limbs = _limbs_by_coordinate(report)
    coordinates = {(modelo.id, revision.id) for modelo, revision in filing_revisions}

    assert set(limbs) == {
        (modelo.id, revision.id) for modelo in authority.modelos for revision in modelo.revisions.values()
    }
    assert coordinates <= set(limbs)

    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    for modelo, revision in filing_revisions:
        for filing_year, period in revision_selection_coordinates(
            revision,
            assessment_horizon=assessment_horizon,
        ):
            inspection = authority.inspect_revision(
                modelo.id,
                filing_year=filing_year,
                period=period,
            )
            assert inspection.revision_id == revision.id

        limb = limbs[(modelo.id, revision.id)]
        assert limb.name == "filing_export"
        if limb.outcome == "satisfied":
            evidence_by_authority = {evidence.authority: evidence.locator for evidence in limb.evidence}
            generation = evidence_by_authority["dev.registry.pipeline.verify_export_fragment_provenance_manifest"]
            emission = evidence_by_authority["cadrumo.application.filing.export_draft"]
            assert ";semantic=" in generation and ";render=" in generation and ";loader=" in generation
            assert ";payload-sha256=" in emission and ";checked-offsets=" in emission
            continue

        assert limb.outcome == "refused"
        assert limb.refusal is not None
        assert limb.refusal.disposition.owner == _EXPORT_OWNER
        assert limb.refusal.disposition.work_item.startswith(f"{_EXPORT_OWNER}:")
        assert limb.refusal.disposition.reconsideration_condition


def test_an_empty_canonical_live_proof_cannot_turn_a_declared_layout_into_emitted_byte_evidence() -> None:
    """A real layout plus the real empty proof authority stays visibly refused."""
    assert not CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES

    authority, proof_authority = _canonical_filing_authority()
    modelo, revision = next(
        (modelo, revision) for modelo, revision in _filing_revisions(authority) if revision.export_layouts
    )
    narrowed = _narrow_authority(authority, modelo=modelo, revision=revision)
    report = compose_filing_export_coverage(
        authority=narrowed,
        proof_authority=proof_authority,
    )
    limb = report.limbs[0]

    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.reason == "missing_evidence"
    assert limb.refusal.disposition.owner == _EXPORT_OWNER
    assert limb.refusal.disposition.work_item == f"{_EXPORT_OWNER}:production-emission-proof"
    assert "canonical generation" in limb.refusal.detail
    assert "emitted-byte" in limb.refusal.detail


def test_modelo_353_layout_gap_is_selected_by_its_own_law_coordinate_and_cannot_be_masked_by_2026() -> None:
    """The real M353 source/layout gap stays bound to its pre-2026 selection."""
    authority, proof_authority = _canonical_filing_authority()
    modelo = authority.modelo(Modelo.M353.value)
    revision_limbs = tuple(
        (
            revision,
            compose_filing_export_coverage(
                authority=_narrow_authority(authority, modelo=modelo, revision=revision),
                proof_authority=proof_authority,
            ).limbs[0],
        )
        for revision in modelo.revisions.values()
    )
    gap_revision, gap_limb = next(
        (revision, limb)
        for revision, limb in revision_limbs
        if limb.refusal is not None and limb.refusal.disposition.work_item == f"{_EXPORT_OWNER}:filing-layout"
    )
    successor_revision = next(revision for revision, _limb in revision_limbs if revision.id != gap_revision.id)
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    gap_coordinates = revision_selection_coordinates(gap_revision, assessment_horizon=assessment_horizon)
    successor_coordinates = revision_selection_coordinates(successor_revision, assessment_horizon=assessment_horizon)

    assert all(
        authority.inspect_revision(modelo.id, filing_year=filing_year, period=period).revision_id == gap_revision.id
        for filing_year, period in gap_coordinates
    )
    assert all(
        authority.inspect_revision(modelo.id, filing_year=filing_year, period=period).revision_id
        == successor_revision.id
        for filing_year, period in successor_coordinates
    )
    assert not set(gap_coordinates).intersection(successor_coordinates)

    assert gap_limb.outcome == "refused"
    assert gap_limb.refusal is not None
    assert gap_limb.refusal.reason == "missing_evidence"
    assert gap_limb.refusal.disposition.owner == _EXPORT_OWNER
    assert gap_limb.refusal.disposition.work_item == f"{_EXPORT_OWNER}:filing-layout"
