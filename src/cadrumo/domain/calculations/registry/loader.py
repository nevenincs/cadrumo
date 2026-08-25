"""Read-only TOML loader for AEAT registry definitions.

Compiles TOML authoring fragments into strict runtime objects. Each
:class:`ModeloDefinition` is assembled from one TOML file or a directory
manifest; each :class:`ModeloRevision` is compiled from a single revision
file or a set of append fragments merged in deterministic order.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import cast, get_args, get_origin

from pydantic import BaseModel, ValidationError

from ....core import (
    OBJECT_TUPLE_ADAPTER,
    FilingProducerKey,
    compile_filing_projection_ref,
    freeze_toml,
    read_toml,
)
from ....core.directory_scan import (
    DirectoryEntryKind,
    scan_directory,
)
from ._compiled_cache import load_compiled_registry_cache, store_compiled_registry_cache
from .errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryLoadError,
    RegistryValidationError,
)
from .export_semantics import ExportComputedKey, ExportDraftAttribute
from .identity import RegistryIdentity, resolve_registry_identity, stamped_cache_key_tuples
from .ids import RevisionId
from .loader_cache import (
    BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
    MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS,
    ModeloSource,
    discover_modelo_sources,
    is_bundled_registry_root,
    registry_disk_cache_enabled,
    toml_file_fingerprint,
    validate_modelo_directory_source,
)
from .loader_cache import (
    ModeloRevisionSource as _ModeloRevisionSource,
)
from .loader_fingerprints import (
    _registry_fingerprint_cache,
    bind_tree_fingerprint_collectors,
)
from .loader_fingerprints import (
    clear_fingerprint_cache as _clear_fingerprint_cache,
)
from .loader_fingerprints import (
    collect_registry_tree_fingerprints_for_cache as _collect_fingerprints_for_cache,
)
from .loader_fingerprints import (
    refresh_toml_fingerprint_after_load_error as _refresh_toml_fingerprint_after_load_error,
)
from .modelo_localization import (
    enroll_revision_localization,
    modelo_locale_key,
)
from .schema import (
    REVISION_GOVERNANCE_FIELDS,
    REVISION_MANIFEST_ONLY_FIELDS,
    LegalParameter,
    LegalReference,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    SourceReference,
    SupportedFilingYearsCatalogue,
)
from ._toml_helpers import as_toml_table as _as_toml_table
from .validate_revision_identity import revision_reference_identity_failures

ModeloRevisionSource = _ModeloRevisionSource
clear_fingerprint_cache = _clear_fingerprint_cache

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
        "relations",
        "export_layouts",
        "extraction_profiles",
        "live_cross_references",
        "workbook_parity_refs",
        "verification_expectations",
        "application_links",
        "deadline_windows",
        "filing_schedules",
        "dependency_classifications",
    },
)
type _RegistryPathFingerprint = tuple[str, int, int, str]
"""``(path, size, mtime_ns, content_digest)``; the digest is empty for directories and bundled-tree files."""
type _RegistryPathFingerprints = tuple[_RegistryPathFingerprint, ...]


def _toml_table_id(value: object) -> str | None:
    """Return the string ``id`` of a TOML table value, or ``None``."""
    table = _as_toml_table(value)
    if table is None:
        return None
    table_id = table.get("id")
    return table_id if isinstance(table_id, str) else None


def _as_toml_array(value: object) -> tuple[object, ...] | None:
    """Narrow a frozen TOML array to object entries, or return ``None``."""
    if not isinstance(value, tuple):
        return None
    return OBJECT_TUPLE_ADAPTER.validate_python(value)


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
        return _load_modelo_file_cached(str(resolved), fingerprint[1], fingerprint[2], fingerprint[3])
    except RegistryLoadError as exc:
        refreshed = _refresh_toml_fingerprint_after_load_error(resolved, exc)
        if refreshed == fingerprint:
            raise
        return _load_modelo_file_cached(str(resolved), refreshed[1], refreshed[2], refreshed[3])


@lru_cache(maxsize=256)
def _load_modelo_file_cached(path: str, byte_count: int, modified_ns: int, content_digest: str) -> ModeloDefinition:
    del byte_count, modified_ns, content_digest
    source_path = Path(path)
    data = freeze_toml(read_toml(source_path, error_factory=RegistryLoadError))
    return _build_modelo_definition_from_data(source_path, data)


def _build_modelo_definition_from_data(source_path: Path, data: Mapping[str, object]) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""
    _reject_local_catalogues(source_path, data)
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    modelo_table = _as_toml_table(data["modelo"])
    if modelo_table is None:
        raise RegistryLoadError(f"{source_path}: [modelo] must be a table")
    modelo_id = modelo_table.get("id")
    modelo_id_for_context = modelo_id if isinstance(modelo_id, str) else source_path.as_posix()
    raw_revisions = _as_toml_table(data.get("revisions"))
    if not raw_revisions:
        raise RegistryLoadError(f"{source_path}: missing [revisions.<id>] tables")
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in raw_revisions.items():
        raw_revision_table = _as_toml_table(raw_revision)
        if raw_revision_table is None:
            raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
        payload = enroll_revision_localization(
            modelo_id=str(modelo_id_for_context),
            revision_id=revision_id,
            raw_revision=raw_revision_table,
        )
        payload = _compile_revision_projection_semantics(source_path, payload)
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
        return ModeloDefinition.model_validate(
            {
                **modelo_table,
                "title_localization_key": modelo_locale_key(str(modelo_id_for_context), "title"),
                "official_name_localization_key": modelo_locale_key(str(modelo_id_for_context), "official_name"),
                "revisions": revisions,
            }
        )
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc


def _raise_on_ambiguous_revision_identity(
    source_path: Path,
    *,
    modelo_id: str,
    revision_id: RevisionId,
    revision: ModeloRevision,
) -> None:
    prefix = f"{source_path}: modelo {modelo_id} revision {revision_id}"
    failures = revision_reference_identity_failures(prefix, revision)
    if failures:
        raise RegistryValidationError(
            "registry revision identity is ambiguous:\n" + "\n".join(f" - {failure}" for failure in failures),
        )


def _passthrough_toml_row(raw: object) -> dict[str, object]:
    """Carry a non-table TOML row through unchanged, so validation still sees it.

    Enrolment adds locale identities; it is not a validator. A row that is not a
    table gets no derived key -- there is no id to derive one from -- but it must
    still reach ``model_validate``, which is what turns a malformed fragment into
    an attributable error. Dropping it here would make it vanish silently
    instead.
    """
    # CAST-RATIONALE-TOML-ROW: raw TOML value, shape confirmed by the isinstance
    # guard in the same expression. One site rather than the three near-identical
    # copies this replaces, so the escape hatch is declared once.
    # nosemgrep: no-cast-in-domain-application
    return dict(cast(Mapping[str, object], raw)) if isinstance(raw, Mapping) else {"value": raw}


def _compile_export_semantic_field(source_path: Path, raw_field: object) -> dict[str, object]:
    """Construct closed export selector enums at the TOML compiler boundary.

    Strict registry models deliberately accept only enum members.  This is the
    one boundary where committed TOML's scalar token becomes that member; no
    model validator, renderer, or application call site may repeat it.
    """
    field = _as_toml_table(raw_field)
    if field is None:
        return _passthrough_toml_row(raw_field)
    if "header_key" in field:
        raise RegistryLoadError(
            f"{source_path}: legacy export field header_key is not accepted; use producer_key with a canonical "
            "FilingProducerKey identity",
        )
    payload = dict(field)
    for name, enum_type in (
        ("producer_key", FilingProducerKey),
        ("draft_attribute", ExportDraftAttribute),
        ("computed_key", ExportComputedKey),
    ):
        raw_value = payload.get(name)
        if raw_value is None or isinstance(raw_value, enum_type):
            continue
        if not isinstance(raw_value, str):
            raise RegistryLoadError(
                f"{source_path}: export field {name} must be a canonical string token, got "
                f"{type(raw_value).__name__!r}",
            )
        try:
            payload[name] = enum_type(raw_value)
        except ValueError as exc:
            raise RegistryLoadError(
                f"{source_path}: export field {name} {raw_value!r} is not a canonical {enum_type.__name__}",
            ) from exc
    raw_projection_ref = payload.get("projection_ref")
    if raw_projection_ref is not None:
        try:
            payload["projection_ref"] = compile_filing_projection_ref(raw_projection_ref)
        except (ValidationError, ValueError) as exc:
            raise RegistryLoadError(
                f"{source_path}: export field projection_ref is not a canonical FilingProjectionRef: {exc}",
            ) from exc
    return payload


def _compile_projection_endpoint_declaration(source_path: Path, raw_declaration: object) -> dict[str, object]:
    """Hydrate one revision-owned projection declaration at the TOML boundary."""
    declaration = _as_toml_table(raw_declaration)
    if declaration is None:
        return _passthrough_toml_row(raw_declaration)
    payload = dict(declaration)
    if "projection_ref" in payload:
        try:
            payload["projection_ref"] = compile_filing_projection_ref(payload["projection_ref"])
        except (ValidationError, ValueError) as exc:
            raise RegistryLoadError(f"{source_path}: {exc}") from exc
    return payload


def _compile_revision_projection_record(source_path: Path, raw_record: object) -> dict[str, object]:
    record = _as_toml_table(raw_record)
    if record is None:
        return _passthrough_toml_row(raw_record)
    compiled = dict(record)
    fields = _as_toml_array(record.get("fields"))
    if fields is not None:
        compiled["fields"] = tuple(_compile_export_semantic_field(source_path, raw_field) for raw_field in fields)
    return compiled


def _compile_revision_projection_layout(source_path: Path, raw_layout: object) -> dict[str, object]:
    layout = _as_toml_table(raw_layout)
    if layout is None:
        return _passthrough_toml_row(raw_layout)
    compiled = dict(layout)
    records = _as_toml_array(layout.get("records"))
    if records is not None:
        compiled["records"] = tuple(
            _compile_revision_projection_record(source_path, raw_record) for raw_record in records
        )
    return compiled


def _compile_revision_projection_semantics(source_path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Compile revision-owned typed tokens before schema construction."""
    compiled = dict(payload)
    declarations = _as_toml_array(payload.get("projection_endpoints"))
    if declarations is not None:
        compiled["projection_endpoints"] = tuple(
            _compile_projection_endpoint_declaration(source_path, raw_declaration) for raw_declaration in declarations
        )
    layouts = _as_toml_array(payload.get("export_layouts"))
    if layouts is not None:
        compiled["export_layouts"] = tuple(
            _compile_revision_projection_layout(source_path, raw_layout) for raw_layout in layouts
        )
    return compiled


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
    validate_modelo_directory_source(resolved)

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
    fingerprints: _RegistryPathFingerprints,
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
    for path in scan_directory(revisions_dir, pattern="*.toml"):
        _merge_revision_file(path, merged_revisions)
    for path in scan_directory(revisions_dir, select=DirectoryEntryKind.DIRECTORIES):
        _merge_revision_directory(path, merged_revisions)
    return merged_revisions


def _merge_revision_file(path: Path, merged_revisions: dict[str, object]) -> None:
    """Validate one revisions/*.toml file and append its revisions into ``merged_revisions``."""
    rev_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
    _reject_local_catalogues(path, rev_data)
    if "modelo" in rev_data:
        raise RegistryLoadError(f"{path}: revision file must not declare [modelo]; that lives in manifest.toml")
    file_revisions = _as_toml_table(rev_data.get("revisions"))
    if not file_revisions:
        raise RegistryLoadError(f"{path}: revision file must declare [revisions.<id>]")
    for revision_id, raw_revision in file_revisions.items():
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
    section_fragments = _revision_section_fragment_paths(_revision_section_directories(path))
    merged_revision: dict[str, object] = {}
    _merge_revision_manifest(revision_manifest, revision_id, merged_revision)
    for fragment_path in section_fragments:
        _merge_revision_fragment(fragment_path, revision_id, merged_revision)
    merged_revisions[revision_id] = merged_revision


def _revision_section_directories(path: Path) -> tuple[Path, ...]:
    # require_root: the caller has already resolved this revision fragment
    # directory and read its revision.toml, so an unreadable path here is a
    # broken tree, not an empty revision. Silently returning no sections would
    # compile a revision with none of its casillas.
    return tuple(
        entry
        for entry in scan_directory(path, select=DirectoryEntryKind.DIRECTORIES, require_root=True)
        if entry.name != "locales"
    )


def _revision_section_fragment_paths(section_dirs: tuple[Path, ...]) -> tuple[Path, ...]:
    """Collect every section directory's fragments, refusing an empty section.

    One listing per section directory answers both questions the loader asks
    of it -- "is this section populated" and "which files does it hold" -- so
    the two cannot disagree. They were previously two independent one-level
    walks kept textually identical by hand, on the reasoning that a guard
    seeing more than the collector could call a section "populated" while the
    collector read nothing from it. Deriving both from a single listing makes
    that agreement structural rather than editorial, and halves the walks.

    The listing is narrowed to files, which is what the emptiness question
    always meant: a directory named ``*.toml`` is not a fragment. Nothing of
    the sort can exist anyway -- :func:`_validate_section_fragment_names`
    (``loader_cache.py``, run for every section directory before a fragment
    tree is merged) refuses ANY subdirectory nested inside a section
    directory outright -- so the narrowing restates an upstream categorical
    block rather than introducing a new rule.
    """
    fragments: list[Path] = []
    for section_dir in section_dirs:
        section_fragments = scan_directory(section_dir, pattern="*.toml", select=DirectoryEntryKind.FILES)
        if not section_fragments:
            raise RegistryLoadError(f"{section_dir}: revision section fragment directory contains no TOML fragments")
        fragments.extend(section_fragments)
    return tuple(sorted(fragments))


def _read_single_revision_table(path: Path, expected_revision_id: RevisionId) -> dict[str, object]:
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
    file_revisions = _as_toml_table(fragment_data.get("revisions"))
    if not file_revisions:
        raise RegistryLoadError(f"{path}: revision fragment must declare [revisions.<id>]")
    if len(file_revisions) != 1:
        raise RegistryLoadError(f"{path}: revision fragment must declare exactly one revision")
    revision_id, raw_revision = next(iter(file_revisions.items()))
    if revision_id != expected_revision_id:
        raise RegistryLoadError(
            f"{path}: revision fragment declares {revision_id!r}, expected {expected_revision_id!r}",
        )
    raw_revision_table = _as_toml_table(raw_revision)
    if raw_revision_table is None:
        raise RegistryLoadError(f"{path}: revision {revision_id!r} must be a table")
    return raw_revision_table


def _merge_revision_manifest(path: Path, expected_revision_id: RevisionId, merged_revision: dict[str, object]) -> None:
    """Merge the fragment directory's ``revision.toml`` scalar-metadata manifest.

    In the fragmented layout the ``revision.toml`` manifest carries ONLY scalar
    revision metadata (label, valid_from/valid_to, period_selector, legal_refs,
    source_refs, orden_aplicabilidad, continuidad_validation, authority_grade)
    plus the declared governance stamp
    (:data:`REVISION_GOVERNANCE_FIELDS`). Every per-section
    array-of-tables (bindings, casillas, formulas, verification_expectations, …)
    and the completeness_manifest live in per-section fragment subdirectories;
    an inline section table in ``revision.toml`` is a loud load error naming the
    fragmented layout.

    Some of that scalar metadata is manifest-only in the other direction too
    (:data:`REVISION_MANIFEST_ONLY_FIELDS`): the governance stamp, because it is
    an authorship and signoff claim about the whole revision, ``legal_refs``,
    ``orden_aplicabilidad`` and ``valid_to``, because they are the revision's
    legal grounding, its approving ordenes and the date it stops applying, and
    ``authority_grade``, because it is the claim about how far the whole
    revision's authority reaches.
    :func:`_merge_revision_fragment` refuses all of them inside a section
    fragment rather than letting one hide among thousands of fragment files
    where no reviewer would look for it.
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


def _merge_revision_fragment(path: Path, expected_revision_id: RevisionId, merged_revision: dict[str, object]) -> None:
    """Merge one per-section fragment TOML into a single raw revision payload.

    Two refusals govern what a fragment may declare, and the narrower one runs
    first. A manifest-only field is refused by
    :func:`_reject_revision_fragment_field` with the instruction that moves it to
    ``revision.toml``; every other foreign key is refused as not belonging to the
    folder's owned section. Ordered the other way, the owned-section refusal
    swallows every manifest-only key — no fragment folder is named after one —
    and tells the author to find a different fragment folder for a field whose
    only legal home is the manifest.
    """
    raw_revision_table = _read_single_revision_table(path, expected_revision_id)
    if not raw_revision_table:
        raise RegistryLoadError(f"{path}: revision fragment declares no section fields")
    fragment_directory = path.relative_to(path.parents[1]).parts[0]
    section_name = "export_layouts" if fragment_directory == "export" else fragment_directory
    for key, value in raw_revision_table.items():
        _reject_revision_fragment_field(path, key)
        if key != section_name:
            raise RegistryLoadError(
                f"{path}: revision fragment folder {fragment_directory!r} may declare only its owned section; "
                f"found {key!r}",
            )
        _merge_revision_fragment_field(path, key, value, merged_revision)


def _merge_revision_fragment_field(
    path: Path,
    key: str,
    value: object,
    merged_revision: dict[str, object],
) -> None:
    if key == _REVISION_CONSTRUCTS:
        _merge_revision_fragment_constructs(path, value, merged_revision)
        return
    if key in _REVISION_APPEND_ARRAYS:
        _merge_revision_fragment_append_array(path, key, value, merged_revision)
        return
    if key == _REVISION_EXPORT_LAYOUTS:
        _merge_revision_fragment_export_layouts(path, value, merged_revision)
        return
    if key == _REVISION_COMPLETENESS_MANIFEST:
        _merge_revision_fragment_completeness(path, value, merged_revision)
        return
    if key in merged_revision:
        raise RegistryLoadError(f"{path}: revision fragment redeclares scalar field {key!r}")
    merged_revision[key] = value


def _reject_revision_fragment_field(path: Path, key: str) -> None:
    """Reject revision-wide fields hidden inside a section fragment."""
    if key in REVISION_GOVERNANCE_FIELDS:
        raise RegistryLoadError(
            f"{path}: revision governance field {key!r} must be declared in the revision's revision.toml "
            f"manifest, not in a per-section fragment; the stamp is a claim about the whole revision and "
            f"must be readable in one place",
        )
    if key in REVISION_MANIFEST_ONLY_FIELDS:
        raise RegistryLoadError(
            f"{path}: revision field {key!r} must be declared in the revision's revision.toml manifest, "
            f"not in a per-section fragment; it is a claim about the whole revision and must be readable "
            f"in one place",
        )


def _merge_revision_fragment_constructs(path: Path, value: object, merged_revision: dict[str, object]) -> None:
    incoming = _as_toml_array(value)
    if incoming is None:
        raise RegistryLoadError(f"{path}: revision fragment field 'constructs' must be an array")
    existing = _as_toml_array(merged_revision.get(_REVISION_CONSTRUCTS, ()))
    if existing is None:
        raise RegistryLoadError(f"{path}: revision fragment field 'constructs' conflicts with a non-array field")
    merged_revision[_REVISION_CONSTRUCTS] = _merge_table_array_fragments(
        path,
        existing,
        incoming,
        item_label="construct",
        append_array_fields=_CONSTRUCT_APPEND_ARRAYS,
    )


def _merge_revision_fragment_append_array(
    path: Path,
    key: str,
    value: object,
    merged_revision: dict[str, object],
) -> None:
    incoming = _as_toml_array(value)
    if incoming is None:
        raise RegistryLoadError(f"{path}: revision fragment field {key!r} must be an array")
    existing = _as_toml_array(merged_revision.get(key, ()))
    if existing is None:
        raise RegistryLoadError(f"{path}: revision fragment field {key!r} conflicts with a non-array field")
    merged_revision[key] = (*existing, *incoming)


def _merge_revision_fragment_export_layouts(path: Path, value: object, merged_revision: dict[str, object]) -> None:
    incoming = _as_toml_array(value)
    if incoming is None:
        raise RegistryLoadError(f"{path}: revision fragment field 'export_layouts' must be an array")
    existing = _as_toml_array(merged_revision.get(_REVISION_EXPORT_LAYOUTS, ()))
    if existing is None:
        raise RegistryLoadError(
            f"{path}: revision fragment field 'export_layouts' conflicts with a non-array field",
        )
    merged_revision[_REVISION_EXPORT_LAYOUTS] = _merge_export_layout_fragments(path, existing, incoming)


def _merge_revision_fragment_completeness(path: Path, value: object, merged_revision: dict[str, object]) -> None:
    merged_revision[_REVISION_COMPLETENESS_MANIFEST] = _merge_singleton_table_fragment(
        path,
        _REVISION_COMPLETENESS_MANIFEST,
        merged_revision.get(_REVISION_COMPLETENESS_MANIFEST),
        value,
        append_array_fields=_COMPLETENESS_MANIFEST_APPEND_ARRAYS,
    )


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
        existing_table: dict[str, object] = {}
    else:
        resolved = _as_toml_table(existing)
        if resolved is None:
            raise RegistryLoadError(f"{path}: revision fragment field {field_name!r} conflicts with a non-table field")
        existing_table = resolved

    merged = dict(existing_table)
    for key, value in incoming_table.items():
        if key in append_array_fields:
            incoming = _as_toml_array(value)
            if incoming is None:
                raise RegistryLoadError(f"{path}: revision fragment field {field_name!r}.{key!r} must be an array")
            existing_values = _as_toml_array(merged.get(key, ()))
            if existing_values is None:
                raise RegistryLoadError(
                    f"{path}: revision fragment field {field_name!r}.{key!r} conflicts with a non-array field",
                )
            merged[key] = (*existing_values, *incoming)
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
            incoming_records = _as_toml_array(value)
            if incoming_records is None:
                raise RegistryLoadError(f"{path}: export layout {layout_id!r} records must be an array")
            existing_records = _as_toml_array(merged.get("records", ()))
            if existing_records is None:
                raise RegistryLoadError(f"{path}: export layout {layout_id!r} existing records are not an array")
            merged["records"] = _merge_table_array_fragments(
                path,
                existing_records,
                incoming_records,
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
            incoming_values = _as_toml_array(value)
            if incoming_values is None:
                raise RegistryLoadError(f"{path}: {item_label} {item_id!r} field {key!r} must be an array")
            existing_values = _as_toml_array(merged.get(key, ()))
            if existing_values is None:
                raise RegistryLoadError(
                    f"{path}: {item_label} {item_id!r} field {key!r} conflicts with a non-array fragment",
                )
            _reject_duplicate_appended_table_ids(path, existing_values, incoming_values, item_label, item_id, key)
            merged[key] = (*existing_values, *incoming_values)
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
        return _load_catalogue_file_cached(str(resolved), fingerprint[1], fingerprint[2], fingerprint[3])
    except RegistryLoadError as exc:
        refreshed = _refresh_toml_fingerprint_after_load_error(resolved, exc)
        if refreshed == fingerprint:
            raise
        return _load_catalogue_file_cached(str(resolved), refreshed[1], refreshed[2], refreshed[3])


@lru_cache(maxsize=128)
def _load_catalogue_file_cached(
    path: str,
    byte_count: int,
    modified_ns: int,
    content_digest: str,
) -> RegistryCatalogues:
    del byte_count, modified_ns, content_digest
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
    supported_filing_years = None
    raw_supported_filing_years = data.get("supported_filing_years")
    if raw_supported_filing_years is not None:
        try:
            supported_filing_years = SupportedFilingYearsCatalogue.model_validate(raw_supported_filing_years)
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid supported_filing_years catalogue: {exc}") from exc
    return RegistryCatalogues(
        legal=legal,
        sources=sources,
        parameters=parameters,
        supported_filing_years=supported_filing_years,
    )


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
    table = _as_toml_table(raw)
    if table is None:
        return {}
    out: dict[str, T] = {}
    for ref_id, payload in table.items():
        payload_table = _as_toml_table(payload)
        if payload_table is None:
            raise RegistryLoadError(f"{source_path}: malformed {kind} entry")
        try:
            out[ref_id] = model.model_validate({"id": ref_id, **payload_table})
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
        RegistryLoadError: When duplicate legal or parameter ids are found
            across multiple TOML files in ``root/legal/``.
    """
    resolved = root.resolve()
    legal_dir = resolved / "legal"
    _validate_legal_directory(legal_dir)
    legal: dict[str, LegalReference] = {}
    parameters: dict[str, LegalParameter] = {}
    for path in scan_directory(legal_dir, pattern="*.toml"):
        catalogue = load_catalogue_file(path)
        overlap_legal = set(legal).intersection(catalogue.legal)
        overlap_parameters = set(parameters).intersection(catalogue.parameters)
        if overlap_legal or overlap_parameters:
            raise RegistryLoadError(
                f"{path}: duplicate catalogue ids legal={sorted(overlap_legal)!r} "
                f"sources=[] parameters={sorted(overlap_parameters)!r}",
            )
        legal.update(catalogue.legal)
        parameters.update(catalogue.parameters)
    _validate_legal_parameter_refs(legal_dir, parameters=parameters, legal=legal)
    return parameters


def load_registry_tree(
    root: Path,
    *,
    identity: RegistryIdentity | None = None,
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Load all registry files from ``root``.

    Discovers modelos in two layouts:
      * single-file: ``modelos/<id>.toml``
      * directory:   ``modelos/<id>/manifest.toml`` + ``modelos/<id>/revisions/*.toml``

    A single modelo cannot exist in both layouts simultaneously; the
    loader raises ``RegistryLoadError`` if both forms are present.

    ``identity`` is the caller's already-resolved tree identity, passed by the
    authority so one stamp read serves both. It is a HINT about the tree, never
    a key the caller chooses: on a walked tree this function collects its own
    tree-scoped fingerprints regardless, because the compiled-artefact key must
    be identical for every caller of this function or the cross-process share
    the artefact exists to deliver fragments per call site. Omitted, the
    identity is resolved here through the same canonical resolver.

    On a STAMPED tree the structural discovery pass is skipped along with the
    fingerprint walk. That pass exists so a malformed tree is refused even when
    the compiled artefact hits; on a stamped install the build already proved
    the structure, and on an artefact MISS the compile re-discovers and refuses
    anyway, so the refusal is preserved wherever it can still fire.

    Returns:
        A tuple of all :class:`ModeloDefinition` objects and the merged :class:`RegistryCatalogues`.
    """
    resolved = root.resolve()
    if identity is None:
        identity = resolve_registry_identity(
            resolved,
            collect_fingerprints=_collect_registry_tree_fingerprints,
        )
    if identity.is_stamped:
        return _load_registry_tree_cached(str(resolved), stamped_cache_key_tuples(identity))
    _validate_legal_directory(resolved / "legal")
    discover_modelo_sources(resolved / "modelos")
    fingerprints = _collect_registry_tree_fingerprints(resolved)
    try:
        return _load_registry_tree_cached(str(resolved), fingerprints)
    except RegistryLoadError as exc:
        refreshed = _refresh_registry_tree_fingerprints_after_load_error(resolved, exc)
        if refreshed == fingerprints:
            raise
        return _load_registry_tree_cached(str(resolved), refreshed)


def _collect_registry_tree_fingerprints_for_cache(
    resolved: Path,
    *,
    use_cache: bool,
) -> _RegistryPathFingerprints:
    """Collect the cache key through the dedicated fingerprint orchestrator."""
    return _collect_fingerprints_for_cache(
        resolved,
        use_cache=use_cache,
        fingerprint_cache=_registry_fingerprint_cache,
        is_bundled_root=is_bundled_registry_root,
        bundled_ttl=BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
        mutable_ttl=MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS,
        live_cached=_live_cached_fingerprints,
        collect_directory=_collect_registry_directory_fingerprints,
        collect_sources=_registry_source_fingerprints,
        store=_store_registry_fingerprints,
    )


def _live_cached_fingerprints(
    resolved: Path,
    *,
    now: float,
    ttl: float,
    directory_fingerprints: _RegistryPathFingerprints | None,
) -> _RegistryPathFingerprints | None:
    """Return the cached fingerprints when the entry is still live, else ``None``.

    ``directory_fingerprints`` is ``None`` for the pre-walk bundled
    short-circuit, where the entry's own age is the only question. When it is
    supplied, a live entry must ALSO agree with the freshly walked directory
    fingerprints; a disagreement means the tree's layout changed under the entry,
    so it is evicted rather than served. An entry that has merely aged out is
    left in place for the caller to overwrite.
    """
    entry = _registry_fingerprint_cache.get(resolved)
    if entry is None:
        return None
    cached_time, cached_directories, cached_value = entry
    if now - cached_time >= ttl:
        return None
    if directory_fingerprints is None or cached_directories == directory_fingerprints:
        return cached_value
    _registry_fingerprint_cache.pop(resolved, None)
    return None


def _registry_source_fingerprints(resolved: Path) -> tuple[_RegistryPathFingerprint, ...]:
    """Fingerprint every catalogue TOML the loader will subsequently re-open.

    Ordering is part of the cache key, so the sequence here (authorization
    fragments, legal, single-file modelos, directory-mode modelos, user-profile
    schema) is load-bearing and must not be reordered.
    """
    fingerprints: list[_RegistryPathFingerprint] = []
    for fragment in scan_directory(resolved / "authorization.d", pattern="*.toml"):
        fingerprints.append(_toml_fingerprint(fragment))
    for path in scan_directory(resolved / "legal", pattern="*.toml"):
        fingerprints.append(_toml_fingerprint(path))
    modelos_dir = resolved / "modelos"
    for path in scan_directory(modelos_dir, pattern="*.toml"):
        fingerprints.append(_toml_fingerprint(path))
    for entry in scan_directory(modelos_dir):
        fingerprints.extend(_modelo_directory_fingerprints(entry))
    schema_path = resolved / "user_profile" / "schema.toml"
    if schema_path.is_file():
        fingerprints.append(_toml_fingerprint(schema_path))
    return tuple(fingerprints)


def _store_registry_fingerprints(
    resolved: Path,
    *,
    directory_fingerprints: _RegistryPathFingerprints,
    fingerprints: _RegistryPathFingerprints,
    walk_started: float,
    bundled: bool,
) -> None:
    """Record the freshly walked fingerprints, stamped for their TTL window.

    The bundled tree is read-only package data, so its TTL bounds how often we
    redo the expensive walk rather than how stale the observation may be: stamp
    it at walk COMPLETION so the full window is available to callers. Stamping at
    walk start instead charges the walk's own cost (~1s idle, several times that
    on a loaded machine) against the window, which on a busy host can consume it
    entirely and defeat the cache exactly when it is worth most. A mutable
    authoring tree keeps the conservative start stamp: there the TTL is a
    staleness bound on a tree that can change under us.
    """
    import time

    stamped = time.time() if bundled else walk_started
    _registry_fingerprint_cache[resolved] = (stamped, directory_fingerprints, fingerprints)


def _collect_registry_directory_fingerprints(resolved: Path) -> _RegistryPathFingerprints:
    if not resolved.is_dir():
        return ()

    def _raise_walk_error(exc: OSError) -> None:
        raise RegistryLoadError(
            f"{resolved}: registry directory could not be walked during cache fingerprinting; {exc}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(resolved), "registry_tree_quiescent": False, "operation": "directory_walk"},
            ),
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
    for path in scan_directory(resolved / "locales", pattern="*.toml"):
        fingerprints.append(_toml_fingerprint(path))
    for path in scan_directory(resolved / "revisions", pattern="*.toml", recursive=True):
        fingerprints.append(_toml_fingerprint(path))
    return tuple(fingerprints)


def _modelo_directory_fingerprints(entry: Path) -> _RegistryPathFingerprints:
    """Return fingerprints for one directory-mode modelo entry, or ``()`` if not in that layout."""
    if not (entry.is_dir() and (entry / "manifest.toml").is_file()):
        return ()
    fingerprints: list[_RegistryPathFingerprint] = [_toml_fingerprint(entry / "manifest.toml")]
    for path in scan_directory(entry / "locales", pattern="*.toml", recursive=True):
        fingerprints.append(_toml_fingerprint(path))
    for rev_path in scan_directory(entry / "revisions", pattern="*.toml", recursive=True):
        fingerprints.append(_toml_fingerprint(rev_path))
    return tuple(fingerprints)


@lru_cache(maxsize=32)
def _load_registry_tree_cached(
    root: str,
    fingerprints: _RegistryPathFingerprints,
) -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    resolved = Path(root)
    use_disk_cache = registry_disk_cache_enabled(is_bundled=is_bundled_registry_root(resolved))
    if use_disk_cache:
        # A strict-validated compiled cache lets a warm
        # process skip the TOML parse. It is a shortcut to the same compiled
        # authority, never a second one: the loader here is the sole compile
        # path, and the cache read integrity-checks and structurally validates
        # the payload, deleting and recompiling on any mismatch.
        cached = load_compiled_registry_cache(resolved, fingerprints)
        if cached is not None:
            return cached

    catalogues = _load_shared_catalogue_files(resolved / "legal")
    modelos = _load_all_modelo_definitions(resolved / "modelos")
    result = (modelos, catalogues)

    if use_disk_cache:
        store_compiled_registry_cache(resolved, fingerprints, result)
    return result


def _load_shared_catalogue_files(legal_dir: Path) -> RegistryCatalogues:
    """Load every ``legal/*.toml`` shared-catalogue file with duplicate-id rejection."""
    legal: dict[str, LegalReference] = {}
    sources: dict[str, SourceReference] = {}
    parameters: dict[str, LegalParameter] = {}
    supported_filing_years: SupportedFilingYearsCatalogue | None = None
    for path in scan_directory(legal_dir, pattern="*.toml"):
        catalogue = load_catalogue_file(path)
        overlap_legal = set(legal).intersection(catalogue.legal)
        overlap_sources = set(sources).intersection(catalogue.sources)
        overlap_parameters = set(parameters).intersection(catalogue.parameters)
        if overlap_legal or overlap_sources or overlap_parameters:
            raise RegistryLoadError(
                f"{path}: duplicate catalogue ids legal={sorted(overlap_legal)!r} "
                f"sources={sorted(overlap_sources)!r} parameters={sorted(overlap_parameters)!r}",
            )
        if catalogue.supported_filing_years is not None:
            if supported_filing_years is not None:
                raise RegistryLoadError(
                    f"{path}: supported_filing_years is already declared by another shared catalogue file",
                )
            supported_filing_years = catalogue.supported_filing_years
        legal.update(catalogue.legal)
        sources.update(catalogue.sources)
        parameters.update(catalogue.parameters)
    _validate_legal_parameter_refs(legal_dir, parameters=parameters, legal=legal)
    if supported_filing_years is None:
        raise RegistryLoadError(f"{legal_dir}: missing supported_filing_years catalogue declaration")
    return RegistryCatalogues(
        legal=legal,
        sources=sources,
        parameters=parameters,
        supported_filing_years=supported_filing_years,
    )


def _validate_legal_directory(legal_dir: Path) -> None:
    """Require the shared legal catalogue to remain one flat TOML directory."""
    if not legal_dir.is_dir():
        return
    for entry in scan_directory(legal_dir):
        if entry.is_dir():
            raise RegistryLoadError(f"{entry}: unrecognized legal directory; legal catalogues must be flat")
        if not entry.is_file() or entry.suffix != ".toml":
            raise RegistryLoadError(
                f"{entry}: unrecognized legal catalogue file; legal catalogues must use the '.toml' suffix",
            )


def _load_all_modelo_definitions(modelos_dir: Path) -> tuple[ModeloDefinition, ...]:
    """Load every modelo (single-file + directory-mode) and reject layout collisions.

    A modelo id present both as ``modelos/<id>.toml`` and as
    ``modelos/<id>/manifest.toml`` is a configuration mistake — the
    loader cannot tell which layout is authoritative, so it raises
    instead of silently picking one.
    """
    return tuple(load_modelo_source(source) for source in discover_modelo_sources(modelos_dir))


def _refresh_modelo_directory_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return _collect_modelo_directory_fingerprints(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: modelo directory changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={
                    "path": str(resolved),
                    "registry_tree_quiescent": False,
                    "operation": "modelo_directory_refresh",
                },
            ),
        ) from refresh_error


def _refresh_registry_tree_fingerprints_after_load_error(
    resolved: Path,
    initial_error: RegistryLoadError,
) -> _RegistryPathFingerprints:
    try:
        return _collect_registry_tree_fingerprints_uncached(resolved)
    except RegistryLoadError as refresh_error:
        raise RegistryLoadError(
            f"{resolved}: registry tree changed during load. "
            f"Initial failure: {initial_error}; refresh failure: {refresh_error}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(resolved), "registry_tree_quiescent": False, "operation": "registry_tree_refresh"},
            ),
        ) from refresh_error


def _directory_fingerprint(path: Path) -> _RegistryPathFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry directory could not be fingerprinted; {exc}",
            registry_failure=RegistryFailureClassification(
                condition=RegistryFailureCondition.TREE_QUIESCENT,
                facts={"path": str(path), "registry_tree_quiescent": False, "operation": "directory_stat"},
            ),
        ) from exc
    # A directory has no hashable content of its own; layout changes are what
    # its stat observes, and member-file content is covered by the per-file
    # digests, so the content slot stays empty.
    return str(path), stat.st_size, stat.st_mtime_ns, ""


def _toml_fingerprint(path: Path) -> _RegistryPathFingerprint:
    """Return the ``(path, size, mtime_ns, content_digest)`` fingerprint for one TOML file.

    Delegates to :func:`~cadrumo.domain.calculations.registry.loader_cache.toml_file_fingerprint`,
    the shared primitive that makes mutable-tree fingerprints content-sensitive
    (a same-size, same-mtime rewrite still re-keys every cache above the
    loader) while the read-only bundled tree keeps the cheap stat-only form.
    """
    return toml_file_fingerprint(path)


_collect_registry_tree_fingerprints, _collect_registry_tree_fingerprints_uncached = bind_tree_fingerprint_collectors(
    is_bundled_root=is_bundled_registry_root,
    bundled_ttl=BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS,
    mutable_ttl=MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS,
    live_cached=_live_cached_fingerprints,
    collect_directory=_collect_registry_directory_fingerprints,
    collect_sources=_registry_source_fingerprints,
    store=_store_registry_fingerprints,
)


collect_registry_tree_fingerprints = _collect_registry_tree_fingerprints
