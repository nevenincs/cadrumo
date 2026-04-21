"""``aeat filing`` sub-app — filing draft engine CLI (#39).

Subcommands:

- ``aeat filing build`` — build a draft from a JSON inputs file.
- ``aeat filing validate`` — re-validate a saved draft.
- ``aeat filing show`` — pretty-print a draft.
- ``aeat filing list`` — list drafts under the configured drafts dir.
- ``aeat filing import`` — reconstruct a draft from a justificante PDF
  (#271; cert-free, offline).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from ...config import load_settings
from ...filing import (
    FilingAmendment,
    FilingAmendmentError,
    FilingDraft,
    FilingDraftError,
    FilingDraftStatus,
    FilingFindingSeverity,
    FilingImportError,
    FilingOperatorProfile,
    approval_stale_reasons,
    build_complementaria,
    build_draft,
    describe_stale_reason,
    import_filing_from_justificante,
    iter_findings,
    load_amendment,
    refresh_review_status,
    validate_draft,
)
from ...filing.runtime import build_runtime_schema_provider, load_default_filing_profile
from ...i18n import Language, get_translation
from ...justificante import JustificanteError
from ...logging import get_logger
from ...submission import SubmissionEngine, SubmissionError
from ..submission._helpers import build_engine as build_submission_engine

app = typer.Typer(
    name="filing",
    no_args_is_help=True,
    help="Filing draft engine commands (#39).",
)
complementaria_app = typer.Typer(
    name="complementaria",
    no_args_is_help=True,
    help="Build and submit amendment filings (#93).",
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


def _submission_engine() -> SubmissionEngine:
    """Return a submission engine instance for amendment commands."""
    return build_submission_engine()


def _schema_provider():
    """Return the production filing schema provider."""
    return build_runtime_schema_provider()


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


def _refresh_persisted_draft(path: Path, draft: FilingDraft | None = None) -> FilingDraft:
    """Refresh review status for a persisted draft and rewrite it when needed."""

    loaded = draft or _load_draft(path)
    refreshed = refresh_review_status(
        loaded,
        schema_provider=_schema_provider(),
    )
    if refreshed != loaded:
        path.write_text(refreshed.model_dump_json(indent=2), encoding="utf-8")
    return refreshed


def _save_draft(draft: FilingDraft) -> Path:
    """Write a draft to the configured drafts directory."""
    target = _drafts_dir() / _draft_filename(draft)
    target.write_text(
        draft.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return target


def _parse_json_argument(raw: str) -> dict[str, object]:
    """Parse ``raw`` as either an inline JSON object or a JSON file path."""
    candidate = Path(raw)
    payload_text = candidate.read_text(encoding="utf-8") if candidate.exists() else raw
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"invalid amendment JSON {raw!r}: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("amendment payload must be a JSON object")
    return payload


def _parse_amendment_inputs(raw_inputs: Mapping[str, object]) -> dict[str, object]:
    """Coerce the amendment input payload into filing-builder-compatible values."""
    parsed: dict[str, object] = {}
    for key, value in raw_inputs.items():
        if not isinstance(key, str):
            raise typer.BadParameter(f"updated input key must be a string, got {type(key).__name__}")
        if isinstance(value, dict):
            parsed[key] = _parse_amendment_inputs(cast(Mapping[str, object], value))
        elif isinstance(value, str | int | bool) or value is None:
            parsed[key] = value
        elif isinstance(value, float):
            parsed[key] = Decimal(str(value))
        else:
            raise typer.BadParameter(f"unsupported amendment value type for {key!r}: {type(value).__name__}")
    return parsed


def _render_amendment(amendment: FilingAmendment) -> None:
    """Pretty-print a built amendment for operator review."""
    header = Table(title=f"Amendment {amendment.amendment_id}", show_header=False)
    header.add_row("submission_id", amendment.submission_id)
    header.add_row("modelo", amendment.original_model)
    header.add_row("period", amendment.original_period)
    header.add_row("kind", amendment.amendment_kind.value)
    header.add_row("original_csv", amendment.original_csv)
    header.add_row("created_at", amendment.created_at.isoformat())
    _console.print(header)

    delta_table = Table(title="Casilla delta")
    delta_table.add_column("casilla")
    delta_table.add_column("old")
    delta_table.add_column("new")
    delta_table.add_column("reason")
    for change in amendment.delta:
        delta_table.add_row(
            change.casilla_code,
            "" if change.old_value is None else str(change.old_value),
            str(change.new_value),
            change.reason,
        )
    _console.print(delta_table)


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
        if draft.approved_at is not None:
            header.add_row("approved_at", draft.approved_at.isoformat())
        if draft.approved_by is not None:
            header.add_row("approved_by", draft.approved_by)
        if draft.review_checksum is not None:
            header.add_row("review_checksum", draft.review_checksum)
        if draft.status is FilingDraftStatus.APPROVAL_STALE:
            reasons = approval_stale_reasons(
                draft,
                schema_provider=_schema_provider(),
            )
            if reasons:
                header.add_row(
                    "stale_reason",
                    ", ".join(describe_stale_reason(reason) for reason in reasons),
                )
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
    profile: Annotated[
        Path | None,
        typer.Option(
            "--profile",
            help="Optional path to an AutonomoProfile JSON file (defaults to AEAT_DEFAULT_PROFILE_PATH).",
        ),
    ] = None,
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
    resolved_display_name = None if profile_name == _DEFAULT_PROFILE_NAME else profile_name
    operator_profile: FilingOperatorProfile
    if profile is not None:
        try:
            operator_profile = load_default_filing_profile(profile, display_name=resolved_display_name)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    elif (
        settings.aeat_default_profile_path is not None
        and profile_tax_id == _DEFAULT_PROFILE_TAX_ID
        and profile_name == _DEFAULT_PROFILE_NAME
    ):
        try:
            operator_profile = load_default_filing_profile(display_name=resolved_display_name)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        operator_profile = FilingOperatorProfile(
            tax_id=profile_tax_id,
            display_name=profile_name,
            applicable_modelos=(modelo,),
        )
    try:
        draft = build_draft(
            modelo=modelo,
            period=period,
            profile=operator_profile,
            inputs=parsed_inputs,
            schema_provider=_schema_provider(),
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
        schema_provider=_schema_provider(),
    )
    refreshed = _refresh_persisted_draft(draft_path, refreshed)
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
    draft = _refresh_persisted_draft(draft_path)
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
    table.add_column("approved_by")
    table.add_column("path")

    drafts_dir = _drafts_dir()
    for path in sorted(drafts_dir.glob("*.json")):
        try:
            draft = FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
        except FilingDraftError:
            _logger.warning("Skipping invalid draft file: %s", path)
            continue
        draft = _refresh_persisted_draft(path, draft)
        if modelo is not None and draft.modelo != modelo:
            continue
        if target_status is not None and draft.status is not target_status:
            continue
        table.add_row(
            draft.draft_id,
            draft.modelo,
            draft.period,
            draft.status.value,
            draft.approved_by or "-",
            str(path),
        )
    _console.print(table)


@app.command("import")
def import_(
    from_justificante: Annotated[
        Path | None,
        typer.Option(
            "--from-justificante",
            help="Path to an AEAT justificante (receipt) PDF; produces a metadata scaffold draft (#271).",
        ),
    ] = None,
    from_declaracion: Annotated[
        Path | None,
        typer.Option(
            "--from-declaracion",
            help=(
                "Path to an AEAT declaración (full filing copy) PDF; "
                "produces a casilla-complete draft (#305 cluster D)."
            ),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            help="Override auto-detected modelo (e.g. '130'). Only used with --from-declaracion.",
        ),
    ] = None,
    año: Annotated[
        int | None,
        typer.Option(
            "--año",
            help="Override auto-detected tax year. Only used with --from-declaracion.",
        ),
    ] = None,
) -> None:
    """Import a past filing from an AEAT PDF.

    Exactly one of ``--from-justificante`` or ``--from-declaracion``
    must be supplied.

    ``--from-justificante`` reconstructs a metadata scaffold draft +
    companion submission record from the filing receipt (#271). Every
    casilla lands EMPTY.

    ``--from-declaracion`` parses the full filing copy PDF and extracts
    every printed casilla value; produces a casilla-complete draft
    ready for ``aeat filing verify`` (#305 cluster D / E).
    """
    provided = sum(p is not None for p in (from_justificante, from_declaracion))
    if provided == 0:
        raise typer.BadParameter("exactly one of --from-justificante or --from-declaracion is required")
    if provided > 1:
        raise typer.BadParameter("only one --from-* flag at a time: --from-justificante or --from-declaracion")

    if from_justificante is not None:
        _handle_justificante_import(from_justificante)
        return

    assert from_declaracion is not None  # narrowed by the sum-check above
    _handle_declaracion_import(from_declaracion, modelo=modelo, año=año)


def _handle_justificante_import(from_justificante: Path) -> None:
    """Dispatch the justificante (#271) import path."""
    settings = load_settings()
    try:
        result = import_filing_from_justificante(
            from_justificante,
            schema_provider=_schema_provider(),
        )
    except (FilingImportError, FilingDraftError, JustificanteError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    draft_path = _save_draft(result.draft)
    submissions_dir = settings.aeat_submissions_dir
    submissions_dir.mkdir(parents=True, exist_ok=True)
    submission_path = submissions_dir / f"{result.submission.submission_id}.json"
    submission_path.write_text(result.submission.model_dump_json(indent=2), encoding="utf-8")

    typer.echo(
        f"Imported draft {result.draft.draft_id} from justificante {result.submission.justificante_csv} -> {draft_path}"
    )
    typer.echo(f"Saved submission {result.submission.submission_id} -> {submission_path}")
    for warning in result.warnings:
        rendered = get_translation(warning, Language.EN)
        typer.echo(f"[warning] {rendered}")
    _render_draft(result.draft)


def _handle_declaracion_import(
    from_declaracion: Path,
    *,
    modelo: str | None,
    año: int | None,
) -> None:
    """Dispatch the declaración (#305 cluster D) import path."""
    from ...declaracion import DeclaracionParseError, parse_declaracion

    try:
        filing = parse_declaracion(
            from_declaracion,
            modelo_override=modelo,
            año_override=año,
        )
    except DeclaracionParseError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"Parsed Modelo {filing.modelo} {filing.period} declaración "
        f"(template {filing.template_revision.revision}). "
        f"{len(filing.values)} of {len(filing.values) + len(filing.warnings)} casillas extracted."
    )
    typer.echo(f"Status: {filing.extraction_status.value}")
    if filing.warnings:
        typer.echo(f"[warnings] {len(filing.warnings)}:")
        for warning in filing.warnings:
            rendered = get_translation(warning.message, Language.EN)
            typer.echo(f"  - casilla {warning.casilla_id or '-'}: {rendered}")


@complementaria_app.command("build")
def build_complementaria_cmd(
    modelo: Annotated[str, typer.Argument(help="Modelo string ID, e.g. 130")],
    period: Annotated[str, typer.Argument(help="Period identifier, e.g. 2024Q1")],
    delta_json: Annotated[
        str,
        typer.Argument(
            help="Inline JSON object or path to JSON with original_submission_id + updated_inputs",
        ),
    ],
) -> None:
    """Build an amendment from a persisted submission plus revised inputs."""
    payload = _parse_json_argument(delta_json)
    original_submission_id = payload.get("original_submission_id")
    if not isinstance(original_submission_id, str) or not original_submission_id:
        raise typer.BadParameter("amendment payload must include non-empty 'original_submission_id'")
    raw_inputs = payload.get("updated_inputs")
    if not isinstance(raw_inputs, dict):
        raise typer.BadParameter("amendment payload must include object 'updated_inputs'")
    reasons = payload.get("reasons")
    parsed_inputs = _parse_amendment_inputs(cast(Mapping[str, object], raw_inputs))
    if reasons is not None:
        if not isinstance(reasons, dict):
            raise typer.BadParameter("'reasons' must be a JSON object of casilla -> reason")
        parsed_inputs["_reasons"] = _parse_amendment_inputs(cast(Mapping[str, object], reasons))

    engine = _submission_engine()
    original = engine.load_submission(original_submission_id)
    if original.modelo != modelo:
        raise typer.BadParameter(
            f"payload modelo {modelo!r} does not match original submission modelo {original.modelo!r}"
        )
    if original.period != period:
        raise typer.BadParameter(
            f"payload period {period!r} does not match original submission period {original.period!r}"
        )
    try:
        amendment = build_complementaria(original, parsed_inputs)
    except FilingAmendmentError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _render_amendment(amendment)


@complementaria_app.command("submit")
def submit_complementaria_cmd(
    amendment_id: Annotated[str, typer.Argument(help="Persisted amendment id to submit")],
    live: Annotated[
        bool,
        typer.Option("--live", help="Perform a live submission instead of the safe dry-run default."),
    ] = False,
) -> None:
    """Submit a persisted amendment, dry-run by default."""
    amendment = load_amendment(amendment_id)
    engine = _submission_engine()

    dry_run = not live
    try:
        submission_result = asyncio.run(
            engine.submit_amendment(
                amendment,
                dry_run=dry_run,
            )
        )
    except SubmissionError as exc:
        _console.print(f"[red]refusing:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    status_label = "dry-run" if submission_result.dry_run else "LIVE"
    typer.echo(
        f"{status_label} amendment submission OK amendment_id={submission_result.amendment_id} "
        f"submission_id={submission_result.filing.submission_id} "
        f"status={submission_result.filing.status.value}"
    )


app.add_typer(complementaria_app, name="complementaria", help="Build and submit amendment filings (#93).")


__all__ = ["app"]
