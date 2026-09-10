"""IVA grounding consumes the signed authority artifact at runtime."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.ed25519_signing import Ed25519KeypairHex, generate_ed25519_keypair_hex
from ...calculations.registry import authority as authority_module
from ...calculations.registry.authority_artifact import AuthorityArtifact, write_authority_artifact
from ...calculations.registry.schema import RegistryCatalogues
from ...calculations.registry.schema_base import EvidenceTier
from ...calculations.registry.schema_references import LegalReference
from .._grounding import registry_catalogues
from ..rates import _verify_rate_grounding
from ..schema import EUMemberState, IvaRateKind, IvaRateRecord

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
        ),
        signing_private_key_hex=keys.private_key_hex,
    )
    return keys


def test_iva_rate_grounding_reads_its_legal_basis_from_a_staged_signed_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rate validates against artifact catalogues while corpus evidence stays package-owned."""
    keys = _stage_catalogue_artifact(tmp_path)
    package_data_root = authority_module._bundled_path()

    def staged_path(*parts: str) -> Path:
        if parts[:2] == ("registry", "authority"):
            return tmp_path.joinpath(*parts)
        return package_data_root.joinpath(*parts)

    monkeypatch.setattr(authority_module, "_bundled_path", staged_path)
    monkeypatch.setattr(authority_module, "_BUNDLED_AUTHORITY_VERIFICATION_PUBLIC_KEY_HEX", keys.public_key_hex)

    legal, _sources, source_root = registry_catalogues()
    _verify_rate_grounding(
        {
            EUMemberState.ES: (
                IvaRateRecord(
                    member_state=EUMemberState.ES,
                    kind=IvaRateKind.GENERAL,
                    pct=Decimal("21"),
                    effective_from=date(2025, 1, 1),
                    legal_refs=("ley-37-1992:art-90",),
                ),
            )
        }
    )

    assert set(legal) == {"ley-37-1992:art-90"}
    assert source_root == package_data_root
