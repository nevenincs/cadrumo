"""Operator check, publication, and digest-bound republication for one generated tree.

This privileged development CLI intentionally has no product-CLI registration.
It assembles one explicitly selected revision from the validated registry, then
delegates all rendering, validation, comparison, and transactional cutover to
the generator pipeline's canonical authorities. ``publish-authority`` validates
the whole registry candidate and republishes the runtime authority artifact.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Annotated, Literal, cast

import typer

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.i18n.render import locale_map, override_locales_root
from cadrumo.core.locks_errors import LockAcquisitionError
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryError, RegistryValidationError
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)

from ..compiler.authority import compile_validated_authority, compiled_bundled_authority
from ..compiler.edition_materialisation import MaterialisedEdition, materialise_edition
from ._export_tree import render_complete_export_tree
from ._form_layout_companion import prepare_generated_form_layout_companion
from ._tree_check import CheckedGeneratedExportTree, GeneratedExportTreeCheckContext, check_generated_export_tree
from ._tree_publication import publish_validated_generated_export_tree
from ._tree_validation import GeneratedExportTreeValidationContext, validate_generated_export_tree
from .authored_form_bridge import AuthoredFormBridge, prepare_authored_form_bridge
from .authority_publication import (
    authority_database_currency,
    authority_publication_destination,
    publish_sqlite_authority_candidate,
)
from .bootstrap_supersession import (
    bootstrap_layout_supersession_fingerprint,
    bootstrap_manual_source_revision_root,
    validate_bootstrap_manual_export_layout_supersession,
)
from .bootstrap_targets import GeneratedExportBootstrapTarget, generated_export_bootstrap_target
from .candidate_source_chain import requires_source_chain, stage_source_chain
from .candidate_staging import stage_attested_inherited_modelo, stage_generated_export_candidate
from .edition_candidate_staging import (
    drop_cross_edition_evolutions,
    edition_requires_detachment,
    write_complete_edition,
)
from .export_fragment_provenance import SHA256_PATTERN, ExportFragmentTarget
from .export_tree_models import RenderedExportTree
from .generated_export_inheritance import select_generated_export_inheritance
from .generated_export_inheritance_model import GeneratedExportInheritanceContext
from .generated_form_bridge import (
    GeneratedFormBridge,
    generated_form_companion_changed,
    prepare_generated_form_bridge,
)
from .generated_tree_dispositions import GeneratedTreeRecordDriftDisposition, record_drift_dispositions
from .historical_static_repair import validated_historical_repair_source
from .legacy_publication_recovery import retire_completed_legacy_publication
from .render_check import (
    GeneratedExportBootstrapTransport,
    RenderComparison,
    RevisionRenderInputs,
    compare_export_tree_roots,
    revision_render_inputs,
    select_revision_record_design_source,
)
from .source_defects import source_defects_for
from .tree_publication_contracts import (
    GeneratedExportSupersession,
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
)
from .tree_publication_supersession_recovery import recover_interrupted_supersession_bundle

app = typer.Typer(
    name="pipeline",
    help=(
        "Check, publish, or digest-bound republish one generated AEAT registry export tree, "
        "or republish the runtime authority artifact."
    ),
    no_args_is_help=True,
)

_SOURCE_MODELO_RE = re.compile(r'^\s*source_modelo\s*=\s*"(?P<modelo>[^"]+)"', re.MULTILINE)


@app.command("publish-authority")
def publish_authority(
    registry_root: Annotated[
        Path | None,
        typer.Option("--registry-root", help="Registry tree to publish; defaults to the bundled registry."),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option("--source-root", help="Source tree holding the legal corpus; defaults to bundled data."),
    ] = None,
    destination: Annotated[
        Path | None,
        typer.Option(
            "--destination",
            help="Authority directory to update; defaults to the configured authority root.",
        ),
    ] = None,
    profile_schema: Annotated[
        Path | None,
        typer.Option(
            "--profile-schema",
            help="Profile declaration captured with the candidate; required for custom source sets.",
        ),
    ] = None,
    eager_baseline: Annotated[
        Path | None,
        typer.Option(
            "--eager-baseline",
            help="Write the development benchmark baseline from the same validated artifact.",
        ),
    ] = None,
    if_stale: Annotated[
        bool,
        typer.Option(
            "--if-stale",
            help="Publish only when the existing artifact no longer records the live sources.",
        ),
    ] = False,
) -> None:
    """Validate the registry candidate and atomically republish the runtime authority artifact.

    A refused validation, or a candidate that changes while it is validated,
    leaves the previous artifact byte-for-byte in place.

    ``--if-stale`` asks the currency reader first and returns without
    publishing when the recorded generation still matches a fresh receipt over
    the same trees. That question is a content read with no compilation, so it
    costs seconds against a publication's minutes, and it makes repeated
    invocation cheap enough for a lifecycle step to run unconditionally. The
    recorded identity names the legal sources only, so a compiler change
    reaches the artifact through a publication without ``--if-stale``.
    """
    if profile_schema is None and (registry_root is not None or source_root is not None):
        raise typer.BadParameter(
            "custom authority candidates require an explicit --profile-schema source",
            param_hint="--profile-schema",
        )
    destination_path = destination or authority_publication_destination()
    resolved_registry_root = registry_root or bundled_path("registry", "aeat")
    resolved_source_root = source_root or bundled_path()
    resolved_profile_schema = profile_schema or bundled_path("registry", "cadrumo", "user_profile", "schema.toml")
    if if_stale:
        currency = authority_database_currency(
            destination_path / "authority.current.json",
            registry_root=resolved_registry_root,
            source_root=resolved_source_root,
            profile_schema_path=resolved_profile_schema,
        )
        if currency.is_current:
            typer.echo(
                "publish-authority"
                f"	descriptor={currency.descriptor_path}"
                f"	identity_digest={currency.recorded_identity_digest}"
                "	published=skipped-current",
            )
            return
    descriptor = publish_sqlite_authority_candidate(
        registry_root=resolved_registry_root,
        source_root=resolved_source_root,
        destination=destination_path,
        profile_schema_path=resolved_profile_schema,
        eager_baseline_path=eager_baseline,
    )
    typer.echo(
        "publish-authority"
        f"\tdescriptor={destination_path / 'authority.current.json'}"
        f"\tidentity_digest={descriptor.logical_generation}"
        f"\tdatabase={descriptor.database}",
    )
    # Named recipes, not prose: an operator is expected to run these verbatim.
    # Target publication stays explicit and per-target because the guidance for a
    # drifted target is to investigate the record bytes rather than republish, so
    # there is deliberately no publish-every-stale-target verb to point at.
    typer.echo("next\tcurrentness=check-registry\tpublication=registry-publish-target")


@dataclass(frozen=True, slots=True)
class GeneratedTreeInvocation:
    """One explicit generated-tree lifecycle request: target, source, filing context and reviewed digest."""

    modelo: str
    revision: str
    source_ref: str
    filing_year: int
    period: str
    expected_manifest_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedGeneratedTreeInvocation:
    """A request with its staged candidate registry, derived render inputs and live target roots."""

    invocation: GeneratedTreeInvocation
    inputs: RevisionRenderInputs
    validation: GeneratedExportTreeValidationContext
    candidate_root: Path
    target_root: Path
    target_export_root: Path
    published_modelo_root: Path | None
    supersession: GeneratedExportSupersession | None = None
    inheritance: GeneratedExportInheritanceContext | None = None


def reviewed_bootstrap_target(
    invocation: GeneratedTreeInvocation, *, source_sha256: str
) -> GeneratedExportBootstrapTarget:
    """Load the reviewed bootstrap authority for one explicitly owed tree."""
    target = generated_export_bootstrap_target(
        modelo=invocation.modelo,
        revision=invocation.revision,
        source_ref=invocation.source_ref,
        source_sha256=source_sha256,
    )
    if target is None:
        raise ValueError(
            "no reviewed generated-export bootstrap target matches "
            f"{invocation.modelo}/{invocation.revision}/{invocation.source_ref}; publication is refused",
        )
    return target


def prepare_generated_tree_invocation(
    invocation: GeneratedTreeInvocation,
    root: Path,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> PreparedGeneratedTreeInvocation:
    """Stage one narrow candidate and derive its render inputs from authority."""
    target_root = bundled_path("registry", "aeat")
    if authority is None:
        recover_interrupted_supersession_bundle(
            target_root=target_root,
            modelo=invocation.modelo,
            revision=invocation.revision,
        )
        try:
            authority = compiled_bundled_authority()
        except RegistryValidationError:
            # The exact reviewed historical target may itself be the one stale
            # export preventing whole-source compilation. Its structural render
            # is admitted only after a one-target whole-registry overlay passes
            # complete validation; every other compile refusal remains closed.
            authority = validated_historical_repair_source(
                modelo=invocation.modelo,
                revision=invocation.revision,
                source_ref=invocation.source_ref,
                filing_year=invocation.filing_year,
                period=invocation.period,
                expected_manifest_sha256=invocation.expected_manifest_sha256,
            )
    target_export_root = target_root / "modelos" / invocation.modelo / "revisions" / invocation.revision / "export"
    source = next(
        (item for ref, item in authority.catalogues.sources.items() if str(ref) == invocation.source_ref),
        None,
    )
    bootstrap = None
    bootstrap_target: GeneratedExportBootstrapTarget | None = None
    supersession: GeneratedExportSupersession | None = None
    if not target_export_root.exists():
        if source is None:
            raise ValueError(f"no source {invocation.source_ref!r} exists for bootstrap target selection")
        bootstrap_target = reviewed_bootstrap_target(invocation, source_sha256=source.sha256)
        if bootstrap_target.supersedes_layout_id is not None:
            source_modelo_root = target_root / "modelos" / invocation.modelo
            source_state_sha256 = validate_bootstrap_manual_export_layout_supersession(
                source_modelo_root,
                revision=invocation.revision,
                superseded_layout_id=bootstrap_target.supersedes_layout_id,
                expected_references=bootstrap_target.superseded_construct_references,
                generated_layout_id=bootstrap_target.layout_id,
                source_ref=bootstrap_target.source_ref,
                source_sha256=bootstrap_target.source_sha256,
                manual_origin_revision=bootstrap_target.manual_origin_revision,
            )
            manual_source_root, _ = bootstrap_manual_source_revision_root(
                source_modelo_root,
                authority.modelo(invocation.modelo),
                revision=invocation.revision,
                expected_origin_revision=bootstrap_target.manual_origin_revision,
            )
            supersession = GeneratedExportSupersession(
                superseded_layout_id=bootstrap_target.supersedes_layout_id,
                generated_layout_id=bootstrap_target.layout_id,
                expected_construct_references=bootstrap_target.superseded_construct_references,
                source_state_sha256=source_state_sha256,
                source_ref=bootstrap_target.source_ref,
                source_sha256=bootstrap_target.source_sha256,
                manual_source_sha256=bootstrap_layout_supersession_fingerprint(manual_source_root),
                manual_origin_revision=bootstrap_target.manual_origin_revision,
            )
        bootstrap = GeneratedExportBootstrapTransport(
            layout_id=bootstrap_target.layout_id,
            line_ending=bootstrap_target.line_ending,
            source_ref=bootstrap_target.source_ref,
            source_sha256=bootstrap_target.source_sha256,
            supersedes_layout_id=bootstrap_target.supersedes_layout_id,
        )
    try:
        inputs = revision_render_inputs(
            authority,
            modelo=invocation.modelo,
            revision=invocation.revision,
            source_ref=invocation.source_ref,
            bootstrap_transport=bootstrap,
            filing_year=invocation.filing_year,
            period=invocation.period,
        )
    except (RegistryError, ValueError) as error:
        raise ValueError(str(error)) from error

    candidate_root = root / "candidate" / "registry" / "aeat"
    inheritance = select_generated_export_inheritance(
        authority,
        target_root,
        modelo=invocation.modelo,
        revision=invocation.revision,
    )
    source_modelo = authority.modelo(invocation.modelo)
    retain_source_chain = inheritance is None and requires_source_chain(source_modelo.revisions[invocation.revision])
    stage_generated_export_candidate(
        target_root,
        candidate_root,
        modelo=invocation.modelo,
        revision=invocation.revision,
        supporting_modelos=supporting_modelos(invocation.modelo),
        bootstrap_target=bootstrap_target,
        inheritance=inheritance,
        retain_source_chain=retain_source_chain,
    )
    validation = GeneratedExportTreeValidationContext(
        registry_root=candidate_root,
        source_root=bundled_path(),
        target=ExportFragmentTarget(
            modelo=invocation.modelo,
            revision_id=invocation.revision,
            design_epoch=inputs.transport_profile.design_epoch,
        ),
        filing_year=invocation.filing_year,
        period=invocation.period,
        required_grade=authority.modelo(invocation.modelo).revisions[invocation.revision].effective_authority_grade,
        scope_authority=authority,
        source_chain_revisions=tuple(source_modelo.revisions) if retain_source_chain else (),
        supporting_modelos=supporting_modelos(invocation.modelo),
        # The complete validated source above already supplies continuity scope.
        # A second, detached sibling witness is unused by that validation path
        # and cannot represent edge-specific references without losing them.
        inheritance=inheritance,
        historical_static_source_ref=(
            inputs.transport_profile.source_ref
            if invocation.filing_year < authority.catalogues.require_supported_filing_years().floor
            else None
        ),
    )
    return PreparedGeneratedTreeInvocation(
        invocation=invocation,
        inputs=inputs,
        validation=validation,
        candidate_root=candidate_root,
        target_root=target_root,
        target_export_root=target_export_root,
        published_modelo_root=stage_published_modelo(
            root,
            modelo=invocation.modelo,
            revision=invocation.revision,
            inheritance=inheritance,
            retain_source_chain=retain_source_chain,
        ),
        supersession=supersession,
        inheritance=inheritance,
    )


@cache
def supporting_modelos(modelo: str) -> frozenset[str]:
    """Return declared cross-modelo dependencies that isolated validation needs."""
    modelos_root = bundled_path("registry", "aeat", "modelos")
    source_modelo_root = modelos_root / modelo
    referenced = {
        str(match.group("modelo"))
        for path in source_modelo_root.rglob("*.toml")
        for match in _SOURCE_MODELO_RE.finditer(path.read_text(encoding="utf-8"))
    }
    return frozenset(item for item in referenced - {modelo} if (modelos_root / item).is_dir())


def stage_published_modelo(
    root: Path,
    *,
    modelo: str,
    revision: str,
    inheritance: GeneratedExportInheritanceContext | None = None,
    retain_source_chain: bool = False,
) -> Path | None:
    """Stage a one-revision published modelo only when check needs the witness.

    The witness is staged in registry shape with the published authored facts
    and shared legal catalogues beside it, because loading a modelo validates
    its bindings against the governed facts and filing-year envelope of the
    registry that holds it and refuses without them.
    """
    source_registry_root = bundled_path("registry", "aeat")
    source_modelo_root = source_registry_root / "modelos" / modelo
    revisions = tuple((source_modelo_root / "revisions").iterdir())
    if len(revisions) == 1:
        return None
    staged_registry_root = root / "published-registry" / "aeat"
    shutil.copytree(source_registry_root / "facts", staged_registry_root / "facts")
    shutil.copytree(source_registry_root / "legal", staged_registry_root / "legal")
    if retain_source_chain:
        return stage_source_chain(
            source_modelo_root,
            staged_registry_root / "modelos" / modelo,
            revision=revision,
            include_target_export=True,
        )
    if inheritance is not None:
        return stage_attested_inherited_modelo(
            source_modelo_root,
            staged_registry_root / "modelos" / modelo,
            revision=revision,
            inheritance=inheritance,
            include_target_export=True,
        )
    staged = stage_isolated_edition(
        source_modelo_root,
        staged_registry_root / "modelos" / modelo,
        revision=revision,
        source_locales_root=bundled_path().parent / "locales",
        staged_locales_root=root / "published-locales",
    )
    return staged.modelo_root


@dataclass(frozen=True, slots=True)
class _StagedEdition:
    """An isolated edition and the catalogue its casilla labels resolve from."""

    modelo_root: Path
    locales_root: Path


def stage_isolated_edition(
    source_modelo_root: Path,
    staged_root: Path,
    *,
    revision: str,
    source_locales_root: Path,
    staged_locales_root: Path,
) -> _StagedEdition:
    """Stage ``revision`` as the only edition of a copy of its modelo, complete by construction.

    Pruning the sibling editions is what isolates the target, and it is exactly
    what an edition inheriting from a predecessor cannot survive: its chain
    would be deleted with them. Such an edition is therefore resolved first and
    written back as the full-copy edition it stands for, naming no predecessor,
    so the staged tree never presents the rows it states as the whole edition.
    An edition whose named predecessor is absent from the source is refused by
    that resolution rather than staged thin. An edition stating every row is
    copied unchanged and keeps resolving its labels from the source catalogue.

    The labels travel with the rows. Casilla labels are catalogued per edition,
    so an inherited row's text lives under the key of the edition that last
    stated it, and a full copy names no predecessor through which to reach it.
    The staged catalogue is a copy of the source catalogue in which each
    inherited row's own occurrence key carries its origin's text, in each
    locale where the row has no text of its own, so every staged label resolves
    to exactly what the live edition resolves.
    """
    from dev.locales.locale_yaml import discover_locale_codes
    from dev.locales.manager import LocaleManager

    edition = materialise_edition(source_modelo_root, revision)
    shutil.copytree(source_modelo_root, staged_root)
    revisions_root = staged_root / "revisions"
    for entry in revisions_root.iterdir():
        if entry.name != revision:
            shutil.rmtree(entry)
    if not edition_requires_detachment(edition):
        drop_cross_edition_evolutions(revisions_root / revision)
        return _StagedEdition(modelo_root=staged_root, locales_root=source_locales_root)
    write_complete_edition(revisions_root / revision, edition)
    drop_cross_edition_evolutions(revisions_root / revision)
    if edition.inherits_from is None:
        # A storage-baseline edition restates rows under its own keys; only a
        # predecessor chain moves label text onto inherited occurrences.
        return _StagedEdition(modelo_root=staged_root, locales_root=source_locales_root)
    shutil.copytree(source_locales_root, staged_locales_root)
    manager = LocaleManager(src_dir=staged_locales_root, locales_dir=staged_locales_root)
    for locale in sorted(discover_locale_codes(staged_locales_root)):
        carried = _inherited_labels(edition, source_locales_root, locale=locale)
        if carried:
            manager.set_locale_values(locale, carried)
    return _StagedEdition(modelo_root=staged_root, locales_root=staged_locales_root)


def _inherited_labels(edition: MaterialisedEdition, source_locales_root: Path, *, locale: str) -> dict[str, str | None]:
    """Return the origin text each inherited row needs under its own occurrence key in ``locale``."""
    rows = edition.table.get("casillas")
    origins = edition.label_origins
    if origins is None or not isinstance(rows, tuple) or len(cast(tuple[object, ...], rows)) != len(origins):
        raise ValueError(
            f"edition {edition.revision_id!r} of modelo {edition.modelo_id!r} carries no label origin per casilla",
        )
    with override_locales_root(source_locales_root):
        catalogue = locale_map(locale)
    carried: dict[str, str | None] = {}
    for row, origin in zip(cast(tuple[object, ...], rows), origins, strict=True):
        casilla_id = cast(Mapping[str, object], row).get("id") if isinstance(row, Mapping) else None
        if origin is None or not isinstance(casilla_id, str):
            continue
        own_key = casilla_occurrence_locale_key(
            edition.modelo_id, edition.revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL
        )
        origin_key = casilla_occurrence_locale_key(
            edition.modelo_id, origin, casilla_id, ModeloLocalizationFieldKind.LABEL
        )
        origin_text = _authored_text(catalogue, origin_key)
        if origin_text is not None and _authored_text(catalogue, own_key) is None:
            carried[own_key] = origin_text
    return carried


def _authored_text(catalogue: Mapping[str, str | None], key: str) -> str | None:
    """Apply the catalogue's miss rule: an absent key, a null and a key echo all carry no text."""
    value = catalogue.get(key)
    return None if value is None or value == key else value


def _render_candidate(prepared: PreparedGeneratedTreeInvocation) -> RenderedExportTree:
    """Render one candidate export tree into the staged revision."""
    candidate_export_root = (
        prepared.candidate_root
        / "modelos"
        / prepared.invocation.modelo
        / "revisions"
        / prepared.invocation.revision
        / "export"
    )
    rendered = render_complete_export_tree(
        candidate_export_root,
        revision_id=prepared.inputs.revision_id,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        transport_profile=prepared.inputs.transport_profile,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        source_defects=source_defects_for(prepared.invocation.source_ref),
        inheritance=prepared.inheritance,
    )
    prepare_generated_form_layout_companion(prepared.validation, temporary_root=prepared.candidate_root.parents[2])
    return rendered


def check_prepared_invocation(
    prepared: PreparedGeneratedTreeInvocation,
) -> tuple[Literal["matched", "publishable_absence"], RenderedExportTree, GeneratedExportTreeTargetStateReceipt]:
    """Drive the canonical checker, or validate a fresh candidate for an owed tree.

    An absent tree has no bytes to compare and therefore cannot be called a
    match.  It is nevertheless publishable when the real generator can render
    it and the real validator accepts that candidate.  This narrow bootstrap
    case keeps an owed tree from deadlocking the publisher while preserving the
    same pre-cutover validation boundary publication uses.
    """
    target_state = GeneratedExportTreeTargetStateReceipt.observe(
        prepared.target_export_root,
        supersession_source_sha256=(
            None if prepared.supersession is None else prepared.supersession.source_state_sha256
        ),
    )
    if not prepared.target_export_root.exists():
        rendered = _render_candidate(prepared)
        validate_generated_export_tree(
            context=prepared.validation,
            joined=prepared.inputs.joined,
            semantic_map=prepared.inputs.semantic_map,
            rendered=rendered,
            render_profile=prepared.inputs.render_profile,
            render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        )
        return "publishable_absence", rendered, target_state
    checked: CheckedGeneratedExportTree = check_generated_export_tree(
        context=GeneratedExportTreeCheckContext(
            validation=prepared.validation,
            temporary_root=prepared.candidate_root.parents[2],
            target_registry_root=prepared.target_root,
            target_export_root=prepared.target_export_root,
            published_modelo_root=prepared.published_modelo_root,
        ),
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        transport_profile=prepared.inputs.transport_profile,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        source_defects=source_defects_for(prepared.invocation.source_ref),
    )
    return "matched", checked.rendered, target_state


def publish_prepared_invocation(
    prepared: PreparedGeneratedTreeInvocation,
    rendered: RenderedExportTree,
    target_state: GeneratedExportTreeTargetStateReceipt,
    *,
    generated_form_bridge: GeneratedFormBridge | AuthoredFormBridge | None = None,
) -> None:
    """Publish the exact prepared candidate the read-only check just validated."""
    publish_validated_generated_export_tree(
        context=GeneratedExportTreePublicationContext(
            validation=prepared.validation,
            temporary_root=prepared.candidate_root.parents[2],
            target_root=prepared.target_root,
            target_export_root=prepared.target_export_root,
            expected_target_state=target_state,
            supersession=prepared.supersession,
            final_live_validator=(
                (lambda: generated_form_bridge.require_export_cutover(prepared.target_root))
                if generated_form_bridge is not None
                else (lambda: _validate_final_live_target(prepared))
            ),
        ),
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )


def _validate_final_live_target(prepared: PreparedGeneratedTreeInvocation) -> None:
    """Compile the complete live registry and prove the named export is current before commit."""
    authority = compile_validated_authority(
        prepared.target_root,
        bundled_path(),
        verify_evidence_bytes=True,
        complete_validation=True,
    )
    fact = target_currentness(
        prepared.invocation.modelo,
        prepared.invocation.revision,
        prepared.invocation.source_ref,
        prepared.invocation.filing_year,
        prepared.invocation.period,
        authority=authority,
    )
    if fact.state is not TargetCurrentnessState.CURRENT:
        raise RegistryValidationError(
            "generated target failed live-root currentness after cutover: "
            f"state={fact.state.value}; detail={fact.detail}",
        )


def require_republication_eligibility(
    invocation: GeneratedTreeInvocation,
    target_state: GeneratedExportTreeTargetStateReceipt,
    comparison: RenderComparison,
    *,
    source_sha256: str | None = None,
    dispositions: tuple[GeneratedTreeRecordDriftDisposition, ...] | None = None,
) -> None:
    """Admit one explicitly digest-bound manifest repair and nothing broader.

    ``dispositions`` defaults to the pipeline's own ledger, which is what every
    caller uses. It is a parameter so the admission rules can be proven against
    a stated row: a row retires as soon as its cause is repaired, so a proof
    that reaches into the live ledger for "some row with this remedy" passes or
    fails on whichever corrections happen to be outstanding.
    """
    _require_republication_target_binding(invocation, target_state, comparison)
    if comparison.disposition_class == "provenance_only":
        return
    _require_republication_record_disposition(invocation, comparison, dispositions, source_sha256=source_sha256)


def _require_republication_target_binding(
    invocation: GeneratedTreeInvocation,
    target_state: GeneratedExportTreeTargetStateReceipt,
    comparison: RenderComparison,
) -> None:
    expected = invocation.expected_manifest_sha256
    if expected is None or re.fullmatch(SHA256_PATTERN, expected) is None:
        raise ValueError("republish requires an exact lowercase 64-character target manifest sha256")
    if target_state.manifest_sha256 is None:
        raise ValueError("republish requires an existing generated export tree")
    if target_state.manifest_sha256 != expected:
        raise ValueError(
            "republish target manifest sha256 differs from the explicitly reviewed digest: "
            f"expected {expected}, found {target_state.manifest_sha256}",
        )
    if comparison.modelo != invocation.modelo or comparison.revision != invocation.revision:
        raise ValueError("republish comparison identity differs from the explicitly selected target")


def _require_republication_record_disposition(
    invocation: GeneratedTreeInvocation,
    comparison: RenderComparison,
    dispositions: tuple[GeneratedTreeRecordDriftDisposition, ...] | None,
    *,
    source_sha256: str | None,
) -> None:
    if comparison.disposition_class != "record_drift":
        raise ValueError(
            "republish admits attestation drift, or record drift a disposition explains; "
            f"differing={list(comparison.differing)!r} "
            f"only_committed={list(comparison.only_committed)!r} "
            f"only_rendered={list(comparison.only_rendered)!r}",
        )
    # A tree whose RECORDS changed can be replaced only where a disposition row
    # states why. Without this, a correction could never be published at all: the
    # check compares the shipped manifest against a fresh render and refuses the
    # difference, which is precisely the difference being landed. The generator
    # could be made right and the corpus could not be made to match it.
    #
    # The bar is HIGHER here than for attestation drift, not lower. That path
    # needs one proof - the reviewed digest. This needs two: the digest, and a
    # source-pinned row carrying a reason and a retirement condition, which the
    # ledger's own gate fails when its cause is gone. An unexplained record
    # change is refused exactly as before.
    subject = f"{invocation.modelo}/{invocation.revision}"
    rows = {row.subject: row for row in (record_drift_dispositions() if dispositions is None else dispositions)}
    disposition = rows.get(subject)
    if disposition is None:
        raise ValueError(
            f"republish refuses an unexplained record change for {subject}: "
            "declare a disposition row stating why the shipped records differ from what the "
            "current inputs produce, with its source pin and reconsideration condition",
        )
    if disposition.remedy != "republish":
        # A row saying the SHIPPED bytes are right must never be read as
        # permission to overwrite them. Both directions produce identical record
        # drift, so without this the informative modelo whose type-2 record must
        # repeat per declarado would be republished into a return naming one
        # counterparty and dropping the rest.
        raise ValueError(
            f"republish refuses {subject}: its disposition declares the shipped records correct "
            f"and the inputs wrong (remedy={disposition.remedy!r}). Regenerating would ship the "
            "defect. Repair the inputs and retire the row instead",
        )
    if disposition.source_ref != invocation.source_ref or disposition.source_sha256 != source_sha256:
        raise ValueError("republish disposition source ref/SHA differs from the exact selected design")
    if comparison.only_committed or comparison.only_rendered:
        raise ValueError("republish disposition does not admit added or removed target files")
    if disposition.differing_records != len(comparison.record_differing):
        raise ValueError(
            f"republish disposition explains {disposition.differing_records} differing record(s), "
            f"but the exact comparison has {len(comparison.record_differing)}"
        )


def _republish(prepared: PreparedGeneratedTreeInvocation, target_state: GeneratedExportTreeTargetStateReceipt) -> None:
    """Replace one stale manifest only after an exact target-bound safety proof."""
    rendered = _render_candidate(prepared)
    candidate_export_root = (
        prepared.candidate_root
        / "modelos"
        / prepared.invocation.modelo
        / "revisions"
        / prepared.invocation.revision
        / "export"
    )
    comparison = compare_export_tree_roots(
        modelo=prepared.invocation.modelo,
        revision=prepared.invocation.revision,
        layout_id=prepared.inputs.layout_id,
        committed_root=prepared.target_export_root,
        rendered_root=candidate_export_root,
    )
    validate_generated_export_tree(
        context=prepared.validation,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )
    generated_form_bridge = None
    if prepared.inheritance is not None and comparison.disposition_class == "record_drift":
        _require_storage_equivalent_republication(prepared, rendered, target_state, comparison)
    else:
        require_republication_eligibility(
            prepared.invocation,
            target_state,
            comparison,
            source_sha256=str(prepared.inputs.transport_profile.source_sha256),
        )
    if (prepared.invocation.modelo, prepared.invocation.revision) in {
        ("232", "2016-2017"),
        ("232", "2018-y-siguientes"),
        ("190", "2025-y-siguientes"),
        ("347", "2011-2024"),
        ("347", "2025-y-siguientes"),
        ("720", "2013-y-siguientes"),
    } and generated_form_companion_changed(
        prepared.target_root,
        prepared.candidate_root,
        prepared.invocation.modelo,
        prepared.invocation.revision,
    ):
        generated_form_bridge = prepare_generated_form_bridge(
            registry_root=prepared.target_root,
            candidate_root=prepared.candidate_root,
            modelo=prepared.invocation.modelo,
            revision=prepared.invocation.revision,
            source_ref=prepared.invocation.source_ref,
            source_sha256=str(prepared.inputs.transport_profile.source_sha256),
            expected_manifest_sha256=prepared.invocation.expected_manifest_sha256,
        )
    publish_prepared_invocation(prepared, rendered, target_state, generated_form_bridge=generated_form_bridge)
    if generated_form_bridge is not None:
        _finish_form_republication(
            prepared.target_root,
            generated_form_bridge,
            final_live_validator=lambda: _validate_final_live_target(prepared),
        )


def _finish_form_republication(
    registry_root: Path,
    bridge: GeneratedFormBridge | AuthoredFormBridge,
    *,
    final_live_validator: Callable[[], None],
) -> None:
    """Report the separate-owner interval as incomplete until full live proof."""
    try:
        bridge.finish_with_form_owner(registry_root, bundled_path())
        final_live_validator()
    except (OSError, RegistryError, ValueError) as error:
        raise RegistryValidationError(
            "Generated export source was installed but companion/currentness closure is incomplete; "
            f"repair through the canonical form owner: {error}"
        ) from error


def _require_storage_equivalent_republication(
    prepared: PreparedGeneratedTreeInvocation,
    rendered: RenderedExportTree,
    target_state: GeneratedExportTreeTargetStateReceipt,
    comparison: RenderComparison,
) -> None:
    """Admit only an exact old full tree becoming an equal, attested keyed delta."""
    _require_republication_target_binding(prepared.invocation, target_state, comparison)
    if (
        prepared.inheritance is None
        or rendered.output_files != ("0000-export-layout.toml",)
        or rendered.provenance_manifest.generated_export_inheritance != prepared.inheritance.attestation
        or comparison.disposition_class != "record_drift"
        or comparison.only_rendered
    ):
        raise ValueError("storage-equivalent republish requires an exact attested child delta and old full tree")
    full_root = prepared.candidate_root.parents[2] / "full-storage-witness" / "export"
    full_rendered = render_complete_export_tree(
        full_root,
        revision_id=prepared.inputs.revision_id,
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        transport_profile=prepared.inputs.transport_profile,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
        source_defects=source_defects_for(prepared.invocation.source_ref),
    )
    if full_rendered.layout != rendered.layout or full_rendered.field_derivations != rendered.field_derivations:
        raise ValueError("storage-equivalent republish changed fresh child layout or derivations")
    old_full_comparison = compare_export_tree_roots(
        modelo=prepared.invocation.modelo,
        revision=prepared.invocation.revision,
        layout_id=prepared.inputs.layout_id,
        committed_root=prepared.target_export_root,
        rendered_root=full_root,
    )
    if not old_full_comparison.reproduced:
        raise ValueError(
            "storage-equivalent republish refuses an old target that does not reproduce the current full source render"
        )


def _run(
    invocation: GeneratedTreeInvocation,
    *,
    action: Literal["check", "publish", "republish"],
    reconcile_authored_form: bool = False,
    reconcile_casilla_splits: bool = False,
    reconcile_row_bindings: bool = False,
    reconcile_scalar_sources: bool = False,
    temporary_directory: Callable[..., tempfile.TemporaryDirectory[str]] = tempfile.TemporaryDirectory,
) -> None:
    """Run one explicit lifecycle action without retaining a staging tree."""
    try:
        with temporary_directory(prefix="cadrumo-generated-export-") as temporary_name:
            root = Path(temporary_name)
            prepared = prepare_generated_tree_invocation(invocation, root)
            if (
                reconcile_authored_form
                or reconcile_casilla_splits
                or reconcile_row_bindings
                or reconcile_scalar_sources
            ):
                if (
                    sum(
                        (
                            reconcile_authored_form,
                            reconcile_casilla_splits,
                            reconcile_row_bindings,
                            reconcile_scalar_sources,
                        )
                    )
                    > 1
                ):
                    raise ValueError("choose one authored form reconciliation mode")
                if (
                    reconcile_casilla_splits or reconcile_row_bindings or reconcile_scalar_sources
                ) and action != "republish":
                    raise ValueError("field reconciliation requires exclusive republication")
                correcting_producers = action == "republish"
                if not correcting_producers and (
                    action != "publish" or prepared.target_export_root.exists() or prepared.supersession is not None
                ):
                    raise ValueError("authored form reconciliation requires a first export publication")
                if correcting_producers and (prepared.inheritance is not None or prepared.supersession is not None):
                    raise ValueError("authored producer reconciliation refuses inherited or superseded export targets")
                target_state = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
                rendered = _render_candidate(prepared)
                if correcting_producers:
                    comparison = compare_export_tree_roots(
                        modelo=invocation.modelo,
                        revision=invocation.revision,
                        layout_id=prepared.inputs.layout_id,
                        committed_root=prepared.target_export_root,
                        rendered_root=prepared.candidate_root
                        / "modelos"
                        / invocation.modelo
                        / "revisions"
                        / invocation.revision
                        / "export",
                    )
                    require_republication_eligibility(
                        invocation,
                        target_state,
                        comparison,
                        source_sha256=str(prepared.inputs.transport_profile.source_sha256),
                    )
                bridge = prepare_authored_form_bridge(
                    registry_root=prepared.target_root,
                    candidate_root=prepared.candidate_root,
                    source_root=prepared.validation.source_root,
                    temporary_root=root,
                    modelo=invocation.modelo,
                    revision=invocation.revision,
                    unreferenced_producers=correcting_producers
                    and not (reconcile_casilla_splits or reconcile_row_bindings or reconcile_scalar_sources),
                    casilla_splits=reconcile_casilla_splits,
                    row_bindings=reconcile_row_bindings,
                    scalar_sources=reconcile_scalar_sources,
                )
                validate_generated_export_tree(
                    context=prepared.validation,
                    joined=prepared.inputs.joined,
                    semantic_map=prepared.inputs.semantic_map,
                    rendered=rendered,
                    render_profile=prepared.inputs.render_profile,
                    render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
                )
                publish_prepared_invocation(prepared, rendered, target_state, generated_form_bridge=bridge)
                _finish_form_republication(
                    prepared.target_root, bridge, final_live_validator=lambda: _validate_final_live_target(prepared)
                )
            elif action == "check":
                result, _rendered, _target_state = check_prepared_invocation(prepared)
                typer.echo(
                    "checked "
                    f"modelo={invocation.modelo} revision={invocation.revision} source={invocation.source_ref} "
                    f"result={result}",
                )
            elif action == "publish":
                # Publishing is never the first question: a candidate must first
                # pass the independent read-only proof against its live target.
                _result, rendered, target_state = check_prepared_invocation(prepared)
                publish_prepared_invocation(prepared, rendered, target_state)
            else:
                target_state = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
                _republish(prepared, target_state)
    except (RegistryError, ValueError) as error:
        typer.echo(f"refused: {error}", err=True)
        raise typer.Exit(code=1) from error


class TargetCurrentnessState(StrEnum):
    """Read-only state of one named generated export target."""

    CURRENT = "current"
    STALE = "stale"
    DRIFTED = "drifted"
    NEVER_COMMITTED = "never-committed"


@dataclass(frozen=True, slots=True)
class TargetCurrentnessFact:
    """Canonical generated-tree currentness fact and its comparison evidence."""

    modelo: str
    revision: str
    state: TargetCurrentnessState
    differing: tuple[str, ...] = ()
    only_committed: tuple[str, ...] = ()
    only_rendered: tuple[str, ...] = ()
    serialization_only: tuple[str, ...] = ()
    provenance_fields: tuple[str, ...] = ()
    detail: str = ""


def at_edition_grade(
    prepared: PreparedGeneratedTreeInvocation,
    grade: RegistryAuthorityGrade,
) -> PreparedGeneratedTreeInvocation:
    """Validate a prepared target at the authority grade its edition declares.

    Currentness asks whether the committed tree still reproduces and still
    loads, not whether the edition can back a filing. A calculation-grade
    edition never selects at filing grade, so proving its tree at the filing
    default reports drift for a tree that is exactly current.
    """
    return replace(prepared, validation=replace(prepared.validation, required_grade=grade))


def target_currentness(
    modelo: str,
    revision: str,
    source_ref: str | None,
    filing_year: int | None,
    period: str | None = None,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> TargetCurrentnessFact:
    """Prove one generated target currentness without publishing or repairing it.

    The canonical generated-tree checker owns the fresh render, isolated
    authority validation, published-layout load, and byte comparison. The
    comparison below is used only to classify a refused check as stale
    attestation or substantive drift for the read-only fact.
    """
    effective_authority = compiled_bundled_authority() if authority is None else authority
    selected = effective_authority.modelo(modelo).revisions.get(revision)
    if selected is None:
        raise ValueError(f"modelo {modelo} declares no revision {revision!r}")
    effective_filing_year = selected.valid_from.year if filing_year is None else filing_year
    effective_period = period or str(selected.period_selector.periods_for_year(effective_filing_year)[0])
    selected_source_ref, _epoch = select_revision_record_design_source(
        effective_authority,
        modelo=modelo,
        revision=revision,
        filing_year=effective_filing_year,
        period=effective_period,
        source_ref=source_ref,
    )
    invocation = GeneratedTreeInvocation(
        modelo,
        revision,
        str(selected_source_ref),
        effective_filing_year,
        effective_period,
    )
    with tempfile.TemporaryDirectory(
        prefix="cadrumo-generated-export-currentness-", dir=prepare_temporary_directory()
    ) as temporary_name:
        prepared = at_edition_grade(
            prepare_generated_tree_invocation(invocation, Path(temporary_name), authority=effective_authority),
            selected.effective_authority_grade,
        )
        return _target_currentness_for_prepared(modelo, revision, prepared)


def _target_currentness_for_prepared(
    modelo: str,
    revision: str,
    prepared: PreparedGeneratedTreeInvocation,
) -> TargetCurrentnessFact:
    if not prepared.target_export_root.exists():
        check_prepared_invocation(prepared)
        return TargetCurrentnessFact(
            modelo=modelo,
            revision=revision,
            state=TargetCurrentnessState.NEVER_COMMITTED,
            detail="the target rendered successfully but has no committed export tree",
        )
    try:
        check_prepared_invocation(prepared)
    except (OSError, RegistryError, ValueError) as error:
        return _classify_target_currentness_failure(prepared, error)
    return TargetCurrentnessFact(
        modelo=modelo,
        revision=revision,
        state=TargetCurrentnessState.CURRENT,
        detail="fresh canonical output matches the committed target",
    )


def _classify_target_currentness_failure(
    prepared: PreparedGeneratedTreeInvocation,
    error: OSError | RegistryError | ValueError,
) -> TargetCurrentnessFact:
    modelo = prepared.invocation.modelo
    revision = prepared.invocation.revision
    candidate_export_root = prepared.candidate_root / "modelos" / modelo / "revisions" / revision / "export"
    comparison: RenderComparison | None = None
    try:
        if not candidate_export_root.exists():
            _render_candidate(prepared)
        comparison = compare_export_tree_roots(
            modelo=modelo,
            revision=revision,
            layout_id=prepared.inputs.layout_id,
            committed_root=prepared.target_export_root,
            rendered_root=candidate_export_root,
        )
    except (OSError, RegistryError, ValueError):
        pass
    if comparison is None:
        return TargetCurrentnessFact(
            modelo=modelo,
            revision=revision,
            state=TargetCurrentnessState.DRIFTED,
            detail=str(error),
        )
    return _target_currentness_comparison_fact(modelo, revision, comparison, error)


def _target_currentness_comparison_fact(
    modelo: str,
    revision: str,
    comparison: RenderComparison,
    error: OSError | RegistryError | ValueError,
) -> TargetCurrentnessFact:
    state = TargetCurrentnessState.STALE if comparison.provenance_only else TargetCurrentnessState.DRIFTED
    # A stale manifest's refusal names the digest that failed; the members that
    # differ from a fresh render say which input moved.
    detail = str(error)
    if comparison.provenance_fields:
        detail = f"{detail}; manifest members differing from a fresh render: " + ", ".join(comparison.provenance_fields)
    return TargetCurrentnessFact(
        modelo=modelo,
        revision=revision,
        state=state,
        differing=comparison.differing,
        only_committed=comparison.only_committed,
        only_rendered=comparison.only_rendered,
        serialization_only=comparison.serialization_only,
        provenance_fields=comparison.provenance_fields,
        detail=detail,
    )


_MODELO = Annotated[str, typer.Argument(help="Three-digit AEAT modelo identifier.")]
_REVISION = Annotated[str, typer.Argument(help="Exact declared revision identifier.")]
_SOURCE = Annotated[str, typer.Argument(help="Exact declared record-design source reference.")]
_FILING_YEAR = Annotated[int, typer.Argument(help="Filing year used to select the stated source.")]
_PERIOD = Annotated[str, typer.Argument(help="Non-empty declared filing period, for example 0A.")]


@app.command("target-current")
def target_current_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
) -> None:
    """Prove one named generated target is current without changing it."""
    try:
        fact = target_currentness(modelo, revision, source_ref, filing_year, period)
    except (OSError, RegistryError, ValueError) as error:
        typer.echo(f"refused: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(
        "target-current"
        f"\tmodelo={fact.modelo}"
        f"\trevision={fact.revision}"
        f"\tstate={fact.state.value}"
        f"\tdetail={fact.detail}",
    )
    if fact.state is not TargetCurrentnessState.CURRENT:
        raise typer.Exit(code=1)


@app.command("publish-target")
def publish_target_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    reconcile_authored_form: Annotated[
        bool,
        typer.Option("--reconcile-authored-form", help="Preserve an authored draft while installing its first export."),
    ] = False,
) -> None:
    """Check, then transactionally publish one named static target tree."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period),
        action="publish",
        reconcile_authored_form=reconcile_authored_form,
    )
    typer.echo(f"publish-target\tmodelo={modelo}\trevision={revision}\tsource={source_ref}")
    typer.echo(
        "next\tcurrentness=check-registry-target-current\tpublication=registry-publish-authority-if-authority-stale"
    )


@app.command("recover-completed-legacy-target")
def recover_completed_legacy_target_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[str, typer.Option("--expected-manifest-sha256")],
) -> None:
    """Retire a completed legacy journal after digest-bound current record equivalence."""
    invocation = GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256)
    try:
        if re.fullmatch(SHA256_PATTERN, expected_manifest_sha256) is None:
            raise ValueError("legacy recovery requires an exact lowercase target manifest sha256")
        authority = compiled_bundled_authority()
        with tempfile.TemporaryDirectory(
            prefix="cadrumo-legacy-export-recovery-", dir=prepare_temporary_directory()
        ) as directory:
            prepared = prepare_generated_tree_invocation(invocation, Path(directory), authority=authority)
            rendered = _render_candidate(prepared)
            receipt = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
            if receipt.manifest_sha256 != expected_manifest_sha256:
                raise ValueError("legacy recovery target manifest differs from the explicitly reviewed digest")
            retire_completed_legacy_publication(
                context=GeneratedExportTreePublicationContext(
                    validation=prepared.validation,
                    temporary_root=prepared.candidate_root.parents[2],
                    target_root=prepared.target_root,
                    target_export_root=prepared.target_export_root,
                    expected_target_state=receipt,
                ),
                joined=prepared.inputs.joined,
                semantic_map=prepared.inputs.semantic_map,
                rendered=rendered,
                render_profile=prepared.inputs.render_profile,
                render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
            )
    except (RegistryError, LockAcquisitionError, OSError, ValueError) as error:
        typer.echo(f"refused: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"recovered-completed-legacy-target\tmodelo={modelo}\trevision={revision}")


@app.command("republish-target")
def republish_target_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[
        str,
        typer.Argument(help="Exact current manifest sha256 reviewed for replacement."),
    ],
    reconcile_unreferenced_producers: Annotated[
        bool,
        typer.Option(
            "--reconcile-unreferenced-producers",
            help="Reconcile unseen headers or computed markers replaced by displayed manual X-or-blank casillas.",
        ),
    ] = False,
    reconcile_casilla_splits: Annotated[
        bool,
        typer.Option(
            "--reconcile-casilla-splits", help="Preserve an authored draft through reviewed text-field subdivision."
        ),
    ] = False,
    reconcile_row_bindings: Annotated[
        bool,
        typer.Option(
            "--reconcile-row-bindings", help="Preserve official positions while connecting repeated row sources."
        ),
    ] = False,
    reconcile_scalar_sources: Annotated[
        bool,
        typer.Option(
            "--reconcile-scalar-sources",
            help="Preserve an authored draft while reviewed manual export fields use existing canonical casillas.",
        ),
    ] = False,
) -> None:
    """Digest-bound republish of one named target after its exact state was reviewed."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256),
        action="republish",
        reconcile_authored_form=reconcile_unreferenced_producers,
        reconcile_casilla_splits=reconcile_casilla_splits,
        reconcile_row_bindings=reconcile_row_bindings,
        reconcile_scalar_sources=reconcile_scalar_sources,
    )
    typer.echo(f"republish-target\tmodelo={modelo}\trevision={revision}\tsource={source_ref}")
    typer.echo(
        "next\tcurrentness=check-registry-target-current\tpublication=registry-publish-authority-if-authority-stale"
    )


@app.command("check")
def check_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[
        str | None,
        typer.Option("--expected-manifest-sha256", help="Reviewed current manifest for an exact stale-target repair."),
    ] = None,
) -> None:
    """Regenerate and validate one target without changing the published registry."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256),
        action="check",
    )


@app.command("publish")
def publish_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
) -> None:
    """Check, then transactionally publish one target through the canonical authority."""
    _run(GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period), action="publish")
    typer.echo(f"published modelo={modelo} revision={revision} source={source_ref}")


@app.command("republish")
def republish_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
    expected_manifest_sha256: Annotated[
        str,
        typer.Argument(help="Exact current manifest sha256 reviewed for provenance-only replacement."),
    ],
) -> None:
    """Replace one digest-pinned tree only when its records reproduce semantically."""
    _run(
        GeneratedTreeInvocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256),
        action="republish",
    )
    typer.echo(f"republished modelo={modelo} revision={revision} source={source_ref}")


__all__ = [
    "TargetCurrentnessFact",
    "TargetCurrentnessState",
    "app",
    "at_edition_grade",
    "stage_isolated_edition",
    "supporting_modelos",
    "target_currentness",
]
