"""Compile a merged registry modelo payload into its typed definition."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry.ids import RevisionId
from cadrumo.domain.calculations.registry.modelo_localization import (
    enroll_revision_localization,
    modelo_locale_key,
)
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
)
from cadrumo.domain.calculations.registry.validate_revision_identity import revision_reference_identity_failures

from . import revision_materialisation as _revision_materialisation
from ._loader_revision_fragments import (
    reject_local_catalogues as _reject_local_catalogues,
)
from ._toml_helpers import as_toml_table as _as_toml_table
from .casilla_inheritance import _LabelOrigins
from .inherited_label_localization import _enroll_inherited_label_fallbacks, _mark_inherited_casillas
from .lineage_sidecars import _validate_lineage_sidecars, _with_lineage_claims
from .reference_defaults import _apply_edition_reference_defaults
from .reference_resolution import _resolve_inherited_references
from .revision_export_projection import (
    _compile_revision_projection_semantics,
    _refuse_authored_export_refs,
    _with_derived_export_refs,
)


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


def _build_modelo_definition_from_data(
    source_path: Path,
    data: Mapping[str, object],
    *,
    validation_context: Mapping[str, object] | None = None,
) -> ModeloDefinition:
    """Validate a merged modelo TOML payload into a ModeloDefinition."""
    _reject_local_catalogues(source_path, data)
    modelo_table, modelo_id, declared_revisions = _validated_modelo_input(source_path, data)
    materialised = _revision_materialisation._materialise_revisions(source_path, str(modelo_id), declared_revisions)
    predecessor_declarations = _revision_materialisation._raw_predecessor_declarations(declared_revisions)
    revisions = _materialise_typed_revisions(
        source_path,
        modelo_id,
        materialised.revisions,
        materialised.label_origins,
        materialised.text_origins,
        validation_context,
    )
    predecessors = {} if predecessor_declarations is None else predecessor_declarations.named
    revisions = _validate_and_attach_lineage_claims(source_path, revisions, predecessors)
    return _validate_modelo_definition(source_path, modelo_table, modelo_id, revisions, validation_context)


def _validated_modelo_input(
    source_path: Path,
    data: Mapping[str, object],
) -> tuple[Mapping[str, object], str, Mapping[str, object]]:
    if "modelo" not in data:
        raise RegistryLoadError(f"{source_path}: missing [modelo] table")
    modelo_table = _as_toml_table(data["modelo"])
    if modelo_table is None:
        raise RegistryLoadError(f"{source_path}: [modelo] must be a table")
    modelo_id = modelo_table.get("id")
    modelo_id_for_context = modelo_id if isinstance(modelo_id, str) else source_path.as_posix()
    declared_revisions = _as_toml_table(data.get("revisions"))
    if not declared_revisions:
        raise RegistryLoadError(f"{source_path}: missing [revisions.<id>] tables")
    return modelo_table, modelo_id_for_context, declared_revisions


def _materialise_typed_revisions(
    source_path: Path,
    modelo_id: str,
    raw_revisions: Mapping[str, object],
    label_origins_by_revision: Mapping[str, _LabelOrigins],
    text_origins_by_revision: Mapping[str, _LabelOrigins],
    validation_context: Mapping[str, object] | None,
) -> dict[str, ModeloRevision]:
    revisions: dict[str, ModeloRevision] = {}
    for revision_id, raw_revision in raw_revisions.items():
        revisions[revision_id] = _materialise_typed_revision(
            source_path,
            modelo_id,
            revision_id,
            raw_revision,
            label_origins_by_revision.get(revision_id),
            text_origins_by_revision.get(revision_id),
            validation_context,
        )
    return revisions


def _materialise_typed_revision(
    source_path: Path,
    modelo_id: str,
    revision_id: str,
    raw_revision: object,
    label_origins: _LabelOrigins | None,
    text_origins: _LabelOrigins | None,
    validation_context: Mapping[str, object] | None,
) -> ModeloRevision:
    raw_revision_table = _as_toml_table(raw_revision)
    if raw_revision_table is None:
        raise RegistryLoadError(f"{source_path}: revision {revision_id!r} must be a table")
    context = f"{source_path}: revision {revision_id!r}"
    payload = _enroll_revision_payload(
        source_path,
        modelo_id,
        revision_id,
        context,
        raw_revision_table,
        label_origins,
        text_origins,
    )
    try:
        revision = ModeloRevision.model_validate(payload, context=validation_context)
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid revision {revision_id!r}: {exc}") from exc
    revision = _with_derived_export_refs(source_path, revision, payload)
    _raise_on_ambiguous_revision_identity(
        source_path,
        modelo_id=modelo_id,
        revision_id=revision_id,
        revision=revision,
    )
    return revision


def _enroll_revision_payload(
    source_path: Path,
    modelo_id: str,
    revision_id: str,
    context: str,
    raw_revision_table: Mapping[str, object],
    label_origins: _LabelOrigins | None,
    text_origins: _LabelOrigins | None,
) -> dict[str, object]:
    if label_origins is not None:
        raw_revision_table = _resolve_inherited_references(
            source_path,
            revision_id=revision_id,
            table=raw_revision_table,
            label_origins=label_origins,
        )
    raw_revision_table = _apply_edition_reference_defaults(context, raw_revision_table)
    payload = enroll_revision_localization(
        modelo_id=str(modelo_id),
        revision_id=revision_id,
        raw_revision=raw_revision_table,
    )
    if text_origins is not None:
        payload = _enroll_inherited_label_fallbacks(
            context,
            modelo_id=str(modelo_id),
            payload=payload,
            label_origins=text_origins,
        )
    payload = _mark_inherited_casillas(context, payload=payload, label_origins=label_origins)
    payload = _compile_revision_projection_semantics(source_path, payload)
    _refuse_authored_export_refs(source_path, revision_id, payload)
    return payload


def _validate_and_attach_lineage_claims(
    source_path: Path,
    revisions: dict[str, ModeloRevision],
    predecessors: Mapping[str, str],
) -> dict[str, ModeloRevision]:
    try:
        _validate_lineage_sidecars(revisions, predecessors=predecessors)
        return {key: _with_lineage_claims(revision) for key, revision in revisions.items()}
    except RegistryValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid lineage attestations: {exc}") from exc


def _validate_modelo_definition(
    source_path: Path,
    modelo_table: Mapping[str, object],
    modelo_id: str,
    revisions: Mapping[str, ModeloRevision],
    validation_context: Mapping[str, object] | None,
) -> ModeloDefinition:
    try:
        return ModeloDefinition.model_validate(
            {
                **modelo_table,
                "title_localization_key": modelo_locale_key(str(modelo_id), "title"),
                "official_name_localization_key": modelo_locale_key(str(modelo_id), "official_name"),
                "revisions": revisions,
            },
            context=validation_context,
        )
    except ValidationError as exc:
        raise RegistryLoadError(f"{source_path}: invalid modelo definition: {exc}") from exc
