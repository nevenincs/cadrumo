"""Operator invocation surface for one generated registry export tree.

This privileged development CLI intentionally has no product-CLI registration.
It assembles one explicitly selected revision from the validated registry, then
delegates all rendering, validation, comparison, and transactional cutover to
the generator pipeline's canonical authorities.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import typer

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.errors import RegistryError

from ._export_tree import render_complete_export_tree
from ._provenance_manifest import ExportFragmentTarget
from ._tree_check import GeneratedExportTreeCheckContext, check_generated_export_tree
from ._tree_publication import GeneratedExportTreePublicationContext, publish_validated_generated_export_tree
from ._tree_validation import GeneratedExportTreeValidationContext
from .render_check import RevisionRenderInputs, revision_render_inputs

app = typer.Typer(
    name="pipeline",
    help="Check or transactionally publish one generated AEAT registry export tree.",
    no_args_is_help=True,
)

_SOURCE_MODELO_RE = re.compile(r'^\s*source_modelo\s*=\s*"(?P<modelo>[^"]+)"', re.MULTILINE)


@dataclass(frozen=True, slots=True)
class _Invocation:
    modelo: str
    revision: str
    source_ref: str
    filing_year: int
    period: str


@dataclass(frozen=True, slots=True)
class _PreparedInvocation:
    invocation: _Invocation
    inputs: RevisionRenderInputs
    validation: GeneratedExportTreeValidationContext
    candidate_root: Path
    target_root: Path
    target_export_root: Path
    published_modelo_root: Path | None


def _prepare(invocation: _Invocation, root: Path) -> _PreparedInvocation:
    """Stage one narrow candidate and derive its render inputs from authority."""
    authority = bundled_authority()
    try:
        inputs = revision_render_inputs(
            authority,
            modelo=invocation.modelo,
            revision=invocation.revision,
            source_ref=invocation.source_ref,
        )
    except (RegistryError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error

    candidate_root = root / "candidate" / "registry" / "aeat"
    target_root = bundled_path("registry", "aeat")
    _stage_candidate(
        candidate_root,
        modelo=invocation.modelo,
        revision=invocation.revision,
    )
    target_export_root = target_root / "modelos" / invocation.modelo / "revisions" / invocation.revision / "export"
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
        continuity_metadata_modelo_root=_stage_continuity_metadata(
            root,
            modelo=invocation.modelo,
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


def _stage_candidate(candidate_root: Path, *, modelo: str, revision: str) -> None:
    """Copy the selected non-export authority into an isolated candidate tree."""
    source_root = bundled_path("registry", "aeat")
    shutil.copytree(source_root / "legal", candidate_root / "legal")
    if modelo == "303":
        shutil.copytree(source_root / "m303_orden_anual", candidate_root / "m303_orden_anual")
    source_modelo_root = source_root / "modelos" / modelo
    staged_modelo_root = candidate_root / "modelos" / modelo
    shutil.copytree(source_modelo_root, staged_modelo_root, ignore=shutil.ignore_patterns("export"))
    for sibling in (staged_modelo_root / "revisions").iterdir():
        if sibling.name != revision:
            shutil.rmtree(sibling)
    for supporting_modelo in _supporting_modelos(modelo):
        shutil.copytree(source_root / "modelos" / supporting_modelo, candidate_root / "modelos" / supporting_modelo)


def _supporting_modelos(modelo: str) -> frozenset[str]:
    """Return declared cross-modelo dependencies that isolated validation needs."""
    modelos_root = bundled_path("registry", "aeat", "modelos")
    source_modelo_root = modelos_root / modelo
    referenced = {
        match.group("modelo")
        for path in source_modelo_root.rglob("*.toml")
        for match in _SOURCE_MODELO_RE.finditer(path.read_text(encoding="utf-8"))
    }
    return frozenset(item for item in referenced - {modelo} if (modelos_root / item).is_dir())


def _stage_continuity_metadata(root: Path, *, modelo: str, revision: str) -> Path | None:
    """Stage only predecessor facts needed by the strict-continuity validator."""
    source_modelo_root = bundled_path("registry", "aeat", "modelos", modelo)
    definition = bundled_authority().modelo(modelo)
    selected = definition.revisions.get(revision)
    if selected is None:
        raise typer.BadParameter(f"modelo {modelo} declares no revision {revision!r}")
    predecessors = sorted({str(item.from_revision) for item in selected.casilla_continuidad_evolutions})
    if not predecessors:
        return None
    staged_root = root / "continuity-metadata" / modelo
    staged_root.mkdir(parents=True)
    shutil.copy2(source_modelo_root / "manifest.toml", staged_root / "manifest.toml")
    for predecessor in predecessors:
        source_revision = source_modelo_root / "revisions" / predecessor
        staged_revision = staged_root / "revisions" / predecessor
        staged_revision.mkdir(parents=True)
        shutil.copy2(source_revision / "revision.toml", staged_revision / "revision.toml")
        for member in ("casillas", "casilla_continuidad_evolutions"):
            if (source_revision / member).is_dir():
                shutil.copytree(source_revision / member, staged_revision / member)
    return staged_root


def _stage_published_modelo(root: Path, *, modelo: str, revision: str) -> Path | None:
    """Stage a one-revision published modelo only when check needs the witness."""
    source_modelo_root = bundled_path("registry", "aeat", "modelos", modelo)
    revisions = tuple((source_modelo_root / "revisions").iterdir())
    if len(revisions) == 1:
        return None
    staged_root = root / "published-modelo" / modelo
    shutil.copytree(source_modelo_root, staged_root)
    for sibling in (staged_root / "revisions").iterdir():
        if sibling.name != revision:
            shutil.rmtree(sibling)
    return staged_root


def _check(prepared: _PreparedInvocation) -> None:
    """Drive the canonical read-only checker over the prepared target."""
    check_generated_export_tree(
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
    )


def _publish(prepared: _PreparedInvocation) -> None:
    """Render the fresh candidate then drive the canonical transactional publisher."""
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
    )
    publish_validated_generated_export_tree(
        context=GeneratedExportTreePublicationContext(
            validation=prepared.validation,
            temporary_root=prepared.candidate_root.parents[2],
            target_root=prepared.target_root,
            target_export_root=prepared.target_export_root,
        ),
        joined=prepared.inputs.joined,
        semantic_map=prepared.inputs.semantic_map,
        rendered=rendered,
        render_profile=prepared.inputs.render_profile,
        render_profile_source_evidence=prepared.inputs.render_profile_source_evidence,
    )


def _run(
    invocation: _Invocation,
    *,
    action: Literal["check", "publish"],
    temporary_directory: Callable[..., tempfile.TemporaryDirectory[str]] = tempfile.TemporaryDirectory,
) -> None:
    """Run one explicit lifecycle action without retaining a staging tree."""
    try:
        with temporary_directory(prefix="cadrumo-generated-export-") as temporary_name:
            root = Path(temporary_name)
            prepared = _prepare(invocation, root)
            if action == "check":
                _check(prepared)
            else:
                # Publishing is never the first question: a candidate must first
                # pass the independent read-only proof against its live target.
                _check(prepared)
                publish_root = root / "publish"
                prepared = _prepare(invocation, publish_root)
                _publish(prepared)
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
    typer.echo(f"checked modelo={modelo} revision={revision} source={source_ref}")


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


__all__ = ["app"]
