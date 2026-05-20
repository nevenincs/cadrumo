"""Read-only TOML loader for AEAT registry definitions."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from ._errors import RegistryLoadError
from ._schema import (
    LegalParameter,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SourceReference,
)

_REVISION_APPEND_ARRAYS: frozenset[str] = frozenset(
    {
        "parameters",
        "casillas",
        "formulas",
        "bindings",
        "algorithm_providers",
        "algorithm_bindings",
        "relations",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "support_removal_decisions",
        "constructs",
        "dependency_classifications",
    }
)
_REVISION_EXPORT_LAYOUTS = "export_layouts"
_REVISION_CONSTRUCTS = "constructs"
_CONSTRUCT_APPEND_ARRAYS: frozenset[str] = frozenset(
    {
        "casillas",
        "formulas",
        "parameters",
        "bindings",
        "algorithm_providers",
        "algorithm_bindings",
        "relations",
        "export_layouts",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "support_removal_decisions",
        "dependency_classifications",
    }
)
ModeloSourceLayout = Literal["single_file", "directory"]
ModeloRevisionSourceLayout = Literal["revision_file", "fragment_directory"]


@dataclass(frozen=True, slots=True)
class ModeloRevisionSource:
    """On-disk source for one modelo revision before schema validation."""

    revision_id: str
    layout: ModeloRevisionSourceLayout
    path: Path
    fragment_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class ModeloSource:
    """On-disk source for one modelo before schema validation."""

    modelo_id: str
    layout: ModeloSourceLayout
    path: Path
    manifest_path: Path
    revision_sources: tuple[ModeloRevisionSource, ...] = ()


def _read_toml(path: Path) -> dict[str, object]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise RegistryLoadError(f"{path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise RegistryLoadError(f"{path}: cannot read TOML: {exc}") from exc


def _freeze_toml_value(value: object) -> object:
    if isinstance(value, list):
        return tuple(_freeze_toml_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _freeze_toml_value(item) for key, item in value.items()}
    return value


def _freeze_toml(data: dict[str, object]) -> dict[str, object]:
    return {key: _freeze_toml_value(value) for key, value in data.items()}


def _reject_local_catalogues(path: Path, data: Mapping[str, object]) -> None:
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


def _build_modelo_definition_from_data(source_path: Path, data: Mapping[str, object]) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""

    _reject_local_catalogues(source_path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    raw_revisions = data.get("revisions")
    if not isinstance(raw_revisions, dict) or not raw_revisions:
        raise RegistryLoadError(f"{source_path}: missing [revisions.<id>] tables")
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in raw_revisions.items():
        if not isinstance(revision_id, str):
            raise RegistryLoadError(f"{source_path}: revision key must be a string")
        if not isinstance(raw_revision, dict):
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
        payload = {"id": revision_id, **raw_revision}
        try:
            revisions[revision_id] = ModeloRevision.model_validate(payload)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision_id!r}: {exc}") from exc
    modelo_table = data["modelo"]
    if not isinstance(modelo_table, dict):
        raise RegistryLoadError(f"{source_path}: [modelo] must be a table")
    try:
        return ModeloDefinition.model_validate({**modelo_table, "revisions": revisions})
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


def load_modelo_directory(directory: Path) -> ModeloDefinition:
    """Load a modelo from a directory layout.

    The directory must contain ``manifest.toml`` carrying the ``[modelo]``
    metadata table. Per-revision data lives in ``revisions/{id}.toml``
    files, or in ``revisions/{id}/`` fragment directories. Revision
    files declare one or more revisions via top-level
    ``[revisions."<id>"]`` (and ``[[revisions."<id>".X]]`` array tables).
    Fragment directories declare exactly the directory revision id
    across one or more TOML files using the same table shape. All
    revision sources are merged into the single in-memory
    ``ModeloDefinition`` that single-file mode produces.

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
        for path in sorted(revisions_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    return _load_modelo_directory_cached(str(resolved), tuple(fingerprints))


def load_modelo_path(path: Path) -> ModeloDefinition:
    """Load a modelo from either supported on-disk layout."""

    resolved = path.resolve()
    if resolved.is_file():
        return load_modelo_file(resolved)
    if resolved.is_dir():
        return load_modelo_directory(resolved)
    raise RegistryLoadError(f"{resolved}: modelo source does not exist")


def load_modelo_source(source: ModeloSource) -> ModeloDefinition:
    """Load a modelo from a discovered source descriptor."""

    if source.layout == "single_file":
        return load_modelo_file(source.path)
    return load_modelo_directory(source.path)


@lru_cache(maxsize=64)
def _load_modelo_directory_cached(
    directory: str,
    fingerprints: tuple[tuple[str, int, int], ...],
) -> ModeloDefinition:
    del fingerprints
    resolved = Path(directory)
    manifest_data = _load_modelo_manifest(resolved)
    merged_revisions = _load_modelo_revisions(resolved)
    if not merged_revisions:
        raise RegistryLoadError(f"{resolved}: no revisions found in revisions/")
    merged: dict[str, object] = {**manifest_data, "revisions": merged_revisions}
    return _build_modelo_definition_from_data(resolved, merged)


def _load_modelo_manifest(resolved: Path) -> dict[str, object]:
    """Load the directory-mode manifest.toml and reject inlined [revisions]."""
    manifest_path = resolved / "manifest.toml"
    manifest_data = _freeze_toml(_read_toml(manifest_path))
    if "revisions" in manifest_data:
        raise RegistryLoadError(
            f"{manifest_path}: directory-mode manifest must not declare [revisions]; "
            f"revision data lives in revisions/<id>.toml"
        )
    return manifest_data


def _load_modelo_revisions(resolved: Path) -> dict[str, object]:
    """Read every ``revisions/*.toml`` and merge into one ``{revision_id: raw}`` map.

    A missing ``revisions/`` directory returns an empty dict; the
    caller raises if no revisions land. Each per-file ``[revisions.X]``
    payload is added to the merged map under its id, rejecting
    inline ``[modelo]`` declarations, local catalogues, and any
    duplicate ``revision_id`` across files.
    """
    revisions_dir = resolved / "revisions"
    if not revisions_dir.is_dir():
        return {}
    merged_revisions: dict[str, object] = {}
    for path in sorted(revisions_dir.glob("*.toml")):
        _merge_revision_file(path, merged_revisions)
    for path in sorted(revisions_dir.iterdir()):
        if path.is_dir():
            _merge_revision_directory(path, merged_revisions)
    return merged_revisions


def _merge_revision_file(path: Path, merged_revisions: dict[str, object]) -> None:
    """Validate one revisions/*.toml file and append its revisions into ``merged_revisions``."""
    rev_data = _freeze_toml(_read_toml(path))
    _reject_local_catalogues(path, rev_data)
    if "modelo" in rev_data:
        raise RegistryLoadError(f"{path}: revision file must not declare [modelo]; that lives in manifest.toml")
    file_revisions = rev_data.get("revisions")
    if not isinstance(file_revisions, dict) or not file_revisions:
        raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
    for revision_id, raw_revision in file_revisions.items():
        if not isinstance(revision_id, str):
            raise RegistryLoadError(f"{path}: revision key must be a string")
        if revision_id in merged_revisions:
            raise RegistryLoadError(
                f"{path}: revision {revision_id!r} already declared in another revisions/*.toml file"
            )
        merged_revisions[revision_id] = raw_revision


def _merge_revision_directory(path: Path, merged_revisions: dict[str, object]) -> None:
    """Merge a ``revisions/{id}/`` fragment tree into ``merged_revisions``."""
    revision_id = path.name
    if revision_id in merged_revisions:
        raise RegistryLoadError(
            f"{path}: revision {revision_id!r} already declared in another revisions/*.toml file"
        )
    revision_manifest = path / "revision.toml"
    if not revision_manifest.is_file():
        raise RegistryLoadError(f"{path}: revision fragment directory must contain revision.toml")
    fragment_paths = [revision_manifest]
    fragment_paths.extend(sorted(p for p in path.rglob("*.toml") if p != revision_manifest))
    merged_revision: dict[str, object] = {}
    for fragment_path in fragment_paths:
        _merge_revision_fragment(fragment_path, revision_id, merged_revision)
    merged_revisions[revision_id] = merged_revision


def _merge_revision_fragment(path: Path, expected_revision_id: str, merged_revision: dict[str, object]) -> None:
    """Merge one fragment TOML into a single raw revision payload."""
    fragment_data = _freeze_toml(_read_toml(path))
    _reject_local_catalogues(path, fragment_data)
    if "modelo" in fragment_data:
        raise RegistryLoadError(f"{path}: revision fragment must not declare [modelo]; that lives in manifest.toml")
    file_revisions = fragment_data.get("revisions")
    if not isinstance(file_revisions, dict) or not file_revisions:
        raise RegistryLoadError(f"{path}: revision fragment must declare [revisions.<id>]")
    if len(file_revisions) != 1:
        raise RegistryLoadError(f"{path}: revision fragment must declare exactly one revision")
    revision_id, raw_revision = next(iter(file_revisions.items()))
    if not isinstance(revision_id, str):
        raise RegistryLoadError(f"{path}: revision key must be a string")
    if revision_id != expected_revision_id:
        raise RegistryLoadError(
            f"{path}: revision fragment declares {revision_id!r}, expected {expected_revision_id!r}"
        )
    if not isinstance(raw_revision, dict):
        raise RegistryLoadError(f"{path}: revision {revision_id!r} must be a table")
    for key, value in raw_revision.items():
        _merge_revision_fragment_field(path, key, value, merged_revision)


def _merge_revision_fragment_field(
    path: Path,
    key: str,
    value: object,
    merged_revision: dict[str, object],
) -> None:
    if key == _REVISION_CONSTRUCTS:
        if not isinstance(value, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field 'constructs' must be an array")
        existing = merged_revision.get(key, ())
        if not isinstance(existing, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field 'constructs' conflicts with a non-array field")
        merged_revision[key] = _merge_table_array_fragments(
            path,
            existing,
            value,
            item_label="construct",
            append_array_fields=_CONSTRUCT_APPEND_ARRAYS,
        )
        return
    if key in _REVISION_APPEND_ARRAYS:
        if not isinstance(value, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field {key!r} must be an array")
        existing = merged_revision.get(key, ())
        if not isinstance(existing, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field {key!r} conflicts with a non-array field")
        merged_revision[key] = (*existing, *value)
        return
    if key == _REVISION_EXPORT_LAYOUTS:
        if not isinstance(value, tuple):
            raise RegistryLoadError(f"{path}: revision fragment field 'export_layouts' must be an array")
        existing = merged_revision.get(key, ())
        if not isinstance(existing, tuple):
            raise RegistryLoadError(
                f"{path}: revision fragment field 'export_layouts' conflicts with a non-array field"
            )
        merged_revision[key] = _merge_export_layout_fragments(path, existing, value)
        return
    if key in merged_revision:
        raise RegistryLoadError(f"{path}: revision fragment redeclares scalar field {key!r}")
    merged_revision[key] = value


def _merge_export_layout_fragments(
    path: Path,
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
) -> tuple[object, ...]:
    """Merge export-layout fragments by layout id, appending record arrays."""
    layouts: list[object] = list(existing)
    index_by_id: dict[str, int] = {}
    for index, layout in enumerate(layouts):
        if isinstance(layout, dict) and isinstance(layout.get("id"), str):
            index_by_id[layout["id"]] = index
    for layout in incoming:
        if not isinstance(layout, dict) or not isinstance(layout.get("id"), str):
            layouts.append(layout)
            continue
        layout_id = layout["id"]
        existing_index = index_by_id.get(layout_id)
        if existing_index is None:
            index_by_id[layout_id] = len(layouts)
            layouts.append(layout)
            continue
        existing_layout = layouts[existing_index]
        if not isinstance(existing_layout, dict):
            raise RegistryLoadError(f"{path}: export layout {layout_id!r} conflicts with a non-table layout")
        layouts[existing_index] = _merge_export_layout_by_id(path, layout_id, existing_layout, layout)
    return tuple(layouts)


def _merge_export_layout_by_id(
    path: Path,
    layout_id: str,
    existing: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "id":
            continue
        if key == "records":
            if not isinstance(value, tuple):
                raise RegistryLoadError(f"{path}: export layout {layout_id!r} records must be an array")
            existing_records = merged.get("records", ())
            if not isinstance(existing_records, tuple):
                raise RegistryLoadError(f"{path}: export layout {layout_id!r} existing records are not an array")
            merged["records"] = _merge_table_array_fragments(
                path,
                existing_records,
                value,
                item_label=f"export layout {layout_id!r} record",
                append_array_fields=frozenset({"fields"}),
            )
            continue
        if key in merged and merged[key] != value:
            raise RegistryLoadError(
                f"{path}: export layout {layout_id!r} field {key!r} conflicts with another fragment"
            )
        merged[key] = value
    return merged


def _merge_table_array_fragments(
    path: Path,
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
    *,
    item_label: str,
    append_array_fields: frozenset[str],
) -> tuple[object, ...]:
    """Merge fragment table arrays by ``id``, appending explicitly mergeable arrays."""

    items: list[object] = list(existing)
    index_by_id: dict[str, int] = {}
    for index, item in enumerate(items):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            index_by_id[item["id"]] = index
    for item in incoming:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            items.append(item)
            continue
        item_id = item["id"]
        existing_index = index_by_id.get(item_id)
        if existing_index is None:
            index_by_id[item_id] = len(items)
            items.append(item)
            continue
        existing_item = items[existing_index]
        if not isinstance(existing_item, dict):
            raise RegistryLoadError(f"{path}: {item_label} {item_id!r} conflicts with a non-table fragment")
        items[existing_index] = _merge_table_fragment_by_id(
            path,
            existing_item,
            item,
            item_label=item_label,
            item_id=item_id,
            append_array_fields=append_array_fields,
        )
    return tuple(items)


def _merge_table_fragment_by_id(
    path: Path,
    existing: dict[str, object],
    incoming: dict[str, object],
    *,
    item_label: str,
    item_id: str,
    append_array_fields: frozenset[str],
) -> dict[str, object]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "id":
            continue
        if key in append_array_fields:
            if not isinstance(value, tuple):
                raise RegistryLoadError(f"{path}: {item_label} {item_id!r} field {key!r} must be an array")
            existing_values = merged.get(key, ())
            if not isinstance(existing_values, tuple):
                raise RegistryLoadError(
                    f"{path}: {item_label} {item_id!r} field {key!r} conflicts with a non-array fragment"
                )
            merged[key] = (*existing_values, *value)
            continue
        if key in merged and merged[key] != value:
            raise RegistryLoadError(f"{path}: {item_label} {item_id!r} field {key!r} conflicts with another fragment")
        merged[key] = value
    return merged


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
    legal = _validate_catalogue_section(
        source_path,
        raw=data.get("legal"),
        kind="legal reference",
        model=LegalReference,
    )
    sources = _validate_catalogue_section(
        source_path,
        raw=data.get("sources") or data.get("source"),
        kind="source reference",
        model=SourceReference,
    )
    parameters = _validate_catalogue_section(
        source_path,
        raw=data.get("parameters"),
        kind="legal parameter",
        model=LegalParameter,
    )
    return RegistryCatalogues(legal=legal, sources=sources, parameters=parameters)


def _validate_catalogue_section[T: BaseModel](
    source_path: Path,
    *,
    raw: object,
    kind: str,
    model: type[T],
) -> dict[str, T]:
    """Validate one ``{id: payload}`` section of a catalogue TOML into typed records.

    Returns an empty dict when ``raw`` is not a dict (the section is
    absent or malformed at the top level — the absent case is
    legitimate for catalogues that don't declare every section).
    Each ``(id, payload)`` pair is fed through ``model.model_validate``
    with ``id`` injected; type-shape errors raise the typed
    ``RegistryLoadError`` envelope so the catalogue loader's failure
    mode stays uniform across the three sections (legal, sources,
    parameters).
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, T] = {}
    for ref_id, payload in raw.items():
        if not isinstance(ref_id, str) or not isinstance(payload, dict):
            raise RegistryLoadError(f"{source_path}: malformed {kind} entry")
        try:
            out[ref_id] = model.model_validate({"id": ref_id, **payload})
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid {kind} {ref_id!r}: {exc}") from exc
    return out


def load_legal_parameters_only(root: Path) -> Mapping[str, LegalParameter]:
    """Load only the legal-parameter catalogue from ``root/legal/*.toml``.

    Lightweight cycle-safe entry point. Consumers in ``aeat.domain.iva``
    and ``aeat.domain.rental`` need parameter values at module-import
    time, but the full :func:`load_registry_tree` path pulls in
    ``_bindings`` which itself imports from ``aeat.domain.iva`` — a
    circular import.

    This function reuses :func:`load_catalogue_file` (already
    Pydantic-validated and ``lru_cache``-deduplicated) and walks only
    ``root/legal/*.toml``. Modelo parsing, binding validation, and
    cross-catalogue checks do not run; for that, callers must use
    :func:`load_registry_tree`.

    Args:
        root: Repository ``registry/aeat`` directory.

    Returns:
        Frozen mapping of parameter-id → :class:`LegalParameter`.
        Duplicates across files raise :class:`RegistryLoadError`.
    """

    resolved = root.resolve()
    legal_dir = resolved / "legal"
    parameters: dict[str, LegalParameter] = {}
    for path in sorted(legal_dir.glob("*.toml")):
        catalogue = load_catalogue_file(path)
        overlap = set(parameters).intersection(catalogue.parameters)
        if overlap:
            raise RegistryLoadError(f"{path}: duplicate parameter ids {sorted(overlap)!r}")
        parameters.update(catalogue.parameters)
    return parameters


def load_registry_tree(root: Path) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load all registry files from ``root``.

    Discovers modelos in two layouts:
      * single-file: ``modelos/<id>.toml``
      * directory:   ``modelos/<id>/manifest.toml`` + ``modelos/<id>/revisions/*.toml``

    A single modelo cannot exist in both layouts simultaneously; the
    loader raises ``RegistryLoadError`` if both forms are present.
    """

    resolved = root.resolve()
    fingerprints = _collect_registry_tree_fingerprints(resolved)
    return _load_registry_tree_cached(str(resolved), fingerprints)


def discover_modelo_sources(modelos_dir: Path) -> tuple[ModeloSource, ...]:
    """Discover modelo source layouts under a ``modelos/`` directory.

    This is the generic source-layout contract for the registry: callers
    can reason about single-file modelos, directory-mode modelos,
    per-revision files, and fragmented revision directories without
    special-casing a modelo id.
    """

    resolved = modelos_dir.resolve()
    sources: list[ModeloSource] = []
    seen_modelo_ids: dict[str, ModeloSource] = {}
    for path in sorted(resolved.glob("*.toml")):
        modelo = load_modelo_file(path)
        source = ModeloSource(
            modelo_id=modelo.id,
            layout="single_file",
            path=path.resolve(),
            manifest_path=path.resolve(),
        )
        _append_modelo_source(source, sources, seen_modelo_ids)
    if resolved.is_dir():
        for entry in sorted(resolved.iterdir()):
            if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
                continue
            modelo = load_modelo_directory(entry)
            source = ModeloSource(
                modelo_id=modelo.id,
                layout="directory",
                path=entry.resolve(),
                manifest_path=(entry / "manifest.toml").resolve(),
                revision_sources=_discover_revision_sources(entry / "revisions"),
            )
            _append_modelo_source(source, sources, seen_modelo_ids)
    return tuple(sources)


def _append_modelo_source(
    source: ModeloSource,
    sources: list[ModeloSource],
    seen_modelo_ids: dict[str, ModeloSource],
) -> None:
    previous = seen_modelo_ids.get(source.modelo_id)
    if previous is not None:
        raise RegistryLoadError(
            f"{source.path}: modelo {source.modelo_id!r} also declared at {previous.path}; "
            "remove one of the two layouts"
        )
    seen_modelo_ids[source.modelo_id] = source
    sources.append(source)


def _discover_revision_sources(revisions_dir: Path) -> tuple[ModeloRevisionSource, ...]:
    if not revisions_dir.is_dir():
        return ()
    sources: list[ModeloRevisionSource] = []
    for path in sorted(revisions_dir.glob("*.toml")):
        rev_data = _freeze_toml(_read_toml(path))
        file_revisions = rev_data.get("revisions")
        if not isinstance(file_revisions, dict) or not file_revisions:
            raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
        for revision_id in sorted(file_revisions):
            if not isinstance(revision_id, str):
                raise RegistryLoadError(f"{path}: revision key must be a string")
            sources.append(
                ModeloRevisionSource(
                    revision_id=revision_id,
                    layout="revision_file",
                    path=path.resolve(),
                    fragment_paths=(path.resolve(),),
                )
            )
    for path in sorted(revisions_dir.iterdir()):
        if not path.is_dir():
            continue
        revision_manifest = path / "revision.toml"
        fragment_paths = (revision_manifest.resolve(),) if revision_manifest.is_file() else ()
        fragment_paths = (
            *fragment_paths,
            *tuple(p.resolve() for p in sorted(path.rglob("*.toml")) if p != revision_manifest),
        )
        sources.append(
            ModeloRevisionSource(
                revision_id=path.name,
                layout="fragment_directory",
                path=path.resolve(),
                fragment_paths=fragment_paths,
            )
        )
    return tuple(sources)


def _collect_registry_tree_fingerprints(resolved: Path) -> tuple[tuple[str, int, int], ...]:
    """Walk ``resolved`` and return ``(path, size, mtime)`` fingerprints for the lru_cache key.

    Covers every catalogue source the loader will subsequently
    re-open: ``legal/*.toml``, single-file ``modelos/*.toml``, and
    directory-mode ``modelos/<id>/manifest.toml`` plus its
    ``revisions/*.toml`` siblings. The cache key invalidates the
    moment any of those files changes shape on disk.
    """
    legal_dir = resolved / "legal"
    modelos_dir = resolved / "modelos"
    fingerprints: list[tuple[str, int, int]] = []
    for path in sorted(legal_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    for path in sorted(modelos_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    if modelos_dir.is_dir():
        for entry in sorted(modelos_dir.iterdir()):
            fingerprints.extend(_modelo_directory_fingerprints(entry))
    return tuple(fingerprints)


def _modelo_directory_fingerprints(entry: Path) -> tuple[tuple[str, int, int], ...]:
    """Return fingerprints for one directory-mode modelo entry, or ``()`` if not in that layout."""
    if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
        return ()
    fingerprints: list[tuple[str, int, int]] = [_toml_fingerprint(entry / "manifest.toml")]
    revisions_dir = entry / "revisions"
    if revisions_dir.is_dir():
        for rev_path in sorted(revisions_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(rev_path))
    return tuple(fingerprints)


@lru_cache(maxsize=32)
def _load_registry_tree_cached(
    root: str,
    fingerprints: tuple[tuple[str, int, int], ...],
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    del fingerprints
    resolved = Path(root)
    catalogues = _load_shared_catalogue_files(resolved / "legal")
    modelos = _load_all_modelo_definitions(resolved / "modelos")
    return modelos, catalogues


def _load_shared_catalogue_files(legal_dir: Path) -> RegistryCatalogues:
    """Load every ``legal/*.toml`` shared-catalogue file with duplicate-id rejection."""
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    parameters: dict[str, LegalParameter] = {}
    for path in sorted(legal_dir.glob("*.toml")):
        catalogue = load_catalogue_file(path)
        overlap_legal = set(legal).intersection(catalogue.legal)
        overlap_sources = set(sources).intersection(catalogue.sources)
        overlap_parameters = set(parameters).intersection(catalogue.parameters)
        if overlap_legal or overlap_sources or overlap_parameters:
            raise RegistryLoadError(
                f"{path}: duplicate catalogue ids legal={sorted(overlap_legal)!r} "
                f"sources={sorted(overlap_sources)!r} parameters={sorted(overlap_parameters)!r}"
            )
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
        parameters.update(catalogue.parameters)
    return RegistryCatalogues(legal=legal, sources=sources, parameters=parameters)


def _load_all_modelo_definitions(modelos_dir: Path) -> tuple[ModeloDefinition, ...]:
    """Load every modelo (single-file + directory-mode) and reject layout collisions.

    A modelo id present both as ``modelos/<id>.toml`` and as
    ``modelos/<id>/manifest.toml`` is a configuration mistake — the
    loader cannot tell which layout is authoritative, so it raises
    instead of silently picking one.
    """
    return tuple(load_modelo_source(source) for source in discover_modelo_sources(modelos_dir))


def _toml_fingerprint(path: Path) -> tuple[str, int, int]:
    resolved = path.resolve()
    stat = resolved.stat()
    return str(resolved), stat.st_size, stat.st_mtime_ns
