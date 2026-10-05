"""Compile export projection declarations and derive typed casilla export references."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.modelo_localization import (
    as_toml_array,
)
from cadrumo.domain.calculations.registry.schema import (
    ModeloRevision,
)
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ._toml_helpers import as_toml_table as _as_toml_table
from .loader_fields import (
    _EXPORT_REFS_FIELD,
    _INHERITED_SECTION,
)
from .loader_semantics import (
    compile_export_semantic_field,
    compile_projection_endpoint_declaration,
    passthrough_toml_row,
)


def _refuse_authored_export_refs(source_path: Path, revision_id: str, payload: Mapping[str, object]) -> None:
    """Refuse a casilla row that declares ``export_refs``, which the loader derives from the layouts."""
    rows = as_toml_array(payload.get(_INHERITED_SECTION, ())) or ()
    authored = sorted(
        str(table.get("id"))
        for row in rows
        if (table := _as_toml_table(row)) is not None and _EXPORT_REFS_FIELD in table
    )
    if authored:
        raise RegistryLoadError(
            f"{source_path}: revision {revision_id!r} casillas {authored!r} declare export_refs; a casilla's "
            "export references are derived from the export fields that resolve to it, so remove the key",
        )


def _with_derived_export_refs(
    source_path: Path,
    revision: ModeloRevision,
    payload: Mapping[str, object],
) -> ModeloRevision:
    """Return ``revision`` with every casilla's ``export_refs`` derived from the edition's own layouts.

    The derivation runs on the materialised edition, so an inherited row takes
    the references of the layout it now sits beside and never its origin's.
    Each re-derived row is constructed again from its enrolled payload, so the
    casilla's own coherence rules see the derived value exactly as they would
    an authored one.
    """
    try:
        derived = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    except RegistryValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid revision {revision.id!r}: {exc}") from exc
    if not derived:
        return revision
    _require_declared_export_targets(source_path, revision, derived)
    casillas = _casillas_with_export_references(source_path, revision, payload, derived)
    return revision.model_copy(update={_INHERITED_SECTION: casillas})


def _require_declared_export_targets(
    source_path: Path,
    revision: ModeloRevision,
    derived: Mapping[str, object],
) -> None:
    declared = {casilla.id for casilla in revision.casillas}
    undeclared = sorted(casilla_id for casilla_id in derived if casilla_id not in declared)
    if undeclared:
        raise RegistryLoadError(
            f"{source_path}: invalid revision {revision.id!r}: export fields resolve to casillas {undeclared!r}, "
            "which the edition does not declare",
        )


def _casillas_with_export_references(
    source_path: Path,
    revision: ModeloRevision,
    payload: Mapping[str, object],
    derived: Mapping[str, object],
) -> tuple[CasillaDefinition, ...]:
    rows = as_toml_array(payload.get(_INHERITED_SECTION, ())) or ()
    casillas: list[CasillaDefinition] = []
    for casilla, row in zip(revision.casillas, rows, strict=True):
        refs = derived.get(casilla.id)
        table = _as_toml_table(row)
        if refs is None or table is None:
            casillas.append(casilla)
            continue
        try:
            casillas.append(CasillaDefinition.model_validate({**table, _EXPORT_REFS_FIELD: refs}))
        except ValidationError as exc:
            raise RegistryLoadError(f"{source_path}: invalid revision {revision.id!r}: {exc}") from exc
    return tuple(casillas)


def _compile_revision_projection_record(source_path: Path, raw_record: object) -> dict[str, object]:
    record = _as_toml_table(raw_record)
    if record is None:
        return passthrough_toml_row(raw_record)
    compiled = dict(record)
    fields = as_toml_array(record.get("fields"))
    if fields is not None:
        compiled["fields"] = tuple(compile_export_semantic_field(source_path, raw_field) for raw_field in fields)
    return compiled


def _compile_revision_projection_layout(source_path: Path, raw_layout: object) -> dict[str, object]:
    layout = _as_toml_table(raw_layout)
    if layout is None:
        return passthrough_toml_row(raw_layout)
    compiled = dict(layout)
    records = as_toml_array(layout.get("records"))
    if records is not None:
        compiled["records"] = tuple(
            _compile_revision_projection_record(source_path, raw_record) for raw_record in records
        )
    return compiled


def _compile_revision_projection_semantics(source_path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Compile revision-owned typed tokens before schema construction."""
    compiled = dict(payload)
    declarations = as_toml_array(payload.get("projection_endpoints"))
    if declarations is not None:
        compiled["projection_endpoints"] = tuple(
            compile_projection_endpoint_declaration(source_path, raw_declaration) for raw_declaration in declarations
        )
    layouts = as_toml_array(payload.get("export_layouts"))
    if layouts is not None:
        compiled["export_layouts"] = tuple(
            _compile_revision_projection_layout(source_path, raw_layout) for raw_layout in layouts
        )
    return compiled
