"""``aeat filing`` sub-app — filing draft engine CLI (#39).

Subcommands:

- ``aeat filing build`` — build a draft from a JSON inputs file.
- ``aeat filing validate`` — re-validate a saved draft.
- ``aeat filing show`` — pretty-print a draft.
- ``aeat filing list`` — list drafts under the configured drafts dir.

The CLI deliberately consumes the synthetic Modelo 130 schema
provider exposed by :mod:`aeat.filing.testing`, because the real
casilla DB (#23) and modelo catalogue (#6) are not on ``main``
yet. Wiring the production providers is a follow-up rebase.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from aeat.config import load_settings
from aeat.filing import (
    FilingDraft,
    FilingDraftError,
    FilingDraftStatus,
    FilingFindingSeverity,
    build_draft,
    iter_findings,
    validate_draft,
)
from aeat.filing.testing import (
    SyntheticProfile,
    default_schema_provider,
)
from aeat.logging import get_logger

app = typer.Typer(
    name="filing",
    no_args_is_help=True,
    help="Filing draft engine commands (#39).",
)

_console = Console()
_logger = get_logger(__name__)

_DEFAULT_PROFILE_TAX_ID = "00000000T"
_DEFAULT_PROFILE_NAME = "Demo autónomo"


def _drafts_dir() -> Path:
    """Return the configured drafts directory, creating it if missing."""
    settings = load_settings()
    path = Path(settings.aeat_drafts_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _draft_filename(draft: FilingDraft) -> str:
    """Build the canonical filename for a draft on disk."""
    return f"{draft.modelo}_{draft.period}_{draft.draft_id}.json"


def _load_inputs(path: Path) -> dict[str, object]:
    """Load and parse a JSON inputs file from disk."""
    if not path.exists():
        raise typer.BadParameter(f"inputs file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise typer.BadParameter(f"inputs file {path} must contain a JSON object")
    parsed: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise typer.BadParameter(f"input key must be string, got {type(key).__name__}")
        if isinstance(value, str | int | bool) or value is None:
            parsed[key] = value
        elif isinstance(value, float):
            # Use Decimal so monetary precision is preserved.
            parsed[key] = Decimal(str(value))
        else:
            raise typer.BadParameter(f"unsupported value type for casilla {key!r}: {type(value).__name__}")
    return parsed


def _load_draft(path: Path) -> FilingDraft:
    """Load and parse a draft JSON file."""
    if not path.exists():
        raise typer.BadParameter(f"draft file not found: {path}")
    try:
        return FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
    except FilingDraftError as exc:
        raise typer.BadParameter(f"invalid draft in {path}: {exc}") from exc


def _save_draft(draft: FilingDraft) -> Path:
    """Write a draft to the configured drafts directory."""
    target = _drafts_dir() / _draft_filename(draft)
    target.write_text(
        draft.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return target


def _render_draft(draft: FilingDraft, *, findings_only: bool = False) -> None:
    """Pretty-print a draft to the console."""
    if not findings_only:
        header = Table(title=f"Draft {draft.draft_id}", show_header=False)
        header.add_row("modelo", draft.modelo)
        header.add_row("period", draft.period)
        header.add_row("profile_tax_id", draft.profile_tax_id)
        header.add_row("status", draft.status.value)
        header.add_row("schema_version", draft.schema_version)
        header.add_row("created_at", draft.created_at.isoformat())
        header.add_row("updated_at", draft.updated_at.isoformat())
        _console.print(header)

        values_table = Table(title="Casillas", show_lines=False)
        values_table.add_column("casilla")
        values_table.add_column("kind")
        values_table.add_column("value")
        values_table.add_column("source")
        for value in draft.values:
            values_table.add_row(
                value.casilla_id,
                value.kind.value,
                "" if value.value is None else str(value.value),
                value.source,
            )
        _console.print(values_table)

    findings_table = Table(title="Findings")
    findings_table.add_column("severity")
    findings_table.add_column("code")
    findings_table.add_column("casilla")
    findings_table.add_column("message (en)")
    for finding in draft.findings:
        message_en = finding.message.get("en", "") if finding.message else ""
        findings_table.add_row(
            finding.severity.value,
            finding.code,
            finding.casilla_id or "-",
            message_en,
        )
    _console.print(findings_table)


@app.command("build")
def build(
    modelo: Annotated[str, typer.Option("--modelo", help="Modelo string ID, e.g. 130")],
    period: Annotated[str, typer.Option("--period", help="Period identifier, e.g. 2026Q1")],
    inputs: Annotated[
        Path,
        typer.Option("--inputs", help="Path to a JSON file with casilla → value mapping"),
    ],
    profile_tax_id: Annotated[
        str,
        typer.Option(
            "--profile-tax-id",
            help="Taxpayer tax ID to stamp on the draft",
        ),
    ] = _DEFAULT_PROFILE_TAX_ID,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", help="Display name of the taxpayer profile"),
    ] = _DEFAULT_PROFILE_NAME,
) -> None:
    """Build a draft from a JSON inputs file and save it to disk."""
    settings = load_settings()
    parsed_inputs = _load_inputs(inputs)
    profile = SyntheticProfile(
        tax_id=profile_tax_id,
        display_name=profile_name,
        applicable_modelos=(modelo,),
    )
    try:
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=profile,
            inputs=parsed_inputs,
            schema_provider=default_schema_provider(),
            fail_on_warning=settings.aeat_draft_fail_on_warning,
        )
    except FilingDraftError as exc:
        raise typer.BadParameter(str(exc)) from exc
    saved = _save_draft(draft)
    typer.echo(f"Saved draft {draft.draft_id} → {saved}")
    _render_draft(draft)


@app.command("validate")
def validate(
    draft_path: Annotated[Path, typer.Argument(help="Path to a draft JSON file")],
) -> None:
    """Re-validate an existing draft and rewrite it to disk."""
    draft = _load_draft(draft_path)
    refreshed = validate_draft(
        draft,
        schema_provider=default_schema_provider(),
    )
    draft_path.write_text(refreshed.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Re-validated draft {refreshed.draft_id} (status={refreshed.status.value})")
    _render_draft(refreshed)


@app.command("show")
def show(
    draft_path: Annotated[Path, typer.Argument(help="Path to a draft JSON file")],
    findings_only: Annotated[
        bool,
        typer.Option("--findings-only", help="Only print findings, not casillas"),
    ] = False,
) -> None:
    """Pretty-print a draft to the console."""
    draft = _load_draft(draft_path)
    _render_draft(draft, findings_only=findings_only)
    if findings_only:
        for finding in iter_findings(draft, severity_at_least="INFO"):
            if finding.severity is FilingFindingSeverity.ERROR:
                _logger.debug("draft %s has error %s", draft.draft_id, finding.code)


@app.command("list")
def list_drafts(
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help="Filter by modelo string ID"),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by FilingDraftStatus value"),
    ] = None,
) -> None:
    """List drafts in the configured drafts directory."""
    target_status: FilingDraftStatus | None = None
    if status is not None:
        try:
            target_status = FilingDraftStatus(status)
        except ValueError as exc:
            raise typer.BadParameter(
                f"unknown status {status!r}; valid: {[s.value for s in FilingDraftStatus]}"
            ) from exc

    table = Table(title="Filing drafts")
    table.add_column("draft_id")
    table.add_column("modelo")
    table.add_column("period")
    table.add_column("status")
    table.add_column("path")

    drafts_dir = _drafts_dir()
    for path in sorted(drafts_dir.glob("*.json")):
        try:
            draft = FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
        except FilingDraftError:
            _logger.warning("Skipping invalid draft file: %s", path)
            continue
        if modelo is not None and draft.modelo != modelo:
            continue
        if target_status is not None and draft.status is not target_status:
            continue
        table.add_row(
            draft.draft_id,
            draft.modelo,
            draft.period,
            draft.status.value,
            str(path),
        )
    _console.print(table)


__all__ = ["app"]
