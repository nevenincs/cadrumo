"""Structural view of the published registry generation for registry-aware tests."""

from __future__ import annotations

from functools import cache

from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..authority_artifact import SnapshotGlobalsComponentQuery
from ..errors import RegistryValidationError
from ..schema import ModeloDefinition, RegistryCatalogues, SnapshotGlobalCatalogues
from ..snapshot import collect_snapshot_ref_ids


def full_published_modelo(operation: PinnedAuthorityOperation, modelo_id: str) -> ModeloDefinition:
    """Reconstruct one modelo carrying every revision the published generation declares.

    ``operation`` addresses components lazily, so this materializes each
    revision separately and folds them into one multi-revision view -- the
    same shape :func:`bundled_registry_tree` returns for every modelo.
    """
    directory = operation.modelo_directory(modelo_id)
    revisions = {
        str(metadata.id): operation.revision_with_export_layouts(modelo_id, str(metadata.id))
        for metadata in directory.revisions
    }
    first_revision = next(iter(revisions.values()))
    return directory.materialize(first_revision).model_copy(update={"revisions": revisions})


@cache
def bundled_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Return a structural view of the published registry generation.

    The view lists every published modelo with every revision the generation
    stores, and the legal and source references those modelos cite. A query for
    an id no modelo cites is absent here, exactly as it is absent from any one
    modelo's own snapshot closure.

    It is a view for inspecting declarations, not a stand-in for the published
    generation. Its catalogues carry no governed facts, and revision selection,
    projection and admission stay with the generation itself. A snapshot built
    from this view must therefore be built inside a published operation lease,
    which scopes the generation's governed facts for that build.

    Tests that need a mutable source tree belong to the development authoring
    lane, not here.
    """
    with bundled_indexed_authority().operation() as operation:
        modelo_ids = operation.modelo_ids()
        if not modelo_ids:
            raise RegistryValidationError("published registry generation declares no modelos")
        modelos = tuple(full_published_modelo(operation, modelo_id) for modelo_id in modelo_ids)
        legal_ids: set[str] = set()
        source_ids: set[str] = set()
        for modelo in modelos:
            for revision in modelo.revisions.values():
                revision_legal_ids, revision_source_ids = collect_snapshot_ref_ids(modelo, revision)
                legal_ids.update(revision_legal_ids)
                source_ids.update(revision_source_ids)
        globals_value = operation.load(SnapshotGlobalsComponentQuery(), pin=operation.pin())
        if not isinstance(globals_value, SnapshotGlobalCatalogues):
            raise RegistryValidationError("snapshot globals component decoded to an unexpected type")
        directory = operation.modelo_directory(modelo_ids[0])
        catalogues = RegistryCatalogues(
            legal={reference_id: operation.legal_reference(reference_id) for reference_id in sorted(legal_ids)},
            sources={reference_id: operation.source_reference(reference_id) for reference_id in sorted(source_ids)},
            convenio=globals_value.convenio,
            supplementary_ordenes=globals_value.supplementary_ordenes,
            supported_filing_years=directory.supported_filing_years,
        )
        return modelos, catalogues


def bundled_modelo_components(modelo_id: str) -> tuple[ModeloDefinition, RegistryCatalogues]:
    """Return one modelo of :func:`bundled_registry_tree` together with the view's catalogues."""
    modelos, catalogues = bundled_registry_tree()
    for modelo in modelos:
        if modelo.id == modelo_id:
            return modelo, catalogues
    raise LookupError(f"published registry generation declares no modelo {modelo_id!r}")


__all__ = ["bundled_modelo_components", "bundled_registry_tree", "full_published_modelo"]
