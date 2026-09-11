"""IVA grounding consumes the published authority artifact at runtime."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ....core.hashing import sha256_hex
from ...calculations.registry import authority as authority_module
from ...calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    write_authority_artifact,
)
from ...calculations.registry.schema import RegistryCatalogues
from ...calculations.registry.schema_base import EvidenceTier
from ...calculations.registry.schema_references import LegalReference
from .._grounding import registry_catalogues, verify_table_legal_refs
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


def _stage_catalogue_artifact(root: Path, anchored_text: str) -> None:
    artifact_path = root / "registry" / "authority" / "authority.json"
    artifact_path.parent.mkdir(parents=True)
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(),
            catalogues=RegistryCatalogues(legal={_ARTICLE_90: _article_90_reference()}, sources={}),
            identity_digest="a4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f",
            evidence=AuthorityEvidenceProjection(
                legal=(
                    PublishedLegalEvidence(
                        legal_reference_id=_ARTICLE_90,
                        anchored_text=anchored_text,
                        text_sha256=sha256_hex(anchored_text.encode("utf-8")),
                    ),
                )
            ),
        ),
    )


def _use_staged_package(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    """Point the runtime's package-resource seam at ``root`` for the authority artifact only."""
    package_data_root = authority_module._bundled_path()

    def staged_path(*parts: str) -> Path:
        if parts[:2] == ("registry", "authority"):
            return root.joinpath(*parts)
        return package_data_root.joinpath(*parts)

    monkeypatch.setattr(authority_module, "_bundled_path", staged_path)
    return package_data_root


def test_iva_grounding_reads_its_legal_basis_from_a_staged_published_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rate citation validates against artifact catalogues and evidence, not corpus files."""
    _stage_catalogue_artifact(tmp_path, _ARTICLE_90_TEXT)
    package_data_root = _use_staged_package(monkeypatch, tmp_path)

    legal, _sources, source_root = registry_catalogues()
    verify_table_legal_refs("iva rates", [("ES general 21", (_ARTICLE_90,))])

    assert set(legal) == {_ARTICLE_90}
    assert source_root == package_data_root


def test_iva_grounding_refuses_a_citation_the_published_evidence_does_not_support(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anchor text lacking a declared clause, or an uncatalogued citation, is refused."""
    _stage_catalogue_artifact(tmp_path, "el impuesto se exigira al tipo impositivo general del 10 por ciento.")
    _use_staged_package(monkeypatch, tmp_path)

    with pytest.raises(IvaCatalogueError, match="missing required text '21 por ciento'"):
        verify_table_legal_refs("iva rates", [("ES general 21", (_ARTICLE_90,))])
    with pytest.raises(IvaCatalogueError, match="unknown legal_ref 'ley-37-1992:art-91'"):
        verify_table_legal_refs("iva rates", [("ES reducido", ("ley-37-1992:art-91",))])
