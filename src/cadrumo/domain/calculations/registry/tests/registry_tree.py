"""Canonical compiled-registry-tree accessor for registry-aware tests."""

from __future__ import annotations

from functools import cache

from ..authority import PinnedAuthorityOperation, ValidatedRegistryAuthority, bundled_indexed_authority
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
def _bundled_registry_tree_with_identity() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues, str]:
    """Return the immutable bundled registry published for runtime use.

    Test fixtures that need a mutable source tree must live in the development
    authoring test lane. This accessor is deliberately limited to the
    published artifact, so shared source tests do not reach ``dev`` or a root
    test-support package just to obtain bundled facts.

    The legal and source catalogues carry every reference the published
    modelos actually cite, not the raw authored corpus; a query for an id no
    modelo cites is absent here exactly as it is absent from any one modelo's
    own snapshot closure. The governed-fact catalogue is intentionally empty:
    callers that need governed-fact resolution must do so from inside a
    :func:`bundled_indexed_authority` operation lease, which is itself
    registered as the ambient governed-fact source for that lease.
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
        return modelos, catalogues, operation.pin().logical_generation


def bundled_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    """Return the immutable bundled registry published for runtime use.

    Test fixtures that need a mutable source tree must live in the development
    authoring test lane. This accessor is deliberately limited to the
    published artifact, so shared source tests do not reach ``dev`` or a root
    test-support package just to obtain bundled facts.

    The legal and source catalogues carry every reference the published
    modelos actually cite, not the raw authored corpus; a query for an id no
    modelo cites is absent here exactly as it is absent from any one modelo's
    own snapshot closure. The governed-fact catalogue is intentionally empty:
    callers that need governed-fact resolution must do so from inside a
    :func:`bundled_indexed_authority` operation lease, which is itself
    registered as the ambient governed-fact source for that lease.
    """
    modelos, catalogues, _identity_digest = _bundled_registry_tree_with_identity()
    return modelos, catalogues


def bundled_validated_registry_authority() -> ValidatedRegistryAuthority:
    """Return an eager :class:`ValidatedRegistryAuthority` view of the published tree.

    Only for legacy production surfaces (such as
    :class:`~..queries.RegistryQueryService`) that deliberately accept no
    other authority shape. Built from the same published components
    :func:`bundled_registry_tree` returns, never from mutable source.
    """
    modelos, catalogues, identity_digest = _bundled_registry_tree_with_identity()
    return ValidatedRegistryAuthority.from_validated_components(
        modelos=modelos,
        catalogues=catalogues,
        identity_digest=identity_digest,
    )


__all__ = ["bundled_registry_tree", "bundled_validated_registry_authority", "full_published_modelo"]
