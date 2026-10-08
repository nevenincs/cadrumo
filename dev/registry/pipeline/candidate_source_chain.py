"""Retain edge-local evidence while rendering one export in an isolated copy."""

from pathlib import Path
from shutil import copytree

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export_field_casilla import derive_casilla_export_refs
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from ..compiler.export_fragment_grammar import EXPORT_SECTION_DIRECTORY_NAMES
from ..compiler.loader import load_modelo_directory
from ..export_clearance import remaining_export_clearances


def requires_source_chain(revision: ModeloRevision) -> bool:
    """Identify evidence that the detached inline representation cannot retain."""
    rows = {row.continuidad_id: row for row in revision.casillas}
    for attestation in revision.lineage_attestations:
        row = rows.get(attestation.identity)
        if (
            attestation.family != "casillas"
            or row is None
            or row.legal_refs != attestation.legal_refs
            or row.source_refs != attestation.source_refs
        ):
            return True
    return False


def stage_source_chain(source: Path, destination: Path, *, revision: str, include_target_export: bool) -> Path:
    """Copy the actual chain; only the selected export is replaced by the renderer."""
    target = (source / "revisions" / revision).resolve()
    if source.resolve() == destination.resolve() or destination.resolve().is_relative_to(source.resolve()):
        raise RegistryValidationError("source-chain staging requires a separate destination")
    definition = load_modelo_directory(source)
    if revision not in definition.revisions:
        raise RegistryValidationError("source-chain staging target is absent")

    def ignore(directory: str, names: list[str]) -> set[str]:
        if not include_target_export and Path(directory).resolve() == target:
            return set(names).intersection(EXPORT_SECTION_DIRECTORY_NAMES)
        return set()

    copytree(source, destination, ignore=ignore)
    return destination


def require_source_chain_unchanged(source: ModeloDefinition, candidate: ModeloDefinition, *, revision: str) -> None:
    """Refuse altered siblings, metadata, lineage or target calculation facts.

    The selected export and its reconciled form belong to their separate
    generators. Every other effective fact remains exactly the source fact.
    """
    if tuple(source.revisions) != tuple(candidate.revisions) or revision not in source.revisions:
        raise RegistryValidationError("source-chain candidate has an unpinned or missing revision")
    if source.model_copy(update={"revisions": candidate.revisions}) != candidate:
        raise RegistryValidationError("source-chain candidate changed modelo metadata")
    for revision_id, before in source.revisions.items():
        after = candidate.revisions[revision_id]
        if revision_id == revision:
            before = _without_derived_export_refs(before)
            after = _without_derived_export_refs(after)
            if not before.export_layouts and after.export_layouts:
                before = before.model_copy(update={"cleared_families": remaining_export_clearances(before)})
            after = after.model_copy(
                update={"export_layouts": before.export_layouts, "form_layouts": before.form_layouts}
            )
        if before != after:
            raise RegistryValidationError(f"source-chain candidate changed protected facts in revision {revision_id!r}")


def _without_derived_export_refs(revision: ModeloRevision) -> ModeloRevision:
    references = derive_casilla_export_refs(revision.export_layouts, revision.bindings)
    if set(references) - {row.id for row in revision.casillas} or any(
        row.export_refs != references.get(row.id, ()) for row in revision.casillas
    ):
        raise RegistryValidationError("source-chain candidate has inconsistent derived export references")
    return revision.model_copy(
        update={"casillas": tuple(row.model_copy(update={"export_refs": ()}) for row in revision.casillas)}
    )
