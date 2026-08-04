"""Real-behavior tests for migration candidate classification."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from dev.registry.migration import (
    ClassifiedOccurrenceCandidate,
    build_source_inventory,
    classify_canonical_occurrence_candidates,
    extract_resolved_localization_matrix,
    generate_canonical_occurrence_candidates,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_bundled_candidates_classify_without_promoting_ungrounded_identity() -> None:
    """The real corpus partitions grounded, exact, and provisional groups honestly."""
    root = bundled_path("registry", "aeat")
    inventory = build_source_inventory(root)
    matrix = extract_resolved_localization_matrix(root, inventory)
    candidates = generate_canonical_occurrence_candidates(matrix)
    classified = classify_canonical_occurrence_candidates(candidates)

    assert classified.corpus_fingerprint == matrix.corpus_fingerprint
    assert classified.candidate_count == 126_192
    assert classified.grounded_count == 144
    assert classified.revision_exact_count == 32_008
    assert classified.continuity_candidate_count == 94_040
    assert classified.continuity_candidate_group_count == 2_354

    grounded = next(
        item
        for item in classified.candidates
        if item.candidate.continuidad_id == "irpf.inmueble.porcentaje-propiedad"
        and item.candidate.locale == "en"
        and item.candidate.field == "label"
    )
    assert grounded.classification == "grounded"
    assert grounded.provisional_candidate_id is None

    candidate = next(
        item
        for item in classified.candidates
        if (
            item.candidate.modelo_id,
            item.candidate.casilla_id,
            item.candidate.locale,
            item.candidate.field,
        )
        == ("100", "0001", "en", "label")
        and item.candidate.revision_id == "2020"
    )
    assert candidate.classification == "continuity_candidate"
    assert candidate.provisional_candidate_id == "candidate/100/casilla/0001"
    assert candidate.candidate.continuidad_id is None
    assert candidate.candidate.canonical_key == "modelo/100/revision/2020/casilla/0001/label"

    exact = next(item for item in classified.candidates if item.classification == "revision_exact")
    assert exact.candidate.continuidad_id is None
    assert exact.provisional_candidate_id is None


def test_classified_candidate_requires_provisional_id_for_candidate_state() -> None:
    """A provisional classification cannot be serialized without its explicit token."""
    root = bundled_path("registry", "aeat")
    inventory = build_source_inventory(root)
    matrix = extract_resolved_localization_matrix(root, inventory)
    candidate = next(
        item for item in generate_canonical_occurrence_candidates(matrix).candidates if item.continuidad_id is None
    )

    with pytest.raises(ValidationError, match="provisional group id"):
        ClassifiedOccurrenceCandidate(
            candidate=candidate,
            classification="continuity_candidate",
        )
