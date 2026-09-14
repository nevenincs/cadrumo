"""Development-only verification of the authored source corpus.

These checks prove the mutable acquisition tree before publication.  Runtime
uses the published authority artifact and immutable evidence metadata instead.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Final, cast

from cadrumo.core.corpus_annotation import CORPUS_PAGE_ANNOTATION_SUFFIX, CorpusPageAnnotation
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import hash_file
from cadrumo.core.resources.bundled_data import resolve_companion_binary
from cadrumo.core.type_guards import is_object_dict
from cadrumo.domain.calculations.registry.artifact_catalogue import (
    ArtifactCatalogue,
    ArtifactIdentity,
    ArtifactRole,
    SemanticAnnotation,
    compile_artifact_catalogue,
    manual_manifest_identity,
    record_design_manifest_identities,
    registry_source_identity,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactSource

from .legal_grounding import PROVISION_SUFFIXED_FILENAME

_NORMATIVES_TREE_PREFIX: Final = "corpus/normatives/"
_SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR: Final = 10000


def verify_source_file(root: Path, source: GeneratedArtifactSource) -> Path:
    """Verify source bytes independently of optional authored manual structures.

    Structured manual citations are validated by their legal-reference owner;
    their availability does not establish or invalidate an acquired PDF's identity.
    """
    repo_root = root.resolve()
    path = _resolve_corpus_path(repo_root, source)
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"source {source.id!r} escapes repository root")
    if path.is_file():
        present_path = path
    else:
        companion_path = resolve_companion_binary(*source.corpus_path.split("/"))
        if companion_path is None:
            raise RegistryValidationError(f"source {source.id!r} missing corpus file {source.corpus_path!r}")
        present_path = companion_path
    actual_sha256, length = hash_file(present_path)
    if length != source.bytes:
        raise RegistryValidationError(f"source {source.id!r} byte count mismatch")
    if actual_sha256 != source.sha256:
        raise RegistryValidationError(f"source {source.id!r} sha256 mismatch")
    _validate_source_corpus_tier_declaration(source, present_path)
    return present_path


def verify_source_catalogue(root: Path, sources: Mapping[str, SourceReference]) -> None:
    """Verify every distinct declared source identity against the corpus."""
    verified: set[tuple[Path, int, str]] = set()
    for source in sources.values():
        key = ((root / source.corpus_path).resolve(), source.bytes, source.sha256)
        if key not in verified:
            verify_source_file(root, source)
            verified.add(key)


def verify_manual_annotation_catalogue(root: Path, sources: Mapping[str, SourceReference]) -> None:
    """Catalog every authored PDF page selector against its source and manifest."""
    bundle_root = _bundle_root(root).resolve()
    corpus_root = bundle_root / "corpus"
    annotation_files = scan_directory(
        corpus_root,
        pattern=f"*{CORPUS_PAGE_ANNOTATION_SUFFIX}",
        recursive=True,
        select=DirectoryEntryKind.FILES,
    )
    if not annotation_files:
        return
    sources_by_path: dict[PurePosixPath, list[SourceReference]] = {}
    for source in sources.values():
        sources_by_path.setdefault(PurePosixPath(source.corpus_path), []).append(source)
    known_paths: list[PurePosixPath] = []
    identities: list[ArtifactIdentity] = []
    annotations: list[SemanticAnnotation] = []
    for annotation_file in annotation_files:
        relative = PurePosixPath(*annotation_file.resolve().relative_to(bundle_root).parts)
        target = PurePosixPath(relative.as_posix()[: -len(CORPUS_PAGE_ANNOTATION_SUFFIX)])
        declared_sources = sources_by_path.get(target, [])
        if not declared_sources:
            raise RegistryValidationError(
                f"semantic annotation {relative.as_posix()!r} has no declared registry source target"
            )
        manifest_path = annotation_file.parent / "manifest.json"
        try:
            raw_manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not is_object_dict(raw_manifest):
                raise TypeError("manifest must be a JSON object")
            typed_manifest = cast(Mapping[str, object], raw_manifest)
            identity = manual_manifest_identity(
                typed_manifest,
                manifest_path=(relative.parent / manifest_path.name).as_posix(),
            )
            annotation = CorpusPageAnnotation.model_validate_json(annotation_file.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise RegistryValidationError(
                f"semantic annotation {relative.as_posix()!r} has invalid source metadata: {error}"
            ) from error
        if identity.path != target or annotation.source_sha256 != identity.sha256:
            raise RegistryValidationError(
                f"semantic annotation {relative.as_posix()!r} does not bind its manual manifest source"
            )
        for source in declared_sources:
            if not _same_payload_identity(identity, registry_source_identity(source)):
                raise RegistryValidationError(
                    f"semantic annotation {relative.as_posix()!r} target disagrees with registry source {source.id!r}"
                )
        known_paths.extend((target, relative))
        identities.append(identity)
        annotations.append(SemanticAnnotation(path=relative, target_path=target))
    catalogue = compile_artifact_catalogue(
        known_paths=known_paths,
        official_identities=identities,
        semantic_annotations=annotations,
    )
    if catalogue.diagnostics:
        rendered = "; ".join(
            f"{diagnostic.kind.value} at {diagnostic.path}: {diagnostic.message}"
            for diagnostic in catalogue.diagnostics
        )
        raise RegistryValidationError(f"semantic annotation catalogue is invalid: {rendered}")


def verify_catalogue_identity_bindings(catalogue: ArtifactCatalogue, sources: Mapping[str, SourceReference]) -> None:
    """Require registry source identities to match the official artifact catalogue."""
    failures = [
        f"artifact catalog diagnostic {d.kind.value} for {d.path!s}: {d.message}" for d in catalogue.diagnostics
    ]
    for source in sources.values():
        identity = registry_source_identity(source)
        catalogued = catalogue.identities.get(identity.path)
        if (
            catalogued is None
            or catalogue.roles.get(identity.path) is not ArtifactRole.OFFICIAL_ARTIFACT
            or not _same_payload_identity(catalogued, identity)
        ):
            failures.append(
                f"source {source.id!r} does not exactly bind an official artifact catalog identity "
                f"for {source.corpus_path!r}"
            )
    if failures:
        raise RegistryValidationError("; ".join(sorted(failures)))


def compile_record_design_manifest_catalogue(
    root: Path, sources: Mapping[str, SourceReference]
) -> tuple[ArtifactCatalogue, Mapping[str, SourceReference]] | None:
    """Compile acquisition identities for the declared record-design sources."""
    record_design_sources = {
        source_id: source
        for source_id, source in sources.items()
        if _record_design_manifest_path(source.corpus_path) is not None
    }
    if not record_design_sources:
        return None
    bundle_root = _bundle_root(root)
    identities: list[ArtifactIdentity] = []
    paths = {_record_design_manifest_path(source.corpus_path) for source in record_design_sources.values()}
    for manifest_path in sorted(path for path in paths if path is not None):
        try:
            raw_manifest: object = json.loads(bundle_root.joinpath(*manifest_path.parts).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RegistryValidationError(
                f"record-design manifest {manifest_path.as_posix()!r} is unavailable: {error}"
            ) from error
        if not is_object_dict(raw_manifest):
            raise RegistryValidationError(f"record-design manifest {manifest_path.as_posix()!r} must be a JSON object")
        typed_manifest = cast(Mapping[str, object], raw_manifest)
        try:
            identities.extend(record_design_manifest_identities(typed_manifest, manifest_path=manifest_path.as_posix()))
        except (TypeError, ValueError) as error:
            raise RegistryValidationError(
                f"record-design manifest {manifest_path.as_posix()!r} has invalid acquisition identity: {error}"
            ) from error
    registry_identities = tuple(registry_source_identity(source) for source in record_design_sources.values())
    known_paths = tuple(identity.path for identity in registry_identities)
    known_set = set(known_paths)
    return compile_artifact_catalogue(
        known_paths=known_paths,
        official_identities=tuple(identity for identity in identities if identity.path in known_set),
    ), record_design_sources


def _validate_source_corpus_tier_declaration(source: GeneratedArtifactSource, path: Path) -> None:
    if source.corpus_tier is None:
        return
    if not source.corpus_path.startswith(_NORMATIVES_TREE_PREFIX):
        raise RegistryValidationError(
            f"source {source.id!r} declares corpus_tier={source.corpus_tier!r} "
            f"but corpus_path {source.corpus_path!r} is not under {_NORMATIVES_TREE_PREFIX!r}"
        )
    provision_suffixed = bool(PROVISION_SUFFIXED_FILENAME.search(path.name))
    if source.corpus_tier == "full_consolidated" and (
        provision_suffixed or path.stat().st_size < _SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR
    ):
        raise RegistryValidationError(
            f"source {source.id!r} declares corpus_tier='full_consolidated' "
            f"but {path.name!r} is not a full consolidated text"
        )
    if source.corpus_tier == "provision_excerpt" and not provision_suffixed:
        raise RegistryValidationError(
            f"source {source.id!r} declares corpus_tier='provision_excerpt' "
            f"but {path.name!r} carries no provision-suffixed filename"
        )


def _resolve_corpus_path(root: Path, source: GeneratedArtifactSource) -> Path:
    direct = (root / source.corpus_path).resolve()
    if direct.is_file():
        return direct
    packaged = (root / "src" / "cadrumo" / "_data" / source.corpus_path).resolve()
    return packaged if packaged.is_file() else direct


def _bundle_root(root: Path) -> Path:
    return (
        root
        if (root / "corpus").is_dir()
        else root / "src" / "cadrumo" / "_data"
        if (root / "src" / "cadrumo" / "_data" / "corpus").is_dir()
        else root
    )


def _record_design_manifest_path(corpus_path: str) -> PurePosixPath | None:
    parts = Path(corpus_path).parts
    prefix = ("corpus", "aeat_official", "disenos_registro")
    if len(parts) < len(prefix) + 2 or parts[: len(prefix)] != prefix or not parts[len(prefix)].startswith("modelo_"):
        return None
    return PurePosixPath(*prefix, parts[len(prefix)], "manifest.json")


def _same_payload_identity(left: ArtifactIdentity, right: ArtifactIdentity) -> bool:
    return (
        left.path == right.path
        and left.sha256 == right.sha256
        and left.bytes == right.bytes
        and left.source_url == right.source_url
    )
