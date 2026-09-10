"""Development-only fragmented revision compiler and merge rules.

This module owns the grammar for a directory-mode revision: the manifest is
kept separate from section fragments, and repeated table ids are merged only
at the explicitly appendable fields.  The public loader remains the owner of
file and directory discovery; this private module contains only the raw TOML
fragment transformation used by that loader.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import get_args, get_origin

from pydantic import BaseModel

from cadrumo.core.toml import freeze_toml, read_toml
from cadrumo.domain.calculations.registry._toml_helpers import as_toml_table as _as_toml_table
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.modelo_localization import as_toml_array
from cadrumo.domain.calculations.registry.schema import (
    REVISION_GOVERNANCE_FIELDS,
    REVISION_MANIFEST_ONLY_FIELDS,
    ModeloRevision,
)

_REVISION_EXPORT_LAYOUTS = "export_layouts"
_REVISION_CONSTRUCTS = "constructs"
_REVISION_COMPLETENESS_MANIFEST = "completeness_manifest"
_REVISION_SPECIAL_MERGE_FIELDS = frozenset({_REVISION_EXPORT_LAYOUTS, _REVISION_CONSTRUCTS})


def _compute_revision_append_arrays() -> frozenset[str]:
    names: set[str] = set()
    for field_name, field in ModeloRevision.model_fields.items():
        if (
            field.default == ()
            and get_origin(field.annotation) is tuple
            and field_name not in _REVISION_SPECIAL_MERGE_FIELDS
        ):
            names.add(field_name)
    return frozenset(names)


_REVISION_APPEND_ARRAYS: frozenset[str] = _compute_revision_append_arrays()


def _compute_revision_section_fields() -> frozenset[str]:
    """Return ModeloRevision fields that are per-section fragment content."""
    sections: set[str] = {_REVISION_COMPLETENESS_MANIFEST}
    for field_name, field in ModeloRevision.model_fields.items():
        if get_origin(field.annotation) is not tuple:
            continue
        args = get_args(field.annotation)
        element = args[0] if args else None
        if isinstance(element, type) and issubclass(element, BaseModel):
            sections.add(field_name)
    return frozenset(sections)


REVISION_SECTION_FIELDS: frozenset[str] = _compute_revision_section_fields()
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


def _toml_table_id(value: object) -> str | None:
    """Return the string ``id`` of a TOML table value, or ``None``."""
    table = _as_toml_table(value)
    if table is None:
        return None
    table_id = table.get("id")
    return table_id if isinstance(table_id, str) else None


def reject_local_catalogues(path: Path, data: Mapping[str, object]) -> None:
    forbidden = {"source", "sources", "legal", "legal_refs_catalogue"}
    present = sorted(forbidden.intersection(data))
    if present:
        raise RegistryLoadError(f"{path}: modelo files must not define local legal/source catalogues: {present!r}")


def _read_single_revision_table(path: Path, expected_revision_id: RevisionId) -> dict[str, object]:
    """Parse one revision TOML and return its ``[revisions.<id>]`` table."""
    fragment_data = freeze_toml(read_toml(path, error_factory=RegistryLoadError))
    reject_local_catalogues(path, fragment_data)
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


def merge_revision_manifest(path: Path, expected_revision_id: RevisionId, merged_revision: dict[str, object]) -> None:
    """Merge scalar metadata from a fragmented revision's manifest."""
    raw_revision_table = _read_single_revision_table(path, expected_revision_id)
    for key, value in raw_revision_table.items():
        if key in REVISION_SECTION_FIELDS:
            raise RegistryLoadError(
                f"{path}: revision.toml must declare only scalar revision metadata; the {key!r} section "
                f"must live in a '{key}/' fragment subdirectory (fragmented layout), not inline in revision.toml",
            )
        if key in merged_revision:
            raise RegistryLoadError(f"{path}: revision manifest redeclares field {key!r}")
        merged_revision[key] = value


def merge_revision_fragment(path: Path, expected_revision_id: RevisionId, merged_revision: dict[str, object]) -> None:
    """Merge one per-section fragment into its raw revision payload."""
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
    incoming = as_toml_array(value)
    if incoming is None:
        raise RegistryLoadError(f"{path}: revision fragment field 'constructs' must be an array")
    existing = as_toml_array(merged_revision.get(_REVISION_CONSTRUCTS, ()))
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
    incoming = as_toml_array(value)
    if incoming is None:
        raise RegistryLoadError(f"{path}: revision fragment field {key!r} must be an array")
    existing = as_toml_array(merged_revision.get(key, ()))
    if existing is None:
        raise RegistryLoadError(f"{path}: revision fragment field {key!r} conflicts with a non-array field")
    merged_revision[key] = (*existing, *incoming)


def _merge_revision_fragment_export_layouts(path: Path, value: object, merged_revision: dict[str, object]) -> None:
    incoming = as_toml_array(value)
    if incoming is None:
        raise RegistryLoadError(f"{path}: revision fragment field 'export_layouts' must be an array")
    existing = as_toml_array(merged_revision.get(_REVISION_EXPORT_LAYOUTS, ()))
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
    """Merge a singleton nested TOML table whose selected arrays append."""
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
            incoming = as_toml_array(value)
            if incoming is None:
                raise RegistryLoadError(f"{path}: revision fragment field {field_name!r}.{key!r} must be an array")
            existing_values = as_toml_array(merged.get(key, ()))
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
            incoming_records = as_toml_array(value)
            if incoming_records is None:
                raise RegistryLoadError(f"{path}: export layout {layout_id!r} records must be an array")
            existing_records = as_toml_array(merged.get("records", ()))
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
    """Merge fragment table arrays by id, appending explicitly mergeable arrays."""
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
            incoming_values = as_toml_array(value)
            if incoming_values is None:
                raise RegistryLoadError(f"{path}: {item_label} {item_id!r} field {key!r} must be an array")
            existing_values = as_toml_array(merged.get(key, ()))
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
