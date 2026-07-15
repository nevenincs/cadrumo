"""Read-only TOML loader for AEAT registry definitions.

Compiles TOML authoring fragments into strict runtime objects. Each
:class:`ModeloDefinition` is assembled from one TOML file or a directory
manifest; each :class:`ModeloRevision` is compiled from a single revision
file or a set of append fragments merged in deterministic order.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, cast, get_args, get_origin

from pydantic import BaseModel, ValidationError

from ....core import freeze_toml, read_toml
from . import _loader_locales
from ._errors import RegistryLoadError, RegistryValidationError
from ._loader_cache import (
    BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
    MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS,
    is_bundled_registry_root,
    registry_disk_cache_dir,
    registry_disk_cache_enabled,
    registry_disk_cache_max_entries,
)
from ._schema import (
    LegalParameter,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SourceReference,
)
from ._validate_revision_identity import revision_reference_identity_failures

_REVISION_EXPORT_LAYOUTS = "export_layouts"
_REVISION_CONSTRUCTS = "constructs"
_REVISION_COMPLETENESS_MANIFEST = "completeness_manifest"
_REVISION_SPECIAL_MERGE_FIELDS = frozenset({_REVISION_EXPORT_LAYOUTS, _REVISION_CONSTRUCTS})
_REVISION_APPEND_ARRAYS: frozenset[str] = frozenset(
    field_name
    for field_name, field in ModeloRevision.model_fields.items()
    if field.default == ()
    and get_origin(field.annotation) is tuple
    and field_name not in _REVISION_SPECIAL_MERGE_FIELDS
)


def _compute_revision_section_fields() -> frozenset[str]:
    """Return the ModeloRevision fields that are per-section fragment content.

    A "section" is an array-of-tables field (bindings, casillas, formulas, …) or
    the ``completeness_manifest`` singleton table — the content that lives in
    per-section fragment subdirectories. Scalar metadata (label, valid_from,
    period_selector, legal_refs, source_refs, orden_aplicabilidad, …) is NOT a
    section: it stays inline in the fragment directory's ``revision.toml``
    manifest. Derived from the schema so a new section field is section-classified
    automatically.
    """
    sections: set[str] = {_REVISION_COMPLETENESS_MANIFEST}
    for field_name, field in ModeloRevision.model_fields.items():
        if get_origin(field.annotation) is not tuple:
            continue
        args = get_args(field.annotation)
        element = args[0] if args else None
        if isinstance(element, type) and issubclass(element, BaseModel):
            sections.add(field_name)
    return frozenset(sections)


# Fields that MUST live in per-section fragment files, never inline in the
# fragment directory's revision.toml manifest (the fragmented-layout invariant).
_REVISION_SECTION_FIELDS: frozenset[str] = _compute_revision_section_fields()
_COMPLETENESS_MANIFEST_APPEND_ARRAYS: frozenset[str] = frozenset({"casillas"})
_CONSTRUCT_APPEND_ARRAYS: frozenset[str] = frozenset(
    {
        "casilla_ids",
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
    },
)
ModeloSourceLayout = Literal["single_file", "directory"]
ModeloRevisionSourceLayout = Literal["revision_file", "fragment_directory"]
_REGISTRY_TREE_CACHE_SCHEMA_VERSION = "legal-parameter-refs-v1"


_EMBEDDED_SCHEMA_CORE_MODULES = (
    # Cross-package core modules whose TYPES are EMBEDDED in the pickled compiled
    # (modelos, catalogues) objects. The registry-package hash below covers the
    # schema MODELS and the compiler/resolvers, but the compiled objects also
    # embed core primitives defined OUTSIDE the registry package -- a change to
    # one of these (a new BindingSourceKind member, a BindingAggregation field,
    # a SensitivityClass value, a Period/TaxDomain shape) alters the pickled
    # object semantics without touching any registry module, so it must be in
    # the key too. Extend this tuple when a new core type becomes embedded in
    # the compiled objects; `test_embedded_schema_core_modules_all_resolve`
    # guards it against drift to a non-existent module.
    "cadrumo.core.aggregation",  # BindingSourceKind / BindingAggregation / BindingTypedEnumKind
    "cadrumo.core.classification",  # SensitivityClass
    "cadrumo.core._period",  # Period
    "cadrumo.core._tax_domain",  # TaxDomain
)


def _compute_loader_code_fingerprint() -> str:
    """Return a content hash of the loader/compiler/schema source.

    The registry disk cache stores COMPILED ``(modelos, catalogues)`` objects.
    The tree fingerprint keys only the TOML inputs, so a change to the
    compilation logic (or to a core type embedded in the compiled objects) that
    produces DIFFERENT compiled objects from IDENTICAL TOML is invisible to the
    cache key -- a stale pickle from a prior session (the shared OS temp dir
    persists across sessions and code changes) would be served for the current
    loader. The hand-maintained :data:`_REGISTRY_TREE_CACHE_SCHEMA_VERSION` only
    guards against this when a developer remembers to bump it. Folding a content
    hash of the source into the cache key closes the gap automatically:

    * every registry-package module (excluding its tests) -- the schema models,
      the compiler, and the resolvers; and
    * the cross-package core modules whose types are embedded in the compiled
      objects (:data:`_EMBEDDED_SCHEMA_CORE_MODULES`).

    Any change to either surface yields a new key, so pre-change pickles can
    never be served. Best-effort per surface: an unreadable registry tree (e.g.
    a zip-imported install) falls back to the interpreter version + bytecode
    cache tag; an unresolvable core module folds in a stable marker so the key
    stays deterministic and distinct rather than crashing.
    """
    import hashlib
    import importlib
    import sys

    hasher = hashlib.sha256()
    try:
        package_dir = Path(__file__).resolve().parent
        source_files = sorted(
            path for path in package_dir.rglob("*.py") if "tests" not in path.relative_to(package_dir).parts
        )
        for path in source_files:
            hasher.update(path.relative_to(package_dir).as_posix().encode("utf-8"))
            hasher.update(path.read_bytes())
    except OSError:
        hasher.update(sys.version.encode("utf-8"))
        hasher.update((sys.implementation.cache_tag or "").encode("utf-8"))

    for module_name in _EMBEDDED_SCHEMA_CORE_MODULES:
        try:
            module = importlib.import_module(module_name)
            module_file = getattr(module, "__file__", None)
            if module_file is None:
                hasher.update(f"unresolved:{module_name}".encode())
                continue
            hasher.update(module_name.encode("utf-8"))
            hasher.update(Path(module_file).read_bytes())
        except (OSError, ImportError):
            hasher.update(f"unresolved:{module_name}".encode())
    return hasher.hexdigest()


_LOADER_CODE_FINGERPRINT = _compute_loader_code_fingerprint()


def _registry_disk_cache_key(
    root: str,
    fingerprints: tuple[tuple[str, int, int], ...],
    *,
    loader_code_fingerprint: str = _LOADER_CODE_FINGERPRINT,
) -> str:
    """Compute the registry disk-cache pickle key.

    The key binds the compiled snapshot to (1) the schema-version marker, (2) a
    content hash of the loader/compiler/schema source (so a code change that
    alters compiled semantics invalidates the pickle even without a manual
    version bump), (3) the registry root path, and (4) the per-TOML tree
    fingerprints (path, size, mtime_ns). ``loader_code_fingerprint`` is injected
    for test isolation; production always uses :data:`_LOADER_CODE_FINGERPRINT`.
    """
    import hashlib

    hasher = hashlib.sha256()
    hasher.update(_REGISTRY_TREE_CACHE_SCHEMA_VERSION.encode("utf-8"))
    hasher.update(loader_code_fingerprint.encode("utf-8"))
    hasher.update(root.encode("utf-8"))
    for item in fingerprints:
        hasher.update(item[0].encode("utf-8"))
        hasher.update(str(item[1]).encode("utf-8"))
        hasher.update(str(item[2]).encode("utf-8"))
    return hasher.hexdigest()


_DISK_CACHE_READ_ATTEMPTS = 3
"""Total read attempts against the shared disk-cache pickle before falling back.

Closes a narrow, real Windows race: ``os.replace`` is atomic at the
filesystem level (sub-millisecond), but a reader's ``open(..., "rb")`` can
transiently observe a sharing-violation ``OSError`` while a concurrent
writer's replace is in flight -- an xdist worker racing a sibling worker (or
an earlier invocation) that is mid-write to the SAME bundled-root pickle.
2 retries with a short backoff comfortably outlasts an atomic replace; the
broad ``except`` after the final attempt still falls through to a safe
recompute for a genuinely corrupt or foreign file, unchanged from before.
"""
_DISK_CACHE_READ_RETRY_BASE_DELAY_SECONDS = 0.01
type _RegistryPathFingerprint = tuple[str, int, int]
type _RegistryPathFingerprints = tuple[_RegistryPathFingerprint, ...]


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


def _as_toml_table(value: object) -> dict[str, object] | None:
    """Narrow a parsed TOML value to a string-keyed table, or ``None``.

    ``tomllib`` and :func:`freeze_toml` always emit ``str`` keys, so a
    parsed-TOML ``dict`` is genuinely ``dict[str, object]``. The runtime
    ``isinstance`` check loses the key type because TOML payloads flow
    through ``object``; the annotation below re-attaches the known ``str``
    key type at this single TOML deserialization boundary.
    """
    if isinstance(value, dict):
        # CAST-RATIONALE-TOML-STR-KEY-ERASURE: tomllib/freeze_toml always
        # produces str-keyed dicts; isinstance loses the key type annotation.
        return cast("dict[str, object]", value)
    return None


def _toml_table_id(value: object) -> str | None:
    """Return the string ``id`` of a TOML table value, or ``None``."""
    table = _as_toml_table(value)
    if table is None:
        return None
    table_id = table.get("id")
    return table_id if isinstance(table_id, str) else None


def _reject_local_catalogues(path: Path, data: Mapping[str, object]) -> None:
    forbidden = {"source", "sources", "legal", "legal_refs_catalogue"}
    present = sorted(forbidden.intersection(data))
    if present:
        raise RegistryLoadError(f"{path}: modelo files must not define local legal/source catalogues: {present!r}")


def load_modelo_file(path: Path) -> ModeloDefinition:
    """Load one modelo TOML file into strict schema objects.

    Returns:
        The compiled :class:`ModeloDefinition` from the TOML file.
    """
    resolved = path.resolve()
    fingerprint = _toml_fingerprint(resolved)
    try:
        return _load_modelo_file_cached(str(resolved), fingerprint[1], fingerprint[2])
    except RegistryLoadError as exc:
        refreshed = _refresh_toml_fingerprint_after_load_error(resolved, exc)
        if refreshed == fingerprint:
            raise
        return _load_modelo_file_cached(str(resolved), refreshed[1], refreshed[2])


@lru_cache(maxsize=256)
def _load_modelo_file_cached(path: str, byte_count: int, modified_ns: int) -> ModeloDefinition:
    del byte_count, modified_ns
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    return _build_modelo_definition_from_data(source_path, data)


def _build_modelo_definition_from_data(source_path: Path, data: Mapping[str, object]) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""
    _reject_local_catalogues(source_path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    modelo_table = data["modelo"]
    if not isinstance(modelo_table, dict):
        raise RegistryLoadError(f"{source_path}: [modelo] must be a table")
    modelo_id = modelo_table.get("id")
    modelo_id_for_context = modelo_id if isinstance(modelo_id, str) else source_path.as_posix()
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
            revision = ModeloRevision.model_validate(payload)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision_id!r}: {exc}") from exc
        _raise_on_ambiguous_revision_identity(
            source_path,
            modelo_id=modelo_id_for_context,
            revision_id=revision_id,
            revision=revision,
        )
        revisions[revision_id] = revision
    try:
        return ModeloDefinition.model_validate({**modelo_table, "revisions": revisions})
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


def _raise_on_ambiguous_revision_identity(
    source_path: Path,
    *,
    modelo_id: str,
    revision_id: str,
    revision: ModeloRevision,
) -> None:
    prefix = f"{source_path}: modelo {modelo_id} revision {revision_id}"
    failures = revision_reference_identity_failures(prefix, revision)
    if failures:
        raise RegistryValidationError(
            "registry revision identity is ambiguous:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def load_modelo_directory(directory: Path) -> ModeloDefinition:
    """Load a :class:`ModeloDefinition` from a directory layout.

    The directory must contain ``manifest.toml`` carrying the ``[modelo]``
    metadata table. Per-revision data lives in ``revisions/{id}.toml``
    files, or in ``revisions/{id}/`` fragment directories. Revision
    files declare one or more revisions via top-level
    ``[revisions."<id>"]`` (and ``[[revisions."<id>".X]]`` array tables).
    Fragment directories declare exactly the directory revision id
    across one or more TOML files using the same table shape. All
    revision sources are merged into the single in-memory
    :class:`ModeloDefinition` that single-file mode produces.

    Public API stays identical to ``load_modelo_file``: callers receive
    the same :class:`ModeloDefinition` regardless of on-disk layout.
    """
    resolved = directory.resolve()
    if not resolved.is_dir():
        raise RegistryLoadError(f"{resolved}: modelo directory does not exist")
    manifest_path = resolved / "manifest.toml"
    if not manifest_path.is_file():
        raise RegistryLoadError(f"{resolved}: missing manifest.toml")

    fingerprints = _collect_modelo_directory_fingerprints(resolved)
    try:
        return _load_modelo_directory_cached(str(resolved), fingerprints)
    except RegistryLoadError as exc:
        refreshed = _refresh_modelo_directory_fingerprints_after_load_error(resolved, exc)
        if refreshed == fingerprints:
            raise
        return _load_modelo_directory_cached(str(resolved), refreshed)


def load_modelo_path(path: Path) -> ModeloDefinition:
    """Load a :class:`ModeloDefinition` from either supported on-disk layout."""
    resolved = path.resolve()
    if resolved.is_file():
        return load_modelo_file(resolved)
    if resolved.is_dir():
        return load_modelo_directory(resolved)
    raise RegistryLoadError(f"{resolved}: modelo source does not exist")


def load_modelo_source(source: ModeloSource) -> ModeloDefinition:
    """Load a modelo from a discovered source descriptor.

    Returns:
        The compiled :class:`ModeloDefinition` from the source.
    """
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
    _loader_locales.apply_locales(resolved, merged_revisions)
    merged: dict[str, object] = {**manifest_data, "revisions": merged_revisions}
    return _build_modelo_definition_from_data(resolved, merged)


def load_modelo_directory_without_locales(resolved: Path) -> ModeloDefinition:
    """Load a directory-mode :class:`ModeloDefinition` without applying locale TOML.

    Composes the same manifest/revisions/build steps as
    :func:`load_modelo_directory` but skips
    :func:`~cadrumo.domain.calculations.registry._loader_locales.apply_locales`,
    for callers (the schema-local locale-authoring CLI) that must read the
    raw Spanish schema before any translation overlay is injected.

    Raises:
        RegistryLoadError: If the manifest is missing, malformed, or no
            revisions are found under ``resolved/revisions``.
    """
    manifest_data = _load_modelo_manifest(resolved)
    merged_revisions = _load_modelo_revisions(resolved)
    if not merged_revisions:
        raise RegistryLoadError(f"{resolved}: no revisions found in revisions/")
    merged: dict[str, object] = {**manifest_data, "revisions": merged_revisions}
    return _build_modelo_definition_from_data(resolved, merged)


def _load_modelo_manifest(resolved: Path) -> dict[str, object]:
    """Load the directory-mode manifest.toml and reject inlined [revisions]."""
    manifest_path = resolved / "manifest.toml"
    manifest_data = freeze_toml(read_toml(manifest_path, error_factory=RegistryLoadError))
    if "revisions" in manifest_data:
        raise RegistryLoadError(
            f"{manifest_path}: directory-mode manifest must not declare [revisions]; "
            f"revision data lives in revisions/<id>.toml",
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
    rev_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
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
                f"{path}: revision {revision_id!r} already declared in another revisions/*.toml file",
            )
        merged_revisions[revision_id] = raw_revision


def _merge_revision_directory(path: Path, merged_revisions: dict[str, object]) -> None:
    """Merge a ``revisions/{id}/`` fragment tree into ``merged_revisions``."""
    revision_id = path.name
    if revision_id in merged_revisions:
        raise RegistryLoadError(f"{path}: revision {revision_id!r} already declared in another revisions/*.toml file")
    revision_manifest = path / "revision.toml"
    if not revision_manifest.is_file():
        raise RegistryLoadError(f"{path}: revision fragment directory must contain revision.toml")
    section_fragment_paths = sorted(
        p for p in path.rglob("*.toml") if p != revision_manifest and not any(part == "locales" for part in p.parts)
    )
    merged_revision: dict[str, object] = {}
    _merge_revision_manifest(revision_manifest, revision_id, merged_revision)
    for fragment_path in section_fragment_paths:
        _merge_revision_fragment(fragment_path, revision_id, merged_revision)
    merged_revisions[revision_id] = merged_revision


def _read_single_revision_table(path: Path, expected_revision_id: str) -> dict[str, object]:
    """Parse one revision TOML and return its ``[revisions."<id>"]`` table.

    Enforces the shared preconditions for both the fragment-directory
    ``revision.toml`` manifest and its per-section fragment files: no ``[modelo]``
    table, no local catalogues, exactly one revision, and the declared id must
    match the owning fragment directory.
    """
    fragment_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
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
            f"{path}: revision fragment declares {revision_id!r}, expected {expected_revision_id!r}",
        )
    raw_revision_table = _as_toml_table(raw_revision)
    if raw_revision_table is None:
        raise RegistryLoadError(f"{path}: revision {revision_id!r} must be a table")
    return raw_revision_table


def _merge_revision_manifest(path: Path, expected_revision_id: str, merged_revision: dict[str, object]) -> None:
    """Merge the fragment directory's ``revision.toml`` scalar-metadata manifest.

    In the fragmented layout the ``revision.toml`` manifest carries ONLY scalar
    revision metadata (label, valid_from/valid_to, period_selector, legal_refs,
    source_refs, orden_aplicabilidad, continuidad_validation). Every per-section
    array-of-tables (bindings, casillas, formulas, verification_expectations, …)
    and the completeness_manifest live in per-section fragment subdirectories;
    an inline section table in ``revision.toml`` is a loud load error naming the
    fragmented layout.
    """
    raw_revision_table = _read_single_revision_table(path, expected_revision_id)
    for key, value in raw_revision_table.items():
        if key in _REVISION_SECTION_FIELDS:
            raise RegistryLoadError(
                f"{path}: revision.toml must declare only scalar revision metadata; the {key!r} section "
                f"must live in a '{key}/' fragment subdirectory (fragmented layout), not inline in revision.toml",
            )
        if key in merged_revision:
            raise RegistryLoadError(f"{path}: revision manifest redeclares field {key!r}")
        merged_revision[key] = value


def _merge_revision_fragment(path: Path, expected_revision_id: str, merged_revision: dict[str, object]) -> None:
    """Merge one per-section fragment TOML into a single raw revision payload."""
    raw_revision_table = _read_single_revision_table(path, expected_revision_id)
    for key, value in raw_revision_table.items():
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
                f"{path}: revision fragment field 'export_layouts' conflicts with a non-array field",
            )
        merged_revision[key] = _merge_export_layout_fragments(path, existing, value)
        return
    if key == _REVISION_COMPLETENESS_MANIFEST:
        existing = merged_revision.get(key)
        merged_revision[key] = _merge_singleton_table_fragment(
            path,
            key,
            existing,
            value,
            append_array_fields=_COMPLETENESS_MANIFEST_APPEND_ARRAYS,
        )
        return
    if key in merged_revision:
        raise RegistryLoadError(f"{path}: revision fragment redeclares scalar field {key!r}")
    merged_revision[key] = value


def _merge_singleton_table_fragment(
    path: Path,
    field_name: str,
    existing: object | None,
    incoming: object,
    *,
    append_array_fields: frozenset[str],
) -> dict[str, object]:
    """Merge a singleton nested TOML table whose selected arrays are appendable."""
    incoming_table = _as_toml_table(incoming)
    if incoming_table is None:
        raise RegistryLoadError(f"{path}: revision fragment field {field_name!r} must be a table")
    if existing is None:
        existing_table: dict[str, object] | None = {}
    else:
        existing_table = _as_toml_table(existing)
        if existing_table is None:
            raise RegistryLoadError(f"{path}: revision fragment field {field_name!r} conflicts with a non-table field")

    merged = dict(existing_table)
    for key, value in incoming_table.items():
        if key in append_array_fields:
            if not isinstance(value, tuple):
                raise RegistryLoadError(f"{path}: revision fragment field {field_name!r}.{key!r} must be an array")
            existing_values = merged.get(key, ())
            if not isinstance(existing_values, tuple):
                raise RegistryLoadError(
                    f"{path}: revision fragment field {field_name!r}.{key!r} conflicts with a non-array field",
                )
            merged[key] = (*existing_values, *value)
            continue
        if key in merged and merged[key] != value:
            raise RegistryLoadError(
                f"{path}: revision fragment field {field_name!r}.{key!r} conflicts with another fragment",
            )
        merged[key] = value
    return merged


def _merge_export_layout_fragments(
    path: Path,
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
) -> tuple[object, ...]:
    """Merge export-layout fragments by layout id, appending record arrays."""
    layouts: list[object] = list(existing)
    index_by_id: dict[str, int] = {}
    for index, layout in enumerate(layouts):
        layout_id = _toml_table_id(layout)
        if layout_id is not None:
            index_by_id[layout_id] = index
    for layout in incoming:
        incoming_table = _as_toml_table(layout)
        layout_id = None if incoming_table is None else _toml_table_id(incoming_table)
        if incoming_table is None or layout_id is None:
            layouts.append(layout)
            continue
        existing_index = index_by_id.get(layout_id)
        if existing_index is None:
            index_by_id[layout_id] = len(layouts)
            layouts.append(layout)
            continue
        existing_layout = _as_toml_table(layouts[existing_index])
        if existing_layout is None:
            raise RegistryLoadError(f"{path}: export layout {layout_id!r} conflicts with a non-table layout")
        layouts[existing_index] = _merge_export_layout_by_id(path, layout_id, existing_layout, incoming_table)
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
                f"{path}: export layout {layout_id!r} field {key!r} conflicts with another fragment",
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
        item_id = _toml_table_id(item)
        if item_id is not None:
            index_by_id[item_id] = index
    for item in incoming:
        incoming_table = _as_toml_table(item)
        item_id = None if incoming_table is None else _toml_table_id(incoming_table)
        if incoming_table is None or item_id is None:
            items.append(item)
            continue
        existing_index = index_by_id.get(item_id)
        if existing_index is None:
            index_by_id[item_id] = len(items)
            items.append(item)
            continue
        existing_item = _as_toml_table(items[existing_index])
        if existing_item is None:
            raise RegistryLoadError(f"{path}: {item_label} {item_id!r} conflicts with a non-table fragment")
        items[existing_index] = _merge_table_fragment_by_id(
            path,
            existing_item,
            incoming_table,
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
                    f"{path}: {item_label} {item_id!r} field {key!r} conflicts with a non-array fragment",
                )
            _reject_duplicate_appended_table_ids(path, existing_values, value, item_label, item_id, key)
            merged[key] = (*existing_values, *value)
            continue
        if key in merged and merged[key] != value:
            raise RegistryLoadError(f"{path}: {item_label} {item_id!r} field {key!r} conflicts with another fragment")
        merged[key] = value
    return merged


def _reject_duplicate_appended_table_ids(
    path: Path,
    existing: tuple[object, ...],
    incoming: tuple[object, ...],
    item_label: str,
    item_id: str,
    field: str,
) -> None:
    existing_ids = {iid for item in existing if (iid := _toml_table_id(item)) is not None}
    incoming_ids = {iid for item in incoming if (iid := _toml_table_id(item)) is not None}
    duplicate_ids = sorted(existing_ids.intersection(incoming_ids))
    if duplicate_ids:
        raise RegistryLoadError(
            f"{path}: {item_label} {item_id!r} field {field!r} appends duplicate ids {duplicate_ids!r}",
        )


def load_catalogue_file(path: Path) -> RegistryCatalogues:
    """Load one shared legal/source catalogue TOML file.

    Returns:
        The compiled :class:`RegistryCatalogues` from the TOML file.
    """
    resolved = path.resolve()
    fingerprint = _toml_fingerprint(resolved)
    try:
        return _load_catalogue_file_cached(str(resolved), fingerprint[1], fingerprint[2])
    except RegistryLoadError as exc:
        refreshed = _refresh_toml_fingerprint_after_load_error(resolved, exc)
        if refreshed == fingerprint:
            raise
        return _load_catalogue_file_cached(str(resolved), refreshed[1], refreshed[2])


@lru_cache(maxsize=128)
def _load_catalogue_file_cached(path: str, byte_count: int, modified_ns: int) -> RegistryCatalogues:
    del byte_count, modified_ns
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
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


def _validate_legal_parameter_refs(
    scope: Path,
    *,
    parameters: Mapping[str, LegalParameter],
    legal: Mapping[str, LegalReference],
) -> None:
    failures = [
        f"legal parameter {parameter_id!r} references unknown legal id {legal_ref!r}"
        for parameter_id, parameter in sorted(parameters.items())
        for legal_ref in parameter.legal_refs
        if legal_ref not in legal
    ]
    if failures:
        raise RegistryLoadError(
            f"{scope}: unresolved legal parameter references:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def load_legal_parameters_only(root: Path) -> Mapping[str, LegalParameter]:
    """Load only the legal-parameter catalogue from ``root/legal/*.toml``.

    Lightweight cycle-safe entry point. Consumers in ``cadrumo.domain.iva``
    and ``cadrumo.domain.rental`` need parameter values at module-import
    time, but the full :func:`load_registry_tree` path pulls in
    ``_bindings`` which itself imports from ``cadrumo.domain.iva`` — a
    circular import.

    This function reuses :func:`load_catalogue_file` (already
    Pydantic-validated and ``lru_cache``-deduplicated) and walks only
    ``root/legal/*.toml``. Modelo parsing and binding validation do not
    run; the legal refs carried by returned parameters are still resolved
    against the legal catalogue.

    Args:
        root: Repository ``registry/aeat`` directory.

    Returns:
        Frozen mapping of parameter-id → :class:`LegalParameter`.

    Raises:
        RegistryLoadError: When duplicate parameter ids are found across
            multiple TOML files in ``root/legal/``.
    """
    resolved = root.resolve()
    legal_dir = resolved / "legal"
    legal: dict[str, LegalReference] = {}
    parameters: dict[str, LegalParameter] = {}
    for path in sorted(legal_dir.glob("*.toml")):
        catalogue = load_catalogue_file(path)
        overlap = set(parameters).intersection(catalogue.parameters)
        if overlap:
            raise RegistryLoadError(f"{path}: duplicate parameter ids {sorted(overlap)!r}")
        legal.update(catalogue.legal)
        parameters.update(catalogue.parameters)
    _validate_legal_parameter_refs(legal_dir, parameters=parameters, legal=legal)
    return parameters


def load_registry_tree(root: Path) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load all registry files from ``root``.

    Discovers modelos in two layouts:
      * single-file: ``modelos/<id>.toml``
      * directory:   ``modelos/<id>/manifest.toml`` + ``modelos/<id>/revisions/*.toml``

    A single modelo cannot exist in both layouts simultaneously; the
    loader raises ``RegistryLoadError`` if both forms are present.

    Returns:
        A tuple of all :class:`ModeloDefinition` objects and the merged :class:`RegistryCatalogues`.
    """
    resolved = root.resolve()
    fingerprints = _collect_registry_tree_fingerprints(resolved)
    try:
        return _load_registry_tree_cached(str(resolved), fingerprints)
    except RegistryLoadError as exc:
        refreshed = _refresh_registry_tree_fingerprints_after_load_error(resolved, exc)
        if refreshed == fingerprints:
            raise
        return _load_registry_tree_cached(str(resolved), refreshed)


def discover_modelo_sources(modelos_dir: Path) -> tuple[ModeloSource, ...]:
    """Discover :class:`ModeloSource` layouts under a ``modelos/`` directory.

    This is the generic source-layout contract for the registry: callers
    can reason about single-file modelos, directory-mode modelos,
    per-revision files, and fragmented revision directories without
    special-casing a modelo id.
    """
    resolved = modelos_dir.resolve()
    sources: list[ModeloSource] = []
    seen_modelo_ids: dict[str, ModeloSource] = {}
    for path in sorted(resolved.glob("*.toml")):
        try:
            raw_data = read_toml(path, error_factory=RegistryLoadError)
            modelo_table = _as_toml_table(raw_data.get("modelo"))
            if modelo_table is None or "id" not in modelo_table:
                raise RegistryLoadError(f"{path}: missing [modelo].id")
            modelo_id = str(modelo_table["id"])
        except Exception as exc:
            raise RegistryLoadError(f"{path}: invalid modelo file: {exc}") from exc
        source = ModeloSource(
            modelo_id=modelo_id,
            layout="single_file",
            path=path.resolve(),
            manifest_path=path.resolve(),
        )
        _append_modelo_source(source, sources, seen_modelo_ids)
    if resolved.is_dir():
        for entry in sorted(resolved.iterdir()):
            if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
                continue
            manifest_path = entry / "manifest.toml"
            try:
                manifest_data = read_toml(manifest_path, error_factory=RegistryLoadError)
                modelo_table = _as_toml_table(manifest_data.get("modelo"))
                if modelo_table is None or "id" not in modelo_table:
                    raise RegistryLoadError(f"{manifest_path}: missing [modelo].id")
                modelo_id = str(modelo_table["id"])
            except Exception as exc:
                raise RegistryLoadError(f"{manifest_path}: invalid manifest: {exc}") from exc
            source = ModeloSource(
                modelo_id=modelo_id,
                layout="directory",
                path=entry.resolve(),
                manifest_path=manifest_path.resolve(),
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
            "remove one of the two layouts",
        )
    seen_modelo_ids[source.modelo_id] = source
    sources.append(source)


def _discover_revision_sources(revisions_dir: Path) -> tuple[ModeloRevisionSource, ...]:
    if not revisions_dir.is_dir():
        return ()
    sources: list[ModeloRevisionSource] = []
    for path in sorted(revisions_dir.glob("*.toml")):
        rev_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
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
                    path=path,
                    fragment_paths=(path,),
                ),
            )
    for path in sorted(revisions_dir.iterdir()):
        if not path.is_dir():
            continue
        revision_manifest = path / "revision.toml"
        fragment_paths = (revision_manifest,) if revision_manifest.is_file() else ()
        fragment_paths = (
            *fragment_paths,
            *tuple(
                p
                for p in sorted(path.rglob("*.toml"))
                if p != revision_manifest and not any(part == "locales" for part in p.parts)
            ),
        )
        sources.append(
            ModeloRevisionSource(
                revision_id=path.name,
                layout="fragment_directory",
                path=path,
                fragment_paths=fragment_paths,
            ),
        )
    return tuple(sources)


_registry_fingerprint_cache: dict[Path, tuple[float, _RegistryPathFingerprints, _RegistryPathFingerprints]] = {}


def clear_fingerprint_cache() -> None:
    """Clear the TTL-backed registry-tree fingerprint cache."""
    _registry_fingerprint_cache.clear()


def _collect_registry_tree_fingerprints(resolved: Path) -> _RegistryPathFingerprints:
    return _collect_registry_tree_fingerprints_for_cache(resolved, use_cache=True)


def _collect_registry_tree_fingerprints_uncached(resolved: Path) -> _RegistryPathFingerprints:
    return _collect_registry_tree_fingerprints_for_cache(resolved, use_cache=False)


def _collect_registry_tree_fingerprints_for_cache(
    resolved: Path,
    *,
    use_cache: bool,
) -> _RegistryPathFingerprints:
    """Walk ``resolved`` and return ``(path, size, mtime)`` fingerprints for the lru_cache key.

    Covers every catalogue source the loader will subsequently
    re-open: ``legal/*.toml``, single-file ``modelos/*.toml``, and
    directory-mode ``modelos/<id>/manifest.toml`` plus its
    ``revisions/*.toml`` siblings. It also includes directory mtimes
    under the registry root so add/remove/rename layout changes invalidate
    the fingerprint cache before a stale file list can be reused. It also
    covers every multi-year-renta ``authorization.d/<modelo>.toml``
    fragment, which the authority reads at the same registry root: per
    ``aeat-registry-authority-flow`` the authorization surface must
    invalidate the registry cache when it changes, so adding, editing, or
    removing an enrollment fragment reliably re-derives every per-modelo
    capability rather than serving a stale authorization. Fresh
    fingerprints key on every TOML file; the TTL cache also rechecks
    directory fingerprints so structural edits do not reuse a stale file
    list.

    The TTL window is longer for the package-bundled registry tree
    (:data:`BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS`) than for a mutable
    authoring tree (:data:`MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS`), and a
    bundled-tree cache hit skips the directory-mtime walk entirely rather
    than recomputing it only to compare it against the cached copy: within
    that window the walk is redundant work repeated on every calculate,
    snapshot, and revision lookup in quick succession. See
    :mod:`._loader_cache` for the TTL values and the bundled-root predicate.
    """
    import time

    now = time.time()
    bundled = use_cache and is_bundled_registry_root(resolved)
    ttl = BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS if bundled else MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS

    if bundled and resolved in _registry_fingerprint_cache:
        cached_time, _cached_directories, cached_val = _registry_fingerprint_cache[resolved]
        if now - cached_time < ttl:
            return cached_val

    directory_fingerprints = _collect_registry_directory_fingerprints(resolved)
    if use_cache and resolved in _registry_fingerprint_cache:
        cached_time, cached_directories, cached_val = _registry_fingerprint_cache[resolved]
        if now - cached_time < ttl:
            if cached_directories == directory_fingerprints:
                return cached_val
            _registry_fingerprint_cache.pop(resolved, None)

    legal_dir = resolved / "legal"
    modelos_dir = resolved / "modelos"
    fingerprints: list[_RegistryPathFingerprint] = list(directory_fingerprints)
    authorization_dir = resolved / "authorization.d"
    if authorization_dir.is_dir():
        for fragment in sorted(authorization_dir.glob("*.toml")):
            fingerprints.append(_toml_fingerprint(fragment))
    for path in sorted(legal_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    for path in sorted(modelos_dir.glob("*.toml")):
        fingerprints.append(_toml_fingerprint(path))
    if modelos_dir.is_dir():
        for entry in sorted(modelos_dir.iterdir()):
            fingerprints.extend(_modelo_directory_fingerprints(entry))
    schema_path = resolved / "user_profile" / "schema.toml"
    if schema_path.is_file():
        fingerprints.append(_toml_fingerprint(schema_path))

    refreshed_directory_fingerprints = _collect_registry_directory_fingerprints(resolved)
    if refreshed_directory_fingerprints != directory_fingerprints:
        _registry_fingerprint_cache.pop(resolved, None)
        raise RegistryLoadError(
            f"{resolved}: registry directory changed during cache fingerprinting; "
            "retry after concurrent registry writes settle",
        )
    res = tuple(fingerprints)
    _registry_fingerprint_cache[resolved] = (now, refreshed_directory_fingerprints, res)
    return res


def _collect_registry_directory_fingerprints(resolved: Path) -> _RegistryPathFingerprints:
    if not resolved.is_dir():
        return ()

    def _raise_walk_error(exc: OSError) -> None:
        raise RegistryLoadError(
            f"{resolved}: registry directory could not be walked during cache fingerprinting; "
            f"retry after concurrent registry writes settle: {exc}",
        ) from exc

    fingerprints: list[_RegistryPathFingerprint] = []
    for dirpath, dirnames, _filenames in os.walk(resolved, onerror=_raise_walk_error):
        dirnames.sort()
        fingerprints.append(_directory_fingerprint(Path(dirpath)))
    return tuple(fingerprints)


def _collect_modelo_directory_fingerprints(resolved: Path) -> _RegistryPathFingerprints:
    manifest_path = resolved / "manifest.toml"
    fingerprints: list[_RegistryPathFingerprint] = list(_collect_registry_directory_fingerprints(resolved))
    fingerprints.append(_toml_fingerprint(manifest_path))
    locales_dir = resolved / "locales"
    if locales_dir.is_dir():
        for path in sorted(locales_dir.glob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    revisions_dir = resolved / "revisions"
    if revisions_dir.is_dir():
        for path in sorted(revisions_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    return tuple(fingerprints)


def _modelo_directory_fingerprints(entry: Path) -> _RegistryPathFingerprints:
    """Return fingerprints for one directory-mode modelo entry, or ``()`` if not in that layout."""
    if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
        return ()
    fingerprints: list[_RegistryPathFingerprint] = [_toml_fingerprint(entry / "manifest.toml")]
    locales_dir = entry / "locales"
    if locales_dir.is_dir():
        for path in sorted(locales_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(path))
    revisions_dir = entry / "revisions"
    if revisions_dir.is_dir():
        for rev_path in sorted(revisions_dir.rglob("*.toml")):
            fingerprints.append(_toml_fingerprint(rev_path))
    return tuple(fingerprints)


def _read_registry_disk_cache_pickle(
    cache_path: Path,
    *,
    logger: logging.Logger,
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues] | None:
    """Read the shared registry disk-cache pickle, retrying past a transient replace race.

    Returns the unpickled payload, or ``None`` if every attempt failed (the
    caller falls through to a safe recompute). See
    :data:`_DISK_CACHE_READ_ATTEMPTS` for why the retry exists: a concurrent
    writer's ``os.replace`` is atomic but can transiently make ``open()``
    raise on some platforms while the replace is in flight.
    """
    import pickle
    import time

    for attempt in range(_DISK_CACHE_READ_ATTEMPTS):
        try:
            with open(cache_path, "rb") as f:
                # Internal same-user performance cache of first-party registry data only.
                # The payload is produced exclusively by the dump in the caller and keyed
                # by a sha256 of the registry tree fingerprints; no untrusted input is ever
                # deserialized here. A corrupt/foreign file is swallowed and recomputed.
                return pickle.load(f)  # noqa: S301  # nosemgrep: python.lang.security.deserialization.pickle.avoid-pickle
        except Exception:
            final_attempt = attempt == _DISK_CACHE_READ_ATTEMPTS - 1
            logger.debug(
                "Registry disk-cache read attempt %d/%d failed at %s%s",
                attempt + 1,
                _DISK_CACHE_READ_ATTEMPTS,
                cache_path,
                " -- giving up, will recompute" if final_attempt else " -- retrying",
                exc_info=True,
            )
            if not final_attempt:
                time.sleep(_DISK_CACHE_READ_RETRY_BASE_DELAY_SECONDS * (2**attempt))
    return None


def _evict_stale_registry_pickles(cache_dir: Path, *, logger: logging.Logger) -> None:
    """Keep only the newest ``registry_disk_cache_max_entries`` pickles, prune the rest.

    One pickle accumulates per registry-tree fingerprint, so a long-lived cache
    directory (an editable checkout re-compiling after successive registry
    edits, or a shared bundled-root temp directory) would otherwise grow without
    bound. Called after a successful write; entirely best-effort -- a prune
    failure (a permission error, a concurrent writer's unlink, a file that
    vanished mid-scan) is logged and swallowed. Eviction must never crash a
    registry load; the worst case is a few extra stale pickles on disk.
    """
    keep = registry_disk_cache_max_entries()
    try:
        entries: list[tuple[int, Path]] = []
        for pickle_path in cache_dir.glob("cadrumo_registry_*.pkl"):
            try:
                entries.append((pickle_path.stat().st_mtime_ns, pickle_path))
            except OSError:
                continue
    except OSError:
        logger.debug("Could not enumerate registry disk-cache pickles in %s", cache_dir, exc_info=True)
        return
    entries.sort(reverse=True)
    for _mtime_ns, stale in entries[keep:]:
        try:
            stale.unlink()
        except OSError:
            logger.debug("Could not evict stale registry disk-cache pickle %s", stale, exc_info=True)


@lru_cache(maxsize=32)
def _load_registry_tree_cached(
    root: str,
    fingerprints: tuple[tuple[str, int, int], ...],
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    import logging
    import os
    import pickle
    import tempfile

    logger = logging.getLogger(__name__)
    resolved = Path(root)
    cache_path: Path | None = None
    if registry_disk_cache_enabled(is_bundled=is_bundled_registry_root(resolved)):
        key_hash = _registry_disk_cache_key(root, fingerprints)

        cache_path = registry_disk_cache_dir() / f"cadrumo_registry_{key_hash}.pkl"
        if cache_path.is_file():
            cached = _read_registry_disk_cache_pickle(cache_path, logger=logger)
            if cached is not None:
                return cached

    catalogues = _load_shared_catalogue_files(resolved / "legal")
    modelos = _load_all_modelo_definitions(resolved / "modelos")
    result = (modelos, catalogues)

    if cache_path is not None:
        temp_name = None
        try:
            # The production cache dir (<storage-root>/cache/registry) may not
            # exist yet on a cold first run; the pytest/host-shared temp dir
            # always does. Create it best-effort so the sibling write below has
            # a parent; any failure falls through to the recompute-and-skip
            # branch rather than crashing the load.
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("wb", dir=cache_path.parent, delete=False) as tf:
                # Serialises first-party registry objects to the same-user temp cache read
                # back above; the data never crosses a trust boundary. See the load note.
                pickle.dump(result, tf, protocol=pickle.HIGHEST_PROTOCOL)  # nosemgrep
                temp_name = tf.name
            os.replace(temp_name, cache_path)
            _evict_stale_registry_pickles(cache_path.parent, logger=logger)
        except Exception:
            logger.debug("Could not write registry disk cache at %s", cache_path, exc_info=True)
            if temp_name is not None:
                try:
                    os.unlink(temp_name)
                except Exception:
                    logger.debug("Could not remove temporary registry disk cache file %s", temp_name, exc_info=True)
    return result


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
                f"sources={sorted(overlap_sources)!r} parameters={sorted(overlap_parameters)!r}",
            )
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
        parameters.update(catalogue.parameters)
    _validate_legal_parameter_refs(legal_dir, parameters=parameters, legal=legal)
    return RegistryCatalogues(legal=legal, sources=sources, parameters=parameters)


def _load_all_modelo_definitions(modelos_dir: Path) -> tuple[ModeloDefinition, ...]:
    """Load every modelo (single-file + directory-mode) and reject layout collisions.

    A modelo id present both as ``modelos/<id>.toml`` and as
    ``modelos/<id>/manifest.toml`` is a configuration mistake — the
    loader cannot tell which layout is authoritative, so it raises
    instead of silently picking one.
    """
    return tuple(load_modelo_source(source) for source in discover_modelo_sources(modelos_dir))


def _refresh_toml_fingerprint_after_load_error(
    path: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprint:
    try:
        return _toml_fingerprint(path)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{path}: registry TOML changed during load; retry after concurrent registry writes settle. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
        ) from refresh_error


def _refresh_modelo_directory_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return _collect_modelo_directory_fingerprints(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: modelo directory changed during load; retry after concurrent registry writes settle. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
        ) from refresh_error


def _refresh_registry_tree_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return _collect_registry_tree_fingerprints_uncached(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: registry tree changed during load; retry after concurrent registry writes settle. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
        ) from refresh_error


def _directory_fingerprint(path: Path) -> _RegistryPathFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry directory could not be fingerprinted; "
            f"retry after concurrent registry writes settle: {exc}",
        ) from exc
    return str(path), stat.st_size, stat.st_mtime_ns


def _toml_fingerprint(path: Path) -> _RegistryPathFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry TOML could not be fingerprinted; retry after concurrent registry writes settle: {exc}",
        ) from exc
    return str(path), stat.st_size, stat.st_mtime_ns
