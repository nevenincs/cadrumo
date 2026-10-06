"""Fail-closed validation for one un-published generated export revision.

This development-only boundary never locates an existing export tree, accepts a
single-file modelo, or publishes a candidate.  Its sole purpose is to prove
that the fresh isolated tree selected by the generator can survive both the
real directory loader and the validated registry authority before publication
is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.directory_scan import iter_directory
from cadrumo.core.link_safety import is_link_like
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.ids import SourceRefId
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues, RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.static_inspection import RegistryRevisionInspection
from cadrumo.domain.calculations.registry.temporal import ModeloRevisionDirectory, select_authored_revision_metadata
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot

from ..compiler.authority import compile_registry_tree, compile_validated_authority
from ..compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ..compiler.identity import resolve_registry_identity
from ..compiler.loader import load_modelo_directory
from ..compiler.loader_fingerprints import collect_registry_tree_fingerprints
from ..compiler.profile_schema import capture_profile_schema_source
from ..compiler.registry_scope import validate_registry_scope
from ..edition_delta_chain_materialisation import chain_materialisation, member_identities
from ..edition_delta_proof_source import read_staged_edition
from .candidate_source_chain import require_source_chain_unchanged
from .export_fragment_provenance import (
    ExportFragmentProvenanceManifest,
    ExportFragmentTarget,
    verify_export_fragment_provenance_manifest,
)
from .export_tree_models import RenderedExportTree
from .generated_export_inheritance import require_generated_export_inheritance
from .generated_export_inheritance_model import GeneratedExportInheritanceContext
from .joined_record_design import JoinedRecordDesign
from .render_check import _select_record_design_source
from .render_profile_evidence import RenderProfileSourceEvidence
from .render_profile_model import RenderProfile
from .semantic_map import SemanticMap
from .tree_paths import require_existing_non_link

__all__ = [
    "GeneratedExportTreeValidationContext",
    "ValidatedGeneratedExportTree",
    "ValidatedHistoricalStaticGeneratedExportTree",
    "validate_generated_export_tree",
]


@dataclass(frozen=True, slots=True)
class GeneratedExportTreeValidationContext:
    """The one isolated candidate registry and filing selection to validate."""

    registry_root: Path
    source_root: Path
    target: ExportFragmentTarget
    filing_year: int
    period: str
    on: date | None = None
    #: Modelos other than the target that the candidate root is allowed to hold.
    #:
    #: The target's own validation resolves its cross-modelo folds against the
    #: LOADED registry, so a candidate holding only the target refuses every
    #: revision that reads another modelo -- Modelo 353's per-member fan-in over
    #: Modelo 322 is the worked case, and it refused with "references unknown
    #: source modelo" from an isolation the caller created, not an authoring gap.
    #: Naming them keeps the isolation bounded and auditable: anything staged
    #: beyond the target and this set is still refused, and the checks that
    #: actually pin the verdict -- the target directory loading exactly one
    #: revision, and the authority selecting exactly that modelo and revision --
    #: are unchanged and unaffected by a supporting modelo being present.
    supporting_modelos: frozenset[str] = frozenset()
    #: A separately staged, non-export witness for continuity predecessors.
    #:
    #: A generated candidate intentionally contains only its target revision.
    #: Strict continuidad evolutions, however, name real predecessor revisions.
    #: This optional directory-mode modelo supplies only those predecessors'
    #: scalar revision metadata, casilla continuity surfaces, and evolution
    #: declarations.  It is never part of the candidate registry, never
    #: rendered, compared, or published, and its target revision is refused:
    #: the rendered target remains the sole source of its own facts.
    continuity_metadata_modelo_root: Path | None = None
    #: Full validated source supplies corpus context for scope-only checks.
    #: Its target revision is always replaced with the freshly loaded candidate;
    #: it supplies no generated layout, snapshot or target-validation verdict.
    scope_authority: ValidatedRegistryAuthority | None = None
    #: Authority grade the caller is entitled to establish.  Existing check and
    #: validation callers keep the filing-grade default; publication supplies
    #: the selected revision's declared grade because a static generated layout
    #: does not establish calculation or filing readiness.
    required_grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING
    inheritance: GeneratedExportInheritanceContext | None = None
    #: The exact selected official source for a static target below the
    #: product's filing support floor. The normal None route still requires a
    #: runtime snapshot at required_grade and refuses that historical year.
    historical_static_source_ref: SourceRefId | None = None
    source_chain_revisions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.source_chain_revisions and (self.scope_authority is None or self.inheritance is not None):
            raise RegistryValidationError("source-chain validation requires source authority and no export inheritance")
        if not self.period.strip():
            raise RegistryValidationError("generated-tree validation requires a non-empty filing period")
        if str(self.target.modelo) in self.supporting_modelos:
            raise RegistryValidationError(
                "generated-tree validation must not name the target modelo as a supporting modelo",
            )


@dataclass(frozen=True, slots=True)
class ValidatedGeneratedExportTree:
    """The authority-selected result of validating one fresh generated tree."""

    target: ExportFragmentTarget
    layout: ExportLayoutDefinition
    snapshot: RegistrySnapshot
    provenance_manifest: ExportFragmentProvenanceManifest


@dataclass(frozen=True, slots=True)
class ValidatedHistoricalStaticGeneratedExportTree:
    """A complete historical generated target with no runtime filing admission."""

    target: ExportFragmentTarget
    layout: ExportLayoutDefinition
    inspection: RegistryRevisionInspection
    provenance_manifest: ExportFragmentProvenanceManifest


def validate_generated_export_tree(
    *,
    context: GeneratedExportTreeValidationContext,
    joined: JoinedRecordDesign,
    semantic_map: SemanticMap,
    rendered: RenderedExportTree,
    render_profile: RenderProfile,
    render_profile_source_evidence: RenderProfileSourceEvidence,
) -> ValidatedGeneratedExportTree | ValidatedHistoricalStaticGeneratedExportTree:
    """Prove an isolated generated tree at its requested admission boundary.

    An ordinary candidate contains only its target edition. An attested
    inherited candidate contains exactly its pinned ancestor chain and thin
    child; every staged edition must preserve its canonical effective meaning,
    and the child must hydrate to the freshly rendered layout. Extra revisions,
    modelos, or export files remain refusals. A pinned pre-floor target yields
    only a static revision inspection; ordinary callers still select a runtime
    snapshot at the requested grade and retain the support-floor refusal.
    """
    registry_root = _require_directory(context.registry_root, subject="generated registry root")
    source_root = _require_directory(context.source_root, subject="generation source root")
    if registry_root == source_root / "registry" / "aeat":
        raise RegistryValidationError("generated-tree validation requires an isolated un-published registry root")

    modelo_id = str(context.target.modelo)
    revision_id = str(context.target.revision_id)
    modelo_root, _revision_root, export_root = _require_isolated_target_context(
        registry_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
        supporting_modelos=context.supporting_modelos,
        baseline_revisions=(
            tuple(revision_id for revision_id, _digest in context.inheritance.pinned_ancestors)
            if context.inheritance is not None
            else ()
        ),
        source_chain_revisions=context.source_chain_revisions,
    )
    if context.inheritance is not None:
        if context.scope_authority is None:
            raise RegistryValidationError("generated export inheritance requires the complete validated source")
        require_generated_export_inheritance(
            context.inheritance,
            context.scope_authority,
            source_root / "registry" / "aeat",
            modelo=modelo_id,
            revision=revision_id,
        )
    _require_exact_generated_outputs(export_root, rendered.output_files)

    definition = load_modelo_directory(modelo_root)
    if str(definition.id) != modelo_id:
        raise RegistryValidationError(
            f"generated modelo directory loads modelo {definition.id!r}, expected {modelo_id!r}",
        )
    expected_revisions = context.source_chain_revisions or (
        (revision_id,)
        if context.inheritance is None
        else (*tuple(revision_id for revision_id, _digest in context.inheritance.pinned_ancestors), revision_id)
    )
    if tuple(definition.revisions) != expected_revisions:
        raise RegistryValidationError(
            f"isolated generated modelo must load exactly revisions {expected_revisions!r}, "
            f"got {tuple(definition.revisions)!r}",
        )
    if context.source_chain_revisions:
        if context.scope_authority is None:
            raise RegistryValidationError("source-chain validation has no source authority")
        require_source_chain_unchanged(context.scope_authority.modelo(modelo_id), definition, revision=revision_id)
    if context.inheritance is not None and (
        definition.revisions[expected_revisions[-2]].export_layouts != (context.inheritance.baseline_layout,)
    ):
        raise RegistryValidationError("generated export inheritance staged baseline layout changed")
    if context.inheritance is not None:
        source_modelo_root = source_root / "registry" / "aeat" / "modelos" / modelo_id
        for selected_id in expected_revisions:
            original = read_staged_edition(source_modelo_root, selected_id, side="source")
            staged = read_staged_edition(modelo_root, selected_id, side="staged")
            if member_identities(staged) != member_identities(original) or chain_materialisation(
                staged,
            ) != chain_materialisation(original):
                raise RegistryValidationError(
                    f"generated export inheritance changed hydrated {modelo_id}/{selected_id} source facts",
                )
    loaded_revision = definition.revisions[revision_id]
    loaded_layout = _require_exact_generated_layout(
        loaded_revision.export_layouts,
        rendered=rendered,
        revision_id=revision_id,
    )
    provenance = verify_export_fragment_provenance_manifest(
        export_root=export_root,
        joined=joined,
        semantic_map=semantic_map,
        target=context.target,
        loaded_layout=loaded_layout,
        field_derivations=rendered.field_derivations,
        render_profile=render_profile,
        render_profile_source_evidence=render_profile_source_evidence,
        generated_export_inheritance=(context.inheritance.attestation if context.inheritance is not None else None),
    )

    if context.historical_static_source_ref is not None:
        inspection = _validated_historical_static_target(
            context=context,
            registry_root=registry_root,
            source_root=source_root,
            modelo_id=modelo_id,
            revision_id=revision_id,
            target_definition=definition,
            joined=joined,
        )
        return ValidatedHistoricalStaticGeneratedExportTree(
            target=context.target,
            layout=loaded_layout,
            inspection=inspection,
            provenance_manifest=provenance,
        )

    snapshot = _validated_target_snapshot(
        context=context,
        registry_root=registry_root,
        source_root=source_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
        target_definition=definition,
    )
    if str(snapshot.modelo.id) != modelo_id or str(snapshot.revision.id) != revision_id:
        raise RegistryValidationError(
            f"validated authority selected modelo/revision {snapshot.modelo.id!r}/{snapshot.revision.id!r}, "
            f"expected {modelo_id!r}/{revision_id!r}",
        )
    _require_exact_generated_layout(
        snapshot.revision.export_layouts,
        rendered=rendered,
        revision_id=revision_id,
    )
    return ValidatedGeneratedExportTree(
        target=context.target,
        layout=loaded_layout,
        snapshot=snapshot,
        provenance_manifest=provenance,
    )


def _validated_target_snapshot(
    *,
    context: GeneratedExportTreeValidationContext,
    registry_root: Path,
    source_root: Path,
    modelo_id: str,
    revision_id: str,
    target_definition: ModeloDefinition,
) -> RegistrySnapshot:
    """Select fresh target facts with separately supplied registry-wide context.

    The validated source can supply full corpus context for scope checks such
    as semantic-role cardinality. Its target revision is replaced with the
    freshly loaded candidate before validation; snapshot selection always uses
    the candidate. Without that context, normal candidates retain the ordinary
    authority route. A candidate that declares an incoming continuity transition
    can instead carry a separate witness for the predecessor facts that are
    intentionally absent from its target-only tree.  That witness is checked by
    the existing registry-scope validator after replacing *only* its target
    revision with the freshly loaded candidate revision; it cannot validate a
    stale target by copying one into the witness.
    """
    if context.continuity_metadata_modelo_root is None and context.scope_authority is None:
        return _validated_authority_target_snapshot(
            context,
            registry_root=registry_root,
            source_root=source_root,
            modelo_id=modelo_id,
            revision_id=revision_id,
        )
    return _validated_scoped_target_snapshot(
        context,
        registry_root=registry_root,
        source_root=source_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
        target_definition=target_definition,
    )


def _validated_historical_static_target(
    *,
    context: GeneratedExportTreeValidationContext,
    registry_root: Path,
    source_root: Path,
    modelo_id: str,
    revision_id: str,
    target_definition: ModeloDefinition,
    joined: JoinedRecordDesign,
) -> RegistryRevisionInspection:
    """Fully validate an authored pre-floor target without a filing snapshot."""
    authority = context.scope_authority
    source_ref = context.historical_static_source_ref
    if authority is None or source_ref is None:
        raise RegistryValidationError("historical static target requires its complete validated source and source pin")
    loaded_modelos, catalogues = compile_registry_tree(registry_root, source_root)
    _require_loaded_candidate_target(loaded_modelos, modelo_id=modelo_id, target_definition=target_definition)
    scoped_modelos = _scope_modelos_with_candidate(
        context, loaded_modelos, modelo_id=modelo_id, revision_id=revision_id, target_definition=target_definition
    )
    _validate_scoped_candidate(source_root, loaded_modelos, catalogues, scoped_modelos)
    support = catalogues.require_supported_filing_years()
    if support != authority.catalogues.require_supported_filing_years():
        raise RegistryValidationError("historical static target changed the supported filing years catalogue")
    if context.filing_year >= support.floor:
        raise RegistryValidationError("historical static target must be below the unchanged filing support floor")
    scoped_modelo = next(modelo for modelo in scoped_modelos if str(modelo.id) == modelo_id)
    selected = select_authored_revision_metadata(
        ModeloRevisionDirectory.from_modelo(scoped_modelo),
        filing_year=context.filing_year,
        period=context.period,
        on=context.on,
    )
    if str(selected.id) != revision_id:
        raise RegistryValidationError(
            f"historical static target selected authored revision {selected.id!r}, expected {revision_id!r}"
        )
    selected_source_ref, epoch = _select_record_design_source(
        target_definition.revisions[revision_id],
        catalogues.sources,
        modelo=modelo_id,
        revision=revision_id,
        filing_year=context.filing_year,
        period=context.period,
        source_ref=None,
    )
    if (
        selected_source_ref != source_ref
        or joined.source.source_ref != source_ref
        or epoch != context.target.design_epoch
    ):
        raise RegistryValidationError("historical static target source differs from the exact selected official design")
    source = catalogues.sources.get(source_ref)
    if source is None or joined.source.source_sha256 != source.sha256:
        raise RegistryValidationError("historical static target source digest differs from the candidate catalogue")
    return RegistryRevisionInspection.from_revision(
        modelo=scoped_modelo,
        revision=target_definition.revisions[revision_id],
        source_root=source_root,
        sources=catalogues.sources,
        legal_ref_ids=frozenset(catalogues.legal),
    )


def _validated_authority_target_snapshot(
    context: GeneratedExportTreeValidationContext,
    *,
    registry_root: Path,
    source_root: Path,
    modelo_id: str,
    revision_id: str,
) -> RegistrySnapshot:
    identity = resolve_registry_identity(
        registry_root,
        collect_fingerprints=collect_registry_tree_fingerprints,
    )
    authority = compile_validated_authority(registry_root, source_root, identity=identity)
    return authority.snapshot(
        modelo_id,
        filing_year=context.filing_year,
        period=context.period,
        on=context.on,
        revision_id=revision_id,
        grade=context.required_grade,
    )


def _validated_scoped_target_snapshot(
    context: GeneratedExportTreeValidationContext,
    *,
    registry_root: Path,
    source_root: Path,
    modelo_id: str,
    revision_id: str,
    target_definition: ModeloDefinition,
) -> RegistrySnapshot:
    loaded_modelos, catalogues = compile_registry_tree(registry_root, source_root)
    _require_loaded_candidate_target(loaded_modelos, modelo_id=modelo_id, target_definition=target_definition)
    scoped_modelos = _scope_modelos_with_candidate(
        context,
        loaded_modelos,
        modelo_id=modelo_id,
        revision_id=revision_id,
        target_definition=target_definition,
    )
    _validate_scoped_candidate(source_root, loaded_modelos, catalogues, scoped_modelos)
    # ``build_snapshot`` owns the same model-local validation and requested-grade
    # selection the production authority delegates to after registry scope passes.
    return build_snapshot(
        target_definition,
        catalogues,
        source_root=source_root,
        filing_year=context.filing_year,
        period=context.period,
        on=context.on,
        revision_id=revision_id,
        grade=context.required_grade,
    )


def _require_loaded_candidate_target(
    loaded_modelos: tuple[ModeloDefinition, ...],
    *,
    modelo_id: str,
    target_definition: ModeloDefinition,
) -> None:
    loaded_target = next((modelo for modelo in loaded_modelos if str(modelo.id) == modelo_id), None)
    if loaded_target is None:
        raise RegistryValidationError(f"generated target modelo {modelo_id!r} is absent from the isolated registry")
    if loaded_target != target_definition:
        raise RegistryValidationError("generated target loader result changed before continuity validation")


def _scope_modelos_with_candidate(
    context: GeneratedExportTreeValidationContext,
    loaded_modelos: tuple[ModeloDefinition, ...],
    *,
    modelo_id: str,
    revision_id: str,
    target_definition: ModeloDefinition,
) -> tuple[ModeloDefinition, ...]:
    if context.scope_authority is not None:
        return _candidate_scope_modelos(
            context.scope_authority,
            loaded_modelos,
            modelo_id=modelo_id,
            revision_id=revision_id,
        )
    if context.continuity_metadata_modelo_root is None:
        raise RegistryValidationError("generated scope validation requires its declared source witness")
    continuity_modelo = _load_continuity_metadata_modelo(
        context.continuity_metadata_modelo_root,
        modelo_id=modelo_id,
        revision_id=revision_id,
    )
    witness = continuity_modelo.model_copy(
        update={"revisions": {**continuity_modelo.revisions, revision_id: target_definition.revisions[revision_id]}},
    )
    return tuple(witness if str(modelo.id) == modelo_id else modelo for modelo in loaded_modelos)


def _validate_scoped_candidate(
    source_root: Path,
    loaded_modelos: tuple[ModeloDefinition, ...],
    catalogues: RegistryCatalogues,
    scoped_modelos: tuple[ModeloDefinition, ...],
) -> None:
    # Binding validators and snapshot selection resolve governed vocabulary. They
    # must read the candidate's own compiled facts, exactly as the full authority
    # compile does, never whatever authority happens to be ambient.
    with validating_governed_facts(
        CandidateFactAuthority(catalogues.facts, catalogues.require_supported_filing_years())
    ):
        # The witness replaces only the registry-wide scope. Every loaded modelo
        # and the compiled catalogues still pass the checks a full authority
        # compile applies, so an absent governed fact is refused on this route too.
        from ..compiler.validator import RegistryValidator

        validator = RegistryValidator(
            catalogues,
            source_root=source_root,
            user_profile_schema=capture_profile_schema_source(
                source_root / "registry" / "cadrumo" / "user_profile" / "schema.toml"
            ).schema,
        )
        for loaded_modelo in loaded_modelos:
            validator.validate_modelo(loaded_modelo)
        scope_failures = validate_registry_scope(scoped_modelos)
        if scope_failures:
            raise RegistryValidationError(
                "registry validation failed:\n" + "\n".join(f" - {failure}" for failure in scope_failures)
            )


def _candidate_scope_modelos(
    authority: ValidatedRegistryAuthority,
    loaded_modelos: tuple[ModeloDefinition, ...],
    *,
    modelo_id: str,
    revision_id: str,
) -> tuple[ModeloDefinition, ...]:
    """Replace only the candidate revision within the complete validated scope."""
    source_by_id = {str(modelo.id): modelo for modelo in authority.modelos}
    candidate_by_id = {str(modelo.id): modelo for modelo in loaded_modelos}
    if not candidate_by_id.keys() <= source_by_id.keys():
        raise RegistryValidationError("generated candidate contains modelos absent from its validated source scope")
    source_target = source_by_id[modelo_id]
    candidate_target = candidate_by_id[modelo_id]
    _require_candidate_revision_in_source_scope(source_target, revision_id)
    _require_candidate_target_metadata(source_target, candidate_target)
    _require_supporting_modelos_unchanged(source_by_id, candidate_by_id, modelo_id=modelo_id)
    witness = source_target.model_copy(
        update={"revisions": {**source_target.revisions, revision_id: candidate_target.revisions[revision_id]}},
    )
    return tuple(witness if str(modelo.id) == modelo_id else modelo for modelo in authority.modelos)


def _require_candidate_revision_in_source_scope(source_target: ModeloDefinition, revision_id: str) -> None:
    if revision_id not in source_target.revisions:
        raise RegistryValidationError("generated revision is absent from its validated source scope")


def _require_candidate_target_metadata(source_target: ModeloDefinition, candidate_target: ModeloDefinition) -> None:
    if source_target.model_copy(update={"revisions": candidate_target.revisions}) != candidate_target:
        raise RegistryValidationError("generated candidate changed modelo metadata outside its target revision")


def _require_supporting_modelos_unchanged(
    source_by_id: dict[str, ModeloDefinition],
    candidate_by_id: dict[str, ModeloDefinition],
    *,
    modelo_id: str,
) -> None:
    for candidate_id, candidate in candidate_by_id.items():
        if candidate_id != modelo_id and candidate != source_by_id[candidate_id]:
            raise RegistryValidationError(
                "generated candidate changed supporting modelo facts from its validated scope"
            )


def _load_continuity_metadata_modelo(
    metadata_root: Path,
    *,
    modelo_id: str,
    revision_id: str,
) -> ModeloDefinition:
    """Load source-copied predecessor facts without admitting another target."""
    resolved = _require_directory(metadata_root, subject="generated continuity metadata modelo root")
    modelo = load_modelo_directory(resolved)
    if str(modelo.id) != modelo_id:
        raise RegistryValidationError(
            f"generated continuity metadata loads modelo {modelo.id!r}, expected {modelo_id!r}",
        )
    if revision_id in modelo.revisions:
        raise RegistryValidationError(
            f"generated continuity metadata must not contain target revision {revision_id!r}",
        )
    if not modelo.revisions:
        raise RegistryValidationError("generated continuity metadata declares no sibling revisions")
    return modelo


def _require_isolated_target_context(
    registry_root: Path,
    *,
    modelo_id: str,
    revision_id: str,
    supporting_modelos: frozenset[str] = frozenset(),
    baseline_revisions: tuple[str, ...] = (),
    source_chain_revisions: tuple[str, ...] = (),
) -> tuple[Path, Path, Path]:
    modelos_root = _require_directory(registry_root / "modelos", subject="generated registry modelos root")
    modelo_root = modelos_root / modelo_id
    _require_exact_children(
        modelos_root,
        expected={modelo_id, *supporting_modelos},
        subject="generated registry modelos root",
    )
    _require_directory(modelo_root, subject="generated modelo directory")
    _require_exact_children(
        modelo_root,
        expected={"manifest.toml", "revisions"},
        subject="generated modelo directory",
    )

    revisions_root = _require_directory(modelo_root / "revisions", subject="generated modelo revisions directory")
    revision_root = revisions_root / revision_id
    _require_exact_children(
        revisions_root,
        expected=set(source_chain_revisions) if source_chain_revisions else {revision_id, *baseline_revisions},
        subject="generated modelo revisions directory",
    )
    if len(set((*baseline_revisions, revision_id))) != len(baseline_revisions) + 1:
        raise RegistryValidationError("generated export inheritance repeats a target or ancestor revision")
    for baseline_revision in baseline_revisions:
        baseline_root = _require_directory(
            revisions_root / baseline_revision, subject="generated export inheritance baseline revision"
        )
        require_existing_non_link(baseline_root / "export", subject="generated export inheritance baseline target")
    _require_directory(revision_root, subject="generated target revision directory")
    for name in ("revision.toml", "export"):
        require_existing_non_link(revision_root / name, subject=f"generated target revision member {name!r}")
    stale_sibling_manifest = revision_root / "export.provenance.json"
    if stale_sibling_manifest.exists() or is_link_like(stale_sibling_manifest):
        raise RegistryValidationError(
            f"generated target revision refuses stale sibling export provenance manifest: {stale_sibling_manifest}",
        )
    export_root = _require_directory(revision_root / "export", subject="generated export directory")
    require_existing_non_link(
        export_root / EXPORT_FRAGMENT_PROVENANCE_FILENAME,
        subject="generated export provenance manifest",
    )
    return modelo_root, revision_root, export_root


def _require_exact_children(directory: Path, *, expected: set[str], subject: str) -> None:
    actual = {child.name for child in _children_without_links(directory, subject=subject)}
    if actual != expected:
        raise RegistryValidationError(
            f"{subject} must contain exactly {sorted(expected)!r}, got {sorted(actual)!r}",
        )


def _require_exact_generated_outputs(export_root: Path, output_files: tuple[str, ...]) -> None:
    expected_files = {_normalise_output_path(path) for path in output_files}
    if not expected_files:
        raise RegistryValidationError("generated render result declares no output files")
    actual_files, actual_directories = _collect_regular_tree_members(export_root)
    expected_directories = _expected_generated_directories(expected_files)
    _require_generated_tree_matches(expected_files, actual_files, actual_directories, expected_directories)


def _expected_generated_directories(expected_files: set[PurePosixPath]) -> set[str]:
    return {parent.as_posix() for path in expected_files for parent in path.parents if parent != PurePosixPath(".")}


def _require_generated_tree_matches(
    expected_files: set[PurePosixPath],
    actual_files: set[PurePosixPath],
    actual_directories: set[str],
    expected_directories: set[str],
) -> None:
    manifest_path = PurePosixPath(EXPORT_FRAGMENT_PROVENANCE_FILENAME)
    actual_toml_files = actual_files - {manifest_path}
    if (
        actual_toml_files != expected_files
        or manifest_path not in actual_files
        or actual_directories != expected_directories
    ):
        raise RegistryValidationError(
            "generated export directory must contain exactly the current rendered outputs; "
            f"expected_files={sorted(path.as_posix() for path in expected_files)!r}, "
            f"actual_files={sorted(path.as_posix() for path in actual_toml_files)!r}, "
            f"expected_directories={sorted(expected_directories)!r}, "
            f"actual_directories={sorted(actual_directories)!r}",
        )


def _require_exact_generated_layout(
    layouts: tuple[ExportLayoutDefinition, ...],
    *,
    rendered: RenderedExportTree,
    revision_id: str,
) -> ExportLayoutDefinition:
    if layouts != (rendered.layout,):
        raise RegistryValidationError(
            f"generated revision {revision_id!r} loader semantics do not equal the current rendered layout",
        )
    return layouts[0]


def _normalise_output_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RegistryValidationError(f"generated render result declares unsafe output path {value!r}")
    if path.suffix != ".toml":
        raise RegistryValidationError(f"generated render result declares non-TOML output path {value!r}")
    return path


def _collect_regular_tree_members(root: Path) -> tuple[set[PurePosixPath], set[str]]:
    files: set[PurePosixPath] = set()
    directories: set[str] = set()

    def visit(directory: Path) -> None:
        for child in _children_without_links(directory, subject="generated export directory"):
            relative = PurePosixPath(*child.relative_to(root).parts)
            if child.is_dir():
                directories.add(relative.as_posix())
                visit(child)
            elif child.is_file():
                files.add(relative)
            else:
                raise RegistryValidationError(f"generated export directory contains non-regular member {child}")

    visit(root)
    return files, directories


def _require_directory(path: Path, *, subject: str) -> Path:
    require_existing_non_link(path, subject=subject)
    if not path.is_dir():
        raise RegistryValidationError(f"{subject} is not a directory: {path}")
    return path.resolve()


def _children_without_links(directory: Path, *, subject: str) -> tuple[Path, ...]:
    # require_root: an unreadable directory yielding empty would pass the
    # link check below without inspecting anything, which is the failure this
    # helper exists to prevent. ``Path.iterdir`` raised here before the move
    # onto the shared scanner; this keeps that.
    children = tuple(sorted(iter_directory(directory, require_root=True), key=lambda path: path.name))
    for child in children:
        if is_link_like(child):
            raise RegistryValidationError(f"{subject} contains a linked member: {child}")
    return children
