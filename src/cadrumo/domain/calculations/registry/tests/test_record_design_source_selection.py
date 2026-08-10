"""Real-binary tests for fail-closed record-design source selection."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._corpus_catalogue import resolve_record_design_binary
from .._errors import RegistryValidationError
from .._schema import SourceReference
from ._catalogue_verification_support import _catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_resolves_the_hash_pinned_modelo_200_2025_binary() -> None:
    sources = _catalogues().sources

    resolved = resolve_record_design_binary(
        bundled_path(),
        sources,
        source_ref="aeat-dr-200-2025",
        filing_year=2025,
        design_epoch="2025",
    )

    assert resolved.source.id == "aeat-dr-200-2025"
    assert resolved.source.record_design_epoch == "2025"
    assert resolved.path.is_file()


def test_rejects_an_exact_design_that_does_not_apply_to_the_filing_year() -> None:
    with pytest.raises(RegistryValidationError, match="does not apply to filing year 2025"):
        resolve_record_design_binary(
            bundled_path(),
            _catalogues().sources,
            source_ref="aeat-dr-200-2024",
            filing_year=2025,
            design_epoch="2024",
        )


def test_rejects_a_hash_drifting_selected_binary() -> None:
    sources = _catalogues().sources
    source = sources["aeat-dr-200-2025"]
    drifting_source = SourceReference.model_validate(
        {**source.model_dump(mode="python"), "sha256": "0" * 64},
    )

    with pytest.raises(RegistryValidationError, match="sha256 mismatch"):
        resolve_record_design_binary(
            bundled_path(),
            {str(drifting_source.id): drifting_source},
            source_ref="aeat-dr-200-2025",
            filing_year=2025,
            design_epoch="2025",
        )


def test_rejects_a_selection_without_a_catalogue_epoch() -> None:
    with pytest.raises(RegistryValidationError, match="does not declare a design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            _catalogues().sources,
            source_ref="aeat-dr-720",
            filing_year=2025,
            design_epoch="2025",
        )


def test_rejects_a_blank_requested_design_epoch() -> None:
    with pytest.raises(RegistryValidationError, match="requires a non-blank design epoch"):
        resolve_record_design_binary(
            bundled_path(),
            _catalogues().sources,
            source_ref="aeat-dr-200-2025",
            filing_year=2025,
            design_epoch="   ",
        )
