"""Prepare a generated form companion inside an isolated export candidate.

The existing form-layout owner generates and serialises the companion. This
preparation runs before the read-only registry validator; it never repairs a
published target or lets validation accept a stale layout.
"""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema_form_layouts import FormLayoutReviewState

from ..compiler.loader import load_registry_tree
from ..form_layout.generator import generate_revision_layout
from ..form_layout.serialization import FORM_LAYOUT_DIRECTORY, FORM_LAYOUT_FRAGMENT, render_form_layout_toml
from ._tree_validation import GeneratedExportTreeValidationContext
from .tree_paths import contains, require_existing_non_link

__all__ = ["prepare_generated_form_layout_companion"]


def prepare_generated_form_layout_companion(
    context: GeneratedExportTreeValidationContext, *, temporary_root: Path
) -> None:
    """Regenerate only the selected modelo's isolated candidate companion.

    A reviewed layout remains authored authority: the owning generator leaves
    it in place and validation refuses it if the new export makes it stale.
    """
    require_existing_non_link(context.registry_root, subject="generated form companion candidate root")
    candidate_root = context.registry_root.resolve()
    staging_root = temporary_root.resolve()
    if candidate_root == staging_root or not contains(staging_root, candidate_root):
        raise RegistryValidationError("generated form companion must be prepared inside its isolated temporary root")
    modelos, catalogues = load_registry_tree(candidate_root)
    modelo = next(modelo for modelo in modelos if str(modelo.id) == str(context.target.modelo))
    if tuple(modelo.revisions) != (str(context.target.revision_id),):
        raise RegistryValidationError("generated form companion candidate must contain exactly the selected revision")
    revision = modelo.revisions[str(context.target.revision_id)]
    if not revision.form_layouts:
        return
    if len(revision.form_layouts) != 1:
        raise RegistryValidationError("generated form companion requires exactly one declared form layout")
    if revision.form_layouts[0].review.state is FormLayoutReviewState.REVIEWED:
        return
    revision_root = candidate_root / "modelos" / str(modelo.id) / "revisions" / str(revision.id)
    fragments = tuple(scan_directory(revision_root / FORM_LAYOUT_DIRECTORY, select=DirectoryEntryKind.FILES))
    if len(fragments) != 1 or fragments[0].name not in (FORM_LAYOUT_FRAGMENT, "0001-complete-edition.toml"):
        raise RegistryValidationError("generated form companion has unknown fragment ownership")
    require_existing_non_link(fragments[0], subject="generated form companion fragment")
    generated = generate_revision_layout(
        str(modelo.id), revision, sources=catalogues.sources, data_root=context.source_root
    )
    if generated.layout is None:
        raise RegistryValidationError(f"generated form companion cannot be regenerated: {generated.failure}")
    fragments[0].write_text(render_form_layout_toml(str(revision.id), generated.layout), encoding="utf-8", newline="\n")
