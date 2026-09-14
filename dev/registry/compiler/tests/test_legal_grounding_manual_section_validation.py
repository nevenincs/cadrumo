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

from ..legal_grounding import _validate_manual_legal_reference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VALIDATION_MESSAGE = "manual section JSON validation failed"


def _reference(corpus_ref: str) -> LegalReference:
    return LegalReference(
        id="manual-iva-2024:seccion-1",
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="aeat",
        kind="manual",
        corpus_ref=corpus_ref,
        document_id="manual-iva-2024",
        permalink="https://sede.agenciatributaria.gob.es/manual-iva-2024",
        effective_from=date(2024, 1, 1),
        review_status="operator_reviewed",
        reviewed_at=date(2024, 2, 1),
        reviewed_by="operator",
        required_text=("Seccion 1",),
    )


def test_malformed_manual_section_json_is_reported_as_a_validation_failure(tmp_path: Path) -> None:
    section = tmp_path / "section.json"
    section.write_text('{"heading": "Seccion 1"}', encoding="utf-8")

    with pytest.raises(RegistryValidationError) as caught:
        _validate_manual_legal_reference(_reference("section.json#seccion-1"), tmp_path)

    assert _VALIDATION_MESSAGE in str(caught.value)
    assert "manual-iva-2024:seccion-1" in str(caught.value)


def test_undecodable_manual_section_file_propagates_with_its_own_type(tmp_path: Path) -> None:
    section = tmp_path / "section.json"
    section.write_bytes(b"\xff\xfe\x00binary payload")

    with pytest.raises(UnicodeDecodeError) as caught:
        _validate_manual_legal_reference(_reference("section.json#seccion-1"), tmp_path)

    assert _VALIDATION_MESSAGE not in str(caught.value)


def test_absent_manual_section_file_is_not_checked(tmp_path: Path) -> None:
    _validate_manual_legal_reference(_reference("missing-section.json#seccion-1"), tmp_path)
