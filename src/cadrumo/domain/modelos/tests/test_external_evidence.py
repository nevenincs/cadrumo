"""Direct pydantic tests for ``ExternalEvidence`` strict invariants."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ..filing_record import (
    ExternalEvidence,
    ExternalEvidenceKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_IMPORTED_AT = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


def test_external_evidence_accepts_every_declared_kind() -> None:
    for kind in ExternalEvidenceKind:
        evidence = ExternalEvidence(kind=kind, reference_id="JUST-001", imported_at=_IMPORTED_AT)
        assert evidence.kind is kind


def test_external_evidence_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError, match="kind"):
        ExternalEvidence.model_validate(
            {"kind": "aeat_unknown_kind", "reference_id": "JUST-001", "imported_at": _IMPORTED_AT},
        )


def test_external_evidence_rejects_blank_reference_id() -> None:
    with pytest.raises(ValidationError, match=r"reference_id|min_length|length"):
        ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="",
            imported_at=_IMPORTED_AT,
        )


def test_external_evidence_strips_whitespace_in_reference_id() -> None:
    evidence = ExternalEvidence(
        kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        reference_id="  JUST-001  ",
        imported_at=_IMPORTED_AT,
    )
    assert evidence.reference_id == "JUST-001"


def test_external_evidence_rejects_reference_id_above_max_length() -> None:
    with pytest.raises(ValidationError, match=r"too_long|at most"):
        ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="x" * 129,
            imported_at=_IMPORTED_AT,
        )


def test_external_evidence_is_frozen_and_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match=r"extra_forbidden|Extra inputs"):
        ExternalEvidence.model_validate(
            {
                "kind": ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                "reference_id": "JUST-001",
                "imported_at": _IMPORTED_AT,
                "extra": "not allowed",
            },
        )

    evidence = ExternalEvidence(
        kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
        reference_id="JUST-001",
        imported_at=_IMPORTED_AT,
    )
    attr = "reference_id"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(evidence, attr, "JUST-002")
