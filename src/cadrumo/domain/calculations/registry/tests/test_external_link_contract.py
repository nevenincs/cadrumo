"""Real contract tests for registry legal and source evidence links."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .....tests.aeat_literal_fixtures import AEAT_NONCANONICAL_HTTP_MANUAL_URL_CANARY
from .._errors import RegistryValidationError
from .._legal import verify_legal_reference
from .._schema_references import LegalReference, SourceReference

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _legal_reference_payload() -> dict[str, object]:
    return {
        "id": "ley-58-2003:art-1",
        "evidence_tier": "legal_authority",
        "authority": "boe",
        "kind": "ley",
        "corpus_ref": "corpus/normatives/html/ley-58-2003.html#a1",
        "document_id": "BOE-A-2003-23186",
        "permalink": "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a1",
        "effective_from": date(2004, 1, 1),
        "required_text": ("Artículo 1",),
    }


def test_pending_legal_reference_refuses_review_claims() -> None:
    payload = _legal_reference_payload() | {
        "review_status": "pending_review",
        "reviewed_at": date(2026, 8, 1),
        "reviewed_by": "pending operator re-stamp",
    }

    with pytest.raises(ValidationError, match="pending legal reference must not declare"):
        LegalReference.model_validate(payload)


@pytest.mark.parametrize("review_status", ("agent_reviewed", "operator_reviewed"))
def test_reviewed_legal_reference_requires_typed_provenance(review_status: str) -> None:
    payload = _legal_reference_payload() | {"review_status": review_status}

    with pytest.raises(ValidationError, match="requires reviewed_by and reviewed_at"):
        LegalReference.model_validate(payload)


def test_agent_review_cannot_supply_filing_grade_authority() -> None:
    reference = LegalReference.model_validate(
        _legal_reference_payload()
        | {
            "review_status": "agent_reviewed",
            "reviewed_at": date(2026, 8, 1),
            "reviewed_by": "agent-review",
        },
    )

    with pytest.raises(RegistryValidationError, match="filing-grade authority requires operator_reviewed"):
        verify_legal_reference(reference)


def test_legal_reference_preserves_https_permalink_fragment() -> None:
    reference = LegalReference(
        id="ley-58-2003:art-1",
        evidence_tier="legal_authority",
        authority="boe",
        kind="ley",
        corpus_ref="corpus/normatives/html/ley-58-2003.html#a1",
        document_id="BOE-A-2003-23186",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a1",
        effective_from=date(2004, 1, 1),
        review_status="operator_reviewed",
        reviewed_at=date(2026, 8, 1),
        reviewed_by="registry reviewer",
        required_text=("Artículo 1",),
    )

    assert str(reference.permalink) == "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a1"


@pytest.mark.parametrize("permalink", ("not-a-url", "http://www.boe.es/act"))
def test_legal_reference_refuses_noncanonical_permalink(permalink: str) -> None:
    with pytest.raises(ValidationError, match="permalink"):
        LegalReference(
            id="ley-58-2003:art-1",
            evidence_tier="legal_authority",
            authority="boe",
            kind="ley",
            corpus_ref="corpus/normatives/html/ley-58-2003.html#a1",
            document_id="BOE-A-2003-23186",
            permalink=permalink,
            effective_from=date(2004, 1, 1),
            review_status="operator_reviewed",
            reviewed_at=date(2026, 8, 1),
            reviewed_by="registry reviewer",
            required_text=("Artículo 1",),
        )


@pytest.mark.parametrize("source_url", ("not-a-url", AEAT_NONCANONICAL_HTTP_MANUAL_URL_CANARY))
def test_source_reference_refuses_noncanonical_source_url(source_url: str) -> None:
    with pytest.raises(ValidationError, match="source_url"):
        SourceReference(
            id="aeat-manual-2025",
            evidence_tier="official_source_guidance",
            authority="aeat",
            kind="manual_pdf",
            corpus_path="aeat/manuals/manual-2025.pdf",
            sha256="a" * 64,
            bytes=1,
            retrieved_at=date(2026, 8, 1),
            source_url=source_url,
            review_status="reviewed",
        )
