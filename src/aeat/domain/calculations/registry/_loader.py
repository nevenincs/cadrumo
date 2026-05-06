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
    """Load all registry files from ``root``."""

    resolved = root.resolve()
    legal_dir = resolved / "legal"
    modelos_dir = resolved / "modelos"
    fingerprints = tuple(
        _toml_fingerprint(path) for directory in (legal_dir, modelos_dir) for path in sorted(directory.glob("*.toml"))
    )
    return _load_registry_tree_cached(str(resolved), fingerprints)


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
    for path in sorted(modelos_dir.glob("*.toml")):
        modelos.append(load_modelo_file(path))
    return tuple(modelos), RegistryCatalogues(legal=legal, sources=sources)


def _toml_fingerprint(path: Path) -> tuple[str, int, int]:
    resolved = path.resolve()
    stat = resolved.stat()
    return str(resolved), stat.st_size, stat.st_mtime_ns
