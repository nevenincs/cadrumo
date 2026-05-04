"""Read-only registry verification CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NamedTuple

import typer
from pydantic import BaseModel, ConfigDict

from ...domain.calculations.registry import RegistryValidator, load_registry_tree, verify_workbook_backend
from ...domain.calculations.registry._workbook_parity import WorkbookBackendVerificationReport

app = typer.Typer(
    name="registry",
    help="Read-only registry verification commands.",
    no_args_is_help=True,
    add_completion=False,
)
workbooks_app = typer.Typer(
    name="workbooks",
    help="Official AEAT workbook parity verification.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(workbooks_app, name="workbooks")


class RegistryTreeReport(BaseModel):
    """Read-only registry tree load or verification result."""

    model_config = ConfigDict(frozen=True)

    registry_root: str
    source_root: str | None = None
    modelo_count: int
    revision_count: int
    legal_reference_count: int
    source_reference_count: int
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: tuple[str, ...]
    modelos: tuple[str, ...]
    verified: bool


class RegistryRevisionInventory(NamedTuple):
    casilla_count: int
    formula_count: int
    extraction_profile_count: int
    cross_reference_count: int
    workbook_parity_ref_count: int
    verification_expectation_count: int
    application_link_count: int
    application_link_surfaces: tuple[str, ...]


def _revision_inventory(modelos) -> RegistryRevisionInventory:
    revisions = tuple(revision for modelo in modelos for revision in modelo.revisions.values())
    application_surfaces = {link.surface for revision in revisions for link in revision.application_links}
    return RegistryRevisionInventory(
        casilla_count=sum(len(revision.casillas) for revision in revisions),
        formula_count=sum(len(revision.formulas) for revision in revisions),
        extraction_profile_count=sum(len(revision.extraction_profiles) for revision in revisions),
        cross_reference_count=sum(len(revision.live_cross_references) for revision in revisions),
        workbook_parity_ref_count=sum(len(revision.workbook_parity_refs) for revision in revisions),
        verification_expectation_count=sum(len(revision.verification_expectations) for revision in revisions),
        application_link_count=sum(len(revision.application_links) for revision in revisions),
        application_link_surfaces=tuple(sorted(application_surfaces)),
    )


def _emit_metric(key: str, value: object) -> None:
    line = f"{key}={value}"
    typer.echo(line)


def inspect_registry_tree(registry_root: Path) -> RegistryTreeReport:
    """Load the registry tree and return stable read-only inventory counts."""

    modelos, catalogues = load_registry_tree(registry_root)
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
        casilla_count=inventory.casilla_count,
        formula_count=inventory.formula_count,
        extraction_profile_count=inventory.extraction_profile_count,
        cross_reference_count=inventory.cross_reference_count,
        workbook_parity_ref_count=inventory.workbook_parity_ref_count,
        verification_expectation_count=inventory.verification_expectation_count,
        application_link_count=inventory.application_link_count,
        application_link_surfaces=inventory.application_link_surfaces,
        modelos=tuple(sorted(modelo.id for modelo in modelos)),
        verified=False,
    )


def verify_registry_tree(registry_root: Path, *, source_root: Path) -> RegistryTreeReport:
    """Load and fail-fast validate every registry modelo against shared catalogues."""

    modelos, catalogues = load_registry_tree(registry_root)
    validator = RegistryValidator(catalogues, source_root=source_root)
    for modelo in modelos:
        validator.validate_modelo(modelo)
    inventory = _revision_inventory(modelos)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        source_root=str(source_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
        casilla_count=inventory.casilla_count,
        formula_count=inventory.formula_count,
        extraction_profile_count=inventory.extraction_profile_count,
        cross_reference_count=inventory.cross_reference_count,
        workbook_parity_ref_count=inventory.workbook_parity_ref_count,
        verification_expectation_count=inventory.verification_expectation_count,
        application_link_count=inventory.application_link_count,
        application_link_surfaces=inventory.application_link_surfaces,
        modelos=tuple(sorted(modelo.id for modelo in modelos)),
        verified=True,
    )


@app.command("inspect", help="Read and inventory the registry tree without writing files.")
def inspect_registry_cmd(
    registry_root: Annotated[
        Path,
        typer.Option(
            "--registry-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Registry root containing legal/ and modelos/.",
        ),
    ] = Path("registry/aeat"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the inspection report as JSON."),
    ] = False,
) -> None:
    """Load the read-only registry tree and report inventory counts."""

    report = inspect_registry_tree(registry_root)
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("modelo_count", report.modelo_count)
    _emit_metric("revision_count", report.revision_count)
    _emit_metric("legal_reference_count", report.legal_reference_count)
    _emit_metric("source_reference_count", report.source_reference_count)
    _emit_metric("casilla_count", report.casilla_count)
    _emit_metric("formula_count", report.formula_count)
    _emit_metric("extraction_profile_count", report.extraction_profile_count)
    _emit_metric("cross_reference_count", report.cross_reference_count)
    _emit_metric("workbook_parity_ref_count", report.workbook_parity_ref_count)
    _emit_metric("verification_expectation_count", report.verification_expectation_count)
    _emit_metric("application_link_count", report.application_link_count)
    _emit_metric("application_link_surfaces", ",".join(report.application_link_surfaces))
    _emit_metric("modelos", ",".join(report.modelos))


@app.command("verify", help="Fail-fast validate the registry tree and official source evidence.")
def verify_registry_cmd(
    registry_root: Annotated[
        Path,
        typer.Option(
            "--registry-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Registry root containing legal/ and modelos/.",
        ),
    ] = Path("registry/aeat"),
    source_root: Annotated[
        Path,
        typer.Option(
            "--source-root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Repository root used to verify referenced corpus artefacts.",
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the verification report as JSON."),
    ] = False,
) -> None:
    """Validate every registry modelo against shared legal/source catalogues."""

    report = verify_registry_tree(registry_root, source_root=source_root)
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("verified", report.verified)
    _emit_metric("modelo_count", report.modelo_count)
    _emit_metric("revision_count", report.revision_count)
    _emit_metric("legal_reference_count", report.legal_reference_count)
    _emit_metric("source_reference_count", report.source_reference_count)
    _emit_metric("casilla_count", report.casilla_count)
    _emit_metric("formula_count", report.formula_count)
    _emit_metric("extraction_profile_count", report.extraction_profile_count)
    _emit_metric("cross_reference_count", report.cross_reference_count)
    _emit_metric("workbook_parity_ref_count", report.workbook_parity_ref_count)
    _emit_metric("verification_expectation_count", report.verification_expectation_count)
    _emit_metric("application_link_count", report.application_link_count)
    _emit_metric("application_link_surfaces", ",".join(report.application_link_surfaces))
    _emit_metric("modelos", ",".join(report.modelos))


@workbooks_app.command("verify", help="Verify workbook parity backend discovery against a corpus root.")
def verify_workbooks_cmd(
    root: Annotated[
        Path,
        typer.Option(
            "--root",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Official AEAT workbook corpus root.",
        ),
    ] = Path("corpus/aeat_official/disenos_registro"),
    limit: Annotated[
        int,
        typer.Option("--limit", min=1, help="Maximum number of workbook artefacts to scan."),
    ] = 25,
    per_file_timeout_seconds: Annotated[
        float,
        typer.Option("--per-file-timeout", min=0.1, help="Maximum seconds to spend scanning one workbook."),
    ] = 10.0,
    output: Annotated[
        Path | None,
        typer.Option("--output", file_okay=True, dir_okay=False, writable=True, help="Write JSON report to this file."),
    ] = None,
    resume_from: Annotated[
        Path | None,
        typer.Option(
            "--resume-from",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Reuse unchanged workbook reports from a previous JSON report.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the verification report as JSON."),
    ] = False,
) -> None:
    """Run the read-only workbook parity backend verification."""

    previous_report = None
    if resume_from is not None:
        previous_report = WorkbookBackendVerificationReport.model_validate_json(resume_from.read_text(encoding="utf-8"))
    report = verify_workbook_backend(
        root,
        scan_limit=limit,
        per_file_timeout_seconds=per_file_timeout_seconds,
        previous_report=previous_report,
    )
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if json_output:
        typer.echo(report.model_dump_json(indent=2))
        return
    _emit_metric("backend_exists", report.backend_exists)
    _emit_metric("workbook_count", report.workbook_count)
    _emit_metric("scanned_count", report.scanned_count)
    _emit_metric("formula_workbook_count", report.formula_workbook_count)
    _emit_metric("unsupported_xls_count", report.unsupported_xls_count)
    _emit_metric("failed_count", report.failed_count)
    _emit_metric("runner_status", report.runner.status)
    _emit_metric("runner_detail", report.runner.detail)


def _json_default(value: object) -> str:
    return str(value)


def render_report_json(report: object) -> str:
    """Render a pydantic report object as stable JSON for tests and scripts."""

    model_dump = getattr(report, "model_dump", None)
    if model_dump is None:
        return json.dumps(report, default=_json_default, sort_keys=True)
    return json.dumps(model_dump(mode="json"), sort_keys=True)


__all__ = [
    "RegistryTreeReport",
    "app",
    "inspect_registry_cmd",
    "inspect_registry_tree",
    "render_report_json",
    "verify_registry_cmd",
    "verify_registry_tree",
    "verify_workbooks_cmd",
    "workbooks_app",
]
