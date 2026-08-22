"""Live application authority for admitting connected source-census claims."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...core import (
    BindingSourceKind,
    SourceConnectivityConnectionIdentity,
    SourceConnectivityEncryptedRevisionProof,
    SourceConnectivityExecutableEvidence,
    SourceConnectivityGroundingLocatorKind,
)
from ...domain.modelos import CalculationRevisionCatalogueRepositoryProtocol
from ..aggregation import BindingSourceDisposition
from ..operator_surface import SupportedModeloCalculationWorkflowCatalogue

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


class LiveSourceResolverEnrollment(BaseModel):
    """Canonical live disposition and resolver owner for one binding source kind."""

    model_config = _STRICT_FROZEN

    source_kind: BindingSourceKind
    resolver_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9][a-z0-9._:-]*$")
    disposition: BindingSourceDisposition


class LiveSourceResolverCatalogue(BaseModel):
    """Deterministic exact source-kind-to-resolver ownership catalogue."""

    model_config = _STRICT_FROZEN

    enrollments: tuple[LiveSourceResolverEnrollment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _require_unique_deterministic_sources(self) -> LiveSourceResolverCatalogue:
        source_kinds = tuple(row.source_kind for row in self.enrollments)
        if len(set(source_kinds)) != len(source_kinds):
            raise ValueError("live source resolver catalogue requires unique source kinds")
        if source_kinds != tuple(sorted(source_kinds, key=lambda item: item.value)):
            raise ValueError("live source resolver catalogue requires deterministic source-kind order")
        return self

    def enrollment_for(self, source_kind: BindingSourceKind) -> LiveSourceResolverEnrollment | None:
        """Return the unique live policy row for ``source_kind``, if declared."""
        return next((row for row in self.enrollments if row.source_kind is source_kind), None)


@runtime_checkable
class RepositoryEvidenceDigestVerifier(Protocol):
    """Injected port that verifies one repository evidence reference."""

    def digest(self, repository_reference: str) -> str | None:
        """Return the deterministic digest only when the reference is safe and readable."""


@dataclass(frozen=True, slots=True)
class RepositoryRootEvidenceDigestVerifier:
    """SHA-256 verifier confined to one explicitly injected repository root."""

    repository_root: Path

    def digest(self, repository_reference: str) -> str | None:
        """Digest a contained regular file, refusing traversal and symlink escape."""
        relative_text = _repository_path_without_line(repository_reference)
        if relative_text is None:
            return None
        try:
            root = self.repository_root.resolve(strict=True)
            candidate = (root / Path(*PurePosixPath(relative_text).parts)).resolve(strict=True)
        except (OSError, RuntimeError):
            return None
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return None
        try:
            return sha256(candidate.read_bytes()).hexdigest()
        except OSError:
            return None


def _repository_path_without_line(reference: str) -> str | None:
    """Return a safe relative POSIX path from a repository evidence locator."""
    path, separator, line = reference.rpartition(":")
    candidate = path if separator and line.isdigit() else reference
    pure_path = PurePosixPath(candidate)
    if (
        not candidate
        or "\\" in candidate
        or pure_path.is_absolute()
        or any(part in {"", ".", ".."} for part in pure_path.parts)
    ):
        return None
    return candidate


@dataclass(frozen=True, slots=True)
class LiveSourceConnectivityProofAuthority:
    """Concrete live authority over enrollment, workflows, evidence, and revisions."""

    source_resolvers: LiveSourceResolverCatalogue
    workflows: SupportedModeloCalculationWorkflowCatalogue
    calculation_revisions: CalculationRevisionCatalogueRepositoryProtocol
    evidence_verifier: RepositoryEvidenceDigestVerifier

    def source_is_enrolled(self, connection: SourceConnectivityConnectionIdentity) -> bool:
        """Require exact resolver ownership under an enrolled live disposition."""
        enrollment = self.source_resolvers.enrollment_for(connection.source_kind)
        return (
            enrollment is not None
            and enrollment.disposition is BindingSourceDisposition.ENROLLED
            and enrollment.resolver_id == connection.resolver_id
        )

    def operator_workflow_is_supported(
        self,
        connection: SourceConnectivityConnectionIdentity,
        *,
        entrypoint_id: str,
        command_id: str,
    ) -> bool:
        """Require the exact reviewed live workflow beside exact source enrollment."""
        return self.source_is_enrolled(connection) and self.workflows.supports(
            entrypoint_id=entrypoint_id,
            command_id=command_id,
        )

    def encrypted_revision_matches(self, proof: SourceConnectivityEncryptedRevisionProof) -> bool:
        """Match one exact provenance row in the encrypted calculation revision."""
        connection = proof.connection
        try:
            if not self.calculation_revisions.exists():
                return False
            catalogue = self.calculation_revisions.load()
        except Exception:
            return False
        revision = catalogue.revisions.get(connection.calculation_revision_id)
        if revision is None or revision.calculation_revision_id != connection.calculation_revision_id:
            return False
        source_identity_rows = tuple(
            row
            for row in revision.source_provenance
            if row.binding_source is connection.source_kind and row.source_ref == proof.persisted_source_identity
        )
        return (
            len(source_identity_rows) == 1
            and source_identity_rows[0].resolver_id == connection.resolver_id
            and source_identity_rows[0].source_kind == connection.source_kind.value
            and source_identity_rows[0].fingerprint == proof.persisted_source_fingerprint
        )

    def executable_evidence_digest(
        self,
        evidence: SourceConnectivityExecutableEvidence,
    ) -> str | None:
        """Verify repository-backed executable evidence through the injected root policy."""
        if evidence.locator.locator_kind is not SourceConnectivityGroundingLocatorKind.REPOSITORY:
            return None
        return self.evidence_verifier.digest(evidence.locator.reference)


__all__ = [
    "LiveSourceConnectivityProofAuthority",
    "LiveSourceResolverCatalogue",
    "LiveSourceResolverEnrollment",
    "RepositoryEvidenceDigestVerifier",
    "RepositoryRootEvidenceDigestVerifier",
]
