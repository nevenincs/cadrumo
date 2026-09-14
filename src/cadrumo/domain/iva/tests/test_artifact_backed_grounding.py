"""IVA grounding consumes the published authority artifact at runtime."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.hashing import sha256_hex
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.authority_artifact import (
    AuthorityComponentKind,
    EvidenceComponentQuery,
    PublishedLegalEvidence,
    ReferenceComponentQuery,
)
from ...calculations.registry.schema_base import EvidenceTier
from ...calculations.registry.schema_references import LegalReference
from ...calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader
from .._grounding import verify_table_legal_refs
from ..errors import IvaCatalogueError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ARTICLE_90 = "ley-37-1992:art-90"
#: Anchor text as the publisher projects it: normalised, casefolded, diacritics folded.
_ARTICLE_90_TEXT = (
    "el impuesto se exigira al tipo impositivo general del 21 por ciento, salvo lo dispuesto en el "
    "articulo siguiente. el tipo impositivo aplicable a cada operacion sera el vigente en el momento del devengo."
)


def _article_90_reference() -> LegalReference:
    return LegalReference(
        id=_ARTICLE_90,
        evidence_tier=EvidenceTier.LEGAL_AUTHORITY,
        authority="boe",
        kind="ley",
        corpus_ref="corpus/normatives/html/ley-37-1992-art-90.html#a90",
        document_id="BOE-A-1992-28740",
        article="90",
        permalink="https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740#a90",
        published_at=date(1992, 12, 29),
        effective_from=date(1993, 1, 1),
        review_status="operator_reviewed",
        reviewed_at=date(2026, 5, 7),
        reviewed_by="test publisher",
        required_text=("Tipo impositivo general", "21 por ciento", "vigente en el momento del devengo"),
    )


def _operation(anchored_text: str) -> PinnedAuthorityOperation:
    """Build a pinned evidence fixture without an eager catalogue or JSON seam."""
    reference = _article_90_reference()
    query = ReferenceComponentQuery(_ARTICLE_90, AuthorityComponentKind.LEGAL_REFERENCE)
    evidence_query = EvidenceComponentQuery(_ARTICLE_90, AuthorityComponentKind.LEGAL_EVIDENCE)
    reader = FakeAuthorityComponentReader(
        {
            query: reference,
            evidence_query: PublishedLegalEvidence(
                legal_reference_id=_ARTICLE_90,
                anchored_text=anchored_text,
                text_sha256=sha256_hex(anchored_text.encode("utf-8")),
            ),
        }
    )
    return PinnedAuthorityOperation(reader, reader.pin())


def test_iva_grounding_reads_its_legal_basis_from_a_pinned_published_operation() -> None:
    """A rate citation validates against addressed authority evidence, not corpus files."""
    operation = _operation(_ARTICLE_90_TEXT)
    verify_table_legal_refs("iva rates", [("ES general 21", (_ARTICLE_90,))], operation=operation)


def test_iva_grounding_refuses_a_citation_the_published_evidence_does_not_support() -> None:
    """Anchor text lacking a declared clause, or an uncatalogued citation, is refused."""
    operation = _operation("el impuesto se exigira al tipo impositivo general del 10 por ciento.")

    with pytest.raises(IvaCatalogueError, match="missing required text '21 por ciento'"):
        verify_table_legal_refs("iva rates", [("ES general 21", (_ARTICLE_90,))], operation=operation)
    with pytest.raises(IvaCatalogueError, match="unknown legal_ref 'ley-37-1992:art-91'"):
        verify_table_legal_refs(
            "iva rates",
            [("ES reducido", ("ley-37-1992:art-91",))],
            operation=operation,
        )
