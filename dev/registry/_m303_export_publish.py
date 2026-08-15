"""Publish the generated Modelo 303 export tree for every mapped design epoch.

Every design epoch under ``dev/registry/mappings/modelo_303/`` already carries a
reviewed :class:`~._semantic_map.SemanticMap` and a matching render profile under
``dev/registry/render_profiles/modelo_303/``; :mod:`.tests.test_modelo_303_semantic_maps`
proves both against the real bundled AEAT record-design workbook on every test run.
What none of that ever did is write the rendered tree back to the real registry: every
call to :func:`~._export_tree.render_complete_export_tree` in this codebase targets a
``tmp_path``. This module is the missing last mile: assemble the same real authorities
the test suite already proves, render into the REAL revision's ``export/`` directory,
and write back the ``export_refs`` the generated layout implies onto the casillas it
addresses -- the second half of the bidirectional fact the registry build validator
(``_validate_export_field_references``) requires before a generated field may exist.

This module renders directly into the target export directory rather than through the
S10/S11 candidate-validate-publish pipeline (:mod:`._generated_tree_validation`,
:mod:`._generated_tree_publication`). That pipeline selects a snapshot through
``ValidatedRegistryAuthority.snapshot(...)``, which requires the target revision's
``review_status`` to be in ``REVIEWED_REVISION_REVIEW_STATUSES`` -- and every Modelo 303
revision in scope here defaults to ``pending_review``. Nothing in this project may stamp
that field (see ``_snapshot.py`` and ``_legal.py``), so routing through S10/S11 for these
revisions would either hard-refuse on a gate this module has no authority to satisfy, or
tempt a shortcut this module must not take. The build-time structural gates this module
DOES need to satisfy -- ``validate_export_layout_section``,
``validate_export_exemption_declarations`` -- run at ``bundled_authority()`` load and
never touch ``review_status`` at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.domain.calculations.registry import (
    ExportEncoding,
    RegistryRevisionInspection,
    RegistryValidationError,
)
from cadrumo.domain.calculations.registry._loader import load_registry_tree

from ._export_tree import ExportTreeTransportProfile, RenderedExportTree, render_complete_export_tree
from ._generated_casilla_export_refs import write_generated_casilla_export_refs
from ._record_design_ir import load_record_design_intermediate
from ._render_profile import (
    RenderProfileDesignIdentity,
    RenderProfileSourceEvidence,
    load_and_validate_render_profile,
)
from ._semantic_map_join import join_record_design_semantics
from ._semantic_map_loader import load_semantic_map

__all__ = [
    "MAPPING_ROOT",
    "PROFILE_ROOT",
    "REGISTRY_ROOT",
    "SOURCE_ROOT",
    "PublishedM303ExportTree",
    "discovered_m303_design_epochs",
    "publish_all_m303_export_trees",
    "publish_m303_export_tree",
]

_MODELO: Final[str] = "303"
MAPPING_ROOT: Final[Path] = Path("dev/registry/mappings/modelo_303")
PROFILE_ROOT: Final[Path] = Path("dev/registry/render_profiles/modelo_303")
SOURCE_ROOT: Final[Path] = Path("src/cadrumo/_data")
REGISTRY_ROOT: Final[Path] = SOURCE_ROOT / "registry" / "aeat"


@dataclass(frozen=True, slots=True)
class PublishedM303ExportTree:
    """One design epoch's freshly rendered, on-disk generated export tree."""

    design_epoch: str
    revision_id: str
    export_root: Path
    output_files: tuple[str, ...]
    casilla_files_updated: tuple[Path, ...]


def discovered_m303_design_epochs() -> tuple[str, ...]:
    """Return every authored mapping epoch, in stable lexical order.

    Discovered rather than enumerated, for the same reason the test suite
    discovers them: a hardcoded list is the thing that silently stops covering
    a newly authored epoch.
    """
    if not MAPPING_ROOT.is_dir():
        raise RegistryValidationError(f"Modelo 303 mapping root is missing: {MAPPING_ROOT}")
    return tuple(sorted(path.name for path in MAPPING_ROOT.iterdir() if path.is_dir()))


def _resolve_owning_inspection(source_ref: str) -> tuple[RegistryRevisionInspection, int]:
    """Resolve the revision owning one record-design source, from its own declaration.

    Mirrors ``dev/registry/tests/test_modelo_303_semantic_maps.py::_resolve_owning_inspection``:
    the revision is found BY the design source it declares, never by feeding a
    guessed or hardcoded revision id into resolution.
    """
    modelos, catalogues = load_registry_tree(REGISTRY_ROOT)
    try:
        modelo = next(candidate for candidate in modelos if str(candidate.id) == _MODELO)
    except StopIteration as exc:
        raise RegistryValidationError(f"modelo {_MODELO!r} is not present under {REGISTRY_ROOT}") from exc
    owners = tuple(revision for revision in modelo.revisions.values() if source_ref in revision.source_refs)
    if len(owners) != 1:
        raise RegistryValidationError(
            f"record-design source {source_ref!r} must be declared by exactly one Modelo 303 revision, "
            f"found {tuple(revision.id for revision in owners)!r}",
        )
    revision = owners[0]
    selector = revision.period_selector
    filing_year = selector.years[0] if selector.years else selector.year_from
    if filing_year is None:
        raise RegistryValidationError(f"revision {revision.id!r} period selector declares no resolvable year")
    inspection = RegistryRevisionInspection.from_revision(
        modelo=modelo,
        revision=revision,
        source_root=SOURCE_ROOT,
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )
    return inspection, int(filing_year)


def _transport_profile(design_epoch: str, *, source_ref: str, source_sha256: str) -> ExportTreeTransportProfile:
    return ExportTreeTransportProfile(
        modelo=_MODELO,
        design_epoch=design_epoch,
        source_ref=source_ref,
        source_sha256=source_sha256,
        layout_id=f"generated-modelo-303-{design_epoch}-fichero",
        format="fixed_width",
        encoding=ExportEncoding.LATIN_1,
        line_ending="crlf",
        serializer_convention="rtoml-pretty-v1",
    )


def _export_refs_by_casilla(rendered: RenderedExportTree) -> dict[str, tuple[str, ...]]:
    """Derive the casilla back-reference the rendered layout implies.

    Every field's :attr:`~ExportFieldDefinition.endpoint_casilla_id` already
    resolves both a direct ``CASILLA``-kind field and a numbered ``PROJECTION``
    endpoint uniformly. The static Modelo 303 renderer never sets
    ``record.binding_record``, so the ``_is_binding_record_template_field``
    exemption in the registry build validator never applies here: every
    addressed casilla needs its field id written back, with no exclusion.
    """
    grouped: dict[str, list[str]] = {}
    for record in rendered.layout.records:
        for field in record.fields:
            casilla_id = field.endpoint_casilla_id
            if casilla_id is None:
                continue
            grouped.setdefault(str(casilla_id), []).append(str(field.id))
    return {casilla_id: tuple(sorted(field_ids)) for casilla_id, field_ids in grouped.items()}


def publish_m303_export_tree(design_epoch: str) -> PublishedM303ExportTree:
    """Render one design epoch's export tree into the real registry and back-fill refs.

    Writes two things: the generated ``export/`` fragment tree under the owning
    revision, and the ``export_refs`` line on every casilla the generated layout
    addresses. Both are required before the registry build validators pass
    cleanly for this revision -- an export layout with no casilla back-reference
    is refused just as loudly as no layout at all.
    """
    semantic_map = load_semantic_map(MAPPING_ROOT / design_epoch)
    if semantic_map.design_epoch != design_epoch:
        raise RegistryValidationError(
            f"semantic map at {MAPPING_ROOT / design_epoch} declares design_epoch "
            f"{semantic_map.design_epoch!r}, expected {design_epoch!r}",
        )
    inspection, filing_year = _resolve_owning_inspection(str(semantic_map.source_ref))
    intermediate = load_record_design_intermediate(
        inspection.source_root,
        inspection.sources,
        source_ref=str(semantic_map.source_ref),
        filing_year=filing_year,
        design_epoch=design_epoch,
    )
    joined = join_record_design_semantics(semantic_map, intermediate, inspection)
    source_evidence = RenderProfileSourceEvidence(
        design_identity=RenderProfileDesignIdentity(
            modelo=_MODELO,
            design_epoch=design_epoch,
            source_ref=str(semantic_map.source_ref),
            source_sha256=semantic_map.source_sha256,
        ),
        entries=(),
    )
    profile = load_and_validate_render_profile(PROFILE_ROOT / design_epoch, joined, source_evidence)

    revision_id = str(inspection.revision_id)
    revision_root = REGISTRY_ROOT / "modelos" / _MODELO / "revisions" / revision_id
    export_root = revision_root / "export"
    rendered = render_complete_export_tree(
        export_root,
        revision_id=revision_id,
        joined=joined,
        semantic_map=semantic_map,
        transport_profile=_transport_profile(
            design_epoch,
            source_ref=str(semantic_map.source_ref),
            source_sha256=semantic_map.source_sha256,
        ),
        render_profile=profile,
        render_profile_source_evidence=source_evidence,
    )
    updated = write_generated_casilla_export_refs(
        revision_root,
        export_refs_by_casilla=_export_refs_by_casilla(rendered),
    )
    return PublishedM303ExportTree(
        design_epoch=design_epoch,
        revision_id=revision_id,
        export_root=export_root,
        output_files=rendered.output_files,
        casilla_files_updated=updated,
    )


def publish_all_m303_export_trees() -> tuple[PublishedM303ExportTree, ...]:
    """Publish every discovered Modelo 303 design epoch, in stable lexical order."""
    return tuple(publish_m303_export_tree(epoch) for epoch in discovered_m303_design_epochs())


if __name__ == "__main__":
    for published in publish_all_m303_export_trees():
        print(  # noqa: T201 -- deliberate operator-facing progress output for a one-shot dev script
            f"{published.design_epoch} -> revision {published.revision_id}: "
            f"{len(published.output_files)} export files, "
            f"{len(published.casilla_files_updated)} casilla files updated",
        )
