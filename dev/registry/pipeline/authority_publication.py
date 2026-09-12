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
    PublishedSourceEvidence,
    read_authority_artifact,
    write_authority_artifact,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference

from ..compiler.authority import compile_structural_authority
from ..compiler.authority_state import canonical_authoring_root_pair
from ..compiler.corpus_provenance import classify_normative_corpus_provenance
from ..compiler.identity import resolve_registry_identity
from ..compiler.fact_providers import (
    compile_authored_fact_catalogue,
    collect_registered_fact_provider_fingerprints,
    fact_catalogue_digest,
)
from ..compiler.legal_grounding import published_legal_evidence_text
from ..compiler.loader_fingerprints import collect_registry_tree_fingerprints
from ..compiler.source_evidence_fingerprint import (
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
)

__all__ = [
    "AuthorityArtifactCurrency",
    "AuthorityArtifactCurrencyStatus",
    "AuthorityPublicationReceipt",
    "FactsAuthorityCandidate",
    "FactsAuthorityPublicationReceipt",
    "ValidatedAuthorityCandidate",
    "authority_artifact_currency",
    "authority_candidate_identity",
    "facts_authority_artifact_currency",
    "facts_authority_candidate_identity",
    "publish_authority_candidate",
    "publish_facts_authority_candidate",
    "publish_validated_authority_candidate",
    "validate_facts_authority_candidate",
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


@dataclass(frozen=True, slots=True)
class FactsAuthorityPublicationReceipt:
    """Mutable inputs consumed by the facts-only publication boundary.

    The receipt deliberately fingerprints only authored fact declarations and
    the existing artifact being merged.  Modelo files never participate in
    this candidate identity: a malformed or changing unrelated revision cannot
    block publication of an otherwise valid facts index.
    """

    fact_source_fingerprints: tuple[tuple[str, int, int, str], ...]
    base_artifact_sha256: str
    facts_digest: str


@dataclass(frozen=True, slots=True)
class FactsAuthorityCandidate:
    """A typed authority candidate with only its facts section replaced."""

    registry_root: Path
    artifact_path: Path
    receipt: FactsAuthorityPublicationReceipt
    facts: GovernedFactCatalogue
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
    authority = compile_structural_authority(
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


def publish_facts_authority_candidate(
    *,
    registry_root: Path,
    artifact_path: Path,
) -> AuthorityArtifact:
    """Publish authored facts into the current typed authority atomically.

    This is the facts-only publication owner.  It compiles and schema-validates
    ``<registry-root>/facts`` and merges that catalogue into an already
    published, digest-checked authority.  The existing model graph, legal and
    source catalogues, runtime projections, and evidence are retained exactly;
    no Modelo loader or validator is reachable from this path.

    A missing or corrupt base artifact is refused because a raw JSON
    merge cannot prove the unrelated sections remain typed and valid.  The
    caller must first provide a current authority publication through the
    canonical authority writer.
    """
    with exclusive_file_lock(artifact_path):
        candidate = validate_facts_authority_candidate(
            registry_root=registry_root,
            artifact_path=artifact_path,
        )
        return _publish_facts_candidate(candidate, artifact_path=artifact_path)


def validate_facts_authority_candidate(
    *,
    registry_root: Path,
    artifact_path: Path,
) -> FactsAuthorityCandidate:
    """Build a facts-only candidate without compiling or validating Modelos."""
    resolved_registry_root = _canonical_facts_registry_root(registry_root)
    resolved_artifact_path = artifact_path.expanduser().resolve()
    facts_fingerprints_before = _fact_source_fingerprints(resolved_registry_root)
    base_artifact_sha256_before = _artifact_sha256(resolved_artifact_path)
    base_artifact = _read_facts_merge_base(resolved_artifact_path)
    facts = compile_authored_fact_catalogue(resolved_registry_root)
    facts_digest = fact_catalogue_digest(facts)
    facts_fingerprints_after = _fact_source_fingerprints(resolved_registry_root)
    base_artifact_sha256_after = _artifact_sha256(resolved_artifact_path)
    if facts_fingerprints_after != facts_fingerprints_before:
        raise RegistryValidationError(
            "authored facts changed while they were being compiled; facts authority publication is refused",
        )
    if base_artifact_sha256_after != base_artifact_sha256_before:
        raise RegistryValidationError(
            "authority artifact changed while facts were being compiled; facts authority publication is refused",
        )
    artifact = AuthorityArtifact(
        modelos=base_artifact.modelos,
        catalogues=base_artifact.catalogues.model_copy(update={"facts": facts}),
        identity_digest=facts_digest,
        evidence=base_artifact.evidence,
    )
    receipt = FactsAuthorityPublicationReceipt(
        fact_source_fingerprints=facts_fingerprints_after,
        base_artifact_sha256=base_artifact_sha256_after,
        facts_digest=facts_digest,
    )
    return FactsAuthorityCandidate(
        registry_root=resolved_registry_root,
        artifact_path=resolved_artifact_path,
        receipt=receipt,
        facts=facts,
        artifact=artifact,
    )


def facts_authority_candidate_identity(*, registry_root: Path) -> str:
    """Return the digest a fresh authored-facts compilation would publish."""
    return fact_catalogue_digest(compile_authored_fact_catalogue(_canonical_facts_registry_root(registry_root)))


def facts_authority_artifact_currency(
    artifact_path: Path,
    *,
    registry_root: Path,
) -> AuthorityArtifactCurrency:
    """Compare the bundled facts index and identity with a fresh compilation."""
    candidate_identity = facts_authority_candidate_identity(registry_root=registry_root)
    try:
        artifact = read_authority_artifact(artifact_path)
    except AuthorityArtifactError as exc:
        return AuthorityArtifactCurrency(
            artifact_path=artifact_path,
            status=AuthorityArtifactCurrencyStatus.UNREADABLE,
            candidate_identity_digest=candidate_identity,
            recorded_identity_digest=None,
            detail=f"{type(exc).__name__}: {exc}",
        )
    published_facts_digest = fact_catalogue_digest(artifact.catalogues.facts)
    if artifact.identity_digest != candidate_identity or published_facts_digest != candidate_identity:
        return AuthorityArtifactCurrency(
            artifact_path=artifact_path,
            status=AuthorityArtifactCurrencyStatus.STALE,
            candidate_identity_digest=candidate_identity,
            recorded_identity_digest=artifact.identity_digest,
            detail=(
                "the published authority facts index or its identity digest differs from the fresh authored-facts "
                "compilation"
            ),
        )
    return AuthorityArtifactCurrency(
        artifact_path=artifact_path,
        status=AuthorityArtifactCurrencyStatus.CURRENT,
        candidate_identity_digest=candidate_identity,
        recorded_identity_digest=artifact.identity_digest,
        detail="the published authority carries the fresh authored-facts compilation",
    )


def _publish_facts_candidate(
    candidate: FactsAuthorityCandidate,
    *,
    artifact_path: Path,
) -> AuthorityArtifact:
    """Recheck the facts/base receipt, write through the canonical writer, and reread it."""
    resolved_artifact_path = artifact_path.expanduser().resolve()
    if resolved_artifact_path != candidate.artifact_path:
        raise RegistryValidationError("facts authority candidate target differs from its reviewed artifact target")
    if _fact_source_fingerprints(candidate.registry_root) != candidate.receipt.fact_source_fingerprints:
        raise RegistryValidationError(
            "authored facts changed after facts compilation; facts authority publication is refused",
        )
    if _artifact_sha256(resolved_artifact_path) != candidate.receipt.base_artifact_sha256:
        raise RegistryValidationError(
            "authority artifact changed after facts compilation; facts authority publication is refused",
        )
    write_authority_artifact(resolved_artifact_path, candidate.artifact)
    try:
        published = read_authority_artifact(resolved_artifact_path)
    except AuthorityArtifactError as exc:
        raise RegistryValidationError(
            "canonical authority writer produced an unreadable facts publication",
        ) from exc
    if published.identity_digest != candidate.receipt.facts_digest:
        raise RegistryValidationError(
            "canonical authority writer changed the facts candidate identity digest",
        )
    if fact_catalogue_digest(published.catalogues.facts) != candidate.receipt.facts_digest:
        raise RegistryValidationError(
            "canonical authority writer changed the facts candidate payload",
        )
    return published


def _canonical_facts_registry_root(registry_root: Path) -> Path:
    """Resolve one existing registry root without touching unrelated Modelo data."""
    try:
        resolved = registry_root.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise RegistryValidationError("facts authority registry root must resolve to an existing directory") from exc
    if not resolved.is_dir():
        raise RegistryValidationError("facts authority registry root must resolve to a directory")
    return resolved


def _fact_source_fingerprints(registry_root: Path) -> tuple[tuple[str, int, int, str], ...]:
    """Capture only registered authored-fact source files for race detection."""
    return tuple(collect_registered_fact_provider_fingerprints(registry_root))


def _artifact_sha256(artifact_path: Path) -> str:
    """Hash the existing publication, refusing a missing merge base."""
    try:
        return hash_file(artifact_path)[0]
    except OSError as exc:
        raise RegistryValidationError(
            f"facts authority publication requires an existing typed authority artifact: {artifact_path}",
        ) from exc


def _read_facts_merge_base(artifact_path: Path) -> AuthorityArtifact:
    """Read the typed merge base through the same strict reader as runtime."""
    try:
        return read_authority_artifact(artifact_path)
    except AuthorityArtifactError as exc:
        raise RegistryValidationError(
            "facts authority publication requires a readable current authority artifact; "
            "corrupt unrelated sections cannot be merged safely",
        ) from exc


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
