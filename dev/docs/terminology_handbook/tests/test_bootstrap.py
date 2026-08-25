"""Gates over the bootstrapped Terminology Handbook tree.

The committed tree must load, pass every validation gate, carry the key migrated
concepts as approved with resolving legal_refs and four-language
short_descriptions, survive a re-scaffold without clobbering migrated prose,
and be drift-free against the enrolment sources so ``scaffold --check`` is
green.
"""

from __future__ import annotations

import pytest

from cadrumo.core import ConceptLifecycle
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import bundled_authority

from .. import (
    audit_handbook,
    build_scaffold_plan,
    collect_enrolment_candidates,
    default_handbook_validators,
    load_bundled_terminology_handbook,
    serialise_concept,
    terminology_concepts_dir,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_bootstrapped_tree_passes_every_validation_gate() -> None:
    handbook = load_bundled_terminology_handbook()
    legal_ids = frozenset(bundled_authority().catalogues.legal)
    for validate in default_handbook_validators(legal_ids):
        validate(handbook)
    assert len(handbook.concepts) >= 95


def test_key_migrated_concepts_are_approved_and_complete() -> None:
    handbook = load_bundled_terminology_handbook()
    for concept_id in ("prorrata", "justificante", "aeat", "modelo-303", "recargo-equivalencia"):
        concept = handbook.concept(concept_id)
        assert concept.lifecycle is ConceptLifecycle.APPROVED, concept_id
        es = concept.section(OutputLanguage.ES)
        assert es.definition and es.definition.strip(), concept_id
        assert es.source is not None and es.source.citation.strip(), concept_id


def test_prorrata_carries_four_languages_and_resolving_legal_refs() -> None:
    handbook = load_bundled_terminology_handbook()
    prorrata = handbook.concept("prorrata")
    assert {s.language for s in prorrata.languages} == {
        OutputLanguage.ES,
        OutputLanguage.EN,
        OutputLanguage.CA,
        OutputLanguage.HU,
    }
    legal_ids = frozenset(bundled_authority().catalogues.legal)
    assert prorrata.legal_refs
    for ref in prorrata.legal_refs:
        assert ref in legal_ids, ref


def test_every_migrated_legal_ref_resolves_in_the_catalogue() -> None:
    handbook = load_bundled_terminology_handbook()
    legal_ids = frozenset(bundled_authority().catalogues.legal)
    for concept in handbook.concepts:
        for ref in concept.legal_refs:
            assert ref in legal_ids, f"{concept.concept_id}: {ref}"


def test_rescaffold_does_not_clobber_migrated_prose() -> None:
    # Re-scaffolding the committed tree against the live sources must be a
    # complete no-op: every curated concept is UNCHANGED, so no migrated
    # definition / short_description / term is overwritten.
    handbook = load_bundled_terminology_handbook()
    before = {c.concept_id: serialise_concept(c) for c in handbook.concepts}

    candidates = collect_enrolment_candidates()
    existing = dict(handbook.by_id)
    plan = build_scaffold_plan(candidates, existing, today=handbook.concepts[0].updated_at)
    assert plan.is_empty, "re-scaffold drifted; a curated concept would be rewritten"

    # The plan carries the existing records unchanged; serialising them must
    # reproduce the curated prose byte-for-byte.
    for entry in plan.entries:
        assert serialise_concept(entry.record) == before[entry.concept_id]


def test_scaffold_check_is_green_against_the_bootstrapped_tree() -> None:
    # The committed tree is in sync with the enrolment sources, so a --check
    # dry-run reports no drift.
    candidates = collect_enrolment_candidates()
    handbook = load_bundled_terminology_handbook()
    plan = build_scaffold_plan(candidates, dict(handbook.by_id), today=handbook.concepts[0].updated_at)
    assert plan.is_empty


def test_audit_reports_structurally_clean_with_a_tracked_backlog() -> None:
    report = audit_handbook(terminology_concepts_dir())
    # Structurally clean (no dangling relations, no retired-without-replacement).
    assert report.is_clean
    # The curation backlog is the honest draft count the ratchet baselines.
    assert report.draft_count >= 1
    assert report.approved_count >= 20
