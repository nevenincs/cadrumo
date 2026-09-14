"""Development-only publication of a validated registry authority artifact.

Runtime never imports this module. A development publication captures the
complete compiler input receipt, validates that exact candidate, and holds one
destination lock through the atomic artifact replacement. The artifact is
generated output.

The artifact records the candidate identity it was compiled from, and
:func:`authority_artifact_currency` compares that record with the identity of
the inputs as they stand now. The identity is content-addressed and
checkout-independent: it folds every registry and source-evidence file's
root-relative path and content digest, never an absolute path, a size, or a
modification time. A fresh clone with the same compiler and declared runtime
environment derives the recorded identity. Registry files use CRLF endings folded
to LF, because the repository normalises the registry tree to LF while a
Windows working copy may still hold CRLF; source evidence is byte-exact legal
evidence and is digested raw.

Currency includes the compiler and domain source identity as well as the data
inputs. The source receipt and compiler receipt are distinct, and their combined
digest identifies the build; the artifact frame separately hashes its output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import content_hash_hex, hash_file, sha256_hex
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityArtifactError,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    PublishedSourceEvidence,
    read_authority_artifact,
    write_authority_artifact,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ..compiler.authority_state import canonical_authoring_root_pair
from ..compiler.build_identity import authority_compiler_identity
from ..compiler.corpus_provenance import classify_normative_corpus_provenance
from ..compiler.identity import resolve_registry_identity
from ..compiler.legal_grounding import published_legal_evidence_text
from ..compiler.loader_fingerprints import collect_registry_tree_fingerprints
from ..compiler.source_evidence_fingerprint import (
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
)

_PUBLICATION_LOCK_TIMEOUT: Final = 30.0
_PUBLICATION_LOCK_RETRY_BACKOFF: Final = 0.05

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

_CANDIDATE_IDENTITY_SCHEMA: Final = "cadrumo-authority-candidate-identity/v2"
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
    candidate_build_identity: AuthorityBuildIdentity
    recorded_build_identity: AuthorityBuildIdentity | None
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
    source_identity_digest: str
    compiler_identity_digest: str
    component_dependency_digest: str
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
    with exclusive_file_lock(
        artifact_path,
        timeout=_PUBLICATION_LOCK_TIMEOUT,
        retry_backoff=_PUBLICATION_LOCK_RETRY_BACKOFF,
    ):
        candidate = validate_authority_candidate(registry_root=registry_root, source_root=source_root)
        return _publish_candidate(candidate, artifact_path=artifact_path)


def validate_authority_candidate(*, registry_root: Path, source_root: Path) -> ValidatedAuthorityCandidate:
    """Compile and validate a candidate, refusing inputs that change mid-validation."""
    # Import at the compile boundary so tooling discovery does not load validators.
    from ..compiler.authority import compile_validated_authority

    resolved_registry_root, resolved_source_root = canonical_authoring_root_pair(registry_root, source_root)
    receipt_before = _capture_receipt(resolved_registry_root, resolved_source_root)
    identity = resolve_registry_identity(
        resolved_registry_root,
        collect_fingerprints=partial(collect_registry_tree_fingerprints, use_cache=False),
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
        build_identity=AuthorityBuildIdentity(
            receipt_after.source_identity_digest,
            receipt_after.compiler_identity_digest,
            receipt_after.component_dependency_digest,
        ),
        evidence=_project_evidence(
            authority.catalogues.legal,
            authority.catalogues.sources,
            source_root=resolved_source_root,
        ),
    )
    return ValidatedAuthorityCandidate(
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        receipt=receipt_after,
        artifact=artifact,
    )


def _project_evidence(
    legal: Mapping[str, LegalReference],
    sources: Mapping[str, SourceReference],
    *,
    source_root: Path,
) -> AuthorityEvidenceProjection:
    """Capture all validated legal anchors as path-free runtime evidence."""
    entries = tuple(
        PublishedLegalEvidence(
            legal_reference_id=str(reference_id),
            anchored_text=(text := published_legal_evidence_text(reference, source_root=source_root)),
            text_sha256=sha256_hex(text.encode("utf-8")),
            provenance=classify_normative_corpus_provenance(source_root, reference.corpus_ref),
        )
        for reference_id, reference in sorted(legal.items())
    )
    runtime_source_ids = _runtime_xml_source_ids(sources)
    source_entries = tuple(
        _project_source_evidence(sources[source_id], source_root=source_root)
        for source_id in sorted(runtime_source_ids)
    )
    return AuthorityEvidenceProjection(legal=entries, sources=source_entries)


def _runtime_xml_source_ids(sources: Mapping[str, SourceReference]) -> frozenset[str]:
    """Select catalogued source kinds whose bytes shipped XML workflows consume."""
    runtime_kinds = frozenset({"dictionary", "xsd"})
    return frozenset(str(source_id) for source_id, source in sources.items() if source.kind in runtime_kinds)


def _project_source_evidence(reference: SourceReference, *, source_root: Path) -> PublishedSourceEvidence:
    """Copy one compiler-validated runtime source into the digest-checked artifact."""
    root = source_root.resolve()
    target = (root / reference.corpus_path).resolve()
    if root not in target.parents or not target.is_file():
        raise RegistryValidationError(f"source reference {reference.id!r} has no publishable corpus payload")
    payload = target.read_bytes()
    digest = sha256_hex(payload)
    if digest != reference.sha256 or len(payload) != reference.bytes:
        raise RegistryValidationError(f"source reference {reference.id!r} changed after compiler validation")
    return PublishedSourceEvidence(
        source_reference_id=str(reference.id),
        payload=payload,
        payload_sha256=digest,
    )


def publish_validated_authority_candidate(
    candidate: ValidatedAuthorityCandidate,
    *,
    artifact_path: Path,
) -> AuthorityArtifact:
    """Publish a prior validation only if registry and source evidence remain unchanged."""
    with exclusive_file_lock(
        artifact_path,
        timeout=_PUBLICATION_LOCK_TIMEOUT,
        retry_backoff=_PUBLICATION_LOCK_RETRY_BACKOFF,
    ):
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
    roots = canonical_authoring_root_pair(registry_root, source_root)
    receipt = _capture_receipt(*roots)
    candidate_identity = receipt.identity_digest
    candidate_build = AuthorityBuildIdentity(
        receipt.source_identity_digest,
        receipt.compiler_identity_digest,
        receipt.component_dependency_digest,
    )
    try:
        artifact = read_authority_artifact(artifact_path)
        recorded_identity = artifact.identity_digest
    except AuthorityArtifactError as exc:
        return AuthorityArtifactCurrency(
            artifact_path=artifact_path,
            status=AuthorityArtifactCurrencyStatus.UNREADABLE,
            candidate_identity_digest=candidate_identity,
            recorded_identity_digest=None,
            candidate_build_identity=candidate_build,
            recorded_build_identity=None,
            detail=f"{type(exc).__name__}: {exc}",
        )
    if recorded_identity != candidate_identity:
        return AuthorityArtifactCurrency(
            artifact_path=artifact_path,
            status=AuthorityArtifactCurrencyStatus.STALE,
            candidate_identity_digest=candidate_identity,
            recorded_identity_digest=recorded_identity,
            candidate_build_identity=candidate_build,
            recorded_build_identity=artifact.build_identity,
            detail="changed authority inputs: "
            + ", ".join(
                name
                for name, changed in (
                    (
                        "source manifest",
                        candidate_build.source_identity_digest != artifact.build_identity.source_identity_digest,
                    ),
                    (
                        "compiler/schema build",
                        candidate_build.compiler_identity_digest != artifact.build_identity.compiler_identity_digest,
                    ),
                    (
                        "component dependencies",
                        candidate_build.component_dependency_digest
                        != artifact.build_identity.component_dependency_digest,
                    ),
                )
                if changed
            ),
        )
    return AuthorityArtifactCurrency(
        artifact_path=artifact_path,
        status=AuthorityArtifactCurrencyStatus.CURRENT,
        candidate_identity_digest=candidate_identity,
        recorded_identity_digest=recorded_identity,
        candidate_build_identity=candidate_build,
        recorded_build_identity=artifact.build_identity,
        detail="the artifact matches the live source manifest, compiler build, and component dependencies",
    )


def _publish_candidate(
    candidate: ValidatedAuthorityCandidate,
    *,
    artifact_path: Path,
) -> AuthorityArtifact:
    def require_current_candidate() -> None:
        if _capture_receipt(candidate.registry_root, candidate.source_root) != candidate.receipt:
            raise RegistryValidationError(
                "registry candidate or source evidence changed after validation; authority publication is refused",
            )

    require_current_candidate()
    write_authority_artifact(artifact_path, candidate.artifact, before_replace=require_current_candidate)
    return candidate.artifact


def _capture_receipt(registry_root: Path, source_root: Path) -> AuthorityPublicationReceipt:
    """Capture every mutable input the authority compiler uses for this candidate."""
    registry_identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=partial(collect_registry_tree_fingerprints, use_cache=False),
    )
    source_evidence = collect_source_evidence_fingerprints(source_root, use_cache=False)
    source_evidence_content_digests = tuple(
        (path, hash_file(Path(path))[0]) for path, _byte_count, _modified_ns in source_evidence
    )
    source_identity_digest = content_hash_hex(
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
    compiler_identity_digest = authority_compiler_identity()
    build_identity = AuthorityBuildIdentity.from_inputs(source_identity_digest, compiler_identity_digest)
    return AuthorityPublicationReceipt(
        registry_identity_digest=registry_identity.digest,
        source_evidence_fingerprints=source_evidence,
        source_evidence_content_digests=source_evidence_content_digests,
        source_identity_digest=source_identity_digest,
        compiler_identity_digest=compiler_identity_digest,
        component_dependency_digest=build_identity.component_dependency_digest,
        identity_digest=build_identity.identity_digest,
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
