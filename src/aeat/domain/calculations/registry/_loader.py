"""Read-only TOML loader for AEAT registry definitions."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from ._errors import RegistryLoadError
from ._schema import (
    LegalParameter,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SourceReference,
)


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
    files; each file declares one or more revisions via top-level
    ``[revisions."<id>"]`` (and ``[[revisions."<id>".X]]`` array tables).
    All revision files are merged into the single in-memory
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


def _validate_catalogue_section[T](
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
            out[ref_id] = model.model_validate({"id": ref_id, **payload})  # type: ignore[attr-defined]
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid {kind} {ref_id!r}: {exc}") from exc
    return out


def load_legal_parameters_only(root: Path) -> Mapping[str, LegalParameter]:
    """Load only the legal-parameter catalogue from ``root/legal/*.toml``.

    Lightweight cycle-safe entry point. Consumers in ``aeat.domain.vat``
    and ``aeat.domain.rental`` need parameter values at module-import
    time, but the full :func:`load_registry_tree` path pulls in
    ``_bindings`` which itself imports from ``aeat.domain.vat`` — a
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
        for rev_path in sorted(revisions_dir.glob("*.toml")):
            fingerprints.append(_toml_fingerprint(rev_path))
    return tuple(fingerprints)


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
    parameters: dict[str, LegalParameter] = {}
    modelos: list[ModeloDefinition] = []
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
    return tuple(modelos), RegistryCatalogues(legal=legal, sources=sources, parameters=parameters)


def _toml_fingerprint(path: Path) -> tuple[str, int, int]:
    resolved = path.resolve()
    stat = resolved.stat()
    return str(resolved), stat.st_size, stat.st_mtime_ns
