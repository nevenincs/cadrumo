"""Focused contracts for live source-connectivity authority dependencies."""

from __future__ import annotations

from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

from ....core import BindingSourceKind, SourceConnectivityConnectionIdentity
from ....domain.modelos import CalculationSourceRef
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


class _RevisionRepository:
    def __init__(self, revision: object) -> None:
        self._revision = revision

    def exists(self) -> bool:
        return True

    def load(self) -> object:
        return SimpleNamespace(revisions={self._revision.calculation_revision_id: self._revision})


def test_encrypted_revision_match_is_not_tautological_over_resolver_identity() -> None:
    revision_id = "a" * 64
    persisted = CalculationSourceRef(
        resolver_id="invoice-source-resolver",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE.value,
        binding_source=BindingSourceKind.COLLECTIBLE_INVOICE,
        source_ref="collectible_invoice:inv-0001",
        fingerprint="sha256:" + "b" * 64,
    )
    revision = SimpleNamespace(calculation_revision_id=revision_id, source_provenance=(persisted,))
    authority = LiveSourceConnectivityProofAuthority(
        source_resolvers=cast(Any, object()),
        workflows=cast(Any, object()),
        calculation_revisions=cast(Any, _RevisionRepository(revision)),
        evidence_verifier=cast(Any, object()),
    )
    connection = SourceConnectivityConnectionIdentity(
        candidate_id="invoice.collectible",
        source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
        source_ref=persisted.source_ref,
        resolver_id=persisted.resolver_id,
        calculation_revision_id=revision_id,
    )

    def proof(asserted_connection: SourceConnectivityConnectionIdentity) -> object:
        return SimpleNamespace(
            connection=asserted_connection,
            persisted_source_identity=persisted.source_ref,
            persisted_source_fingerprint=persisted.fingerprint,
        )

    assert authority.encrypted_revision_matches(cast(Any, proof(connection)))
    assert not authority.encrypted_revision_matches(
        cast(Any, proof(connection.model_copy(update={"resolver_id": "wrong-resolver"}))),
    )

    rival = persisted.model_copy(update={"resolver_id": "rival-resolver"})
    ambiguous_revision = SimpleNamespace(
        calculation_revision_id=revision_id,
        source_provenance=(persisted, rival),
    )
    ambiguous_authority = LiveSourceConnectivityProofAuthority(
        source_resolvers=cast(Any, object()),
        workflows=cast(Any, object()),
        calculation_revisions=cast(Any, _RevisionRepository(ambiguous_revision)),
        evidence_verifier=cast(Any, object()),
    )
    assert not ambiguous_authority.encrypted_revision_matches(cast(Any, proof(connection)))

    incoherent = CalculationSourceRef.model_construct(
        **{
            **persisted.model_dump(),
            "source_kind": BindingSourceKind.PAYABLE_INVOICE.value,
        },
    )
    incoherent_revision = SimpleNamespace(
        calculation_revision_id=revision_id,
        source_provenance=(incoherent,),
    )
    incoherent_authority = LiveSourceConnectivityProofAuthority(
        source_resolvers=cast(Any, object()),
        workflows=cast(Any, object()),
        calculation_revisions=cast(Any, _RevisionRepository(incoherent_revision)),
        evidence_verifier=cast(Any, object()),
    )
    assert not incoherent_authority.encrypted_revision_matches(cast(Any, proof(connection)))
