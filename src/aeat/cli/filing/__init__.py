"""``aeat filing`` sub-app — filing draft engine CLI (#39).

Subcommands:

- ``aeat filing build`` — build a draft from a JSON inputs file.
- ``aeat filing validate`` — re-validate a saved draft.
- ``aeat filing show`` — pretty-print a draft.
- ``aeat filing list`` — list drafts under the configured drafts dir.
- ``aeat filing import`` — reconstruct a draft from a justificante /
  declaración / borrador PDF (#271, #305).
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
from ._reconcile import register as _register_reconcile

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


def _draft_repository():  # type: ignore[no-untyped-def]
    """Return a FilingDraftRepository bound to the configured drafts dir.

    Imports are deferred to avoid pulling aeat.storage (and Alembic
    plugin discovery) into CLI commands that never persist a draft.
    """
    from ...filing._repository import FilingDraftRepository

    return FilingDraftRepository(store_dir=_drafts_dir())


def _load_draft(path: Path) -> FilingDraft:
    """Load and parse a draft.

    Wave-8 silent-leaker close: every NEW draft is ciphertext-at-rest
    via FilingDraftRepository. Reads honour both formats so an operator
    who has legacy plaintext drafts on disk can still read them; on
    the next save the draft is re-persisted as ciphertext.
    """
    if not path.exists():
        raise typer.BadParameter(f"draft file not found: {path}")
    if path.name.endswith(".envelope.json"):
        # New ciphertext-at-rest path — load via the repository so the
        # AAD-bound classification gate fires.
        repository = _draft_repository()
        draft_id = path.name[: -len(".envelope.json")]
        loaded = repository.load(draft_id)
        if loaded is None:
            raise typer.BadParameter(f"draft envelope not found: {path}")
        return loaded
    # Legacy plaintext fallback — kept readable for operator migration.
    try:
        return FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
    except FilingDraftError as exc:
        raise typer.BadParameter(f"invalid draft in {path}: {exc}") from exc


def _refresh_persisted_draft(path: Path, draft: FilingDraft | None = None) -> FilingDraft:
    """Refresh review status for a persisted draft and rewrite it when needed.

    Rewrites always go through FilingDraftRepository (ciphertext) — even
    when the load came from a legacy plaintext file. The legacy file is
    NOT deleted; the next read still finds it via the same path until
    operators migrate.
    """

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
    """Resolve a draft by its content-addressed id.

    Tries the FilingDraftRepository first (new ciphertext envelopes),
    then falls back to the legacy plaintext filename pattern so
    operators who have not yet migrated keep working.
    """
    repository = _draft_repository()
    via_repo = repository.load(draft_id)
    if via_repo is not None:
        # Refresh review status via the repository write path.
        refreshed = refresh_review_status(
            via_repo,
            schema_provider=_schema_provider(),
        )
        if refreshed != via_repo:
            repository.save(refreshed)
        return refreshed
    legacy_matches = sorted(path for path in _drafts_dir().glob(f"*_{draft_id}.json") if path.is_file())
    if not legacy_matches:
        return None
    if len(legacy_matches) > 1:
        joined = ", ".join(str(path) for path in legacy_matches)
        raise typer.BadParameter(f"draft_id={draft_id!r} matched multiple draft files: {joined}")
    return _refresh_persisted_draft(legacy_matches[0])


def _render_draft_next_steps(draft: FilingDraft, *, draft_path: Path) -> None:
    """Print the most likely next operator commands for ``draft``."""

    if draft.status is FilingDraftStatus.APPROVED:
        _console.print(f"Next: aeat submission preflight {draft_path}")
        _console.print(f"Next: aeat submission dry-run {draft_path}")
        return
    if draft.status is FilingDraftStatus.APPROVAL_STALE:
        _console.print(f"Next: aeat review show {draft.draft_id}")
        _console.print(f"Next: aeat review approve {draft.draft_id} --approved-by <you>")
        return
    _console.print(f"Next: aeat review show {draft.draft_id}")
    if draft.status is FilingDraftStatus.READY_TO_SUBMIT:
        _console.print(f"Next: aeat review approve {draft.draft_id} --approved-by <you>")


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
    typer.echo(f"Saved draft {draft.draft_id} -> {saved}")
    _render_draft(draft)
    _render_draft_next_steps(draft, draft_path=saved)


@app.command("validate")
def validate(
    draft_path: Annotated[Path, typer.Argument(help="Path to a draft JSON file")],
) -> None:
    """Re-validate an existing draft and rewrite it through the repository."""
    draft = _load_draft(draft_path)
    refreshed = validate_draft(
        draft,
        schema_provider=_schema_provider(),
    )
    refreshed = _refresh_persisted_draft(draft_path, refreshed)
    # Wave-8: re-validation now persists ciphertext-at-rest via the
    # repository instead of a plaintext write_text to draft_path.
    _draft_repository().save(refreshed)
    typer.echo(f"Re-validated draft {refreshed.draft_id} (status={refreshed.status.value})")
    _render_draft(refreshed)
    _render_draft_next_steps(refreshed, draft_path=draft_path)


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
    repository = _draft_repository()
    seen_ids: set[str] = set()
    # Wave-7/8: drafts are now ciphertext envelopes via FilingDraftRepository.
    for draft in repository.iter_drafts():
        seen_ids.add(draft.draft_id)
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
    # Legacy plaintext drafts (operator hasn't yet migrated) — read,
    # display, and DO NOT re-persist here. Migration happens on the
    # next state-changing CLI action.
    for path in sorted(drafts_dir.glob("*.json")):
        if path.name.endswith(".envelope.json"):
            continue
        try:
            draft = FilingDraft.model_validate_json(path.read_text(encoding="utf-8"))
        except FilingDraftError:
            _logger.warning("Skipping invalid draft file: %s", path)
            continue
        if draft.draft_id in seen_ids:
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
    from_borrador: Annotated[
        Path | None,
        typer.Option(
            "--from-borrador",
            help=(
                "Path to an AEAT Modelo 100 (Renta) borrador / "
                "predeclaración / declaración PDF; extracts the summary "
                "block (#305 cluster F MVP)."
            ),
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            help="Modelo string ID (e.g. '303'). Overrides auto-detection with --from-declaracion.",
        ),
    ] = None,
    año: Annotated[
        int | None,
        typer.Option(
            "--año",
            help="Override auto-detected tax year.",
        ),
    ] = None,
) -> None:
    """Import a past filing from an AEAT PDF.

    Exactly one of ``--from-justificante``, ``--from-declaracion``, or
    ``--from-borrador`` must be supplied.

    ``--from-justificante`` reconstructs a metadata scaffold draft +
    companion submission record from the filing receipt (#271). Every
    casilla lands EMPTY.

    ``--from-declaracion`` parses the full filing copy PDF and extracts
    every printed casilla value; produces a casilla-complete draft
    ready for ``aeat filing verify`` (#305 cluster D / E).

    ``--from-borrador`` parses a Modelo 100 (Renta) artefact (borrador,
    predeclaración, or declaración); extracts the summary-block casillas
    and chains verification against the partial Modelo 100 ruleset
    (#305 cluster F MVP).
    """
    provided = sum(bool(flag) for flag in (from_justificante, from_declaracion, from_borrador))
    if provided == 0:
        raise typer.BadParameter("exactly one of --from-justificante, --from-declaracion, --from-borrador is required")
    if provided > 1:
        raise typer.BadParameter("only one --from-* flag at a time")

    if from_justificante is not None:
        _handle_justificante_import(from_justificante)
        return
    if from_declaracion is not None:
        _handle_declaracion_import(from_declaracion, modelo=modelo, año=año)
        return

    assert from_borrador is not None
    _handle_borrador_import(from_borrador, año=año)


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
    # Wave-8 silent-leaker close: route the justificante-import submission
    # write through the governed SubmissionRepository (ciphertext-at-rest
    # at AUDIT class) instead of a direct plaintext write.
    from ...submission._repository import SubmissionRepository

    submission_repository = SubmissionRepository(store_dir=settings.aeat_submissions_dir)
    submission_repository.save(result.submission)
    submission_path = submission_repository.envelope_path_for(result.submission.submission_id)

    typer.echo(
        f"Imported draft {result.draft.draft_id} from justificante {result.submission.justificante_csv} -> {draft_path}"
    )
    typer.echo(f"Saved submission {result.submission.submission_id} -> {submission_path}")
    lang = _output_language()
    for warning in result.warnings:
        rendered = get_translation(warning, lang)
        typer.echo(f"[warning] {rendered}")
    _render_draft(result.draft)


def _output_language() -> Language:
    """Resolve the Kent-facing output language from settings.

    Defaults to Spanish (Kent is a Spanish autónomo) per project mandate
    ``AEAT_OUTPUT_LANGUAGE`` default = ``es``. Audit finding M5.
    """
    try:
        return Language(load_settings().aeat_output_language)
    except (KeyError, ValueError):
        return Language.ES


def _handle_declaracion_import(
    from_declaracion: Path,
    *,
    modelo: str | None,
    año: int | None,
) -> None:
    """Dispatch the declaración (#305 cluster D + E) import path."""
    from ...declaracion import DeclaracionParseError, parse_declaracion
    from ...verification import verify_declaracion

    try:
        filing = parse_declaracion(
            from_declaracion,
            modelo_override=modelo,
            año_override=año,
        )
    except DeclaracionParseError as exc:
        raise typer.BadParameter(str(exc)) from exc

    lang = _output_language()

    typer.echo(
        f"Parsed Modelo {filing.modelo} {filing.period} declaración "
        f"(template {filing.template_revision.revision}). "
        f"{len(filing.values)} of {len(filing.values) + len(filing.warnings)} casillas extracted."
    )
    typer.echo(f"Extraction status: {filing.extraction_status.value}")
    if filing.warnings:
        typer.echo(f"[warnings] {len(filing.warnings)}:")
        for warning in filing.warnings:
            rendered = get_translation(warning.message, lang)
            typer.echo(f"  - casilla {warning.casilla_id or '-'}: {rendered}")

    ruleset = _resolve_ruleset_for_filing(
        filing_modelo=filing.modelo,
        filing_period=filing.period,
        filing_ejercicio=filing.ejercicio,
    )
    verdict = verify_declaracion(filing, ruleset=ruleset)
    typer.echo(f"Verification status: {verdict.status.value}")
    typer.echo(f"  {get_translation(verdict.narrative, lang)}")
    for discrepancy in verdict.discrepancies:
        rationale = get_translation(discrepancy.cause_rationale, lang)
        typer.echo(
            f"  - casilla {discrepancy.casilla_id}: "
            f"expected {discrepancy.expected}, actual {discrepancy.actual}, "
            f"cause={discrepancy.cause.value} — {rationale}"
        )


def _resolve_ruleset_for_filing(
    *,
    filing_modelo: str,
    filing_period: str,
    filing_ejercicio: str,
):
    """Resolve the ruleset for the filing's (modelo, period). None when absent."""
    from ...formulas._period import FiscalPeriod, Quarter
    from ...formulas._registry import get_registry
    from ...models import ModeloCode

    try:
        modelo_code = ModeloCode(filing_modelo)
    except (KeyError, ValueError):
        return None

    quarter = None
    quarter_token = filing_period[4:] if len(filing_period) >= 6 else ""
    if quarter_token.startswith("Q") and len(quarter_token) == 2 and quarter_token[1].isdigit():
        try:
            quarter = Quarter(f"Q{int(quarter_token[1])}")
        except (KeyError, ValueError):
            quarter = None

    try:
        period_obj = FiscalPeriod(year=int(filing_ejercicio), quarter=quarter)
    except Exception:
        return None

    try:
        return get_registry().resolve(modelo=modelo_code, period=period_obj)
    except Exception:
        return None


def _handle_borrador_import(
    from_borrador: Path,
    *,
    año: int | None,
) -> None:
    """Dispatch the Modelo 100 (Renta) import path (#305 cluster F MVP)."""
    from ...borrador import BorradorParseError, parse_borrador
    from ...borrador._tarifa import validate_tarifa_estatal
    from ...formulas._rulesets import MODELO_100_SUMMARY_2025

    try:
        filing = parse_borrador(from_borrador, año_override=año)
    except BorradorParseError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"Parsed Modelo 100 Renta {filing.ejercicio} "
        f"({filing.artefact_kind.value}). "
        f"{len(filing.values)} summary-block casillas extracted."
    )
    if filing.csv is not None:
        typer.echo(f"CSV: {filing.csv}")

    # Verify against the partial summary ruleset.
    from ...formulas import Engine

    provided: dict[str, Decimal] = {
        v.casilla_id: v.printed_value for v in filing.values if isinstance(v.printed_value, Decimal)
    }
    engine = Engine()
    report = engine.audit_against(
        ruleset=MODELO_100_SUMMARY_2025,
        provided=provided,
        tolerance=Decimal("0.01"),
    )
    ruleset_clean = report.is_clean()
    if ruleset_clean:
        typer.echo(f"Verification status: VERIFIED (ruleset={MODELO_100_SUMMARY_2025.ruleset_id})")
    else:
        typer.echo(f"Verification status: NEEDS_REVIEW — {len(report.discrepancies)} discrepancies")
        for d in report.discrepancies:
            typer.echo(
                f"  - casilla {d.casilla_id}: expected {d.computed_value}, actual {d.user_value}, delta {d.delta}"
            )

    # Tarifa progresiva estatal post-validator — checks that the extracted
    # cuota íntegra estatal (0550, 0560) matches the tarifa-derived value
    # when the corresponding base liquidable casilla (0545, 0555) is present.
    tarifa_ejercicio = filing.ejercicio
    try:
        tarifa_findings = validate_tarifa_estatal(
            ejercicio=tarifa_ejercicio,
            base_liquidable_general=provided.get("0545"),
            base_liquidable_ahorro=provided.get("0555"),
            cuota_estatal_general=provided.get("0550"),
            cuota_estatal_ahorro=provided.get("0560"),
        )
    except ValueError as exc:
        typer.echo(f"Tarifa progresiva: skipped ({exc})")
        tarifa_findings = ()

    if tarifa_findings:
        typer.echo(f"Tarifa progresiva: {len(tarifa_findings)} discrepancies vs. IRPF estatal scale {tarifa_ejercicio}")
        for finding in tarifa_findings:
            typer.echo(
                f"  - casilla {finding.casilla_id} (from base {finding.base_casilla_id}): "
                f"tarifa {finding.expected_cuota} vs. extracted {finding.actual_cuota}"
                f" (delta {finding.delta})"
            )
    elif ruleset_clean:
        typer.echo(f"Tarifa progresiva: cuota íntegra estatal consistent with IRPF {tarifa_ejercicio} scale")


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
    saved_amended_draft = _save_draft(amendment.amended_draft)
    typer.echo(f"Saved amended draft {amendment.amended_draft.draft_id} -> {saved_amended_draft}")
    _console.print(f"Next: aeat review show {amendment.amended_draft.draft_id}")
    _console.print(f"Next: aeat review approve {amendment.amended_draft.draft_id} --approved-by <you>")
    _render_amendment(amendment)


@complementaria_app.command("submit")
def submit_complementaria_cmd(
    amendment_id: Annotated[str, typer.Argument(help="Persisted amendment id to submit")],
) -> None:
    """Submit a persisted amendment via the dry-run-only transport."""
    amendment = load_amendment(amendment_id)
    amended_draft = _load_persisted_draft_by_id(amendment.amended_draft.draft_id)
    if amended_draft is not None:
        amendment = amendment.model_copy(update={"amended_draft": amended_draft})
    engine = _submission_engine()

    try:
        submission_result = asyncio.run(
            engine.submit_amendment(
                amendment,
                dry_run=True,
            )
        )
    except SubmissionError as exc:
        _console.print(f"[red]refusing:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"dry-run amendment submission OK amendment_id={submission_result.amendment_id} "
        f"submission_id={submission_result.filing.submission_id} "
        f"status={submission_result.filing.status.value}"
    )


app.add_typer(complementaria_app, name="complementaria", help="Build and submit amendment filings (#93).")
_register_reconcile(app)


__all__ = ["app"]
