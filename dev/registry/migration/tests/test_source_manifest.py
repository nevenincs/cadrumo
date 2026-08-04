"""Real-behavior tests for the sealed migration source manifest."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.resources import bundled_path
from dev.registry.migration import (
    SourceManifest,
    build_source_inventory,
    build_source_manifest,
    build_unresolved_review_register,
    classify_canonical_occurrence_candidates,
    extract_resolved_localization_matrix,
    fingerprint_registry_corpus,
    generate_canonical_occurrence_candidates,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def bundled_source_manifest() -> tuple[Path, SourceManifest]:
    """Build the manifest from the real bundled registry compiler and corpus."""
    root = bundled_path("registry", "aeat")
    inventory = build_source_inventory(root)
    matrix = extract_resolved_localization_matrix(root, inventory)
    classified = classify_canonical_occurrence_candidates(
        generate_canonical_occurrence_candidates(matrix),
    )
    return root, build_source_manifest(root, classified, inventory)


def test_bundled_source_manifest_seals_all_observations_without_emission(
    bundled_source_manifest: tuple[Path, SourceManifest],
) -> None:
    """The manifest records the measured source boundary and unresolved queue."""
    root, manifest = bundled_source_manifest
    review = build_unresolved_review_register(manifest)

    assert manifest.entry_count == 126_192
    assert manifest.grounded_count == 144
    assert manifest.revision_exact_count == 32_008
    assert manifest.continuity_candidate_count == 94_040
    assert manifest.unresolved_entry_count == 94_040
    assert manifest.source_file_count == 12_944
    assert manifest.manifest_sha256 == "48dcec377463ba3f801d300299d87b11bacd2384b1d005d4d03030b05e4d7508"

    assert review.entry_count == 94_040
    assert review.group_count == 2_354
    assert review.register_sha256 == "bf3deab6777fecaff70158de926dce28737a390f2f643207efb6b8aeedc000b2"
    assert review.source_manifest_sha256 == manifest.manifest_sha256

    assert Counter(entry.leaf_state for entry in manifest.entries) == Counter(
        {
            "absent": 84_084,
            "authored": 32_607,
            "mirrored": 9_453,
            "key_echo": 48,
        },
    )
    assert Counter(entry.source_scope for entry in manifest.entries) == Counter(
        {
            "none": 46_758,
            "schema": 37_326,
            "revision_locale": 42_033,
            "modelo_locale": 75,
        },
    )
    assert all(entry.emitted_target is None for entry in manifest.entries)
    assert all(entry.source_path is None or entry.source_hash is not None for entry in manifest.entries)
    assert all(entry.candidate.candidate.continuidad_id is None for entry in review.entries)

    before = fingerprint_registry_corpus(root)
    assert before == manifest.corpus_fingerprint
    assert fingerprint_registry_corpus(root) == before


def test_source_manifest_preserves_real_fallback_provenance_and_seal_validation(
    bundled_source_manifest: tuple[Path, SourceManifest],
) -> None:
    """A fallback keeps the schema source while a localized leaf keeps its locale source."""
    _root, manifest = bundled_source_manifest

    def find(revision_id: str, locale: str, field: str):
        return next(
            entry
            for entry in manifest.entries
            if (
                entry.candidate.candidate.modelo_id,
                entry.candidate.candidate.revision_id,
                entry.candidate.candidate.casilla_id,
                entry.candidate.candidate.locale,
                entry.candidate.candidate.field,
            )
            == ("100", revision_id, "0001", locale, field)
        )

    fallback = find("2020", "en", "label")
    assert fallback.official_fallback
    assert fallback.source_scope == "schema"
    assert fallback.source_path == "modelos/100/revisions/2020/casillas/0001-0001.toml"
    assert fallback.raw_value == fallback.old_resolved_value
    assert fallback.leaf_state == "absent"
    assert fallback.review_status == "unresolved"

    localized = find("2024", "en", "label")
    assert not localized.official_fallback
    assert localized.source_scope == "revision_locale"
    assert localized.source_path == "modelos/100/revisions/2024/locales/en/001-labels.toml"
    assert localized.raw_value == localized.old_resolved_value
    assert localized.leaf_state == "authored"
    assert localized.normalized_value_hash is not None

    tampered = manifest.model_dump(mode="python")
    tampered["manifest_sha256"] = "0" * 64
    with pytest.raises(ValidationError, match="manifest_sha256"):
        SourceManifest.model_validate(tampered)
