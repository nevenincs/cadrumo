"""Modelo 130 blank-box safety on adjudicated external layout candidates.

The two PDFs exercised here are third-party-hosted layout candidates, not
authenticated AEAT evidence.  Both are verified official-base derivatives whose
layout applies to registry revision ``2019-y-siguientes``, while their artifact
authenticity remains explicitly third-party and non-enrolled.  Their useful parser
signal is physical: both expose all 19 configured M130 box-number anchors while
leaving every value position blank.  The first assertion prevents an all-missing
result from passing vacuously because the form was unreadable; the second proves
the production extraction primitives classify those discovered blank boxes as
missing without fabricating an amount or degrading the document into malformed
or ambiguous outcomes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.schema_extraction import ExtractionProfileDefinition
from .....tests import FIXTURES_DIR
from .....tests.fixtures.external_layout_candidates.models import (
    external_layout_source_class_is_non_authoritative,
    load_external_layout_candidate,
)
from ..parser import (
    _classify_target,
    _extract_pages_words,
    _numeric_casilla_anchors,
    _partition_target_outcomes,
    _PdfWord,
    _printed_box_numbers,
    _select_extraction_profile,
    extract_pages_text,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_EXPECTED_BOX_IDS = tuple(f"{number:02d}" for number in range(1, 20))
_M130_CANDIDATE_ROOT = FIXTURES_DIR / "external_layout_candidates" / "130"
_M130_SIDECARS = tuple(_M130_CANDIDATE_ROOT / f"{kind}.json" for kind in ("plain", "fillable"))


def _physical_box_match_counts(
    pages_words: tuple[list[_PdfWord], ...],
    *,
    profile: ExtractionProfileDefinition,
) -> dict[str, int]:
    """Count physical box-number words inside each target's configured anchor range."""
    counts: dict[str, int] = {}
    for target in profile.target_casillas:
        assert target.match_strategy == "bbox_anchored"
        assert target.bbox_anchor is not None
        anchor = target.bbox_anchor
        pattern = re.compile(anchor.box_number_pattern)
        counts[str(target.casilla_id)] = sum(
            1
            for words in pages_words
            for word in words
            if pattern.fullmatch(word["text"])
            and (anchor.anchor_x_min is None or word["x0"] >= anchor.anchor_x_min)
            and (anchor.anchor_x_max is None or word["x0"] <= anchor.anchor_x_max)
        )
    return counts


@pytest.mark.parametrize("sidecar_path", _M130_SIDECARS, ids=lambda path: path.stem)
def test_m130_external_blank_layout_discovers_every_box_without_fabricating_values(
    sidecar_path: Path,
) -> None:
    """All 19 physical boxes are present and classify only as missing."""
    candidate = load_external_layout_candidate(sidecar_path)
    assert candidate.modelo == "130"
    adjudication = candidate.authority_adjudication
    assert adjudication.artifact_authenticity.verdict == "third_party_sample"
    assert adjudication.official_base_derivation.verdict == "verified_official_base_derivative"
    assert adjudication.registry_applicability.verdict == "current_authored_revision"
    assert adjudication.registry_applicability.revision_id == "2019-y-siguientes"
    assert external_layout_source_class_is_non_authoritative()

    pdf_path = sidecar_path.with_suffix(".pdf")
    assert pdf_path.is_file(), f"{pdf_path} is missing, so the external-layout regression proves nothing"

    snapshot = bundled_authority().snapshot("130", filing_year=2026, period="1T")
    profile = _select_extraction_profile(snapshot, extraction_profile_id=None)
    assert tuple(str(target.casilla_id) for target in profile.target_casillas) == _EXPECTED_BOX_IDS

    pages_words = _extract_pages_words(pdf_path)
    assert pages_words and any(pages_words), f"{pdf_path.name}: no physical PDF words were extracted"
    assert _physical_box_match_counts(pages_words, profile=profile) == dict.fromkeys(_EXPECTED_BOX_IDS, 1)

    pages = extract_pages_text(pdf_path)
    outcomes = _partition_target_outcomes(
        _classify_target(
            target,
            pages=pages,
            pages_words=pages_words,
            numeric_anchors=_numeric_casilla_anchors(profile, snapshot.revision),
            printed_box_numbers=_printed_box_numbers(profile, snapshot.revision),
        )
        for target in profile.target_casillas
    )

    assert tuple(str(casilla_id) for casilla_id in outcomes.missing) == _EXPECTED_BOX_IDS
    assert outcomes.values == []
    assert outcomes.malformed == []
    assert outcomes.ambiguous == []
