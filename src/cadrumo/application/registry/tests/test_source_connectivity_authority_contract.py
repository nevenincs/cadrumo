"""Focused contracts for live source-connectivity authority dependencies."""

from __future__ import annotations

from hashlib import sha256

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind
from ...aggregation import BindingSourceDisposition
from .. import (
    LiveSourceConnectivityProofAuthority,
    LiveSourceResolverCatalogue,
    LiveSourceResolverEnrollment,
    RepositoryEvidenceDigestVerifier,
    RepositoryRootEvidenceDigestVerifier,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _enrollment(
    source_kind: BindingSourceKind,
    resolver_id: str,
    *,
    disposition: BindingSourceDisposition = BindingSourceDisposition.ENROLLED,
) -> LiveSourceResolverEnrollment:
    return LiveSourceResolverEnrollment(
        source_kind=source_kind,
        resolver_id=resolver_id,
        disposition=disposition,
    )


def test_live_source_resolver_catalogue_is_exact_unique_and_deterministic() -> None:
    collectible = _enrollment(BindingSourceKind.COLLECTIBLE_INVOICE, "invoice-source-resolver")
    foreign = _enrollment(BindingSourceKind.FOREIGN_ASSET, "foreign-asset-source-resolver")
    catalogue = LiveSourceResolverCatalogue(enrollments=(collectible, foreign))

    assert catalogue.enrollment_for(BindingSourceKind.COLLECTIBLE_INVOICE) == collectible
    assert catalogue.enrollment_for(BindingSourceKind.PROFILE) is None
    with pytest.raises(ValidationError, match="unique source kinds"):
        LiveSourceResolverCatalogue(enrollments=(collectible, collectible))
    with pytest.raises(ValidationError, match="deterministic source-kind order"):
        LiveSourceResolverCatalogue(enrollments=(foreign, collectible))


def test_repository_digest_verifier_is_deterministic_and_root_contained(tmp_path) -> None:
    repository_root = tmp_path / "repository"
    evidence_path = repository_root / "src" / "cadrumo" / "tests" / "test_evidence.py"
    evidence_path.parent.mkdir(parents=True)
    evidence_bytes = b"def test_evidence():\n    assert True\n"
    evidence_path.write_bytes(evidence_bytes)
    outside_path = tmp_path / "outside.py"
    outside_path.write_bytes(b"outside")
    verifier = RepositoryRootEvidenceDigestVerifier(repository_root=repository_root)

    expected = sha256(evidence_bytes).hexdigest()
    assert verifier.digest("src/cadrumo/tests/test_evidence.py") == expected
    assert verifier.digest("src/cadrumo/tests/test_evidence.py:1") == expected
    assert verifier.digest("../outside.py") is None
    assert verifier.digest(str(outside_path)) is None
    assert verifier.digest("src/cadrumo/tests/missing.py") is None


def test_registry_facade_exposes_authority_and_injected_verifier_port() -> None:
    from .. import __all__

    assert {
        "LiveSourceConnectivityProofAuthority",
        "LiveSourceResolverCatalogue",
        "LiveSourceResolverEnrollment",
        "RepositoryEvidenceDigestVerifier",
        "RepositoryRootEvidenceDigestVerifier",
    } <= set(__all__)
    assert isinstance(RepositoryRootEvidenceDigestVerifier, type)
    assert isinstance(LiveSourceConnectivityProofAuthority, type)
    assert RepositoryEvidenceDigestVerifier.__name__ == "RepositoryEvidenceDigestVerifier"
