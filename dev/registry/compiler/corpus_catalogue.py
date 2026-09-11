"""Development-only verification of the authored source corpus.

These checks prove the mutable acquisition tree before publication.  Runtime
uses the published authority artifact and immutable evidence metadata instead.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.hashing import hash_file
from cadrumo.core.resources.bundled_data import resolve_companion_binary
from cadrumo.domain.calculations.registry.artifact_catalogue import (
    ArtifactCatalogue,
    ArtifactIdentity,
    ArtifactRole,
    compile_artifact_catalogue,
    record_design_manifest_identities,
    registry_source_identity,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_base import RegistrySourceKind
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.static_inspection import GeneratedArtifactSource

from .legal_grounding import PROVISION_SUFFIXED_FILENAME

_NORMATIVES_TREE_PREFIX: Final = "corpus/normatives/"
_SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR: Final = 10000


def verify_source_file(root: Path, source: GeneratedArtifactSource) -> Path:
    """Verify a source declaration against the publication corpus bytes."""
    repo_root = root.resolve()
    path = _resolve_corpus_path(repo_root, source)
    if repo_root not in path.parents and path != repo_root:
        raise RegistryValidationError(f"source {source.id!r} escapes repository root")
    if path.is_file():
        present_path = path
        _verify_manual_structure(repo_root, source)
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
    verified: set[tuple[Path, int, str]] = set()
    for source in sources.values():
        key = ((root / source.corpus_path).resolve(), source.bytes, source.sha256)
        if key not in verified:
            verify_source_file(root, source)
            verified.add(key)


def verify_catalogue_identity_bindings(catalogue: ArtifactCatalogue, sources: Mapping[str, SourceReference]) -> None:
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
                f"source {source.id!r} does not exactly bind an official artifact catalog identity for {source.corpus_path!r}"
            )
    if failures:
        raise RegistryValidationError("; ".join(sorted(failures)))


def compile_record_design_manifest_catalogue(
    root: Path, sources: Mapping[str, SourceReference]
) -> tuple[ArtifactCatalogue, Mapping[str, SourceReference]] | None:
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
            raw_manifest = json.loads(bundle_root.joinpath(*manifest_path.parts).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RegistryValidationError(
                f"record-design manifest {manifest_path.as_posix()!r} is unavailable: {error}"
            ) from error
        if not isinstance(raw_manifest, Mapping):
            raise RegistryValidationError(f"record-design manifest {manifest_path.as_posix()!r} must be a JSON object")
        try:
            identities.extend(record_design_manifest_identities(raw_manifest, manifest_path=manifest_path.as_posix()))
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
            f"source {source.id!r} declares corpus_tier={source.corpus_tier!r} but corpus_path {source.corpus_path!r} is not under {_NORMATIVES_TREE_PREFIX!r}"
        )
    provision_suffixed = bool(PROVISION_SUFFIXED_FILENAME.search(path.name))
    if source.corpus_tier == "full_consolidated" and (
        provision_suffixed or path.stat().st_size < _SOURCE_FULL_CONSOLIDATED_SIZE_FLOOR
    ):
        raise RegistryValidationError(
            f"source {source.id!r} declares corpus_tier='full_consolidated' but {path.name!r} is not a full consolidated text"
        )
    if source.corpus_tier == "provision_excerpt" and not provision_suffixed:
        raise RegistryValidationError(
            f"source {source.id!r} declares corpus_tier='provision_excerpt' but {path.name!r} carries no provision-suffixed filename"
        )


def _verify_manual_structure(repo_root: Path, source: GeneratedArtifactSource) -> None:
    if source.kind is not RegistrySourceKind.MANUAL_PDF or not source.corpus_path.startswith("corpus/manuals/"):
        return
    try:
        parts = source.corpus_path.split("/")
        if len(parts) < 5:
            raise ValueError(
                "a practical-manual source must live at 'corpus/manuals/<manual_id>/<year>[/<part>]/source.pdf'"
            )
        from cadrumo.core.config import Settings
        from cadrumo.domain.manuals.loader import load_manual
        from cadrumo.domain.manuals.schema import ManualId, ManualPart

        manuals_dir = repo_root / "corpus" / "manuals"
        if not manuals_dir.is_dir():
            manuals_dir = repo_root / "src" / "cadrumo" / "_data" / "corpus" / "manuals"
        load_manual(
            manual_id=ManualId(parts[2]),
            year=int(parts[3]),
            part=ManualPart.SINGLE if parts[4] == "source.pdf" else ManualPart(parts[4]),
            settings=Settings(aeat_manuals_root=manuals_dir),
        )
    except Exception as exc:
        raise RegistryValidationError(
            f"source {source.id!r} manual structure check failed for path {source.corpus_path!r}: {exc}"
        ) from exc


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
