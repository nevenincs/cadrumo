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

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.authority import compiled_bundled_authority
from ..conformance.closure_models import RegistryClosureLimb
from ..conformance.filing_export_coverage import compose_filing_export_coverage
from ..filing_export_proof import canonical_two_channel_filing_export_proof_authority
from ..maintenance_support import coverage_assessment_floor, coverage_assessment_horizon, revision_selection_coordinates

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_EXPORT_OWNER = "aeat-export-fragment-generator-authority"


def _canonical_filing_authority():
    """Bind the two-channel filing proof authority the coverage composer requires.

    The composer asks this authority to assess a coordinate, and only the
    two-channel authority carries that. The single-channel one this fixture used
    to build offers the older proof lookup instead, so every test through it
    failed on a missing attribute rather than on the assertion it exists to make.
    Both secure-replay inputs are absent because these tests exercise the public
    channel; an operator supplies those.
    """
    authority = compiled_bundled_authority()
    return authority, canonical_two_channel_filing_export_proof_authority(
        workspace_root=_REPOSITORY_ROOT,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        authority=authority,
        secure_replay_source=None,
        secure_replay_custody=None,
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


def _limbs_by_coordinate(report) -> dict[tuple[str, str], RegistryClosureLimb]:
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
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    assessment_floor = coverage_assessment_floor(authority.catalogues)

    def selectable(revision: ModeloRevision) -> bool:
        return bool(
            revision_selection_coordinates(
                revision,
                assessment_horizon=assessment_horizon,
                assessment_floor=assessment_floor,
            )
        )

    # The denominator is exactly the law-selectable set temporal coverage
    # enumerates. A historical declaration wholly below the support floor has no
    # coordinate this product can file, so it carries no limb at all rather than
    # a limb the closure join could not match to a temporal row.
    assert set(limbs) == {
        (modelo.id, revision.id)
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        if selectable(revision)
    }
    assert any(not selectable(revision) for modelo in authority.modelos for revision in modelo.revisions.values()), (
        "no revision lies outside the support envelope; the exclusion above is untested"
    )

    for modelo, revision in filing_revisions:
        coordinates_for_revision = revision_selection_coordinates(
            revision,
            assessment_horizon=assessment_horizon,
            assessment_floor=assessment_floor,
        )
        if not coordinates_for_revision:
            assert (modelo.id, revision.id) not in limbs
            continue
        limb = limbs[(modelo.id, revision.id)]
        for filing_year, period in coordinates_for_revision:
            inspection = authority.inspect_revision(
                modelo.id,
                filing_year=filing_year,
                period=period,
            )
            assert inspection.revision_id == revision.id

        assert limb.name == "filing_export"
        if limb.outcome == "satisfied":
            evidence_by_authority = {evidence.authority: evidence.locator for evidence in limb.evidence}
            generation = evidence_by_authority["generated_export_fragment_provenance_manifest"]
            emission = evidence_by_authority["cadrumo.application.filing.export_draft"]
            assert ";semantic=" in generation and ";render=" in generation and ";loader=" in generation
            assert ";payload-sha256=" in emission and ";checked-offsets=" in emission
            continue

        assert limb.outcome == "refused"
        assert limb.refusal is not None
        assert limb.refusal.disposition.owner == _EXPORT_OWNER
        assert limb.refusal.disposition.work_item.startswith(f"{_EXPORT_OWNER}:")
        assert limb.refusal.disposition.reconsideration_condition


def test_missing_secure_replay_cannot_turn_a_declared_layout_into_emitted_byte_evidence() -> None:
    """A real layout without operator-custodied replay stays visibly refused."""
    authority, proof_authority = _canonical_filing_authority()
    report = compose_filing_export_coverage(
        authority=authority,
        proof_authority=proof_authority,
    )
    limb = next(
        limb
        for limb in report.limbs
        if limb.refusal is not None
        and limb.refusal.disposition.work_item == f"{_EXPORT_OWNER}:production-emission-proof"
    )

    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.reason == "missing_evidence"
    assert limb.refusal.disposition.owner == _EXPORT_OWNER
    assert limb.refusal.disposition.work_item == f"{_EXPORT_OWNER}:production-emission-proof"

    # Assert the structured refusal rather than its prose. The guard is that an
    # empty channel refuses for want of evidence and names which channel is
    # empty; the wording of the detail is the composer's to change, and this
    # test previously broke on exactly that when the two-channel migration
    # rephrased it, which left the guard silent for as long as it stayed broken.
    channels = {refusal.channel: refusal.reason for refusal in limb.refusal.filing_channels}
    assert channels["conformance"] == "evidence_missing"
    assert not limb.evidence


def test_modelo_353_revisions_keep_distinct_law_coordinates_and_each_require_production_emission_proof() -> None:
    """A later M353 revision cannot mask its predecessor's proof outcome."""
    authority, proof_authority = _canonical_filing_authority()
    modelo = authority.modelo("353")
    report = compose_filing_export_coverage(
        authority=authority,
        proof_authority=proof_authority,
    )
    limbs = _limbs_by_coordinate(report)
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    assessment_floor = coverage_assessment_floor(authority.catalogues)
    revision_limbs = tuple(
        (revision, limbs[(modelo.id, revision.id)])
        for revision in modelo.revisions.values()
        if revision.authority_grade is RegistryAuthorityGrade.FILING
        and revision_selection_coordinates(
            revision,
            assessment_horizon=assessment_horizon,
            assessment_floor=assessment_floor,
        )
    )
    assert revision_limbs, "Modelo 353 has no filing-grade revision inside the support envelope"
    coordinates_by_revision = {
        revision.id: coordinates
        for revision, _limb in revision_limbs
        if (
            coordinates := revision_selection_coordinates(
                revision, assessment_horizon=assessment_horizon, assessment_floor=assessment_floor
            )
        )
    }
    assert coordinates_by_revision
    assert all(
        authority.inspect_revision(modelo.id, filing_year=filing_year, period=period).revision_id == revision_id
        for revision_id, coordinates in coordinates_by_revision.items()
        for filing_year, period in coordinates
    )
    assert all(
        not set(left_coordinates).intersection(right_coordinates)
        for left_revision, left_coordinates in coordinates_by_revision.items()
        for right_revision, right_coordinates in coordinates_by_revision.items()
        if left_revision < right_revision
    )

    for _revision, limb in revision_limbs:
        assert limb.outcome == "refused"
        assert limb.refusal is not None
        assert limb.refusal.reason == "missing_evidence"
        assert limb.refusal.disposition.owner == _EXPORT_OWNER
        assert limb.refusal.disposition.work_item == f"{_EXPORT_OWNER}:production-emission-proof"
