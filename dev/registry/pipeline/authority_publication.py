"""Development-only publication of a validated registry authority artifact.

Runtime never imports this module. A development publication captures the
complete compiler input receipt, validates that exact candidate, and holds one
destination lock through the atomic artifact replacement. The artifact is
generated output.

The indexed generation records the candidate identity it was compiled from, and
:func:`authority_database_currency` compares that record with the identity of
the inputs as they stand now. The identity is content-addressed and
checkout-independent: it folds every registry and source-evidence file's
root-relative path and content digest, never an absolute path, a size, or a
modification time. A fresh clone with the same compiler and declared runtime
environment derives the recorded identity. Registry files use CRLF endings folded
to LF, because the repository normalises the registry tree to LF while a
Windows working copy may still hold CRLF; source evidence is byte-exact legal
evidence and is digested raw.

Currency includes the compiler identity as well as the data inputs. The
compiler identity hashes the closure of compiler source files loaded to compile
the candidate, recorded in the generation with the interpreter and dependency
environment; currency re-hashes exactly those recorded files rather than
compiling again. Every publication compiles in the same canonical child
interpreter, so that closure never depends on which tool launched it. The
source receipt and compiler receipt are distinct, and their combined digest
identifies the build; the artifact frame separately hashes its output.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Final

from cadrumo.core.atomic_write import hardened_staged_publication
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import content_hash_hex, hash_file, sha256_hex
from cadrumo.core.locks import exclusive_file_lock
from cadrumo.domain.calculations.registry.authority_artifact import (
    AuthorityArtifact,
    AuthorityBuildIdentity,
    AuthorityEvidenceProjection,
    PublishedLegalEvidence,
    PublishedSourceEvidence,
)
from cadrumo.domain.calculations.registry.authority_compiler_closure import AuthorityCompilerClosure
from cadrumo.domain.calculations.registry.authority_store import (
    AuthorityDescriptor,
    AuthorityStoreError,
    AuthorityStoreFormatError,
    SQLiteAuthorityReader,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import LegalReference, SourceReference
from cadrumo.domain.calculations.registry.source_byte_availability import embedded_source_ids

from ..compiler.authority_database import build_authority_database
from ..compiler.authority_state import canonical_authoring_root_pair
from ..compiler.build_identity import live_compiler_closure, observe_compiler_closure
from ..compiler.corpus_provenance import classify_normative_corpus_provenance
from ..compiler.identity import resolve_registry_identity
from ..compiler.legal_grounding import published_legal_evidence_text
from ..compiler.loader_fingerprints import collect_registry_tree_fingerprints
from ..compiler.profile_schema import CapturedProfileSchema, capture_profile_schema_source
from ..compiler.source_evidence_fingerprint import (
    SourceEvidenceFingerprint,
    collect_source_evidence_fingerprints,
)
from .candidate_compile_process import run_candidate_compiler

_PUBLICATION_LOCK_TIMEOUT: Final = 30.0
_PUBLICATION_LOCK_RETRY_BACKOFF: Final = 0.05
_DESCRIPTOR_NAME: Final = "authority.current.json"


def require_evidence_closure(artifact: AuthorityArtifact) -> None:
    """Require every runtime evidence projection to agree with its catalogue."""
    legal_ids = {item.legal_reference_id for item in artifact.evidence.legal}
    if legal_ids != set(artifact.catalogues.legal):
        raise ValueError("authority artifact legal evidence must cover exactly its legal catalogue")
    required_sources = embedded_source_ids(artifact.catalogues.sources)
    source_ids = frozenset(item.source_reference_id for item in artifact.evidence.sources)
    if source_ids != required_sources:
        raise ValueError("authority artifact source evidence must cover exactly its runtime source catalogue")
    for item in artifact.evidence.sources:
        source = artifact.catalogues.sources[item.source_reference_id]
        if item.payload_sha256 != source.sha256 or len(item.payload) != source.bytes:
            raise ValueError(f"authority artifact source evidence disagrees with catalogue {source.id!r}")


__all__ = [
    "AuthorityBuildInput",
    "AuthorityDatabaseCurrency",
    "AuthorityDatabaseCurrencyStatus",
    "AuthorityPublicationReceipt",
    "PreparedAuthorityCandidate",
    "ValidatedAuthorityCandidate",
    "authority_database_currency",
    "authority_publication_destination",
    "authority_source_identity",
    "install_validated_authority_database",
    "prepare_authority_candidate",
    "promote_accepted_authority_database",
    "publish_sqlite_authority_candidate",
    "stage_authority_candidate",
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


class AuthorityDatabaseCurrencyStatus(StrEnum):
    """Whether an indexed authority generation describes the live candidate."""

    CURRENT = "current"
    STALE = "stale"
    UNREADABLE = "unreadable"
    UNSUPPORTED_FORMAT = "unsupported_format"
    """The generation predates persisted build receipts; its build identity is unknown."""


class AuthorityBuildInput(StrEnum):
    """One compiler input whose drift a stale generation can name.

    The component-dependency receipt is derived from these two, so it drifts
    exactly when one of them does and is never reported on its own.
    """

    SOURCE = "source"
    COMPILER = "compiler"


@dataclass(frozen=True, slots=True)
class AuthorityDatabaseCurrency:
    """One indexed generation's recorded identity against the candidate's live identity.

    ``recorded_identity_digest`` is ``None`` only when the descriptor could not
    be read, in which case ``detail`` names the refusal.  ``recorded_build_identity``
    is ``None`` whenever the generation's receipts are unknown: unreadable, or an
    older format that never recorded them.  The live compiler identity is the
    recorded compiler closure re-hashed in this checkout, so the candidate
    identities are ``None`` exactly when the recorded ones are; the live source
    identity is always known.  ``drifted_inputs`` names every input whose
    recorded receipt differs from the live one.
    """

    descriptor_path: Path
    status: AuthorityDatabaseCurrencyStatus
    candidate_source_identity_digest: str
    candidate_identity_digest: str | None
    recorded_identity_digest: str | None
    candidate_build_identity: AuthorityBuildIdentity | None
    recorded_build_identity: AuthorityBuildIdentity | None
    detail: str
    drifted_inputs: tuple[AuthorityBuildInput, ...] = ()

    @property
    def is_current(self) -> bool:
        """Whether the indexed generation is the publication of the live candidate."""
        return self.status is AuthorityDatabaseCurrencyStatus.CURRENT


@dataclass(frozen=True, slots=True)
class AuthorityPublicationReceipt:
    """Complete registry and source-evidence state consumed during validation."""

    registry_identity_digest: str
    source_evidence_fingerprints: SourceEvidenceFingerprint
    source_evidence_content_digests: tuple[tuple[str, str], ...]
    profile_schema_sha256: str
    source_identity_digest: str
    """Content-addressed source identity; recorded in the artifact it publishes."""


@dataclass(frozen=True, slots=True)
class ValidatedAuthorityCandidate:
    """A validated artifact inside the canonical compiler process, with its input receipt."""

    registry_root: Path
    source_root: Path
    profile_schema_path: Path
    receipt: AuthorityPublicationReceipt
    artifact: AuthorityArtifact


def validate_authority_candidate(
    *,
    registry_root: Path,
    source_root: Path,
    profile_schema_path: Path | None = None,
) -> ValidatedAuthorityCandidate:
    """Compile and validate a candidate, refusing inputs that change mid-validation.

    The compiler closure is observed after the complete compile, validation and
    evidence projection, so it names every compiler module this process loaded
    to produce the artifact.
    """
    # Import at the compile boundary so tooling discovery does not load validators.
    from ..compiler.authority import compile_validated_authority

    resolved_registry_root, resolved_source_root = canonical_authoring_root_pair(registry_root, source_root)
    resolved_profile_schema = (
        profile_schema_path or resolved_source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    ).resolve(strict=True)
    captured_profile = capture_profile_schema_source(resolved_profile_schema)
    receipt_before = _capture_receipt(
        resolved_registry_root,
        resolved_source_root,
        profile_schema_path=resolved_profile_schema,
        captured_profile_schema=captured_profile,
    )
    identity = resolve_registry_identity(
        resolved_registry_root,
        collect_fingerprints=partial(collect_registry_tree_fingerprints, use_cache=False),
    )
    authority = compile_validated_authority(
        resolved_registry_root,
        resolved_source_root,
        identity=identity,
        profile_schema_path=resolved_profile_schema,
        captured_profile_schema=captured_profile,
        verify_evidence_bytes=True,
        complete_validation=True,
    )
    evidence = _project_evidence(
        authority.catalogues.legal,
        authority.catalogues.sources,
        source_root=resolved_source_root,
    )
    compiler_closure = observe_compiler_closure()
    receipt_after = _capture_receipt(
        resolved_registry_root,
        resolved_source_root,
        profile_schema_path=resolved_profile_schema,
    )
    if receipt_after != receipt_before:
        raise RegistryValidationError(
            "registry candidate changed while it was being validated; authority publication is refused",
        )
    build_identity = AuthorityBuildIdentity.from_inputs(
        receipt_after.source_identity_digest,
        compiler_closure.identity_digest,
    )
    artifact = AuthorityArtifact(
        modelos=authority.modelos,
        catalogues=authority.catalogues,
        identity_digest=build_identity.identity_digest,
        build_identity=build_identity,
        compiler_closure=compiler_closure,
        evidence=evidence,
        profile_schema=authority.profile_schema(),
    )
    return ValidatedAuthorityCandidate(
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        profile_schema_path=resolved_profile_schema,
        receipt=receipt_after,
        artifact=artifact,
    )


@dataclass(frozen=True, slots=True)
class PreparedAuthorityCandidate:
    """A candidate pair the canonical compiler staged, publishable only while its inputs stay current."""

    registry_root: Path
    source_root: Path
    profile_schema_path: Path
    receipt: AuthorityPublicationReceipt
    descriptor_path: Path
    compiler_closure: AuthorityCompilerClosure
    eager_baseline_path: Path | None = None


def stage_authority_candidate(artifact: AuthorityArtifact, output: Path) -> AuthorityDescriptor:
    """Write a validated artifact as a descriptor and content-addressed database pair in ``output``."""
    output.mkdir(parents=True, exist_ok=False)
    compiled = build_authority_database(output / "candidate.sqlite3", artifact)
    database_name = f"authority-{compiled.physical_sha256}.sqlite3"
    compiled.path.replace(output / database_name)
    descriptor = AuthorityDescriptor(
        database=database_name,
        database_size=compiled.byte_count,
        database_sha256=compiled.physical_sha256,
        logical_generation=compiled.logical_generation,
    )
    (output / _DESCRIPTOR_NAME).write_bytes(descriptor.to_bytes())
    return descriptor


def prepare_authority_candidate(
    *,
    registry_root: Path,
    source_root: Path,
    profile_schema_path: Path,
    staging: Path,
    eager_baseline: bool = False,
) -> PreparedAuthorityCandidate:
    """Compile a candidate in the canonical compiler process and admit the pair it staged.

    The parent captures the source receipt first and requires the staged
    generation to record exactly that source identity; the child already
    refused inputs that changed while it validated them.
    """
    resolved_registry_root, resolved_source_root = canonical_authoring_root_pair(registry_root, source_root)
    resolved_profile_schema = profile_schema_path.resolve(strict=True)
    receipt = _capture_receipt(
        resolved_registry_root,
        resolved_source_root,
        profile_schema_path=resolved_profile_schema,
    )
    output = staging / "candidate"
    eager_baseline_path = staging / "eager-baseline.json" if eager_baseline else None
    compiled = run_candidate_compiler(
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        profile_schema_path=resolved_profile_schema,
        output=output,
        eager_baseline_path=eager_baseline_path,
    )
    if not compiled.succeeded:
        raise RegistryValidationError(
            f"the canonical authority compiler refused the candidate (exit {compiled.returncode}): "
            f"{compiled.diagnostics}"
        )
    if compiled.diagnostics:
        print(compiled.diagnostics, file=sys.stderr)
    descriptor_path = output / _DESCRIPTOR_NAME
    try:
        reader = SQLiteAuthorityReader(descriptor_path)
        try:
            build_identity = reader.build_identity()
            compiler_closure = reader.compiler_closure()
        finally:
            reader.close()
    except AuthorityStoreError as exc:
        raise RegistryValidationError(
            f"the canonical authority compiler staged an inadmissible candidate: {exc}"
        ) from exc
    if build_identity.source_identity_digest != receipt.source_identity_digest:
        raise RegistryValidationError(
            "the staged candidate records other source inputs than this publication captured; publication is refused"
        )
    return PreparedAuthorityCandidate(
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        profile_schema_path=resolved_profile_schema,
        receipt=receipt,
        descriptor_path=descriptor_path,
        compiler_closure=compiler_closure,
        eager_baseline_path=eager_baseline_path,
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
    source_entries = tuple(
        _project_source_evidence(sources[source_id], source_root=source_root)
        for source_id in sorted(embedded_source_ids(sources))
    )
    return AuthorityEvidenceProjection(legal=entries, sources=source_entries)


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


def authority_source_identity(
    *,
    registry_root: Path,
    source_root: Path,
    profile_schema_path: Path | None = None,
) -> str:
    """Return the content-addressed source identity a publication of these inputs would record.

    Costs a content read of every registry and source-evidence file and no
    compilation. The compiler half of a generation's identity is known only
    from a recorded compiler closure, which :func:`authority_database_currency`
    re-hashes.
    """
    resolved_registry_root, resolved_source_root = canonical_authoring_root_pair(registry_root, source_root)
    return _capture_receipt(
        resolved_registry_root,
        resolved_source_root,
        profile_schema_path=profile_schema_path,
    ).source_identity_digest


def authority_database_currency(
    descriptor_path: Path,
    *,
    registry_root: Path,
    source_root: Path,
    profile_schema_path: Path | None = None,
    compiler_source_roots: Mapping[str, Path] | None = None,
) -> AuthorityDatabaseCurrency:
    """Compare an admitted indexed generation with the exact live compiler receipt.

    Nothing is compiled. The live compiler identity re-hashes the generation's
    recorded compiler closure under ``compiler_source_roots``, which default to
    this checkout's package and ``dev/registry`` directories; an edit outside
    that closure cannot change what the compiler loads and so is not drift.
    """
    roots = canonical_authoring_root_pair(registry_root, source_root)
    receipt = _capture_receipt(*roots, profile_schema_path=profile_schema_path)
    try:
        reader = SQLiteAuthorityReader(descriptor_path)
        try:
            recorded_identity = reader.pin().logical_generation
            recorded_build = reader.build_identity()
            recorded_closure = reader.compiler_closure()
        finally:
            reader.close()
    except AuthorityStoreFormatError as exc:
        return _unknown_generation_currency(
            descriptor_path, AuthorityDatabaseCurrencyStatus.UNSUPPORTED_FORMAT, receipt, exc
        )
    except (AuthorityStoreError, OSError, ValueError) as exc:
        return _unknown_generation_currency(descriptor_path, AuthorityDatabaseCurrencyStatus.UNREADABLE, receipt, exc)
    candidate_build = AuthorityBuildIdentity.from_inputs(
        receipt.source_identity_digest,
        live_compiler_closure(recorded_closure, roots=compiler_source_roots).identity_digest,
    )
    status = (
        AuthorityDatabaseCurrencyStatus.CURRENT
        if recorded_identity == candidate_build.identity_digest
        else AuthorityDatabaseCurrencyStatus.STALE
    )
    drifted = tuple(
        build_input
        for build_input, recorded, candidate in (
            (
                AuthorityBuildInput.SOURCE,
                recorded_build.source_identity_digest,
                candidate_build.source_identity_digest,
            ),
            (
                AuthorityBuildInput.COMPILER,
                recorded_build.compiler_identity_digest,
                candidate_build.compiler_identity_digest,
            ),
        )
        if recorded != candidate
    )
    detail = (
        "the indexed generation matches the live source manifest, compiler build, and component dependencies"
        if status is AuthorityDatabaseCurrencyStatus.CURRENT
        else "the indexed generation logical identity differs from the live complete-authority receipt; drifted: "
        + (", ".join(build_input.value for build_input in drifted) or "none")
    )
    return AuthorityDatabaseCurrency(
        descriptor_path=descriptor_path,
        status=status,
        candidate_source_identity_digest=receipt.source_identity_digest,
        candidate_identity_digest=candidate_build.identity_digest,
        recorded_identity_digest=recorded_identity,
        candidate_build_identity=candidate_build,
        recorded_build_identity=recorded_build,
        detail=detail,
        drifted_inputs=drifted,
    )


def _unknown_generation_currency(
    descriptor_path: Path,
    status: AuthorityDatabaseCurrencyStatus,
    receipt: AuthorityPublicationReceipt,
    refusal: Exception,
) -> AuthorityDatabaseCurrency:
    """Report a generation whose receipts and compiler closure could not be admitted."""
    return AuthorityDatabaseCurrency(
        descriptor_path=descriptor_path,
        status=status,
        candidate_source_identity_digest=receipt.source_identity_digest,
        candidate_identity_digest=None,
        recorded_identity_digest=None,
        candidate_build_identity=None,
        recorded_build_identity=None,
        detail=f"{type(refusal).__name__}: {refusal}",
    )


def _capture_receipt(
    registry_root: Path,
    source_root: Path,
    *,
    profile_schema_path: Path | None = None,
    captured_profile_schema: CapturedProfileSchema | None = None,
) -> AuthorityPublicationReceipt:
    """Capture every mutable registry, evidence and profile input of this candidate."""
    registry_identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=partial(collect_registry_tree_fingerprints, use_cache=False),
    )
    source_evidence = collect_source_evidence_fingerprints(source_root, use_cache=False)
    source_evidence_content_digests = tuple(
        (path, hash_file(Path(path))[0]) for path, _byte_count, _modified_ns in source_evidence
    )
    profile_path = profile_schema_path or source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
    if captured_profile_schema is not None:
        if captured_profile_schema.source_path != profile_path.resolve(strict=True):
            raise RegistryValidationError("captured profile schema path differs from the publication input")
        profile_schema_sha256 = sha256_hex(captured_profile_schema.payload)
    else:
        try:
            profile_schema_sha256 = sha256_hex(profile_path.resolve(strict=True).read_bytes())
        except OSError as exc:
            raise RegistryValidationError(f"profile schema source is unavailable at {profile_path}") from exc
    source_identity_digest = content_hash_hex(
        {
            "schema": _CANDIDATE_IDENTITY_SCHEMA,
            "registry": _registry_content_digests(registry_root),
            "source_evidence": sorted(
                [_relative_posix(Path(path), source_root), digest]
                for path, digest in source_evidence_content_digests
                if _is_candidate_input(Path(path).relative_to(source_root))
            ),
            "profile_schema": profile_schema_sha256,
        }
    )
    return AuthorityPublicationReceipt(
        registry_identity_digest=registry_identity.digest,
        source_evidence_fingerprints=source_evidence,
        source_evidence_content_digests=source_evidence_content_digests,
        profile_schema_sha256=profile_schema_sha256,
        source_identity_digest=source_identity_digest,
    )


def authority_publication_destination() -> Path:
    """Resolve the directory a publication writes into, from configuration alone.

    The publisher cannot resolve its destination through the descriptor
    selector: that selector refuses a directory holding no descriptor, so a
    first publication into an empty authority tree would fail before it could
    create the descriptor that would have made the selector succeed. The
    configured root is therefore read directly, and the directory is not
    required to exist or to hold anything yet.

    Returns:
        The configured authority root.

    Raises:
        RegistryValidationError: When no root is configured. Publication writes
            generated output whose location is a deliberate choice, so an
            unconfigured destination is a refusal rather than a guess at the
            packaged location, which callers must treat as read-only.
    """
    from cadrumo.core.config import load_settings

    configured = load_settings().cadrumo_authority_root
    if configured is None:
        raise RegistryValidationError(
            "authority publication has no destination; set CADRUMO_AUTHORITY_ROOT or pass an explicit destination"
        )
    return configured


def publish_sqlite_authority_candidate(
    *,
    registry_root: Path,
    source_root: Path,
    profile_schema_path: Path,
    destination: Path,
    eager_baseline_path: Path | None = None,
) -> AuthorityDescriptor:
    """Compile in the canonical child outside the destination lock, then publish only while current."""
    resolved_destination = destination.resolve()
    resolved_destination.mkdir(parents=True, exist_ok=True)
    descriptor_path = resolved_destination / _DESCRIPTOR_NAME
    with TemporaryDirectory(prefix="authority-candidate-", dir=resolved_destination) as staging:
        candidate = prepare_authority_candidate(
            registry_root=registry_root,
            source_root=source_root,
            profile_schema_path=profile_schema_path,
            staging=Path(staging),
            eager_baseline=eager_baseline_path is not None,
        )
        with exclusive_file_lock(
            descriptor_path,
            timeout=_PUBLICATION_LOCK_TIMEOUT,
            retry_backoff=_PUBLICATION_LOCK_RETRY_BACKOFF,
        ):
            _require_candidate_receipt(candidate)
            if eager_baseline_path is not None and candidate.eager_baseline_path is not None:
                with hardened_staged_publication(eager_baseline_path) as publication:
                    publication.path.write_bytes(candidate.eager_baseline_path.read_bytes())
                    publication.publish()
            staged = AuthorityDescriptor.read(candidate.descriptor_path)
            return _install_authority_database(
                candidate.descriptor_path.parent / staged.database,
                staged.logical_generation,
                destination=resolved_destination,
                require_current=lambda: _require_candidate_receipt(candidate),
            )


def _require_candidate_receipt(candidate: PreparedAuthorityCandidate) -> None:
    current = _capture_receipt(
        candidate.registry_root,
        candidate.source_root,
        profile_schema_path=candidate.profile_schema_path,
    )
    if current != candidate.receipt:
        raise RegistryValidationError(
            "registry candidate input receipt changed after validation; descriptor publication is refused"
        )
    recorded = candidate.compiler_closure
    if live_compiler_closure(recorded) != recorded:
        raise RegistryValidationError(
            "authority compiler sources changed after validation; descriptor publication is refused"
        )


def install_validated_authority_database(
    artifact: AuthorityArtifact,
    *,
    destination: Path,
    require_current: Callable[[], None],
) -> AuthorityDescriptor:
    """Install exact validated bytes under the destination's sole publication lock."""
    resolved_destination = destination.resolve()
    resolved_destination.mkdir(parents=True, exist_ok=True)
    descriptor_path = resolved_destination / "authority.current.json"
    with exclusive_file_lock(
        descriptor_path,
        timeout=_PUBLICATION_LOCK_TIMEOUT,
        retry_backoff=_PUBLICATION_LOCK_RETRY_BACKOFF,
    ):
        return _install_validated_authority_database(
            artifact,
            destination=resolved_destination,
            require_current=require_current,
        )


def _remove_unpublished_install(
    installed: Path,
    *,
    created_install: bool,
    descriptor_published: bool,
) -> None:
    """Remove a newly-created database when publication did not complete."""
    if created_install and not descriptor_published:
        with suppress(OSError):
            installed.unlink()


def _install_validated_authority_database(
    artifact: AuthorityArtifact,
    *,
    destination: Path,
    require_current: Callable[[], None],
) -> AuthorityDescriptor:
    """Build and install exact validated bytes while the caller owns the publication lock."""
    resolved_destination = destination.resolve()
    with TemporaryDirectory(prefix="authority-candidate-", dir=resolved_destination) as temporary:
        compiled = build_authority_database(Path(temporary) / "candidate.sqlite3", artifact)
        return _install_authority_database(
            compiled.path,
            compiled.logical_generation,
            destination=resolved_destination,
            require_current=require_current,
        )


def _install_authority_database(
    staged_database: Path,
    logical_generation: str,
    *,
    destination: Path,
    require_current: Callable[[], None],
) -> AuthorityDescriptor:
    """Install one staged database under its content address and cut the descriptor over to it."""
    descriptor_path = destination / _DESCRIPTOR_NAME
    payload = staged_database.read_bytes()
    physical_sha256 = sha256_hex(payload)
    database_name = f"authority-{physical_sha256}.sqlite3"
    installed = destination / database_name
    created_install = False
    descriptor_published = False
    try:
        if installed.exists():
            if installed.stat().st_size != len(payload) or sha256_hex(installed.read_bytes()) != physical_sha256:
                raise RegistryValidationError(
                    f"content-addressed authority collision at {installed}; existing bytes differ"
                )
        else:
            with installed.open("xb") as handle:
                created_install = True
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        descriptor = AuthorityDescriptor(
            database=database_name,
            database_size=len(payload),
            database_sha256=physical_sha256,
            logical_generation=logical_generation,
        )
        with hardened_staged_publication(descriptor_path) as publication:
            publication.path.write_bytes(descriptor.to_bytes())
            reader = SQLiteAuthorityReader(publication.path)
            try:
                with reader.lease() as pin:
                    for query in reader.component_queries():
                        reader.load(query, pin=pin)
            finally:
                reader.close()
            require_current()
            publication.publish()
            descriptor_published = True
    finally:
        _remove_unpublished_install(
            installed,
            created_install=created_install,
            descriptor_published=descriptor_published,
        )
    _cleanup_retired_authority_databases(destination, current_database=descriptor.database)
    return descriptor


def _cleanup_retired_authority_databases(destination: Path, *, current_database: str) -> tuple[Path, ...]:
    """Retire every superseded generation after cutover, reporting what survived.

    A file this targets is one the published descriptor does not name, so no
    reader that resolved through the current descriptor can be using it. A
    reader still holding a superseded descriptor is reading authority that has
    been withdrawn, and losing its file makes that loud instead of letting it
    continue on retired bytes. Unrelated files and the newly selected database
    are never targets.

    Retirement is not optional housekeeping: the whole directory ships in the
    wheel, so a generation left behind is ~80MB of superseded authority in a
    release artefact. Windows still refuses deletion while SQLite holds a
    generation open, and that refusal is the only cross-process lease signal
    available, so the file is left for a later publication to retire and named
    in the return value rather than passing silently.
    """
    leased: list[Path] = []
    for candidate in destination.glob("authority-*.sqlite3"):
        if candidate.name == current_database:
            continue
        if re.fullmatch(r"authority-[0-9a-f]{64}\.sqlite3", candidate.name) is None:
            continue
        try:
            candidate.unlink()
        except OSError:
            leased.append(candidate)
    if leased:
        names = ", ".join(sorted(path.name for path in leased))
        print(
            f"authority retirement deferred for {len(leased)} superseded generation(s), still open by a reader: "
            f"{names}. They remain in {destination} until a later publication retires them. They are not "
            f"published: packaging selects the descriptor and the one database it names, never the directory.",
            file=sys.stderr,
        )
    return tuple(leased)


def promote_accepted_authority_database(
    candidate_descriptor_path: Path,
    *,
    destination: Path,
) -> AuthorityDescriptor:
    """Promote exact already-accepted bytes without recompiling the generation."""
    candidate_descriptor = candidate_descriptor_path.resolve(strict=True)
    accepted_descriptor_bytes = candidate_descriptor.read_bytes()
    descriptor = AuthorityDescriptor.read(candidate_descriptor)
    if candidate_descriptor.read_bytes() != accepted_descriptor_bytes:
        raise RegistryValidationError("accepted authority descriptor changed during admission")
    candidate_database = (candidate_descriptor.parent / descriptor.database).resolve(strict=True)
    if candidate_descriptor.parent != candidate_database.parent:
        raise RegistryValidationError("accepted authority database escapes its candidate directory")
    payload = candidate_database.read_bytes()
    if len(payload) != descriptor.database_size or sha256_hex(payload) != descriptor.database_sha256:
        raise RegistryValidationError("accepted authority database bytes disagree with their descriptor")

    resolved_destination = destination.resolve()
    resolved_destination.mkdir(parents=True, exist_ok=True)
    descriptor_path = resolved_destination / "authority.current.json"
    with exclusive_file_lock(
        descriptor_path,
        timeout=_PUBLICATION_LOCK_TIMEOUT,
        retry_backoff=_PUBLICATION_LOCK_RETRY_BACKOFF,
    ):
        if candidate_descriptor.read_bytes() != accepted_descriptor_bytes:
            raise RegistryValidationError("accepted authority descriptor changed before locked promotion")
        return _promote_accepted_authority_bytes(
            accepted_descriptor_bytes,
            candidate_database,
            descriptor,
            destination=resolved_destination,
        )


def _promote_accepted_authority_bytes(
    accepted_descriptor_bytes: bytes,
    candidate_database: Path,
    descriptor: AuthorityDescriptor,
    *,
    destination: Path,
) -> AuthorityDescriptor:
    """Copy one already-verified candidate while holding its destination lock."""
    payload = candidate_database.read_bytes()
    if len(payload) != descriptor.database_size or sha256_hex(payload) != descriptor.database_sha256:
        raise RegistryValidationError("accepted authority database changed before locked promotion")

    resolved_destination = destination.resolve()
    installed_database = resolved_destination / descriptor.database
    if installed_database.exists():
        existing = installed_database.read_bytes()
        if len(existing) != descriptor.database_size or sha256_hex(existing) != descriptor.database_sha256:
            raise RegistryValidationError(
                f"content-addressed authority collision at {installed_database}; existing bytes differ"
            )
    else:
        with installed_database.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    descriptor_path = resolved_destination / "authority.current.json"
    with hardened_staged_publication(descriptor_path) as publication:
        publication.path.write_bytes(accepted_descriptor_bytes)
        reader = SQLiteAuthorityReader(publication.path)
        try:
            if reader.pin().logical_generation != descriptor.logical_generation:
                raise RegistryValidationError("promoted authority logical generation changed")
        finally:
            reader.close()
        publication.publish()
    if installed_database.read_bytes() != payload or descriptor_path.read_bytes() != accepted_descriptor_bytes:
        raise RegistryValidationError("promoted authority bytes differ from the accepted candidate")
    _cleanup_retired_authority_databases(
        resolved_destination,
        current_database=descriptor.database,
    )
    return descriptor


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
