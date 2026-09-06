"""English-only contributor CLI for registry maintenance workflows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.live_parity import OracleEnvironment

from .maintenance import (
    audit_registry_oracles,
    replay_registry_parity,
    run_registry_parity,
    verify_registry_workbooks,
)

app = typer.Typer(no_args_is_help=True, add_completion=False)
_REGISTRY_ROOT = bundled_path("registry", "aeat")
_WORKBOOK_ROOT = bundled_path("corpus", "aeat_official", "disenos_registro")
_SOURCE_ROOT = bundled_path()


def _json(value: BaseModel | dict[str, object]) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


@app.command("audit-oracles")
def audit_oracles(
    registry_root: Annotated[Path, typer.Option("--registry-root")] = _REGISTRY_ROOT,
    environment: Annotated[OracleEnvironment, typer.Option("--environment")] = OracleEnvironment.PRODUCTION,
) -> None:
    """Gate committed live-oracle bindings for CI and pre-deploy checks."""
    report = audit_registry_oracles(registry_root, environment=environment)
    _json(report)
    if report.failures:
        raise typer.Exit(1)


@app.command("workbooks-verify")
def workbooks_verify(
    root: Annotated[Path, typer.Option("--root")] = _WORKBOOK_ROOT,
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    per_file_timeout: Annotated[float, typer.Option("--per-file-timeout", min=0.1)] = 15.0,
    resume_from: Annotated[Path | None, typer.Option("--resume-from")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """Verify official workbook artefacts and available calculation backends.

    Exits non-zero when the report carries failures. It previously printed
    ``failed_count`` and returned 0 regardless, so a contributor scripting this
    verb got the same exit status whether every workbook verified or none did -
    while its sibling ``audit-oracles`` in this same file already refused.

    It also exits non-zero when ``--root`` names a tree with no workbook to
    scan: a moved or misspelled corpus path once reported ``workbook_count``
    and ``failed_count`` both zero, which reads exactly like a clean audit of
    a real corpus.
    """
    report = verify_registry_workbooks(
        root=root,
        limit=limit,
        per_file_timeout_seconds=per_file_timeout,
        resume_from=resume_from,
        output=output,
    )
    _json(report)
    if not report.backend_exists:
        raise typer.Exit(1)
    if report.failed_count:
        raise typer.Exit(1)


@app.command("parity-run")
def parity_run(
    scenario: Annotated[Path, typer.Option("--scenario")],
    store_root: Annotated[Path, typer.Option("--store-root")],
    registry_root: Annotated[Path, typer.Option("--registry-root")] = _REGISTRY_ROOT,
    source_root: Annotated[Path, typer.Option("--source-root")] = _SOURCE_ROOT,
    output: Annotated[Path | None, typer.Option("--output")] = None,
) -> None:
    """Run a curated parity scenario and archive its tape."""
    tape, target = run_registry_parity(
        scenario_path=scenario,
        registry_root=registry_root,
        source_root=source_root,
        store_root=store_root,
        output=output,
    )
    _json({"tape": tape.model_dump(mode="json"), "path": str(target)})


@app.command("parity-replay")
def parity_replay(
    tape: Annotated[Path, typer.Option("--tape")],
    registry_root: Annotated[Path, typer.Option("--registry-root")] = _REGISTRY_ROOT,
    source_root: Annotated[Path, typer.Option("--source-root")] = _SOURCE_ROOT,
) -> None:
    """Replay an archived parity tape against current product behavior.

    Exits non-zero on a mismatch. A replay whose whole purpose is to detect
    that the product diverged from an archived tape reported that divergence
    in its JSON and then exited 0, so the divergence and the agreement were
    indistinguishable to anything reading the status code.
    """
    report = replay_registry_parity(tape_path=tape, registry_root=registry_root, source_root=source_root)
    _json(report)
    if report.status != "match":
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
