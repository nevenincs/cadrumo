"""``aeat filing`` sub-app — filing draft engine CLI.

Subcommands:

- ``aeat filing build`` — build a draft from a JSON inputs file.
- ``aeat filing validate`` — re-validate a saved draft.
- ``aeat filing show`` — pretty-print a draft.
- ``aeat filing list`` — list drafts under the configured drafts dir.
- ``aeat filing import`` — reconstruct a draft from a justificante /
  declaración / borrador PDF.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

if TYPE_CHECKING:
    from ....domain.filing._repository import FilingDraftRepository

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from ....adapters.persistence.storage.errors import StorageError
from ....application.filing import (
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
    refresh_review_status,
    validate_draft,
)
from ....application.filing.runtime import build_runtime_schema_provider, load_default_filing_profile
from ....core.config import load_settings
from ....core.logging import get_logger
from ....domain.justificante import JustificanteError
from ....domain.submission import SubmissionError, SubmissionRepository, SubmittedFiling
from .._i18n import output_language as _output_language
from .._i18n import tr

app = typer.Typer(
    name="filing",
    no_args_is_help=True,
    help=tr("cli.filing.app_help"),
)
complementaria_app = typer.Typer(
    name="complementaria",
    no_args_is_help=True,
    help=tr("cli.filing.complementaria.app_help"),
)

_console = Console()
_logger = get_logger(__name__)


def _load_submission_record(submission_id: str) -> SubmittedFiling:
    """Read an encrypted persisted submission record for amendment assembly."""
    repository = SubmissionRepository()
    try:
        loaded = repository.load(submission_id)
    except ValueError as exc:
        raise SubmissionError(str(exc)) from exc
    except (OSError, ValidationError, StorageError) as exc:
        raise SubmissionError(
            tr("cli.filing.errors.submission_validation_failed", path=repository.envelope_path_for(submission_id)),
        ) from exc
    if loaded is None:
        raise SubmissionError(
            f"{tr('cli.filing.errors.submission_not_found', id=submission_id)}: {submission_id}",
        )
    return loaded


def _schema_provider():
    """Return the production filing schema provider."""
    return build_runtime_schema_provider()


def _load_inputs(path: Path) -> dict[str, object]:
    """Load and parse a JSON inputs file from disk."""
    if not path.exists():
        raise typer.BadParameter(tr("cli.filing.errors.inputs_not_found", path=path))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _logger.warning("_load_inputs: invalid JSON in %s", path, exc_info=True)
        raise typer.BadParameter(
            tr("cli.filing.errors.invalid_json", path=path, exc=str(exc)),
        ) from exc
    if not isinstance(raw, dict):
        raise typer.BadParameter(tr("cli.filing.errors.inputs_not_object", path=path))
    parsed: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise typer.BadParameter(
                tr("cli.filing.errors.casilla_key_not_string", type=type(key).__name__),
            )
        if isinstance(value, str | int | bool) or value is None:
            parsed[key] = value
        elif isinstance(value, float):
            # Use Decimal so monetary precision is preserved.
            parsed[key] = Decimal(str(value))
        else:
            raise typer.BadParameter(
                tr(
                    "cli.filing.errors.unsupported_value_type",
                    field=key,
                    type=type(value).__name__,
                ),
            )
    return parsed


def _draft_repository() -> FilingDraftRepository:
    """Return the SQL-backed FilingDraftRepository.

    Imports are deferred to avoid pulling aeat.adapters.persistence.storage (and Alembic
    plugin discovery) into CLI commands that never persist a draft.
    """
    from ....domain.filing._repository import FilingDraftRepository

    return FilingDraftRepository()


def _load_draft(path: Path) -> FilingDraft:
    """Load a persisted draft, given a draft id or a logical envelope path.

    The filing draft repository persists every draft as an encrypted
    object in the SQL backend. ``envelope_path_for(draft_id)`` returns
    a logical ``db://`` path whose final segment IS the draft id; this
    helper accepts that logical path, the bare draft id, or a legacy
    on-disk ``<draft_id>.envelope.json`` filename.

    Raises:
        :exc:`typer.BadParameter`: If no draft matches the resolved id
            in the secure-object backend.
    """
    repository = _draft_repository()
    draft_id = _draft_id_from_argument(path)
    loaded = repository.load(draft_id)
    if loaded is None:
        raise typer.BadParameter(tr("cli.filing.errors.failed_to_load_draft", path=path))
    return loaded


def _draft_id_from_argument(path: Path) -> str:
    """Return the draft id encoded in a CLI ``Path`` argument.

    Accepts a logical SQL path (final segment is the id), a legacy
    ``<draft_id>.envelope.json`` filename (strip the suffix), or the
    bare draft id wrapped in a Path (use as-is).
    """
    name = path.name
    if name.endswith(".envelope.json"):
        return name[: -len(".envelope.json")]
    return name


def _refresh_persisted_draft(path: Path, draft: FilingDraft | None = None) -> FilingDraft:
    """Refresh review status for a persisted draft and rewrite it when needed."""
    loaded = draft or _load_draft(path)
    refreshed = refresh_review_status(
        loaded,
        schema_provider=_schema_provider(),
    )
    if refreshed != loaded:
        _draft_repository().save(refreshed)
    return refreshed


def _save_draft(draft: FilingDraft) -> Path:
    """Write a draft through the FilingDraftRepository (ciphertext-at-rest)."""
    repository = _draft_repository()
    repository.save(draft)
    return repository.envelope_path_for(draft.draft_id)


def _load_persisted_draft_by_id(draft_id: str) -> FilingDraft | None:
    """Resolve a draft by its content-addressed id via the repository."""
    repository = _draft_repository()
    loaded = repository.load(draft_id)
    if loaded is None:
        return None
    refreshed = refresh_review_status(
        loaded,
        schema_provider=_schema_provider(),
    )
    if refreshed != loaded:
        repository.save(refreshed)
    return refreshed


def _render_draft_next_steps(draft: FilingDraft, *, draft_path: Path) -> None:
    """Print the most likely next operator commands for ``draft``."""

    next_label = tr("cli.filing.draft.next_steps_label")
    you = tr("cli.filing.draft.approved_by_you")
    if draft.status is FilingDraftStatus.APPROVED:
        _console.print(f"{next_label} aeat submission preflight {draft_path}")
        _console.print(f"{next_label} aeat submission export {draft_path}")
        return
    if draft.status is FilingDraftStatus.APPROVAL_STALE:
        _console.print(f"{next_label} aeat review show {draft.draft_id}")
        _console.print(f"{next_label} aeat review approve {draft.draft_id} --approved-by {you}")
        return
    _console.print(f"{next_label} aeat review show {draft.draft_id}")
    if draft.status is FilingDraftStatus.READY_TO_SUBMIT:
        _console.print(f"{next_label} aeat review approve {draft.draft_id} --approved-by {you}")


def _parse_json_argument(raw: str) -> dict[str, object]:
    """Parse ``raw`` as either an inline JSON object or a JSON file path."""
    candidate = Path(raw)
    payload_text = candidate.read_text(encoding="utf-8") if candidate.exists() else raw
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        _logger.warning("_parse_json_argument: invalid JSON in %r", raw, exc_info=True)
        raise typer.BadParameter(
            tr("cli.filing.errors.invalid_json", path=raw, exc=str(exc)),
        ) from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter(tr("cli.filing.errors.inputs_not_object", path=raw))
    return payload


def _parse_amendment_inputs(raw_inputs: Mapping[str, object]) -> dict[str, object]:
    """Coerce the amendment input payload into filing-builder-compatible values."""
    parsed: dict[str, object] = {}
    for key, value in raw_inputs.items():
        if not isinstance(key, str):
            raise typer.BadParameter(
                tr("cli.filing.errors.casilla_key_not_string", type=type(key).__name__),
            )
        if isinstance(value, dict):
            parsed[key] = _parse_amendment_inputs(cast(Mapping[str, object], value))
        elif isinstance(value, str | int | bool) or value is None:
            parsed[key] = value
        elif isinstance(value, float):
            parsed[key] = Decimal(str(value))
        else:
            raise typer.BadParameter(
                tr(
                    "cli.filing.errors.unsupported_value_type",
                    field=key,
                    type=type(value).__name__,
                ),
            )
    return parsed


def _render_amendment(amendment: FilingAmendment) -> None:
    """Pretty-print a built amendment for operator review."""
    header = Table(
        title=tr("cli.filing.amendment.title", id=amendment.amendment_id),
        show_header=False,
    )
    header.add_row(tr("cli.filing.field.submission_id"), amendment.submission_id)
    header.add_row(tr("cli.filing.field.modelo"), amendment.original_model)
    header.add_row(tr("cli.filing.field.period"), amendment.original_period)
    header.add_row(tr("cli.filing.field.kind"), amendment.amendment_kind.value)
    header.add_row(tr("cli.filing.field.original_csv"), amendment.original_csv)
    header.add_row(tr("cli.filing.field.created_at"), amendment.created_at.isoformat())
    _console.print(header)

    delta_table = Table(title=tr("cli.filing.amendment.delta_table_title"))
    delta_table.add_column(tr("cli.filing.field.casilla"))
    delta_table.add_column(tr("cli.filing.field.old"))
    delta_table.add_column(tr("cli.filing.field.new"))
    delta_table.add_column(tr("cli.filing.field.reason"))
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
        header = Table(title=tr("cli.filing.draft.title", id=draft.draft_id), show_header=False)
        header.add_row(tr("cli.filing.field.modelo"), draft.modelo)
        header.add_row(tr("cli.filing.field.period"), draft.period)
        header.add_row(tr("cli.filing.field.profile_tax_id"), draft.profile_tax_id)
        header.add_row(tr("cli.filing.field.status"), draft.status.value)
        header.add_row(tr("cli.filing.field.schema_version"), draft.schema_version)
        header.add_row(tr("cli.filing.field.created_at"), draft.created_at.isoformat())
        header.add_row(tr("cli.filing.field.updated_at"), draft.updated_at.isoformat())
        if draft.approved_at is not None:
            header.add_row(tr("cli.filing.field.approved_at"), draft.approved_at.isoformat())
        if draft.approved_by is not None:
            header.add_row(tr("cli.filing.field.approved_by"), draft.approved_by)
        if draft.review_checksum is not None:
            header.add_row(tr("cli.filing.field.review_checksum"), draft.review_checksum)
        if draft.status is FilingDraftStatus.APPROVAL_STALE:
            reasons = approval_stale_reasons(
                draft,
                schema_provider=_schema_provider(),
            )
            if reasons:
                header.add_row(
                    tr("cli.filing.field.stale_reason"),
                    ", ".join(describe_stale_reason(reason) for reason in reasons),
                )
        _console.print(header)

        values_table = Table(title=tr("cli.filing.draft.values_table_title"), show_lines=False)
        values_table.add_column(tr("cli.filing.field.casilla"))
        values_table.add_column(tr("cli.filing.field.kind"))
        values_table.add_column(tr("cli.filing.field.value"))
        values_table.add_column(tr("cli.filing.field.source"))
        for value in draft.values:
            values_table.add_row(
                value.casilla_id,
                value.kind.value,
                "" if value.value is None else str(value.value),
                value.source,
            )
        _console.print(values_table)

    findings_table = Table(title=tr("cli.filing.init.findings_table_title"))
    findings_table.add_column(tr("cli.filing.field.severity"))
    findings_table.add_column(tr("cli.filing.field.code"))
    findings_table.add_column(tr("cli.filing.field.casilla"))
    findings_table.add_column(tr("cli.filing.field.message"))
    for finding in draft.findings:
        findings_table.add_row(
            finding.severity.value,
            finding.code,
            finding.casilla_id or "-",
            tr(str(finding.message)),
        )
    _console.print(findings_table)


@app.command("build")
def build(
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.filing.build.modelo_help"))],
    period: Annotated[str, typer.Option("--period", help=tr("cli.filing.build.period_help"))],
    inputs: Annotated[
        Path,
        typer.Option("--inputs", help=tr("cli.filing.build.inputs_help")),
    ],
    profile_tax_id: Annotated[
        str | None,
        typer.Option(
            "--profile-tax-id",
            help=tr("cli.filing.build.profile_tax_id_help"),
        ),
    ] = None,
    profile_name: Annotated[
        str | None,
        typer.Option("--profile-name", help=tr("cli.filing.build.profile_name_help")),
    ] = None,
) -> None:
    """Build a draft from a JSON inputs file and save it to disk."""
    settings = load_settings()
    parsed_inputs = _load_inputs(inputs)
    operator_profile: FilingOperatorProfile
    if profile_tax_id is None:
        try:
            operator_profile = load_default_filing_profile(display_name=profile_name)
        except FilingDraftError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        operator_profile = FilingOperatorProfile(
            tax_id=profile_tax_id,
            display_name=profile_name or profile_tax_id,
        )
    _logger.info("filing build: starting draft build for Modelo %s period %s", modelo, period)
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
        _logger.warning(
            "filing build: draft build failed for modelo %s period %s",
            modelo,
            period,
            exc_info=True,
        )
        raise typer.BadParameter(str(exc)) from exc
    saved = _save_draft(draft)
    _logger.info(
        "filing build: draft %s saved for Modelo %s period %s (status=%s)",
        draft.draft_id,
        modelo,
        period,
        draft.status.value,
    )
    typer.echo(tr("cli.filing.build.success"))
    _render_draft(draft)
    _render_draft_next_steps(draft, draft_path=saved)


@app.command("validate")
def validate(
    draft_path: Annotated[Path, typer.Argument(help=tr("cli.filing.validate.draft_path_help"))],
) -> None:
    """Re-validate an existing draft and rewrite it through the repository."""
    _logger.info("filing validate: re-validating draft at %s", draft_path)
    draft = _load_draft(draft_path)
    refreshed = validate_draft(
        draft,
        schema_provider=_schema_provider(),
    )
    refreshed = _refresh_persisted_draft(draft_path, refreshed)
    _draft_repository().save(refreshed)
    _logger.info(
        "filing validate: draft %s re-validated (status=%s)",
        refreshed.draft_id,
        refreshed.status.value,
    )
    typer.echo(tr("cli.filing.validate.success"))
    _render_draft(refreshed)
    _render_draft_next_steps(refreshed, draft_path=draft_path)


@app.command("show")
def show(
    draft_path: Annotated[Path, typer.Argument(help=tr("cli.filing.validate.draft_path_help"))],
    findings_only: Annotated[
        bool,
        typer.Option("--findings-only", help=tr("cli.filing.show.findings_only_help")),
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
        typer.Option("--modelo", help=tr("cli.filing.list.modelo_help")),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help=tr("cli.filing.list.status_help")),
    ] = None,
) -> None:
    """List drafts in the configured drafts directory."""
    target_status: FilingDraftStatus | None = None
    if status is not None:
        try:
            target_status = FilingDraftStatus(status)
        except ValueError as exc:
            valid_statuses = ", ".join(s.value for s in FilingDraftStatus)
            raise typer.BadParameter(
                tr("cli.filing.errors.invalid_status", status=status, valid=valid_statuses)
            ) from exc

    table = Table(title=tr("cli.filing.list.table_title"))
    table.add_column(tr("cli.filing.field.draft_id"))
    table.add_column(tr("cli.filing.field.modelo"))
    table.add_column(tr("cli.filing.field.period"))
    table.add_column(tr("cli.filing.field.status"))
    table.add_column(tr("cli.filing.field.approved_by"))
    table.add_column(tr("cli.filing.field.path"))

    repository = _draft_repository()
    for draft in repository.iter_drafts():
        refreshed = _refresh_persisted_draft(repository.envelope_path_for(draft.draft_id), draft)
        if modelo is not None and refreshed.modelo != modelo:
            continue
        if target_status is not None and refreshed.status is not target_status:
            continue
        table.add_row(
            refreshed.draft_id,
            refreshed.modelo,
            refreshed.period,
            refreshed.status.value,
            refreshed.approved_by or "-",
            str(repository.envelope_path_for(refreshed.draft_id)),
        )
    _console.print(table)


@app.command("import")
def import_(
    from_justificante: Annotated[
        Path | None,
        typer.Option(
            "--from-justificante",
            help=tr("cli.filing.import.from_justificante_help"),
        ),
    ] = None,
    from_declaracion: Annotated[
        Path | None,
        typer.Option(
            "--from-declaracion",
            help=tr("cli.filing.import.from_declaracion_help"),
        ),
    ] = None,
    from_borrador: Annotated[
        Path | None,
        typer.Option(
            "--from-borrador",
            help=tr("cli.filing.import.from_borrador_help"),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            help=tr("cli.filing.import.modelo_help"),
        ),
    ] = None,
    año: Annotated[
        int | None,
        typer.Option(
            "--año",
            help=tr("cli.filing.import.año_help"),
        ),
    ] = None,
) -> None:
    """Import a past filing from an AEAT PDF."""
    provided = sum(bool(flag) for flag in (from_justificante, from_declaracion, from_borrador))
    if provided == 0:
        raise typer.BadParameter(tr("cli.filing.errors.missing_import_source"))
    if provided > 1:
        raise typer.BadParameter(tr("cli.filing.errors.multiple_import_sources"))

    if from_justificante is not None:
        _handle_justificante_import(from_justificante)
        return
    if from_declaracion is not None:
        _handle_declaracion_import(from_declaracion, modelo=modelo, año=año)
        return

    assert from_borrador is not None
    _handle_borrador_import(from_borrador, año=año)


def _handle_justificante_import(from_justificante: Path) -> None:
    """Dispatch the justificante import path."""
    _logger.info("filing import: importing from justificante %s", from_justificante)
    try:
        result = import_filing_from_justificante(
            from_justificante,
            schema_provider=_schema_provider(),
        )
    except (FilingImportError, FilingDraftError, JustificanteError) as exc:
        _logger.warning(
            "filing import: justificante import failed for %s",
            from_justificante,
            exc_info=True,
        )
        raise typer.BadParameter(str(exc)) from exc

    _save_draft(result.draft)
    from ....domain.submission._repository import SubmissionRepository

    submission_repository = SubmissionRepository()
    submission_repository.save(result.submission)
    submission_repository.envelope_path_for(result.submission.submission_id)
    _logger.info(
        "filing import: justificante import complete (draft=%s submission=%s warnings=%d)",
        result.draft.draft_id,
        result.submission.submission_id,
        len(result.warnings),
    )

    typer.echo(tr("cli.filing.import.justificante_success"))
    typer.echo(tr("cli.filing.import.scaffold_created"))
    _output_language()
    warning_label = tr("cli.filing.import.warning_label")
    for warning in result.warnings:
        rendered = warning
        typer.echo(f"{warning_label} {rendered}")
    _render_draft(result.draft)


# `_output_language` / `_t` / `_msg` are imported from `..._i18n`
# at the module top so every CLI submodule shares the same
# multilingual helper surface; local copies are forbidden.


def _handle_declaracion_import(
    from_declaracion: Path,
    *,
    modelo: str | None,
    año: int | None,
) -> None:
    """Dispatch the declaración import path."""
    from ....adapters.inbound.declaracion import DeclaracionParseError, parse_declaracion
    from ....application.verification import VerificationError, verify_declaracion

    try:
        filing = parse_declaracion(
            from_declaracion,
            modelo_override=modelo,
            año_override=año,
        )
    except DeclaracionParseError as exc:
        _logger.warning(
            "filing import: declaracion parse failed for %s",
            from_declaracion,
            exc_info=True,
        )
        raise typer.BadParameter(str(exc)) from exc

    _output_language()
    typer.echo(tr("cli.filing.import.importing_declaration"))
    typer.echo(tr("cli.filing.import.extraction_complete"))
    if filing.warnings:
        typer.echo(tr("cli.filing.import.warnings_found"))
        casilla_label = tr("cli.filing.import.casilla_label")
        for warning in filing.warnings:
            rendered = warning.message
            typer.echo(f"  - {casilla_label} {warning.casilla_id or '-'}: {rendered}")

    try:
        verdict = verify_declaracion(filing)
    except VerificationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(tr("cli.filing.import.verification_result"))
    typer.echo(f"  {verdict.narrative}")
    casilla_label = tr("cli.filing.import.casilla_label")
    expected_label = tr("cli.filing.import.expected")
    actual_label = tr("cli.filing.import.actual")
    cause_label = tr("cli.filing.import.cause")
    for discrepancy in verdict.discrepancies:
        rationale = discrepancy.cause_rationale
        typer.echo(
            f"  - {casilla_label} {discrepancy.casilla_id}: "
            f"{expected_label} {discrepancy.expected}, {actual_label} {discrepancy.actual}, "
            f"{cause_label}={discrepancy.cause.value} — {rationale}"
        )


def _handle_borrador_import(
    from_borrador: Path,
    *,
    año: int | None,
) -> None:
    """Reject Renta import verification until registry snapshots exist."""

    _ = (from_borrador, año)
    raise typer.BadParameter(tr("cli.filing.import.borrador_unsupported"))


@complementaria_app.command("build")
def build_complementaria_cmd(
    modelo: Annotated[str, typer.Argument(help=tr("cli.filing.build.modelo_help"))],
    period: Annotated[str, typer.Argument(help=tr("cli.filing.build.period_help"))],
    delta_json: Annotated[
        str,
        typer.Argument(
            help=tr("cli.filing.complementaria.build.delta_json_help"),
        ),
    ],
) -> None:
    """Build an amendment from a persisted submission plus revised inputs."""
    payload = _parse_json_argument(delta_json)
    original_submission_id = payload.get("original_submission_id")
    if not isinstance(original_submission_id, str) or not original_submission_id:
        raise typer.BadParameter(tr("cli.filing.errors.missing_original_submission_id"))
    raw_inputs = payload.get("updated_inputs")
    if not isinstance(raw_inputs, dict):
        raise typer.BadParameter(tr("cli.filing.errors.missing_updated_inputs"))
    reasons = payload.get("reasons")
    parsed_inputs = _parse_amendment_inputs(cast(Mapping[str, object], raw_inputs))
    if reasons is not None:
        if not isinstance(reasons, dict):
            raise typer.BadParameter(tr("cli.filing.errors.reasons_not_object"))
        parsed_inputs["_reasons"] = _parse_amendment_inputs(cast(Mapping[str, object], reasons))

    try:
        original = _load_submission_record(original_submission_id)
        if original.modelo != modelo:
            raise typer.BadParameter(tr("cli.filing.errors.modelo_mismatch", modelo=modelo, original=original.modelo))
        if original.period != period:
            raise typer.BadParameter(tr("cli.filing.errors.period_mismatch", period=period, original=original.period))
        amendment = build_complementaria(original, parsed_inputs, schema_provider=_schema_provider())
    except (SubmissionError, FilingAmendmentError, FilingDraftError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _save_draft(amendment.amended_draft)
    amended_draft_id = amendment.amended_draft.draft_id
    typer.echo(tr("cli.filing.errors.amendment_success"))
    next_label = tr("cli.filing.draft.next_steps_label")
    _console.print(f"{next_label} aeat review show {amended_draft_id}")
    _console.print(
        f"{next_label} aeat review approve {amended_draft_id} --approved-by {tr('cli.filing.draft.approved_by_you')}"
    )
    _render_amendment(amendment)


app.add_typer(
    complementaria_app,
    name="complementaria",
    help=tr("cli.filing.complementaria.app_help"),
)


__all__ = ["app"]
