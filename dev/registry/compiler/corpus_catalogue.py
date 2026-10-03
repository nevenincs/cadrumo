"""Development-only verification of the authored source corpus.

These checks prove the mutable acquisition tree before publication.  Runtime
uses the published authority artifact and immutable evidence metadata instead.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.corpus_text import CorpusAnchorResolutionError
from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.hashing import hash_file
from cadrumo.core.text_fold import ascii_slug
from cadrumo.core.type_guards import is_object_dict
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactSource
from dev.corpus.artifact_catalogue import (
    ArtifactCatalogue,
    ArtifactIdentity,
    ArtifactRole,
    SemanticAnnotation,
    compile_artifact_catalogue,
    manual_manifest_identity,
    record_design_manifest_identities,
    registry_source_identity,
)
from dev.registry.compiler.corpus_annotation import (
    CORPUS_PAGE_ANNOTATION_SUFFIX,
    CorpusPageAnnotation,
    resolve_annotated_pdf_pages,
)
from dev.registry.compiler.corpus_source_location import PACKAGED_DATA_ROOT, CorpusPathEscapeError, locate_corpus_file

from .legal_grounding import PROVISION_SUFFIXED_FILENAME

_NORMATIVES_TREE_PREFIX: Final = "corpus/normatives/"
_SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR: Final = 10000


def _string_keyed_object_mapping(value: object, *, subject: str) -> Mapping[str, object]:
    """Validate JSON object keys before passing the object to a typed consumer."""
    if not isinstance(value, dict):
        raise TypeError(f"{subject} must be a JSON object")
    typed: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{subject} keys must be strings")
        typed[key] = item
    return typed


def verify_source_file(root: Path, source: GeneratedArtifactSource) -> Path:
    """Verify source bytes independently of optional authored manual structures.

    Structured manual citations are validated by their legal-reference owner;
    their availability does not establish or invalidate an acquired PDF's identity.
    """
    try:
        present_path = locate_corpus_file(root, source.corpus_path)
    except CorpusPathEscapeError as exc:
        raise RegistryValidationError(f"source {source.id!r} escapes repository root") from exc
    if present_path is None:
        raise RegistryValidationError(f"source {source.id!r} missing corpus file {source.corpus_path!r}")
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


def _read_manual_annotation_identity(
    annotation_file: Path, relative: PurePosixPath
) -> tuple[ArtifactIdentity, CorpusPageAnnotation]:
    manifest_path = annotation_file.parent / "manifest.json"
    try:
        raw_manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not is_object_dict(raw_manifest):
            raise TypeError("manifest must be a JSON object")
        typed_manifest = _string_keyed_object_mapping(raw_manifest, subject="manifest")
        identity = manual_manifest_identity(
            typed_manifest,
            manifest_path=(relative.parent / manifest_path.name).as_posix(),
        )
        annotation = CorpusPageAnnotation.model_validate_json(annotation_file.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RegistryValidationError(
            f"semantic annotation {relative.as_posix()!r} has invalid source metadata: {error}"
        ) from error
    return identity, annotation


def _verify_manual_annotation_source(
    root: Path,
    relative: PurePosixPath,
    target: PurePosixPath,
    identity: ArtifactIdentity,
    annotation: CorpusPageAnnotation,
    declared_sources: list[SourceReference],
) -> Path:
    if identity.path != target or annotation.source_sha256 != identity.sha256:
        raise RegistryValidationError(
            f"semantic annotation {relative.as_posix()!r} does not bind its manual manifest source"
        )
    for source in declared_sources:
        if not _same_payload_identity(identity, registry_source_identity(source)):
            raise RegistryValidationError(
                f"semantic annotation {relative.as_posix()!r} target disagrees with registry source {source.id!r}"
            )
    return verify_source_file(root, declared_sources[0])


def _verify_manual_annotation_selections(
    relative: PurePosixPath,
    target: PurePosixPath,
    annotation_file: Path,
    annotation: CorpusPageAnnotation,
    source_path: Path,
) -> None:
    extraction_path = annotation_file.with_name(target.name + ".extracted.json")
    for selection in annotation.selections:
        if selection.anchor != ascii_slug(selection.anchor):
            raise RegistryValidationError(
                f"semantic annotation {relative.as_posix()!r} has non-canonical anchor {selection.anchor!r}"
            )
        try:
            resolve_annotated_pdf_pages(
                source_path,
                anchor=selection.anchor,
                annotation_path=annotation_file,
                extracted_path=extraction_path,
            )
        except CorpusAnchorResolutionError as error:
            raise RegistryValidationError(
                f"semantic annotation {relative.as_posix()!r} cannot resolve anchor "
                f"{selection.anchor!r} against its sibling extraction: {error}"
            ) from error


def _verify_manual_annotation_file(
    root: Path,
    bundle_root: Path,
    annotation_file: Path,
    sources_by_path: dict[PurePosixPath, list[SourceReference]],
) -> tuple[PurePosixPath, PurePosixPath, ArtifactIdentity]:
    relative = PurePosixPath(*annotation_file.resolve().relative_to(bundle_root).parts)
    target = PurePosixPath(relative.as_posix()[: -len(CORPUS_PAGE_ANNOTATION_SUFFIX)])
    declared_sources = sources_by_path.get(target, [])
    if not declared_sources:
        raise RegistryValidationError(
            f"semantic annotation {relative.as_posix()!r} has no declared registry source target"
        )
    identity, annotation = _read_manual_annotation_identity(annotation_file, relative)
    source_path = _verify_manual_annotation_source(root, relative, target, identity, annotation, declared_sources)
    _verify_manual_annotation_selections(relative, target, annotation_file, annotation, source_path)
    return target, relative, identity


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
        target, relative, identity = _verify_manual_annotation_file(root, bundle_root, annotation_file, sources_by_path)
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
    record_design_sources = _record_design_sources(sources)
    if not record_design_sources:
        return None
    bundle_root = _bundle_root(root)
    identities: list[ArtifactIdentity] = []
    for manifest_path in sorted(_record_design_manifest_paths(record_design_sources)):
        identities.extend(_record_design_manifest_identities(bundle_root, manifest_path))
    return _compile_record_design_catalogue(identities, record_design_sources)


def _record_design_sources(sources: Mapping[str, SourceReference]) -> dict[str, SourceReference]:
    return {
        source_id: source
        for source_id, source in sources.items()
        if _record_design_manifest_path(source.corpus_path) is not None
    }


def _record_design_manifest_paths(sources: Mapping[str, SourceReference]) -> set[PurePosixPath]:
    return {
        manifest_path
        for source in sources.values()
        if (manifest_path := _record_design_manifest_path(source.corpus_path)) is not None
    }


def _compile_record_design_catalogue(
    identities: list[ArtifactIdentity], record_design_sources: Mapping[str, SourceReference]
) -> tuple[ArtifactCatalogue, Mapping[str, SourceReference]]:
    registry_identities = tuple(registry_source_identity(source) for source in record_design_sources.values())
    known_paths = tuple(identity.path for identity in registry_identities)
    known_set = set(known_paths)
    return compile_artifact_catalogue(
        known_paths=known_paths,
        official_identities=tuple(identity for identity in identities if identity.path in known_set),
    ), record_design_sources


def _record_design_manifest_identities(bundle_root: Path, manifest_path: PurePosixPath) -> tuple[ArtifactIdentity, ...]:
    try:
        raw_manifest: object = json.loads(bundle_root.joinpath(*manifest_path.parts).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RegistryValidationError(
            f"record-design manifest {manifest_path.as_posix()!r} is unavailable: {error}"
        ) from error
    if not is_object_dict(raw_manifest):
        raise RegistryValidationError(f"record-design manifest {manifest_path.as_posix()!r} must be a JSON object")
    try:
        typed_manifest = _string_keyed_object_mapping(raw_manifest, subject="record-design manifest")
        return record_design_manifest_identities(typed_manifest, manifest_path=manifest_path.as_posix())
    except (TypeError, ValueError) as error:
        raise RegistryValidationError(
            f"record-design manifest {manifest_path.as_posix()!r} has invalid acquisition identity: {error}"
        ) from error


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


def _bundle_root(root: Path) -> Path:
    return (
        root
        if (root / "corpus").is_dir()
        else root / PACKAGED_DATA_ROOT
        if (root / PACKAGED_DATA_ROOT / "corpus").is_dir()
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
