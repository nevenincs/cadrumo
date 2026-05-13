"""Read-only TOML loader for AEAT registry definitions."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ._errors import RegistryLoadError
from ._schema import LegalReference, ModeloDefinition, ModeloRevision, RegistryCatalogues, SourceReference


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise RegistryLoadError(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise RegistryLoadError(f"{path}: cannot read TOML: {exc}") from exc


def _freeze_toml(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze_toml(item) for item in value)
    if isinstance(value, dict):
        return {key: _freeze_toml(item) for key, item in value.items()}
    return value


def _reject_local_catalogues(path: Path, data: Mapping[str, Any]) -> None:
    forbidden = {"source", "sources", "legal", "legal_refs_catalogue"}
    present = sorted(forbidden.intersection(data))
    if present:
        raise RegistryLoadError(f"{path}: modelo files must not define local legal/source catalogues: {present!r}")


def load_modelo_file(path: Path) -> ModeloDefinition:
    """Load one modelo TOML file into strict schema objects."""

    resolved = path.resolve()
    stat = resolved.stat()
    return _load_modelo_file_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=256)
def _load_modelo_file_cached(path: str, byte_count: int, modified_ns: int) -> ModeloDefinition:
    del byte_count, modified_ns
    source_path = Path(path)
    data = _freeze_toml(_read_toml(source_path))
    return _build_modelo_definition_from_data(source_path, data)


def _build_modelo_definition_from_data(source_path: Path, data: Mapping[str, Any]) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""

    _reject_local_catalogues(source_path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    raw_revisions = data.get("revisions")
    if not isinstance(raw_revisions, dict) or not raw_revisions:
        raise RegistryLoadError(f"{source_path}: missing [revisions.<id>] tables")
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in raw_revisions.items():
        if not isinstance(raw_revision, dict):
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
        payload = {"id": revision_id, **raw_revision}
        try:
            revisions[revision_id] = ModeloRevision.model_validate(payload)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision_id!r}: {exc}") from exc
    try:
        return ModeloDefinition.model_validate({**data["modelo"], "revisions": revisions})
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


def load_modelo_directory(directory: Path) -> ModeloDefinition:
    """Load a modelo from a directory layout.

    The directory must contain ``manifest.toml`` carrying the ``[modelo]``
    metadata table. Per-revision data lives in ``revisions/{id}.toml``
    files; each file declares one or more revisions via top-level
    ``[revisions."<id>"]`` (and ``[[revisions."<id>".X]]`` array tables).
    All revision files are merged into the single in-memory
    ``ModeloDefinition`` that single-file mode produces.

    The directory layout is the segmentation target documented in
    ``.vault/audit/2026-05-08-modelo-100-bulk-segmentation-audit.md``.
    Public API stays identical to ``load_modelo_file``: callers receive
    the same ``ModeloDefinition`` regardless of on-disk layout.
    """

    resolved = directory.resolve()
    if not resolved.is_dir():
        raise RegistryLoadError(f"{resolved}: modelo directory does not exist")
    manifest_path = resolved / "manifest.toml"
    if not manifest_path.is_file():
        raise RegistryLoadError(f"{resolved}: missing manifest.toml")

    fingerprints: list[tuple[str, int, int]] = [_toml_fingerprint(manifest_path)]
    revisions_dir = resolved / "revisions"
    if revisions_dir.is_dir():
        for path in sorted(revisions_dir.glob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    return _load_modelo_directory_cached(str(resolved), tuple(fingerprints))


@lru_cache(maxsize=64)
def _load_modelo_directory_cached(
    directory: str,
    fingerprints: tuple[tuple[str, int, int], ...],
) -> ModeloDefinition:
    del fingerprints
    resolved = Path(directory)
    manifest_path = resolved / "manifest.toml"
    manifest_data = _freeze_toml(_read_toml(manifest_path))
    if "revisions" in manifest_data:
        raise RegistryLoadError(
            f"{manifest_path}: directory-mode manifest must not declare [revisions]; "
            f"revision data lives in revisions/<id>.toml"
        )
    merged_revisions: dict[str, Any] = {}
    revisions_dir = resolved / "revisions"
    if revisions_dir.is_dir():
        for path in sorted(revisions_dir.glob("*.toml")):
            rev_data = _freeze_toml(_read_toml(path))
            _reject_local_catalogues(path, rev_data)
            if "modelo" in rev_data:
                raise RegistryLoadError(f"{path}: revision file must not declare [modelo]; that lives in manifest.toml")
            file_revisions = rev_data.get("revisions")
            if not isinstance(file_revisions, dict) or not file_revisions:
                raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
            for revision_id, raw_revision in file_revisions.items():
                if revision_id in merged_revisions:
                    raise RegistryLoadError(
                        f"{path}: revision {revision_id!r} already declared in another revisions/*.toml file"
                    )
                merged_revisions[revision_id] = raw_revision
    if not merged_revisions:
        raise RegistryLoadError(f"{resolved}: no revisions found in revisions/")
    merged: dict[str, Any] = {**manifest_data, "revisions": merged_revisions}
    return _build_modelo_definition_from_data(resolved, merged)


def load_catalogue_file(path: Path) -> RegistryCatalogues:
    """Load one shared legal/source catalogue TOML file."""

    resolved = path.resolve()
    stat = resolved.stat()
    return _load_catalogue_file_cached(str(resolved), stat.st_size, stat.st_mtime_ns)


@lru_cache(maxsize=128)
def _load_catalogue_file_cached(path: str, byte_count: int, modified_ns: int) -> RegistryCatalogues:
    del byte_count, modified_ns
    source_path = Path(path)
    data = _freeze_toml(_read_toml(source_path))
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    for ref_id, payload in data.get("legal", {}).items():
        try:
            legal[ref_id] = LegalReference.model_validate({"id": ref_id, **payload})
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid legal reference {ref_id!r}: {exc}") from exc
    for ref_id, payload in data.get("sources", data.get("source", {})).items():
        try:
            sources[ref_id] = SourceReference.model_validate({"id": ref_id, **payload})
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid source reference {ref_id!r}: {exc}") from exc
    return RegistryCatalogues(legal=legal, sources=sources)


def load_registry_tree(root: Path) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load all registry files from ``root``.

    Discovers modelos in two layouts:
      * single-file: ``modelos/<id>.toml``
      * directory:   ``modelos/<id>/manifest.toml`` + ``modelos/<id>/revisions/*.toml``

    A single modelo cannot exist in both layouts simultaneously; the
    loader raises ``RegistryLoadError`` if both forms are present.
    """

    resolved = root.resolve()
    legal_dir = resolved / "legal"
    modelos_dir = resolved / "modelos"
    fingerprints: list[tuple[str, int, int]] = []
    for path in sorted(legal_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    for path in sorted(modelos_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    if modelos_dir.is_dir():
        for entry in sorted(modelos_dir.iterdir()):
            if entry.is_dir() and (entry / "manifest.toml").is_file():
                fingerprints.append(_toml_fingerprint(entry / "manifest.toml"))
                revisions_dir = entry / "revisions"
                if revisions_dir.is_dir():
                    for rev_path in sorted(revisions_dir.glob("*.toml")):
                        fingerprints.append(_toml_fingerprint(rev_path))
    return _load_registry_tree_cached(str(resolved), tuple(fingerprints))


@lru_cache(maxsize=32)
def _load_registry_tree_cached(
    root: str,
    fingerprints: tuple[tuple[str, int, int], ...],
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    del fingerprints
    resolved = Path(root)
    legal_dir = resolved / "legal"
    modelos_dir = resolved / "modelos"
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    modelos: list[ModeloDefinition] = []
    for path in sorted(legal_dir.glob("*.toml")):
        catalogue = load_catalogue_file(path)
        overlap_legal = set(legal).intersection(catalogue.legal)
        overlap_sources = set(sources).intersection(catalogue.sources)
        if overlap_legal or overlap_sources:
            raise RegistryLoadError(
                f"{path}: duplicate catalogue ids legal={sorted(overlap_legal)!r} sources={sorted(overlap_sources)!r}"
            )
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
    seen_modelo_ids: set[str] = set()
    for path in sorted(modelos_dir.glob("*.toml")):
        modelo = load_modelo_file(path)
        if modelo.id in seen_modelo_ids:
            raise RegistryLoadError(f"{path}: modelo {modelo.id!r} declared more than once")
        seen_modelo_ids.add(modelo.id)
        modelos.append(modelo)
    if modelos_dir.is_dir():
        for entry in sorted(modelos_dir.iterdir()):
            if entry.is_dir() and (entry / "manifest.toml").is_file():
                modelo = load_modelo_directory(entry)
                if modelo.id in seen_modelo_ids:
                    raise RegistryLoadError(
                        f"{entry}: modelo {modelo.id!r} also declared as a single-file "
                        f"modelos/{modelo.id}.toml; remove one of the two layouts"
                    )
                seen_modelo_ids.add(modelo.id)
                modelos.append(modelo)
    return tuple(modelos), RegistryCatalogues(legal=legal, sources=sources)


def _toml_fingerprint(path: Path) -> tuple[str, int, int]:
    resolved = path.resolve()
    stat = resolved.stat()
    return str(resolved), stat.st_size, stat.st_mtime_ns
