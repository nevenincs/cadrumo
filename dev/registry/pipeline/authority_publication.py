"""Development-only publication of a validated registry authority artifact.

Runtime never imports this module. A development publication captures the
complete compiler input receipt, validates that exact candidate, and holds one
destination lock through the atomic artifact replacement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.core.hashing import content_hash_hex, hash_file, sha256_hex
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    PublishedSourceEvidence,
    write_authority_artifact,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from dev.registry.compiler.authority import canonical_authoring_root_pair, compile_validated_authority
from dev.registry.compiler.corpus_provenance import classify_normative_corpus_provenance
from dev.registry.compiler.identity import resolve_registry_identity
from dev.registry.compiler.legal_grounding import published_legal_evidence_text
from dev.registry.compiler.loader import collect_registry_tree_fingerprints
from dev.registry.compiler.source_evidence_fingerprint import (
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
)

__all__ = [
    "AuthorityPublicationReceipt",
    "ValidatedAuthorityCandidate",
    "publish_authority_candidate",
    "publish_validated_authority_candidate",
    "validate_authority_candidate",
]


@dataclass(frozen=True, slots=True)
class AuthorityPublicationReceipt:
    """Complete registry and source-evidence state consumed during validation."""

    registry_identity_digest: str
    source_evidence_fingerprints: SourceEvidenceFingerprint
    source_evidence_content_digests: tuple[tuple[str, str], ...]
    identity_digest: str


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
    signing_private_key_hex: str,
) -> AuthorityArtifact:
    """Validate and atomically publish one development candidate.

    A destination has exactly one publisher at a time: the artifact sidecar
    lock is held from receipt capture through validation and replacement. The
    release workflow supplies destination and signing key explicitly; this
    module stores neither and defines no runtime artifact location.
    """
    with exclusive_file_lock(artifact_path):
        candidate = validate_authority_candidate(registry_root=registry_root, source_root=source_root)
        return _publish_candidate(
            candidate,
            artifact_path=artifact_path,
            signing_private_key_hex=signing_private_key_hex,
        )


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
        evidence=_project_evidence(
            authority.catalogues.legal,
            authority.catalogues.sources,
            authority.modelos,
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
    modelos: tuple[ModeloDefinition, ...],
    *,
    source_root: Path,
) -> AuthorityEvidenceProjection:
    """Capture all validated legal anchors as signed, path-free runtime evidence."""
    entries = tuple(
        PublishedLegalEvidence(
            legal_reference_id=str(reference_id),
            anchored_text=(text := published_legal_evidence_text(reference, source_root=source_root)),
            text_sha256=sha256_hex(text.encode("utf-8")),
            provenance=classify_normative_corpus_provenance(source_root, reference.corpus_ref),
        )
        for reference_id, reference in sorted(legal.items())
    )
    runtime_source_ids = _runtime_xml_source_ids(modelos, sources)
    source_entries = tuple(
        _project_source_evidence(sources[source_id], source_root=source_root)
        for source_id in sorted(runtime_source_ids)
    )
    return AuthorityEvidenceProjection(legal=entries, sources=source_entries)


def _runtime_xml_source_ids(
    modelos: tuple[ModeloDefinition, ...], sources: Mapping[str, SourceReference]
) -> frozenset[str]:
    """Derive the complete source closure needed by shipped XML workflows.

    The published authority selects revisions at runtime, so every declared
    revision is considered. Only XML dictionary layouts consume external bytes:
    their dictionary and the XSD among their declared layout sources are the
    runtime closure. Other catalogue sources remain compiler-only.
    """
    required: set[str] = set()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for layout in derive_export_layouts_from_bindings(revision):
                if layout.format is not ExportLayoutFormat.XML_DICTIONARY:
                    continue
                if layout.dictionary_source_ref is None:
                    raise RegistryValidationError(f"XML export layout {layout.id!r} has no dictionary source")
                required.add(str(layout.dictionary_source_ref))
                required.update(
                    str(source_id)
                    for source_id in layout.source_refs
                    if sources.get(str(source_id)) is not None and sources[str(source_id)].kind == "xsd"
                )
    return frozenset(required)


def _project_source_evidence(reference: SourceReference, *, source_root: Path) -> PublishedSourceEvidence:
    """Copy one compiler-validated runtime source into the signed artifact."""
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
    signing_private_key_hex: str,
) -> AuthorityArtifact:
    """Publish a prior validation only if registry and source evidence remain unchanged."""
    with exclusive_file_lock(artifact_path):
        return _publish_candidate(
            candidate,
            artifact_path=artifact_path,
            signing_private_key_hex=signing_private_key_hex,
        )


def _publish_candidate(
    candidate: ValidatedAuthorityCandidate,
    *,
    artifact_path: Path,
    signing_private_key_hex: str,
) -> AuthorityArtifact:
    if _capture_receipt(candidate.registry_root, candidate.source_root) != candidate.receipt:
        raise RegistryValidationError(
            "registry candidate or source evidence changed after validation; authority publication is refused",
        )
    write_authority_artifact(
        artifact_path,
        candidate.artifact,
        signing_private_key_hex=signing_private_key_hex,
    )
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
            "schema": "cadrumo-authority-publication-receipt/v1",
            "registry_identity_digest": registry_identity.digest,
            "source_evidence_fingerprints": [list(item) for item in source_evidence],
            "source_evidence_content_digests": [list(item) for item in source_evidence_content_digests],
        }
    )
    return AuthorityPublicationReceipt(
        registry_identity_digest=registry_identity.digest,
        source_evidence_fingerprints=source_evidence,
        source_evidence_content_digests=source_evidence_content_digests,
        identity_digest=identity_digest,
    )
