"""Read-only registry verification CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

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
    modelos: tuple[str, ...]
    verified: bool


def inspect_registry_tree(registry_root: Path) -> RegistryTreeReport:
    """Load the registry tree and return stable read-only inventory counts."""

    modelos, catalogues = load_registry_tree(registry_root)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
        modelos=tuple(sorted(modelo.id for modelo in modelos)),
        verified=False,
    )


def verify_registry_tree(registry_root: Path, *, source_root: Path) -> RegistryTreeReport:
    """Load and fail-fast validate every registry modelo against shared catalogues."""

    modelos, catalogues = load_registry_tree(registry_root)
    validator = RegistryValidator(catalogues, source_root=source_root)
    for modelo in modelos:
        validator.validate_modelo(modelo)
    return RegistryTreeReport(
        registry_root=str(registry_root),
        source_root=str(source_root),
        modelo_count=len(modelos),
        revision_count=sum(len(modelo.revisions) for modelo in modelos),
        legal_reference_count=len(catalogues.legal),
        source_reference_count=len(catalogues.sources),
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
    typer.echo(f"modelo_count={report.modelo_count}")
    typer.echo(f"revision_count={report.revision_count}")
    typer.echo(f"legal_reference_count={report.legal_reference_count}")
    typer.echo(f"source_reference_count={report.source_reference_count}")
    typer.echo(f"modelos={','.join(report.modelos)}")


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
    typer.echo(f"verified={report.verified}")
    typer.echo(f"modelo_count={report.modelo_count}")
    typer.echo(f"revision_count={report.revision_count}")
    typer.echo(f"legal_reference_count={report.legal_reference_count}")
    typer.echo(f"source_reference_count={report.source_reference_count}")
    typer.echo(f"modelos={','.join(report.modelos)}")


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
    typer.echo(f"backend_exists={report.backend_exists}")
    typer.echo(f"workbook_count={report.workbook_count}")
    typer.echo(f"scanned_count={report.scanned_count}")
    typer.echo(f"formula_workbook_count={report.formula_workbook_count}")
    typer.echo(f"unsupported_xls_count={report.unsupported_xls_count}")
    typer.echo(f"failed_count={report.failed_count}")
    typer.echo(f"runner_status={report.runner.status}")
    typer.echo(f"runner_detail={report.runner.detail}")


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
