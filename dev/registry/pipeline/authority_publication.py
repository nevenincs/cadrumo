"""Development-only publication of a validated registry authority artifact.

Runtime never imports this module. A development publication captures the
complete compiler input receipt, validates that exact candidate, and holds one
destination lock through the atomic artifact replacement. The artifact is
generated output, not a signed document: nothing here holds or needs a key.

The artifact records the candidate identity it was compiled from, and
:func:`authority_artifact_currency` compares that record with the identity of
the inputs as they stand now. The identity is content-addressed and
checkout-independent: it folds every registry and source-evidence file's
root-relative path and content digest, never an absolute path, a size, or a
modification time, so a fresh clone on any platform derives the identity the
publisher recorded. Registry files are digested with CRLF line endings folded
to LF, because the repository normalises the registry tree to LF while a
Windows working copy may still hold CRLF; source evidence is byte-exact legal
evidence and is digested raw.

Where the currency check stops: it covers the compiler's INPUTS. A change to
the compiler's own code that alters its output without touching any input
leaves the recorded identity current; the full-registry publication round trip
is the gate that exercises the compiler itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import content_hash_hex, hash_file, sha256_hex
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityArtifactError,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    read_authority_artifact,
    write_authority_artifact,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import LegalReference
from dev.registry.compiler.authority import canonical_authoring_root_pair, compile_validated_authority
from dev.registry.compiler.identity import resolve_registry_identity
from dev.registry.compiler.legal_grounding import published_legal_evidence_text
from dev.registry.compiler.loader import collect_registry_tree_fingerprints
from dev.registry.compiler.source_evidence_fingerprint import (
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
)

__all__ = [
    "AuthorityArtifactCurrency",
    "AuthorityArtifactCurrencyStatus",
    "AuthorityPublicationReceipt",
    "ValidatedAuthorityCandidate",
    "authority_artifact_currency",
    "authority_candidate_identity",
    "publish_authority_candidate",
    "publish_validated_authority_candidate",
    "validate_authority_candidate",
]

_CANDIDATE_IDENTITY_SCHEMA: Final = "cadrumo-authority-candidate-identity/v1"
_UNTRACKED_DIRECTORY_NAMES: Final = frozenset({"__pycache__"})
_UNTRACKED_FILE_SUFFIXES: Final = frozenset({".lock", ".pyc"})
"""Working-tree byproducts -- lock sidecars and bytecode -- that no checkout carries.

A hidden (dot-prefixed) path segment is excluded on the same ground. None of
these is a compiler input, and folding them in would make the identity depend
on which tools last ran in a working copy rather than on the candidate.
"""


class AuthorityArtifactCurrencyStatus(StrEnum):
    """Whether a published artifact still describes the candidate it would be compiled from."""

    CURRENT = "current"
    STALE = "stale"
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class AuthorityArtifactCurrency:
    """One published artifact's recorded identity against the candidate's live identity.

    ``recorded_identity_digest`` is ``None`` only when the artifact could not
    be read, in which case ``detail`` names the refusal.
    """

    artifact_path: Path
    status: AuthorityArtifactCurrencyStatus
    candidate_identity_digest: str
    recorded_identity_digest: str | None
    detail: str

    @property
    def is_current(self) -> bool:
        """Whether the artifact may stand as the publication of the live candidate."""
        return self.status is AuthorityArtifactCurrencyStatus.CURRENT


@dataclass(frozen=True, slots=True)
class AuthorityPublicationReceipt:
    """Complete registry and source-evidence state consumed during validation."""

    registry_identity_digest: str
    source_evidence_fingerprints: SourceEvidenceFingerprint
    source_evidence_content_digests: tuple[tuple[str, str], ...]
    identity_digest: str
    """Content-addressed candidate identity; recorded in the artifact it publishes."""


@dataclass(frozen=True, slots=True)
class ValidatedAuthorityCandidate:
    """An authority publishable only while its input receipt remains current."""

    registry_root: Path
    source_root: Path
    receipt: AuthorityPublicationReceipt
    artifact: AuthorityArtifact


def publish_authority_candidate(
    *,
    registry_root: Path,
    source_root: Path,
    artifact_path: Path,
) -> AuthorityArtifact:
    """Validate and atomically publish one development candidate.

    A destination has exactly one publisher at a time: the artifact sidecar
    lock is held from receipt capture through validation and replacement. The
    caller supplies the destination explicitly; this module defines no runtime
    artifact location.
    """
    with exclusive_file_lock(artifact_path):
        candidate = validate_authority_candidate(registry_root=registry_root, source_root=source_root)
        return _publish_candidate(candidate, artifact_path=artifact_path)


def validate_authority_candidate(*, registry_root: Path, source_root: Path) -> ValidatedAuthorityCandidate:
    """Compile and validate a candidate, refusing inputs that change mid-validation."""
    resolved_registry_root, resolved_source_root = canonical_authoring_root_pair(registry_root, source_root)
    receipt_before = _capture_receipt(resolved_registry_root, resolved_source_root)
    identity = resolve_registry_identity(
        resolved_registry_root,
        collect_fingerprints=collect_registry_tree_fingerprints,
    )
    authority = compile_validated_authority(
        resolved_registry_root,
        resolved_source_root,
        identity=identity,
    )
    receipt_after = _capture_receipt(resolved_registry_root, resolved_source_root)
    if receipt_after != receipt_before:
        raise RegistryValidationError(
            "registry candidate changed while it was being validated; authority publication is refused",
        )
    artifact = AuthorityArtifact(
        modelos=authority.modelos,
        catalogues=authority.catalogues,
        identity_digest=receipt_after.identity_digest,
        evidence=_project_evidence(authority.catalogues.legal, source_root=resolved_source_root),
    )
    return ValidatedAuthorityCandidate(
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        receipt=receipt_after,
        artifact=artifact,
    )


def _project_evidence(legal: Mapping[str, LegalReference], *, source_root: Path) -> AuthorityEvidenceProjection:
    """Capture all validated legal anchors as path-free runtime evidence."""
    entries = tuple(
        PublishedLegalEvidence(
            legal_reference_id=str(reference_id),
            anchored_text=(text := published_legal_evidence_text(reference, source_root=source_root)),
            text_sha256=sha256_hex(text.encode("utf-8")),
        )
        for reference_id, reference in sorted(legal.items())
    )
    return AuthorityEvidenceProjection(legal=entries)


def publish_validated_authority_candidate(
    candidate: ValidatedAuthorityCandidate,
    *,
    artifact_path: Path,
) -> AuthorityArtifact:
    """Publish a prior validation only if registry and source evidence remain unchanged."""
    with exclusive_file_lock(artifact_path):
        return _publish_candidate(candidate, artifact_path=artifact_path)


def authority_candidate_identity(*, registry_root: Path, source_root: Path) -> str:
    """Return the content-addressed identity a publication of these inputs would record.

    Costs a content read of every registry and source-evidence file and no
    compilation, so a gate can ask whether the published artifact is current
    without publishing.
    """
    resolved_registry_root, resolved_source_root = canonical_authoring_root_pair(registry_root, source_root)
    return _capture_receipt(resolved_registry_root, resolved_source_root).identity_digest


def authority_artifact_currency(
    artifact_path: Path,
    *,
    registry_root: Path,
    source_root: Path,
) -> AuthorityArtifactCurrency:
    """Compare a published artifact's recorded identity with the live candidate's.

    The artifact is read through the same strict reader the product runtime
    uses, so an artifact that is missing, corrupt, or of an earlier format is
    reported ``unreadable`` rather than judged on a field it cannot vouch for.
    """
    candidate_identity = authority_candidate_identity(registry_root=registry_root, source_root=source_root)
    try:
        recorded_identity = read_authority_artifact(artifact_path).identity_digest
    except AuthorityArtifactError as exc:
        return AuthorityArtifactCurrency(
            artifact_path=artifact_path,
            status=AuthorityArtifactCurrencyStatus.UNREADABLE,
            candidate_identity_digest=candidate_identity,
            recorded_identity_digest=None,
            detail=f"{type(exc).__name__}: {exc}",
        )
    if recorded_identity != candidate_identity:
        return AuthorityArtifactCurrency(
            artifact_path=artifact_path,
            status=AuthorityArtifactCurrencyStatus.STALE,
            candidate_identity_digest=candidate_identity,
            recorded_identity_digest=recorded_identity,
            detail="the registry or source evidence changed since this artifact was published",
        )
    return AuthorityArtifactCurrency(
        artifact_path=artifact_path,
        status=AuthorityArtifactCurrencyStatus.CURRENT,
        candidate_identity_digest=candidate_identity,
        recorded_identity_digest=recorded_identity,
        detail="the artifact was published from the live registry and source evidence",
    )


def _publish_candidate(
    candidate: ValidatedAuthorityCandidate,
    *,
    artifact_path: Path,
) -> AuthorityArtifact:
    if _capture_receipt(candidate.registry_root, candidate.source_root) != candidate.receipt:
        raise RegistryValidationError(
            "registry candidate or source evidence changed after validation; authority publication is refused",
        )
    write_authority_artifact(artifact_path, candidate.artifact)
    return candidate.artifact


def _capture_receipt(registry_root: Path, source_root: Path) -> AuthorityPublicationReceipt:
    """Capture every mutable input the authority compiler uses for this candidate."""
    registry_identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=collect_registry_tree_fingerprints,
    )
    source_evidence = collect_source_evidence_fingerprints(source_root)
    source_evidence_content_digests = tuple(
        (path, hash_file(Path(path))[0]) for path, _byte_count, _modified_ns in source_evidence
    )
    identity_digest = content_hash_hex(
        {
            "schema": _CANDIDATE_IDENTITY_SCHEMA,
            "registry": _registry_content_digests(registry_root),
            "source_evidence": sorted(
                [_relative_posix(Path(path), source_root), digest]
                for path, digest in source_evidence_content_digests
                if _is_candidate_input(Path(path).relative_to(source_root))
            ),
        }
    )
    return AuthorityPublicationReceipt(
        registry_identity_digest=registry_identity.digest,
        source_evidence_fingerprints=source_evidence,
        source_evidence_content_digests=source_evidence_content_digests,
        identity_digest=identity_digest,
    )


def _registry_content_digests(registry_root: Path) -> list[list[str]]:
    """Return ``[relative path, digest]`` for every registry file, CRLF folded to LF."""
    return sorted(
        [_relative_posix(path, registry_root), sha256_hex(path.read_bytes().replace(b"\r\n", b"\n"))]
        for path in scan_directory(
            registry_root,
            recursive=True,
            select=DirectoryEntryKind.FILES,
            prune_directories=_UNTRACKED_DIRECTORY_NAMES,
        )
        if _is_candidate_input(path.relative_to(registry_root))
    )


def _is_candidate_input(relative: Path) -> bool:
    """Whether a root-relative file is a candidate input rather than a working-tree byproduct."""
    return not (
        any(part.startswith(".") or part in _UNTRACKED_DIRECTORY_NAMES for part in relative.parts)
        or relative.suffix in _UNTRACKED_FILE_SUFFIXES
    )


def _relative_posix(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` in the platform-independent POSIX spelling."""
    return PurePosixPath(*path.relative_to(root).parts).as_posix()
