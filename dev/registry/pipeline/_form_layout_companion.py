"""Prepare a generated form companion inside an isolated export candidate.

The existing form-layout owner generates and serialises the companion. This
preparation runs before the read-only registry validator; it never repairs a
published target or lets validation accept a stale layout.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutReviewState, FormLayoutSeedSource

from ..compiler.loader import load_registry_tree
from ..form_layout.generator import generate_revision_layout
from ..form_layout.serialization import FORM_LAYOUT_DIRECTORY, FORM_LAYOUT_FRAGMENT, render_form_layout_toml
from ._tree_validation import GeneratedExportTreeValidationContext
from .tree_paths import contains, require_existing_non_link

if TYPE_CHECKING:
    from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision, RegistryCatalogues

__all__ = ["prepare_generated_form_layout_companion"]


def prepare_generated_form_layout_companion(
    context: GeneratedExportTreeValidationContext, *, temporary_root: Path
) -> None:
    """Regenerate only the selected modelo's isolated candidate companion.

    An authored or reviewed layout remains authority: leave it in place so
    validation refuses it if the new export makes it stale. Review state alone
    does not distinguish an authored draft from automatic generator output.
    """
    require_existing_non_link(context.registry_root, subject="generated form companion candidate root")
    candidate_root = context.registry_root.resolve()
    staging_root = temporary_root.resolve()
    if candidate_root == staging_root or not contains(staging_root, candidate_root):
        raise RegistryValidationError("generated form companion must be prepared inside its isolated temporary root")
    modelo, revision, catalogues = _selected_candidate_revision(context, candidate_root)
    if not _revision_needs_generated_layout(revision):
        return
    revision_root = candidate_root / "modelos" / str(modelo.id) / "revisions" / str(revision.id)
    fragment = _editable_form_layout_fragment(revision_root)
    generated = generate_revision_layout(
        str(modelo.id), revision, sources=catalogues.sources, data_root=context.source_root
    )
    if generated.layout is None:
        raise RegistryValidationError(f"generated form companion cannot be regenerated: {generated.failure}")
    fragment.write_text(render_form_layout_toml(str(revision.id), generated.layout), encoding="utf-8", newline="\n")


def _selected_candidate_revision(
    context: GeneratedExportTreeValidationContext, candidate_root: Path
) -> tuple[ModeloDefinition, ModeloRevision, RegistryCatalogues]:
    """Load the isolated tree and require it to contain only the requested revision."""
    modelos, catalogues = load_registry_tree(candidate_root)
    modelo = next(modelo for modelo in modelos if str(modelo.id) == str(context.target.modelo))
    expected = context.source_chain_revisions or (
        (str(context.target.revision_id),)
        if context.inheritance is None
        else (
            *tuple(revision_id for revision_id, _digest in context.inheritance.pinned_ancestors),
            str(context.target.revision_id),
        )
    )
    if tuple(modelo.revisions) != expected:
        raise RegistryValidationError("generated form companion candidate has an unpinned or missing revision")
    if context.inheritance is not None and (
        modelo.revisions[expected[-2]].export_layouts != (context.inheritance.baseline_layout,)
    ):
        raise RegistryValidationError("generated form companion baseline layout differs from its attestation")
    revision = modelo.revisions[str(context.target.revision_id)]
    return modelo, revision, catalogues


def _revision_needs_generated_layout(revision: ModeloRevision) -> bool:
    """Preserve authored drafts and reviewed layouts; skip revisions with none."""
    if not revision.form_layouts:
        return False
    if len(revision.form_layouts) != 1:
        raise RegistryValidationError("generated form companion requires exactly one declared form layout")
    layout = revision.form_layouts[0]
    return (
        layout.seed_source is not FormLayoutSeedSource.AUTHORED
        and layout.review.state is not FormLayoutReviewState.REVIEWED
    )


def _editable_form_layout_fragment(revision_root: Path) -> Path:
    """Require the one supported non-link fragment that owns the generated layout."""
    fragments = tuple(scan_directory(revision_root / FORM_LAYOUT_DIRECTORY, select=DirectoryEntryKind.FILES))
    if len(fragments) != 1 or fragments[0].name not in (FORM_LAYOUT_FRAGMENT, "0001-complete-edition.toml"):
        raise RegistryValidationError("generated form companion has unknown fragment ownership")
    require_existing_non_link(fragments[0], subject="generated form companion fragment")
    return fragments[0]
