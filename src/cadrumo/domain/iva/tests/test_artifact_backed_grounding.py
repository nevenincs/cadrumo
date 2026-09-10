"""IVA grounding consumes the signed authority artifact at runtime."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ....core.ed25519_signing import Ed25519KeypairHex, generate_ed25519_keypair_hex
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
from ..schema import IvaCitation
from ..verify import _citation_issues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _article_90_reference() -> LegalReference:
    return LegalReference(
        id="ley-37-1992:art-90",
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


def _stage_catalogue_artifact(root: Path) -> Ed25519KeypairHex:
    keys = generate_ed25519_keypair_hex()
    artifact_path = root / "registry" / "authority" / "authority.json"
    artifact_path.parent.mkdir(parents=True)
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(),
            catalogues=RegistryCatalogues(legal={"ley-37-1992:art-90": _article_90_reference()}, sources={}),
            identity_digest="a4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f",
            evidence=AuthorityEvidenceProjection(
                legal=(
                    PublishedLegalEvidence(
                        legal_reference_id="ley-37-1992:art-90",
                        anchored_text=(
                            "Artículo 90. Tipo impositivo general. El Impuesto se exigirá al tipo del 21 por "
                            "ciento vigente en el momento del devengo."
                        ),
                        text_sha256=sha256_hex(
                            b"Art\xc3\xadculo 90. Tipo impositivo general. El Impuesto se exigir\xc3\xa1 al tipo del 21 por "
                            b"ciento vigente en el momento del devengo."
                        ),
                    ),
                )
            ),
        ),
        signing_private_key_hex=keys.private_key_hex,
    )
    return keys


def test_iva_rate_grounding_and_quotation_read_a_staged_signed_artifact_without_a_corpus_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rate citation and quotation work when only the signed artifact is installed."""
    keys = _stage_catalogue_artifact(tmp_path)
    monkeypatch.setattr(authority_module, "_bundled_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(authority_module, "_BUNDLED_AUTHORITY_VERIFICATION_PUBLIC_KEY_HEX", keys.public_key_hex)

    legal, _sources = registry_catalogues()
    verify_table_legal_refs("staged IVA rate", (("es/general/2025-01-01", ("ley-37-1992:art-90",)),))

    assert set(legal) == {"ley-37-1992:art-90"}
    assert not (tmp_path / "corpus").exists()
    assert not _citation_issues(
        IvaCitation(
            legal_reference="ley-37-1992:art-90",
            quoted_text="El Impuesto se exigira al tipo del 21 por ciento",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        ),
        category_id="test-rate",
        authority=authority_module.bundled_authority(),
    )


def test_iva_rate_grounding_refuses_a_signed_artifact_without_the_required_legal_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A legal catalogue entry alone cannot stand in for signed quotation evidence."""
    keys = generate_ed25519_keypair_hex()
    artifact_path = tmp_path / "registry" / "authority" / "authority.json"
    artifact_path.parent.mkdir(parents=True)
    write_authority_artifact(
        artifact_path,
        AuthorityArtifact(
            modelos=(),
            catalogues=RegistryCatalogues(legal={"ley-37-1992:art-90": _article_90_reference()}, sources={}),
            identity_digest="a4c712d347701b34615314b6e3f8fdfd75ca5ee3eabe9c1c651668549fb7f66f",
        ),
        signing_private_key_hex=keys.private_key_hex,
    )
    monkeypatch.setattr(authority_module, "_bundled_path", lambda *parts: tmp_path.joinpath(*parts))
    monkeypatch.setattr(authority_module, "_BUNDLED_AUTHORITY_VERIFICATION_PUBLIC_KEY_HEX", keys.public_key_hex)

    with pytest.raises(IvaCatalogueError, match="legal grounding verification failed"):
        verify_table_legal_refs("staged IVA rate", (("es/general/2025-01-01", ("ley-37-1992:art-90",)),))
