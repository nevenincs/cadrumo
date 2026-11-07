"""The manual-section check reports only manual section JSON validation failures.

A file the compiler cannot even decode as text is not a schema violation, so it
must keep its own type and message instead of being relabelled as a failed
manual section validation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import EvidenceTier
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..legal_grounding import validate_manual_legal_reference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VALIDATION_MESSAGE = "manual section JSON validation failed"
_YEAR = filing_year_envelope().horizon


def _reference(corpus_ref: str) -> LegalReference:
    return LegalReference(
        id=f"manual-iva-{_YEAR}:seccion-1",
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="aeat",
        kind="manual",
        corpus_ref=corpus_ref,
        document_id=f"manual-iva-{_YEAR}",
        permalink=f"https://sede.agenciatributaria.gob.es/manual-iva-{_YEAR}",
        effective_from=date(_YEAR, 1, 1),
        review_status="operator_reviewed",
        reviewed_at=date(_YEAR, 2, 1),
        reviewed_by="operator",
        required_text=("Seccion 1",),
    )


def test_malformed_manual_section_json_is_reported_as_a_validation_failure(tmp_path: Path) -> None:
    section = tmp_path / "section.json"
    section.write_text('{"heading": "Seccion 1"}', encoding="utf-8")

    with pytest.raises(RegistryValidationError) as caught:
        validate_manual_legal_reference(_reference("section.json#seccion-1"), tmp_path)

    assert _VALIDATION_MESSAGE in str(caught.value)
    assert f"manual-iva-{_YEAR}:seccion-1" in str(caught.value)


def test_undecodable_manual_section_file_propagates_with_its_own_type(tmp_path: Path) -> None:
    section = tmp_path / "section.json"
    section.write_bytes(b"\xff\xfe\x00binary payload")

    with pytest.raises(UnicodeDecodeError) as caught:
        validate_manual_legal_reference(_reference("section.json#seccion-1"), tmp_path)

    assert _VALIDATION_MESSAGE not in str(caught.value)


def test_absent_manual_section_file_is_not_checked(tmp_path: Path) -> None:
    validate_manual_legal_reference(_reference("missing-section.json#seccion-1"), tmp_path)
