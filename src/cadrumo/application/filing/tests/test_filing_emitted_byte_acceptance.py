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

from ....application.registry import compose_filing_export_coverage
from ....application.registry._temporal_coverage import _law_selection_coordinate
from ....core import Modelo, RegistryAuthorityGrade
from ....domain.calculations.registry import ValidatedRegistryAuthority
from dev.registry.conformance.authorities import canonical_live_registry_closure_authorities
from dev.registry.filing_export_proof import CANONICAL_LIVE_FILING_EXPORT_PROOF_ENTRIES

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[5]
_EXPORT_OWNER = "aeat-export-fragment-generator-authority"


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
    with canonical_live_registry_closure_authorities(_REPOSITORY_ROOT) as authorities:
        filing_revisions = _filing_revisions(authorities.registry)
        assert filing_revisions, "the filing-grade inventory is empty; this gate would pass vacuously"

        report = compose_filing_export_coverage(
            authority=authorities.registry,
            proof_authority=authorities.filing_export,
        )
        limbs = _limbs_by_coordinate(report)
        coordinates = {(modelo.id, revision.id) for modelo, revision in filing_revisions}

        assert set(limbs) == {
            (modelo.id, revision.id)
            for modelo in authorities.registry.modelos
            for revision in modelo.revisions.values()
        }
        assert coordinates <= set(limbs)

        for modelo, revision in filing_revisions:
            filing_year, period = _law_selection_coordinate(revision)
            inspection = authorities.registry.inspect_revision(
                modelo.id,
                filing_year=filing_year,
                period=period,
            )
            assert inspection.revision_id == revision.id

            limb = limbs[(modelo.id, revision.id)]
            assert limb.name == "filing_export"
            if limb.outcome == "satisfied":
                evidence_by_authority = {evidence.authority: evidence.locator for evidence in limb.evidence}
                generation = evidence_by_authority[
                    "dev.registry.pipeline.verify_export_fragment_provenance_manifest"
                ]
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

    with canonical_live_registry_closure_authorities(_REPOSITORY_ROOT) as authorities:
        modelo, revision = next(
            (modelo, revision)
            for modelo, revision in _filing_revisions(authorities.registry)
            if revision.export_layouts
        )
        narrowed = _narrow_authority(authorities.registry, modelo=modelo, revision=revision)
        report = compose_filing_export_coverage(
            authority=narrowed,
            proof_authority=authorities.filing_export,
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
    """The real M353 boundary bites: 2008--2025 lacks a layout; 2026 differs."""
    with canonical_live_registry_closure_authorities(_REPOSITORY_ROOT) as authorities:
        modelo = authorities.registry.modelo(Modelo.M353.value)
        gap_revision = next(revision for revision in modelo.revisions.values() if not revision.export_layouts)
        successor_revision = next(revision for revision in modelo.revisions.values() if revision.export_layouts)
        gap_year, gap_period = _law_selection_coordinate(gap_revision)
        successor_year, successor_period = _law_selection_coordinate(successor_revision)

        assert authorities.registry.inspect_revision(
            modelo.id,
            filing_year=gap_year,
            period=gap_period,
        ).revision_id == gap_revision.id
        assert authorities.registry.inspect_revision(
            modelo.id,
            filing_year=successor_year,
            period=successor_period,
        ).revision_id == successor_revision.id
        assert (gap_year, gap_period) != (successor_year, successor_period)

        narrowed = _narrow_authority(authorities.registry, modelo=modelo, revision=gap_revision)
        limb = compose_filing_export_coverage(
            authority=narrowed,
            proof_authority=authorities.filing_export,
        ).limbs[0]

    assert limb.outcome == "refused"
    assert limb.refusal is not None
    assert limb.refusal.reason == "missing_evidence"
    assert limb.refusal.disposition.owner == _EXPORT_OWNER
    assert limb.refusal.disposition.work_item == f"{_EXPORT_OWNER}:filing-layout"
