"""Operator check, publication, and digest-bound republication for one generated tree.

This privileged development CLI intentionally has no product-CLI registration.
It assembles one explicitly selected revision from the validated registry, then
delegates all rendering, validation, comparison, and transactional cutover to
the generator pipeline's canonical authorities.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Literal

import typer

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.i18n.render import locale_map, override_locales_root
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.edition_materialisation import MaterialisedEdition, materialise_edition
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_occurrence_locale_key,
)
from dev.locales.manager import LocaleManager, discover_locale_codes
from dev.registry.compiler.authority import compiled_bundled_authority

from ._export_tree import RenderedExportTree, _render_toml_bytes, render_complete_export_tree
from ._tree_check import CheckedGeneratedExportTree, GeneratedExportTreeCheckContext, check_generated_export_tree
from ._tree_publication import (
    GeneratedExportTreePublicationContext,
    GeneratedExportTreeTargetStateReceipt,
    publish_validated_generated_export_tree,
)
from ._tree_validation import GeneratedExportTreeValidationContext, validate_generated_export_tree
from .authority_publication import publish_authority_candidate
from .candidate_staging import (
    GeneratedExportBootstrapTarget,
    generated_export_bootstrap_target,
    stage_continuity_metadata,
    stage_generated_export_candidate,
)
from .export_fragment_provenance import SHA256_PATTERN, ExportFragmentTarget
from .generated_tree_dispositions import record_drift_dispositions
from .render_check import (
    GeneratedExportBootstrapTransport,
    RenderComparison,
    RevisionRenderInputs,
    compare_export_tree_roots,
    revision_render_inputs,
)
from .source_defects import source_defects_for

app = typer.Typer(
    name="pipeline",
    help="Check, publish, or digest-bound republish one generated AEAT registry export tree.",
    no_args_is_help=True,
)

_SOURCE_MODELO_RE = re.compile(r'^\s*source_modelo\s*=\s*"(?P<modelo>[^"]+)"', re.MULTILINE)


def publish_authority_candidate_workflow(
    *,
    registry_root: Path,
    source_root: Path,
    artifact_path: Path,
    signing_private_key_hex: str,
):
    """Run the dev pipeline's complete authority publication workflow.

    The workflow is programmatic so callers inject a release-held signing key
    instead of exposing it in a product or developer CLI argument.
    """
    return publish_authority_candidate(
        registry_root=registry_root,
        source_root=source_root,
        artifact_path=artifact_path,
        signing_private_key_hex=signing_private_key_hex,
    )


@dataclass(frozen=True, slots=True)
class _Invocation:
    modelo: str
    revision: str
    source_ref: str
    filing_year: int
    period: str
    expected_manifest_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class _PreparedInvocation:
    invocation: _Invocation
    inputs: RevisionRenderInputs
    validation: GeneratedExportTreeValidationContext
    candidate_root: Path
    target_root: Path
    target_export_root: Path
    published_modelo_root: Path | None


def _bootstrap_target(invocation: _Invocation, *, source_sha256: str) -> GeneratedExportBootstrapTarget:
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


def _prepare(invocation: _Invocation, root: Path) -> _PreparedInvocation:
    """Stage one narrow candidate and derive its render inputs from authority."""
    authority = compiled_bundled_authority()
    target_root = bundled_path("registry", "aeat")
    target_export_root = target_root / "modelos" / invocation.modelo / "revisions" / invocation.revision / "export"
    source = next(
        (item for ref, item in authority.catalogues.sources.items() if str(ref) == invocation.source_ref),
        None,
    )
    bootstrap = None
    bootstrap_target: GeneratedExportBootstrapTarget | None = None
    if not target_export_root.exists():
        if source is None:
            raise ValueError(f"no source {invocation.source_ref!r} exists for bootstrap target selection")
        bootstrap_target = _bootstrap_target(invocation, source_sha256=source.sha256)
        bootstrap = GeneratedExportBootstrapTransport(
            layout_id=bootstrap_target.layout_id,
            line_ending=bootstrap_target.line_ending,
            source_ref=bootstrap_target.source_ref,
            source_sha256=bootstrap_target.source_sha256,
        )
    try:
        inputs = revision_render_inputs(
            authority,
            modelo=invocation.modelo,
            revision=invocation.revision,
            source_ref=invocation.source_ref,
            bootstrap_transport=bootstrap,
        )
    except (RegistryError, ValueError) as error:
        raise ValueError(str(error)) from error

    candidate_root = root / "candidate" / "registry" / "aeat"
    stage_generated_export_candidate(
        target_root,
        candidate_root,
        modelo=invocation.modelo,
        revision=invocation.revision,
        supporting_modelos=_supporting_modelos(invocation.modelo),
        bootstrap_target=bootstrap_target,
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
        supporting_modelos=_supporting_modelos(invocation.modelo),
        continuity_metadata_modelo_root=stage_continuity_metadata(
            target_root / "modelos" / invocation.modelo,
            root,
            revision=invocation.revision,
        ),
    )
    return _PreparedInvocation(
        invocation=invocation,
        inputs=inputs,
        validation=validation,
        candidate_root=candidate_root,
        target_root=target_root,
        target_export_root=target_export_root,
        published_modelo_root=_stage_published_modelo(root, modelo=invocation.modelo, revision=invocation.revision),
    )


def _supporting_modelos(modelo: str) -> frozenset[str]:
    """Return declared cross-modelo dependencies that isolated validation needs."""
    modelos_root = bundled_path("registry", "aeat", "modelos")
    source_modelo_root = modelos_root / modelo
    referenced = {
        str(match.group("modelo"))
        for path in source_modelo_root.rglob("*.toml")
        for match in _SOURCE_MODELO_RE.finditer(path.read_text(encoding="utf-8"))
    }
    return frozenset(item for item in referenced - {modelo} if (modelos_root / item).is_dir())


def _stage_published_modelo(root: Path, *, modelo: str, revision: str) -> Path | None:
    """Stage a one-revision published modelo only when check needs the witness."""
    source_modelo_root = bundled_path("registry", "aeat", "modelos", modelo)
    revisions = tuple((source_modelo_root / "revisions").iterdir())
    if len(revisions) == 1:
        return None
    staged = _stage_isolated_edition(
        source_modelo_root,
        root / "published-modelo" / modelo,
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


def _stage_isolated_edition(
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
    edition = materialise_edition(source_modelo_root, revision)
    shutil.copytree(source_modelo_root, staged_root)
    revisions_root = staged_root / "revisions"
    for entry in revisions_root.iterdir():
        if entry.name != revision:
            shutil.rmtree(entry)
    if edition.inherits_from is None:
        return _StagedEdition(modelo_root=staged_root, locales_root=source_locales_root)
    shutil.rmtree(revisions_root / revision)
    (revisions_root / f"{revision}.toml").write_bytes(
        _render_toml_bytes(f"{revision}.toml", {"revisions": {revision: edition.table}}),
    )
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
    if origins is None or not isinstance(rows, tuple) or len(rows) != len(origins):
        raise ValueError(
            f"edition {edition.revision_id!r} of modelo {edition.modelo_id!r} carries no label origin per casilla",
        )
    with override_locales_root(source_locales_root):
        catalogue = locale_map(locale)
    carried: dict[str, str | None] = {}
    for row, origin in zip(rows, origins, strict=True):
        casilla_id = row.get("id") if isinstance(row, Mapping) else None
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


def _render_candidate(prepared: _PreparedInvocation) -> RenderedExportTree:
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
    )
    return rendered


def _check(
    prepared: _PreparedInvocation,
) -> tuple[Literal["matched", "publishable_absence"], RenderedExportTree, GeneratedExportTreeTargetStateReceipt]:
    """Drive the canonical checker, or validate a fresh candidate for an owed tree.

    An absent tree has no bytes to compare and therefore cannot be called a
    match.  It is nevertheless publishable when the real generator can render
    it and the real validator accepts that candidate.  This narrow bootstrap
    case keeps an owed tree from deadlocking the publisher while preserving the
    same pre-cutover validation boundary publication uses.
    """
    target_state = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
    if not prepared.target_export_root.exists():
        rendered = _render_candidate(prepared)
        validate_generated_export_tree(
            context=_bootstrap_validation(prepared.validation),
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


def _bootstrap_validation(context: GeneratedExportTreeValidationContext) -> GeneratedExportTreeValidationContext:
    """Lower only the static-publication proof to its honest authority grade."""
    return replace(context, required_grade=RegistryAuthorityGrade.CALCULATION)


def _publish(
    prepared: _PreparedInvocation,
    rendered: RenderedExportTree,
    target_state: GeneratedExportTreeTargetStateReceipt,
) -> None:
    """Publish the exact prepared candidate the read-only check just validated."""
    publish_validated_generated_export_tree(
        context=GeneratedExportTreePublicationContext(
            validation=_bootstrap_validation(prepared.validation),
            temporary_root=prepared.candidate_root.parents[2],
            target_root=prepared.target_root,
            target_export_root=prepared.target_export_root,
            expected_target_state=target_state,
        ),
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )


def _require_republication_eligibility(
    invocation: _Invocation,
    target_state: GeneratedExportTreeTargetStateReceipt,
    comparison: RenderComparison,
) -> None:
    """Admit one explicitly digest-bound manifest repair and nothing broader."""
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
    if comparison.disposition_class == "provenance_only":
        return
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
    rows = {row.subject: row for row in record_drift_dispositions()}
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


def _republish(prepared: _PreparedInvocation, target_state: GeneratedExportTreeTargetStateReceipt) -> None:
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
    _require_republication_eligibility(prepared.invocation, target_state, comparison)
    validate_generated_export_tree(
        context=_bootstrap_validation(prepared.validation),
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )
    _publish(prepared, rendered, target_state)


def _run(
    invocation: _Invocation,
    *,
    action: Literal["check", "publish", "republish"],
    temporary_directory: Callable[..., tempfile.TemporaryDirectory[str]] = tempfile.TemporaryDirectory,
) -> None:
    """Run one explicit lifecycle action without retaining a staging tree."""
    try:
        with temporary_directory(prefix="cadrumo-generated-export-") as temporary_name:
            root = Path(temporary_name)
            prepared = _prepare(invocation, root)
            if action == "check":
                result, _rendered, _target_state = _check(prepared)
                typer.echo(
                    "checked "
                    f"modelo={invocation.modelo} revision={invocation.revision} source={invocation.source_ref} "
                    f"result={result}",
                )
            elif action == "publish":
                # Publishing is never the first question: a candidate must first
                # pass the independent read-only proof against its live target.
                _result, rendered, target_state = _check(prepared)
                _publish(prepared, rendered, target_state)
            else:
                target_state = GeneratedExportTreeTargetStateReceipt.observe(prepared.target_export_root)
                _republish(prepared, target_state)
    except (RegistryError, ValueError) as error:
        typer.echo(f"refused: {error}", err=True)
        raise typer.Exit(code=1) from error


_MODELO = Annotated[str, typer.Argument(help="Three-digit AEAT modelo identifier.")]
_REVISION = Annotated[str, typer.Argument(help="Exact declared revision identifier.")]
_SOURCE = Annotated[str, typer.Argument(help="Exact declared record-design source reference.")]
_FILING_YEAR = Annotated[int, typer.Argument(help="Filing year used to select the stated source.")]
_PERIOD = Annotated[str, typer.Argument(help="Non-empty declared filing period, for example 0A.")]


@app.command("check")
def check_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
) -> None:
    """Regenerate and validate one target without changing the published registry."""
    _run(_Invocation(modelo, revision, source_ref, filing_year, period), action="check")


@app.command("publish")
def publish_command(
    modelo: _MODELO,
    revision: _REVISION,
    source_ref: _SOURCE,
    filing_year: _FILING_YEAR,
    period: _PERIOD,
) -> None:
    """Check, then transactionally publish one target through the canonical authority."""
    _run(_Invocation(modelo, revision, source_ref, filing_year, period), action="publish")
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
        _Invocation(modelo, revision, source_ref, filing_year, period, expected_manifest_sha256),
        action="republish",
    )
    typer.echo(f"republished modelo={modelo} revision={revision} source={source_ref}")


__all__ = ["app", "publish_authority_candidate_workflow"]
