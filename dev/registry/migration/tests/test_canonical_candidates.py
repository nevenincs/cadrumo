"""Real-behavior tests for canonical localization occurrence candidates."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from dev.registry.migration import (
    CanonicalOccurrenceCandidate,
    build_source_inventory,
    extract_resolved_localization_matrix,
    generate_canonical_occurrence_candidates,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def test_bundled_candidates_use_only_declared_occurrence_identity() -> None:
    """The measured matrix becomes deterministic exact or grounded addresses."""
    root = bundled_path("registry", "aeat")
    inventory = build_source_inventory(root)
    matrix = extract_resolved_localization_matrix(root, inventory)
    candidates = generate_canonical_occurrence_candidates(matrix)

    assert candidates.corpus_fingerprint == matrix.corpus_fingerprint
    assert candidates.candidate_count == 126_192
    assert candidates.occurrence_count == 15_774
    assert 0 < candidates.canonical_key_count < candidates.candidate_count
    assert candidates.candidates == tuple(
        sorted(
            candidates.candidates,
            key=lambda item: (
                item.modelo_id,
                item.revision_id,
                item.casilla_id,
                item.locale,
                item.field,
            ),
        ),
    )

    exact = next(
        candidate
        for candidate in candidates.candidates
        if (
            candidate.modelo_id,
            candidate.revision_id,
            candidate.casilla_id,
            candidate.locale,
            candidate.field,
        )
        == ("100", "2020", "0001", "en", "label")
    )
    assert exact.continuidad_id is None
    assert exact.identity_scope == "revision_occurrence"
    assert exact.canonical_key == "modelo/100/revision/2020/casilla/0001/label"

    grounded = next(
        candidate
        for candidate in candidates.candidates
        if candidate.continuidad_id == "irpf.inmueble.porcentaje-propiedad"
        and candidate.locale == "en"
        and candidate.field == "label"
    )
    assert grounded.identity_scope == "continuity"
    assert grounded.canonical_key == ("modelo/100/casilla/continuidad/irpf.inmueble.porcentaje-propiedad/label")
    assert "/en/" not in grounded.canonical_key


def test_canonical_candidate_rejects_identity_key_mismatch() -> None:
    """A candidate cannot promote an address that differs from declared identity."""
    with pytest.raises(ValidationError, match="canonical_key does not match"):
        CanonicalOccurrenceCandidate(
            modelo_id="100",
            revision_id="2020",
            casilla_id="0001",
            locale="en",
            field="label",
            value="Contribuyente que obtiene los rendimientos",
            resolution="official_spanish",
            identity_scope="revision_occurrence",
            canonical_key="modelo/100/casilla/continuidad/guessed/label",
        )
