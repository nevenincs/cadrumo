"""Real-corpus tests for the pre-emission review contract."""

from __future__ import annotations

from collections import Counter

import pytest
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from dev.registry.migration import (
    PreEmissionReviewRegister,
    build_pre_emission_review_register,
    build_source_inventory,
    build_source_manifest,
    classify_canonical_occurrence_candidates,
    extract_resolved_localization_matrix,
    generate_canonical_occurrence_candidates,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def pre_emission_review() -> PreEmissionReviewRegister:
    """Build the review register from the current real registry loader."""
    root = bundled_path("registry", "aeat")
    inventory = build_source_inventory(root)
    matrix = extract_resolved_localization_matrix(root, inventory)
    classified = classify_canonical_occurrence_candidates(
        generate_canonical_occurrence_candidates(matrix),
    )
    manifest = build_source_manifest(root, classified, inventory)
    return build_pre_emission_review_register(manifest)


def test_real_review_register_prioritizes_placeholders_and_reconstructs_year_labels(
    pre_emission_review: PreEmissionReviewRegister,
) -> None:
    """The real corpus receives explicit parity and canonicalization decisions."""
    assert pre_emission_review.placeholder_entry_count == 9_501
    assert pre_emission_review.placeholder_delete_count == 9_501
    assert pre_emission_review.mirrored_help_count == 9_453
    assert pre_emission_review.mirrored_help_debt_count == 9_477
    assert pre_emission_review.help_key_echo_count == 24
    assert pre_emission_review.label_key_echo_count == 24
    assert pre_emission_review.key_echo_count == 48
    assert all(
        item.field == "help" for item in pre_emission_review.placeholder_entries if item.leaf_state == "mirrored"
    )
    assert Counter(item.parity for item in pre_emission_review.placeholder_entries) == Counter(
        {"preserve_old_value": 9_501},
    )
    assert Counter(item.canonicalization for item in pre_emission_review.placeholder_entries) == Counter(
        {"delete_not_migrate": 9_501},
    )

    vivienda = next(
        entry
        for entry in pre_emission_review.year_entries
        if entry.modelo_id == "100" and "vivienda habitual" in entry.template.casefold()
    )
    assert "vivienda habitual" in vivienda.template.casefold()
    assert "{year}" in vivienda.template
    assert vivienda.source_resolution == "official_spanish"
    assert {item.year for item in vivienda.revisions} >= {"2020", "2021"}
    assert all(vivienda.template.replace("{year}", item.year) == item.rendered_value for item in vivienda.revisions)
    assert all(item.parity == "compare_rendered_value" for item in pre_emission_review.year_entries)

    tampered = pre_emission_review.model_dump(mode="python")
    tampered["review_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="review_sha256"):
        PreEmissionReviewRegister.model_validate(tampered)
