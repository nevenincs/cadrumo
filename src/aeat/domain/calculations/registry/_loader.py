"""Read-only TOML loader for AEAT registry definitions."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
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

    data = _freeze_toml(_read_toml(path))
    _reject_local_catalogues(path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{path}: missing [modelo] table")
    raw_revisions = data.get("revisions")
    if not isinstance(raw_revisions, dict) or not raw_revisions:
        raise RegistryLoadError(f"{path}: missing [revisions.<id>] tables")
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in raw_revisions.items():
        if not isinstance(raw_revision, dict):
            raise RegistryLoadError(f"{path}: revision {revision_id!r} must be a table")
        payload = {"id": revision_id, **raw_revision}
        try:
            revisions[revision_id] = ModeloRevision.model_validate(payload)
        except ValidationError as exc:
            raise RegistryLoadError(f"{path}: invalid revision {revision_id!r}: {exc}") from exc
    try:
        return ModeloDefinition.model_validate({**data["modelo"], "revisions": revisions})
    except ValidationError as exc:
        raise RegistryLoadError(f"{path}: invalid modelo definition: {exc}") from exc


def load_catalogue_file(path: Path) -> RegistryCatalogues:
    """Load one shared legal/source catalogue TOML file."""

    data = _freeze_toml(_read_toml(path))
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    for ref_id, payload in data.get("legal", {}).items():
        try:
            legal[ref_id] = LegalReference.model_validate({"id": ref_id, **payload})
        except ValidationError as exc:
            raise RegistryLoadError(f"{path}: invalid legal reference {ref_id!r}: {exc}") from exc
    for ref_id, payload in data.get("sources", data.get("source", {})).items():
        try:
            sources[ref_id] = SourceReference.model_validate({"id": ref_id, **payload})
        except ValidationError as exc:
            raise RegistryLoadError(f"{path}: invalid source reference {ref_id!r}: {exc}") from exc
    return RegistryCatalogues(legal=legal, sources=sources)


def load_registry_tree(root: Path) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load all registry files from ``root``."""

    legal_dir = root / "legal"
    modelos_dir = root / "modelos"
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
