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
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from ....application.auth import AuthProviderDescription, AuthProviderKind
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
from ....core.i18n import Language, Translatable, get_translation
from ....core.logging import get_logger
from ....domain.justificante import JustificanteError
from ....domain.submission import SubmissionEngine
from .._i18n import output_language as _output_language
from .._i18n import t as _t
from .._i18n import tr as _msg

app = typer.Typer(
    name="filing",
    no_args_is_help=True,
    help="Filing draft engine commands.",
)
complementaria_app = typer.Typer(
    name="complementaria",
    no_args_is_help=True,
    help="Build amendment filings.",
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


def _submission_engine() -> SubmissionEngine:
    """Return a submission engine instance for amendment commands."""

    class _OpenDeadlineChecker:
        """Always-open deadline stub used by amendment commands."""

        def is_window_open(self, modelo: str, period: str, today: date) -> bool:
            """Return ``True`` unconditionally — amendments bypass the deadline gate."""
            return True

    class _CliAuthProvider:
        """Minimal auth-provider stub satisfying the submission preflight protocol."""

        kind = AuthProviderKind.CERTIFICATE

        def describe(self) -> AuthProviderDescription:
            """Return a synthetic CLI-side provider description."""
            return AuthProviderDescription(
                kind=self.kind,
                label="CLI certificate provider",
                configured=True,
                available=True,
                identity_nif="12345678Z",
                subject="CN=cli-provider",
                expires_on=date(2099, 12, 31),
                health_summary="OK:26800",
            )

    return SubmissionEngine(
        auth_provider=_CliAuthProvider(),
        deadline_checker=_OpenDeadlineChecker(),
        settings=load_settings(),
    )


def _schema_provider():
    """Return the production filing schema provider."""
    return build_runtime_schema_provider()


def _load_inputs(path: Path) -> dict[str, object]:
    """Load and parse a JSON inputs file from disk."""
    if not path.exists():
        raise typer.BadParameter(
            _msg(
                _t(
                    f"fichero de entradas no encontrado: {path}",
                    f"inputs file not found: {path}",
                    f"fitxer d'entrades no trobat: {path}",
                    f"bemeneti fájl nem található: {path}",
                )
            )
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            _msg(
                _t(
                    f"JSON inválido en {path}: {exc}",
                    f"invalid JSON in {path}: {exc}",
                    f"JSON no vàlid a {path}: {exc}",
                    f"érvénytelen JSON itt: {path}: {exc}",
                )
            )
        ) from exc
    if not isinstance(raw, dict):
        raise typer.BadParameter(
            _msg(
                _t(
                    f"el fichero de entradas {path} debe contener un objeto JSON",
                    f"inputs file {path} must contain a JSON object",
                    f"el fitxer d'entrades {path} ha de contenir un objecte JSON",
                    f"a bemeneti fájlnak ({path}) JSON objektumot kell tartalmaznia",
                )
            )
        )
    parsed: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise typer.BadParameter(
                _msg(
                    _t(
                        f"la clave de entrada debe ser cadena, recibido {type(key).__name__}",
                        f"input key must be string, got {type(key).__name__}",
                        f"la clau d'entrada ha de ser cadena, rebut {type(key).__name__}",
                        f"a bemeneti kulcsnak szövegnek kell lennie, kapott: {type(key).__name__}",
                    )
                )
            )
        if isinstance(value, str | int | bool) or value is None:
            parsed[key] = value
        elif isinstance(value, float):
            # Use Decimal so monetary precision is preserved.
            parsed[key] = Decimal(str(value))
        else:
            raise typer.BadParameter(
                _msg(
                    _t(
                        f"tipo de valor no soportado para casilla {key!r}: {type(value).__name__}",
                        f"unsupported value type for casilla {key!r}: {type(value).__name__}",
                        f"tipus de valor no admès per a la casella {key!r}: {type(value).__name__}",
                        f"nem támogatott érték típus a rovathoz {key!r}: {type(value).__name__}",
                    )
                )
            )
    return parsed


def _draft_repository():  # type: ignore[no-untyped-def]
    """Return a FilingDraftRepository bound to the configured drafts dir.

    Imports are deferred to avoid pulling aeat.adapters.persistence.storage (and Alembic
    plugin discovery) into CLI commands that never persist a draft.
    """
    from ....domain.filing._repository import FilingDraftRepository

    return FilingDraftRepository(store_dir=_drafts_dir())


def _load_draft(path: Path) -> FilingDraft:
    """Load and parse a draft from a ciphertext envelope file."""
    if not path.exists():
        raise typer.BadParameter(
            _msg(
                _t(
                    f"fichero de borrador no encontrado: {path}",
                    f"draft file not found: {path}",
                    f"fitxer d'esborrany no trobat: {path}",
                    f"piszkozat fájl nem található: {path}",
                )
            )
        )
    if not path.name.endswith(".envelope.json"):
        raise typer.BadParameter(
            _msg(
                _t(
                    f"fichero de borrador no reconocido: {path}; se esperaba <draft_id>.envelope.json.",
                    f"unrecognised draft file: {path}; expected a <draft_id>.envelope.json file.",
                    f"fitxer d'esborrany no reconegut: {path}; s'esperava <draft_id>.envelope.json.",
                    f"fel nem ismert piszkozat fájl: {path}; várható: <draft_id>.envelope.json.",
                )
            ),
        )
    repository = _draft_repository()
    draft_id = path.name[: -len(".envelope.json")]
    loaded = repository.load(draft_id)
    if loaded is None:
        raise typer.BadParameter(
            _msg(
                _t(
                    f"sobre de borrador no encontrado: {path}",
                    f"draft envelope not found: {path}",
                    f"sobre d'esborrany no trobat: {path}",
                    f"piszkozat csomag nem található: {path}",
                )
            )
        )
    return loaded


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

    next_label = _msg(_t("Siguiente:", "Next:", "Següent:", "Következő:"))
    if draft.status is FilingDraftStatus.APPROVED:
        _console.print(f"{next_label} aeat submission preflight {draft_path}")
        _console.print(f"{next_label} aeat submission export {draft_path}")
        return
    if draft.status is FilingDraftStatus.APPROVAL_STALE:
        _console.print(f"{next_label} aeat review show {draft.draft_id}")
        _console.print(f"{next_label} aeat review approve {draft.draft_id} --approved-by <you>")
        return
    _console.print(f"{next_label} aeat review show {draft.draft_id}")
    if draft.status is FilingDraftStatus.READY_TO_SUBMIT:
        _console.print(f"{next_label} aeat review approve {draft.draft_id} --approved-by <you>")


def _parse_json_argument(raw: str) -> dict[str, object]:
    """Parse ``raw`` as either an inline JSON object or a JSON file path."""
    candidate = Path(raw)
    payload_text = candidate.read_text(encoding="utf-8") if candidate.exists() else raw
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            _msg(
                _t(
                    f"JSON de complementaria inválido {raw!r}: {exc}",
                    f"invalid amendment JSON {raw!r}: {exc}",
                    f"JSON de complementària no vàlid {raw!r}: {exc}",
                    f"érvénytelen kiegészítő JSON {raw!r}: {exc}",
                )
            )
        ) from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter(
            _msg(
                _t(
                    "el payload de complementaria debe ser un objeto JSON",
                    "amendment payload must be a JSON object",
                    "el payload de complementària ha de ser un objecte JSON",
                    "a kiegészítő hasznos teher JSON objektum kell legyen",
                )
            )
        )
    return payload


def _parse_amendment_inputs(raw_inputs: Mapping[str, object]) -> dict[str, object]:
    """Coerce the amendment input payload into filing-builder-compatible values."""
    parsed: dict[str, object] = {}
    for key, value in raw_inputs.items():
        if not isinstance(key, str):
            raise typer.BadParameter(
                _msg(
                    _t(
                        f"la clave de entrada actualizada debe ser cadena, recibido {type(key).__name__}",
                        f"updated input key must be a string, got {type(key).__name__}",
                        f"la clau d'entrada actualitzada ha de ser cadena, rebut {type(key).__name__}",
                        f"a frissített bemeneti kulcsnak szövegnek kell lennie, kapott: {type(key).__name__}",
                    )
                )
            )
        if isinstance(value, dict):
            parsed[key] = _parse_amendment_inputs(cast(Mapping[str, object], value))
        elif isinstance(value, str | int | bool) or value is None:
            parsed[key] = value
        elif isinstance(value, float):
            parsed[key] = Decimal(str(value))
        else:
            raise typer.BadParameter(
                _msg(
                    _t(
                        f"tipo de valor de complementaria no soportado para {key!r}: {type(value).__name__}",
                        f"unsupported amendment value type for {key!r}: {type(value).__name__}",
                        f"tipus de valor de complementària no admès per a {key!r}: {type(value).__name__}",
                        f"nem támogatott kiegészítő érték típus ehhez: {key!r}: {type(value).__name__}",
                    )
                )
            )
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
    typer.echo(
        _msg(
            _t(
                f"Borrador guardado {draft.draft_id} -> {saved}",
                f"Saved draft {draft.draft_id} -> {saved}",
                f"Esborrany desat {draft.draft_id} -> {saved}",
                f"Piszkozat mentve {draft.draft_id} -> {saved}",
            )
        )
    )
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
    _draft_repository().save(refreshed)
    typer.echo(
        _msg(
            _t(
                f"Borrador re-validado {refreshed.draft_id} (estado={refreshed.status.value})",
                f"Re-validated draft {refreshed.draft_id} (status={refreshed.status.value})",
                f"Esborrany re-validat {refreshed.draft_id} (estat={refreshed.status.value})",
                f"Piszkozat ujra-validalva {refreshed.draft_id} (allapot={refreshed.status.value})",
            )
        )
    )
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
            valid_statuses = [s.value for s in FilingDraftStatus]
            raise typer.BadParameter(
                _msg(
                    _t(
                        f"estado desconocido {status!r}; válidos: {valid_statuses}",
                        f"unknown status {status!r}; valid: {valid_statuses}",
                        f"estat desconegut {status!r}; vàlids: {valid_statuses}",
                        f"ismeretlen allapot {status!r}; ervenyesek: {valid_statuses}",
                    )
                )
            ) from exc

    table = Table(title="Filing drafts")
    table.add_column("draft_id")
    table.add_column("modelo")
    table.add_column("period")
    table.add_column("status")
    table.add_column("approved_by")
    table.add_column("path")

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
            help="Path to an AEAT justificante (receipt) PDF; produces a metadata scaffold draft.",
        ),
    ] = None,
    from_declaracion: Annotated[
        Path | None,
        typer.Option(
            "--from-declaracion",
            help=("Path to an AEAT declaración (full filing copy) PDF; produces a casilla-complete draft."),
        ),
    ] = None,
    from_borrador: Annotated[
        Path | None,
        typer.Option(
            "--from-borrador",
            help=(
                "Path to an AEAT Modelo 100 (Renta) borrador / "
                "predeclaración / declaración PDF; extracts the summary "
                "block."
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
    companion submission record from the filing receipt. Every casilla
    lands EMPTY.

    ``--from-declaracion`` parses the full filing copy PDF and extracts
    every printed casilla value; produces a casilla-complete draft
    ready for ``aeat filing verify``.

    ``--from-borrador`` parses a Modelo 100 (Renta) artefact (borrador,
    predeclaración, or declaración); extracts the summary-block casillas
    and chains verification against the partial Modelo 100 ruleset.
    """
    provided = sum(bool(flag) for flag in (from_justificante, from_declaracion, from_borrador))
    if provided == 0:
        raise typer.BadParameter(
            _msg(
                _t(
                    "se requiere exactamente uno de --from-justificante, --from-declaracion, --from-borrador",
                    "exactly one of --from-justificante, --from-declaracion, --from-borrador is required",
                    "es requereix exactament un de --from-justificante, --from-declaracion, --from-borrador",
                    "pontosan egy szükséges: --from-justificante, --from-declaracion, --from-borrador",
                )
            )
        )
    if provided > 1:
        raise typer.BadParameter(
            _msg(
                _t(
                    "solo una bandera --from-* a la vez",
                    "only one --from-* flag at a time",
                    "només una marca --from-* alhora",
                    "egyszerre csak egy --from-* kapcsoló",
                )
            )
        )

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
    settings = load_settings()
    try:
        result = import_filing_from_justificante(
            from_justificante,
            schema_provider=_schema_provider(),
        )
    except (FilingImportError, FilingDraftError, JustificanteError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    draft_path = _save_draft(result.draft)
    from ....domain.submission._repository import SubmissionRepository

    submission_repository = SubmissionRepository(store_dir=settings.aeat_submissions_dir)
    submission_repository.save(result.submission)
    submission_path = submission_repository.envelope_path_for(result.submission.submission_id)

    justificante_csv = result.submission.justificante_csv
    submission_id = result.submission.submission_id
    draft_id = result.draft.draft_id
    typer.echo(
        _msg(
            _t(
                f"Borrador importado {draft_id} desde justificante {justificante_csv} -> {draft_path}",
                f"Imported draft {draft_id} from justificante {justificante_csv} -> {draft_path}",
                f"Esborrany importat {draft_id} des de justificant {justificante_csv} -> {draft_path}",
                f"Piszkozat importalva {draft_id} bizonylatbol {justificante_csv} -> {draft_path}",
            )
        )
    )
    typer.echo(
        _msg(
            _t(
                f"Envío guardado {submission_id} -> {submission_path}",
                f"Saved submission {submission_id} -> {submission_path}",
                f"Enviament desat {submission_id} -> {submission_path}",
                f"Beadas mentve {submission_id} -> {submission_path}",
            )
        )
    )
    lang = _output_language()
    warning_label = _msg(_t("[aviso]", "[warning]", "[avís]", "[figyelmeztetes]"))
    for warning in result.warnings:
        rendered = get_translation(warning, lang)
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
    from ....application.verification import verify_declaracion

    try:
        filing = parse_declaracion(
            from_declaracion,
            modelo_override=modelo,
            año_override=año,
        )
    except DeclaracionParseError as exc:
        raise typer.BadParameter(str(exc)) from exc

    lang = _output_language()
    if filing.modelo == "100":
        from ....adapters.persistence.profile import require_tax_residence

        residence = require_tax_residence()
        typer.echo(
            _msg(
                _t(
                    f"CCAA de residencia fiscal: {residence.ccaa.value}",
                    f"Tax residence CCAA: {residence.ccaa.value}",
                    f"CCAA de residència fiscal: {residence.ccaa.value}",
                    f"Adoilletosegi CCAA: {residence.ccaa.value}",
                )
            )
        )

    extracted = len(filing.values)
    total = len(filing.values) + len(filing.warnings)
    typer.echo(
        _msg(
            _t(
                f"Modelo {filing.modelo} {filing.period} declaración procesado "
                f"(plantilla {filing.template_revision.revision}). "
                f"{extracted} de {total} casillas extraídas.",
                f"Parsed Modelo {filing.modelo} {filing.period} declaración "
                f"(template {filing.template_revision.revision}). "
                f"{extracted} of {total} casillas extracted.",
                f"Modelo {filing.modelo} {filing.period} declaració processada "
                f"(plantilla {filing.template_revision.revision}). "
                f"{extracted} de {total} caselles extretes.",
                f"Modelo {filing.modelo} {filing.period} bevallas feldolgozva "
                f"(sablon {filing.template_revision.revision}). "
                f"{extracted} / {total} rovat kinyerve.",
            )
        )
    )
    typer.echo(
        _msg(
            _t(
                f"Estado de extracción: {filing.extraction_status.value}",
                f"Extraction status: {filing.extraction_status.value}",
                f"Estat d'extracció: {filing.extraction_status.value}",
                f"Kinyerés állapota: {filing.extraction_status.value}",
            )
        )
    )
    if filing.warnings:
        typer.echo(
            _msg(
                _t(
                    f"[avisos] {len(filing.warnings)}:",
                    f"[warnings] {len(filing.warnings)}:",
                    f"[avisos] {len(filing.warnings)}:",
                    f"[figyelmeztetesek] {len(filing.warnings)}:",
                )
            )
        )
        casilla_label = _msg(_t("casilla", "casilla", "casella", "rovat"))
        for warning in filing.warnings:
            rendered = get_translation(warning.message, lang)
            typer.echo(f"  - {casilla_label} {warning.casilla_id or '-'}: {rendered}")

    ruleset = _resolve_ruleset_for_filing(
        filing_modelo=filing.modelo,
        filing_period=filing.period,
        filing_ejercicio=filing.ejercicio,
    )
    verdict = verify_declaracion(filing, ruleset=ruleset)
    typer.echo(
        _msg(
            _t(
                f"Estado de verificación: {verdict.status.value}",
                f"Verification status: {verdict.status.value}",
                f"Estat de verificació: {verdict.status.value}",
                f"Verifikalas allapota: {verdict.status.value}",
            )
        )
    )
    typer.echo(f"  {get_translation(verdict.narrative, lang)}")
    casilla_label = _msg(_t("casilla", "casilla", "casella", "rovat"))
    expected_label = _msg(_t("esperado", "expected", "esperat", "várható"))
    actual_label = _msg(_t("real", "actual", "real", "tényleges"))
    cause_label = _msg(_t("causa", "cause", "causa", "ok"))
    for discrepancy in verdict.discrepancies:
        rationale = get_translation(discrepancy.cause_rationale, lang)
        typer.echo(
            f"  - {casilla_label} {discrepancy.casilla_id}: "
            f"{expected_label} {discrepancy.expected}, {actual_label} {discrepancy.actual}, "
            f"{cause_label}={discrepancy.cause.value} — {rationale}"
        )


def _resolve_ruleset_for_filing(
    *,
    filing_modelo: str,
    filing_period: str,
    filing_ejercicio: str,
):
    """Resolve the ruleset for the filing's (modelo, period). None when absent."""
    from ....domain.formulas import FiscalPeriod, Quarter, get_registry
    from ....domain.modelos import ModeloCode

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
    """Dispatch the Modelo 100 (Renta) import path."""
    from ....adapters.inbound.borrador import BorradorParseError, parse_borrador
    from ....adapters.inbound.borrador._tarifa import validate_tarifa_estatal
    from ....adapters.persistence.profile import require_tax_residence
    from ....domain.formulas import MODELO_100_SUMMARY_2025, compute_cuota_autonomica_general

    residence = require_tax_residence()

    try:
        filing = parse_borrador(from_borrador, año_override=año)
    except BorradorParseError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        _msg(
            _t(
                f"Modelo 100 Renta {filing.ejercicio} procesado "
                f"({filing.artefact_kind.value}). "
                f"{len(filing.values)} casillas del bloque resumen extraídas.",
                f"Parsed Modelo 100 Renta {filing.ejercicio} "
                f"({filing.artefact_kind.value}). "
                f"{len(filing.values)} summary-block casillas extracted.",
                f"Modelo 100 Renta {filing.ejercicio} processat "
                f"({filing.artefact_kind.value}). "
                f"{len(filing.values)} caselles del bloc resum extretes.",
                f"Modelo 100 Renta {filing.ejercicio} feldolgozva "
                f"({filing.artefact_kind.value}). "
                f"{len(filing.values)} osszegzo blokk rovat kinyerve.",
            )
        )
    )
    if filing.csv is not None:
        typer.echo(f"CSV: {filing.csv}")
    typer.echo(
        _msg(
            _t(
                f"CCAA de residencia fiscal: {residence.ccaa.value}",
                f"Tax residence CCAA: {residence.ccaa.value}",
                f"CCAA de residència fiscal: {residence.ccaa.value}",
                f"Adoilletosegi CCAA: {residence.ccaa.value}",
            )
        )
    )

    # Verify against the partial summary ruleset.
    from ....domain.formulas import Engine

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
    ruleset_id = MODELO_100_SUMMARY_2025.ruleset_id
    if ruleset_clean:
        typer.echo(
            _msg(
                _t(
                    f"Estado de verificación: VERIFIED (ruleset={ruleset_id})",
                    f"Verification status: VERIFIED (ruleset={ruleset_id})",
                    f"Estat de verificació: VERIFIED (ruleset={ruleset_id})",
                    f"Verifikalas allapota: VERIFIED (ruleset={ruleset_id})",
                )
            )
        )
    else:
        n = len(report.discrepancies)
        typer.echo(
            _msg(
                _t(
                    f"Estado de verificación: NEEDS_REVIEW — {n} discrepancias",
                    f"Verification status: NEEDS_REVIEW — {n} discrepancies",
                    f"Estat de verificació: NEEDS_REVIEW — {n} discrepàncies",
                    f"Verifikalas allapota: NEEDS_REVIEW — {n} elteres",
                )
            )
        )
        casilla_label = _msg(_t("casilla", "casilla", "casella", "rovat"))
        expected_label = _msg(_t("esperado", "expected", "esperat", "várható"))
        actual_label = _msg(_t("real", "actual", "real", "tényleges"))
        for d in report.discrepancies:
            typer.echo(
                f"  - {casilla_label} {d.casilla_id}: "
                f"{expected_label} {d.computed_value}, {actual_label} {d.user_value}, delta {d.delta}"
            )

    # Tarifa progresiva estatal post-validator — checks that the extracted
    # cuota íntegra estatal (0550, 0560) matches the tarifa-derived value
    # when the corresponding base liquidable casilla (0545, 0555) is present.
    tarifa_ejercicio = filing.ejercicio
    tarifa_ejercicio_int = int(filing.ejercicio)
    try:
        tarifa_findings = validate_tarifa_estatal(
            ejercicio=tarifa_ejercicio,
            base_liquidable_general=provided.get("0545"),
            base_liquidable_ahorro=provided.get("0555"),
            cuota_estatal_general=provided.get("0550"),
            cuota_estatal_ahorro=provided.get("0560"),
        )
    except ValueError as exc:
        typer.echo(
            _msg(
                _t(
                    f"Tarifa progresiva: omitida ({exc})",
                    f"Tarifa progresiva: skipped ({exc})",
                    f"Tarifa progressiva: omesa ({exc})",
                    f"Progressziv tarifa: kihagyva ({exc})",
                )
            )
        )
        tarifa_findings = ()

    if tarifa_findings:
        n = len(tarifa_findings)
        typer.echo(
            _msg(
                _t(
                    f"Tarifa progresiva: {n} discrepancias frente a la escala IRPF estatal {tarifa_ejercicio}",
                    f"Tarifa progresiva: {n} discrepancies vs. IRPF estatal scale {tarifa_ejercicio}",
                    f"Tarifa progressiva: {n} discrepàncies enfront de l'escala IRPF estatal {tarifa_ejercicio}",
                    f"Progressziv tarifa: {n} elteres az allami IRPF skalahoz {tarifa_ejercicio} kepest",
                )
            )
        )
        casilla_label = _msg(_t("casilla", "casilla", "casella", "rovat"))
        from_base_label = _msg(_t("desde base", "from base", "des de base", "alapbol"))
        for finding in tarifa_findings:
            typer.echo(
                f"  - {casilla_label} {finding.casilla_id} ({from_base_label} {finding.base_casilla_id}): "
                f"tarifa {finding.expected_cuota} vs. {finding.actual_cuota}"
                f" (delta {finding.delta})"
            )
    elif ruleset_clean:
        typer.echo(
            _msg(
                _t(
                    f"Tarifa progresiva: cuota íntegra estatal consistente con la escala IRPF {tarifa_ejercicio}",
                    f"Tarifa progresiva: cuota íntegra estatal consistent with IRPF {tarifa_ejercicio} scale",
                    f"Tarifa progressiva: quota íntegra estatal coherent amb l'escala IRPF {tarifa_ejercicio}",
                    f"Progressziv tarifa: az allami teljes ado konzisztens az IRPF skalaval {tarifa_ejercicio}",
                )
            )
        )

    base_autonomica = provided.get("0545")
    cuota_autonomica = provided.get("0551")
    if base_autonomica is not None and cuota_autonomica is not None:
        expected_autonomica = compute_cuota_autonomica_general(
            base_autonomica,
            residence.ccaa,
            año=tarifa_ejercicio_int,
        )
        delta = abs(expected_autonomica - cuota_autonomica)
        if delta <= Decimal("0.01"):
            typer.echo(
                _msg(
                    _t(
                        "Tarifa autonómica: cuota íntegra general consistente "
                        f"con la escala IRPF {tarifa_ejercicio} de {residence.ccaa.value}",
                        "Tarifa autonómica: cuota íntegra general consistent "
                        f"with {residence.ccaa.value} IRPF {tarifa_ejercicio} scale",
                        "Tarifa autonòmica: quota íntegra general coherent "
                        f"amb l'escala IRPF {tarifa_ejercicio} de {residence.ccaa.value}",
                        "Autonom tarifa: az altalanos teljes ado osszhangban van "
                        f"a(z) {residence.ccaa.value} IRPF {tarifa_ejercicio} skalaval",
                    )
                )
            )
        else:
            typer.echo(
                _msg(
                    _t(
                        "Tarifa autonómica: discrepancia en la casilla 0551 "
                        f"({residence.ccaa.value}): tarifa {expected_autonomica} "
                        f"frente a extraído {cuota_autonomica} (delta {delta})",
                        "Tarifa autonómica: discrepancy for casilla 0551 "
                        f"({residence.ccaa.value}): tarifa {expected_autonomica} "
                        f"vs. extracted {cuota_autonomica} (delta {delta})",
                        "Tarifa autonòmica: discrepància a la casella 0551 "
                        f"({residence.ccaa.value}): tarifa {expected_autonomica} "
                        f"davant extret {cuota_autonomica} (delta {delta})",
                        "Autonom tarifa: elteres az 0551 mezonek "
                        f"({residence.ccaa.value}): tarifa {expected_autonomica} "
                        f"vs. kinyert {cuota_autonomica} (delta {delta})",
                    )
                )
            )


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
        raise typer.BadParameter(
            _msg(
                _t(
                    "el payload de complementaria debe incluir 'original_submission_id' no vacío",
                    "amendment payload must include non-empty 'original_submission_id'",
                    "el payload de complementària ha d'incloure 'original_submission_id' no buit",
                    "a kiegeszito hasznos teherben szükséges a nem üres 'original_submission_id'",
                )
            )
        )
    raw_inputs = payload.get("updated_inputs")
    if not isinstance(raw_inputs, dict):
        raise typer.BadParameter(
            _msg(
                _t(
                    "el payload de complementaria debe incluir el objeto 'updated_inputs'",
                    "amendment payload must include object 'updated_inputs'",
                    "el payload de complementària ha d'incloure l'objecte 'updated_inputs'",
                    "a kiegeszito hasznos teherben szükséges az 'updated_inputs' objektum",
                )
            )
        )
    reasons = payload.get("reasons")
    parsed_inputs = _parse_amendment_inputs(cast(Mapping[str, object], raw_inputs))
    if reasons is not None:
        if not isinstance(reasons, dict):
            raise typer.BadParameter(
                _msg(
                    _t(
                        "'reasons' debe ser un objeto JSON de casilla -> motivo",
                        "'reasons' must be a JSON object of casilla -> reason",
                        "'reasons' ha de ser un objecte JSON de casella -> motiu",
                        "a 'reasons' egy JSON objektum: rovat -> indok",
                    )
                )
            )
        parsed_inputs["_reasons"] = _parse_amendment_inputs(cast(Mapping[str, object], reasons))

    engine = _submission_engine()
    original = engine.load_submission(original_submission_id)
    if original.modelo != modelo:
        raise typer.BadParameter(
            _msg(
                _t(
                    f"el modelo del payload {modelo!r} no coincide con el modelo del envío original {original.modelo!r}",
                    f"payload modelo {modelo!r} does not match original submission modelo {original.modelo!r}",
                    f"el model del payload {modelo!r} no coincideix amb el model de l'enviament original {original.modelo!r}",
                    f"a hasznos teher modelje {modelo!r} nem egyezik az eredeti beadas modeljevel {original.modelo!r}",
                )
            )
        )
    if original.period != period:
        raise typer.BadParameter(
            _msg(
                _t(
                    f"el período del payload {period!r} no coincide con el período del envío original {original.period!r}",
                    f"payload period {period!r} does not match original submission period {original.period!r}",
                    f"el període del payload {period!r} no coincideix amb el període de l'enviament original {original.period!r}",
                    f"a hasznos teher idoszaka {period!r} nem egyezik az eredeti beadas idoszakaval {original.period!r}",
                )
            )
        )
    try:
        amendment = build_complementaria(original, parsed_inputs)
    except FilingAmendmentError as exc:
        raise typer.BadParameter(str(exc)) from exc
    saved_amended_draft = _save_draft(amendment.amended_draft)
    amended_draft_id = amendment.amended_draft.draft_id
    typer.echo(
        _msg(
            _t(
                f"Borrador complementaria guardado {amended_draft_id} -> {saved_amended_draft}",
                f"Saved amended draft {amended_draft_id} -> {saved_amended_draft}",
                f"Esborrany complementària desat {amended_draft_id} -> {saved_amended_draft}",
                f"Kiegeszito piszkozat mentve {amended_draft_id} -> {saved_amended_draft}",
            )
        )
    )
    next_label = _msg(_t("Siguiente:", "Next:", "Següent:", "Következő:"))
    _console.print(f"{next_label} aeat review show {amended_draft_id}")
    _console.print(f"{next_label} aeat review approve {amended_draft_id} --approved-by <you>")
    _render_amendment(amendment)


app.add_typer(complementaria_app, name="complementaria", help="Build amendment filings.")


__all__ = ["app"]
