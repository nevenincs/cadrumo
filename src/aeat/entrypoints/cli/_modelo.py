"""User-facing modelo registry introspection commands."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import suppress
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

import click
import typer
from pydantic import BaseModel, ValidationError

from ...application.aggregation import (
    CounterpartObservation,
    ForeignAssetIngestObservation,
    PerModeloAggregationCommand,
    RetencionObservation,
    aggregate_per_modelo,
)
from ...application.modelo import (
    AmendmentEvidenceMissingError,
    AmendmentTargetStateError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    discard_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_verification_report,
    get_work_unit,
    list_calculation_revisions,
    list_filing_records,
    list_verification_reports,
    list_work_units,
    rename_work_unit,
    verify_modelo_revision,
)
from ...core.errors import resolve_error_message
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ...domain.calculations.registry import RegistryQueryService
from ...domain.calculations.registry._errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry._ids import _CASILLA_RE, _REF_RE
from ...domain.calculations.registry._queries import parse_modelo_period
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionAmendmentKind
from ...domain.modelos._filing_record import ModeloRecord
from ...domain.modelos._row_models import (
    M347_THRESHOLD_EUR,
    Modelo184MemberRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    ModeloDetailRow,
    validate_m349_nif_format,
)
from ...domain.modelos._verification_report import VerificationReport
from ...domain.modelos._work_unit import WorkUnit
from ...domain.profile import parse_tax_region
from ._common import _emit, _parse_iso_date, _profile_to_taxpayer, activate_subcommand_output_language

if TYPE_CHECKING:
    from ...application.modelo._reconcile import ModeloReconciliationReport
    from ...domain.calculations.registry._schema import ModeloRevision
    from ._modelo_payloads import (
        CalculationRevisionPayload,
        ModeloRecordPayload,
        ResultSummaryRowPayload,
        VerificationReportPayload,
        WorkUnitPayload,
    )

InputKind = Literal["manual", "bound", "computed", "informational"]

_WORK_UNIT_ID_RE = r"^[0-9a-f]{64}$"
"""SHA-256 hex digest expected as the canonical work-unit identifier."""

_CASILLA_MAX_LEN = 64
_BINDING_MAX_LEN = 128
_BARE_NUMERIC_RE = re.compile(r"^\d+$")

_OUTPUT_LANGUAGE_CLI = click.Choice(SUPPORTED_OUTPUT_LANGUAGES)


def _validate_work_unit_id(value: str) -> str:
    """Validate that *value* is a 64-character lowercase hex string.

    Raises :class:`typer.BadParameter` if the format is wrong so that
    invalid identifiers are rejected at the CLI boundary rather than
    surfacing as an opaque application-layer error.
    """

    stripped = value.strip()
    if not re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_work_unit_id",
                default=(f"work_unit_id must be a 64-character lowercase hex string (SHA-256 digest); got {value!r}"),
            )
        )
    return stripped


def _validate_calculation_revision_id(value: str) -> str:
    """Validate that *value* is a 64-character lowercase hex string.

    A ``calculation_revision_id`` is a SHA-256 digest, sharing the same
    shape as a ``work_unit_id``. Rejecting a malformed identifier at the
    CLI boundary keeps the application layer free of input-shape checks.
    """

    stripped = value.strip()
    if not re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_calculation_revision_id",
                default=(
                    "calculation_revision_id must be a 64-character lowercase "
                    f"hex string (SHA-256 digest); got {value!r}"
                ),
            )
        )
    return stripped


app = typer.Typer(
    name="modelo",
    help=tr("cli.app.modelo.app_help"),
    no_args_is_help=True,
)


def _bad_parameter_from_error(exc: BaseException) -> typer.BadParameter:
    """Render registered domain errors before crossing the Typer boundary."""

    return typer.BadParameter(resolve_error_message(exc))


def _resolve_default_actor() -> str:
    """Return the active profile display_name, or a permanent fallback label.

    Per the actor attribution specification, ``--by`` defaults to the active profile's
    display name. When no active profile exists or the bucket is empty the
    fallback label keeps the audit record populated rather than raising.
    """

    with suppress(Exception):
        from ...application.workflow._models import resolve_active_bucket_id
        from ...application.workflow._persistence import workflow_state_repository

        state = workflow_state_repository().load()
        record = state.active_profile_record()
        if record is not None and record.display_name:
            return record.display_name
        active = resolve_active_bucket_id()
        if active:
            return active
    return "operator"


def _require_active_profile() -> None:
    """Refuse cold-start work commands with the clean no-active-profile message.

    Work commands open the active profile's encrypted bucket database.
    Without an active profile that path raises a raw ``StorageError``
    (``aeat_database_url is empty``) or a low-level ``no active bucket
    session`` message — both leak internal plumbing. This guard fires
    first so every cold-start work command produces the same clean,
    translated ``profile create`` guidance that the ledger surface
    already gives.
    """

    from ...application.workflow._models import resolve_active_bucket_id
    from ...core.i18n import tr as _tr
    from ._errors import CliRefusedBoundaryError

    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(_tr("cli.config.errors.no_active_profile"))


def _run_query[T](call: Callable[[], T]) -> T:
    """Run a registry-query call and translate user-input errors to clean CLI failures.

    ``RegistryQueryService`` raises :exc:`ValueError` from ``parse_modelo_period``
    on a malformed ``--period`` arg and :exc:`RegistrySnapshotError` from the
    authority on unknown modelo / unresolved revision. Both are user-input
    errors at the CLI boundary; surfacing them as ``typer.BadParameter``
    keeps the operator-facing experience clean rather than printing a
    traceback.
    """
    try:
        return call()
    except (ValueError, RegistrySnapshotError) as exc:
        raise _bad_parameter_from_error(exc) from exc


@app.command(
    "readiness",
    help=tr(
        "cli.app.modelo.readiness_help",
        default="Report whether the active profile is ready to file one modelo / year / period.",
    ),
)
def modelo_readiness(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option("--modelo", help=tr("cli.app.modelo.readiness.modelo_help", default="Modelo code (e.g. 303).")),
    ],
    revision_id: Annotated[
        str,
        typer.Option(
            "--revision-id",
            help=tr("cli.app.modelo.readiness.revision_help", default="Registry revision id."),
        ),
    ],
    filing_year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.app.modelo.readiness.year_help", default="Filing year.")),
    ],
    period: Annotated[
        str | None,
        typer.Option(
            "--period",
            help=tr("cli.app.modelo.readiness.period_help", default="Period token (e.g. Q1, annual)."),
        ),
    ] = None,
) -> None:
    """Report active-profile readiness for one modelo target.

    Carries the behaviour previously surfaced as
    ``aeat config profile preflight``. Lives on the modelo surface so
    the readiness check sits alongside the other modelo verbs that
    operate on ``(modelo, revision, year, period)`` tuples.

    Consumes the canonical :func:`build_operator_state_projection`: the
    readiness datum is computed once in the projection, so this surface
    cannot disagree with any other operator-facing surface.
    """

    from ...application.state_projection import (
        ModeloReadinessRequest,
        build_operator_state_projection,
    )
    from ...application.workflow._models import resolve_active_bucket_id
    from ...core.i18n import tr as _tr
    from ...domain.user_profile import ProfileNotFoundError
    from ._errors import CliRefusedBoundaryError

    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(_tr("cli.config.errors.no_active_profile"))
    request = ModeloReadinessRequest(
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=period or "",
    )
    try:
        projection = build_operator_state_projection(modelo_readiness_requests=(request,))
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(
            _tr("cli.config.profile.unknown_profile", name=resolve_active_bucket_id() or "")
        ) from exc
    if not projection.modelo_readiness:
        raise CliRefusedBoundaryError(_tr("cli.config.errors.no_active_profile"))
    report = projection.modelo_readiness[0]
    payload = report.model_dump(mode="json")
    lines = [
        f"profile_id\t{report.profile_id}",
        f"modelo\t{modelo}",
        f"revision_id\t{revision_id}",
        f"filing_year\t{filing_year}",
        f"period\t{period or ''}",
        "readiness_scope\tprofile_and_source_preflight_not_manual_casilla_completeness",
        f"ready\t{report.ready}",
        f"profile_ready\t{report.profile_ready}",
        f"missing\t{len(report.missing)}",
        f"ledger_preflight_required\t{report.ledger_preflight_required}",
        f"ledger_ready\t{report.ledger_ready if report.ledger_ready is not None else ''}",
        f"ledger_period\t{report.ledger_period or ''}",
        f"ledger_checked\t{report.ledger_checked_transaction_count}",
        f"ledger_issues\t{len(report.ledger_issues)}",
    ]
    for requirement in report.missing:
        lines.append(f"{requirement.section_key}.{requirement.field_key}\t{requirement.selector}")
    for issue in report.ledger_issues:
        lines.append(f"ledger_issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
    _emit(ctx, payload, lines)


@app.command("list")
def list_modelos(
    ctx: typer.Context,
    year: Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.list.year_help"))] = None,
) -> None:
    report = _run_query(lambda: _service().list_modelos(year=year))
    _emit(
        ctx,
        report,
        [
            "code\ttitle\tcadence\tdomain\trevisions",
            *[
                f"{row.code}\t{row.title}\t{row.cadence}\t{row.tax_domain}\t{row.revision_count}"
                for row in report.modelos
            ],
        ],
    )


@app.command("describe")
def describe_modelo(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Argument(help=tr("cli.app.modelo.describe.modelo_help"))],
    period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.describe.period_help"))] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help=tr("cli.app.modelo.describe.as_of_help"))] = None,
) -> None:
    try:
        report = _service().describe_modelo(modelo, period=period, as_of=_as_of(as_of))
    except (ValueError, RegistrySnapshotError) as exc:
        # A malformed --period yields a generic shape hint from the
        # registry parser; enrich it with the modelo's declared period
        # tokens so the operator sees exactly which tokens are valid.
        # Only the period-parse / period-not-declared errors are
        # rewritten — an unknown-modelo error keeps its own message.
        message = str(exc)
        if period is not None and "period" in message.lower():
            raise typer.BadParameter(_bare_period_error(modelo, period, fallback=message)) from exc
        raise typer.BadParameter(message) from exc
    _emit(
        ctx,
        report,
        [
            f"Modelo\t{report.code}",
            f"Title\t{report.title}",
            f"Official name\t{report.official_name}",
            f"Tax domain\t{report.tax_domain}",
            f"Cadence\t{report.cadence}",
            f"Revision\t{report.revision}",
            f"Revision ids\t{', '.join(report.revision_ids)}",
            f"Periods\t{', '.join(report.periods)}",
            f"Casillas\t{report.casilla_count}",
            f"Bindings\t{report.binding_count}",
            f"Formulas\t{report.formula_count}",
        ],
    )


@app.command("casillas")
def casillas(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Argument(help=tr("cli.app.modelo.casillas.modelo_help"))],
    period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.casillas.period_help"))] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help=tr("cli.app.modelo.casillas.as_of_help"))] = None,
    input_kind: Annotated[
        InputKind | None,
        typer.Option("--input-kind", help=tr("cli.app.modelo.casillas.input_kind_help")),
    ] = None,
    required: Annotated[bool, typer.Option("--required", help=tr("cli.app.modelo.casillas.required_help"))] = False,
    form_number: Annotated[
        str | None,
        typer.Option("--form-number", help=tr("cli.app.modelo.casillas.form_number_help")),
    ] = None,
) -> None:
    report = _run_query(
        lambda: _service().casillas(
            modelo,
            period=period,
            as_of=_as_of(as_of),
            input_kind=input_kind,
            required=True if required else None,
            form_number=form_number,
        )
    )
    _emit(
        ctx,
        report,
        [
            "casilla_id\tnumber\tinput\trequired\tlabel",
            *[
                f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t{str(row.required).lower()}\t{row.label}"
                for row in report.rows
            ],
        ],
    )


bindings_app = typer.Typer(
    name="bindings",
    help=tr("cli.app.modelo.bindings.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(bindings_app, name="bindings")

#: Readiness category attached to every binding, derived from its
#: source kind. Fixes the operator-facing vocabulary that
#: missing-binding errors produce in place of raw registry error
#: strings.
_BINDING_SOURCE_TO_READINESS: dict[str, str] = {
    "constant_value": "casilla",
    "previous_filing": "prior filed revision",
    "live_observation": "live observation",
    "ledger_iva_aggregation": "ledger source",
    "ledger_oss_aggregation": "ledger source",
    "ledger_renta_expense_aggregation": "ledger source",
    "profile": "profile fact",
    "profile_fact": "profile fact",
    "bucket_state": "bucket",
    "waiver": "waiver",
    "blocking_finding": "blocking finding",
}


def _readiness_for_source(source: str) -> str:
    """Return the readiness category for ``source``.

    Unknown sources fall back to ``"ledger source"`` because every
    registered source kind today is bucket / ledger-derived. If a
    new source is added without a readiness mapping the fallback is
    still operator-readable; stricter exhaustiveness belongs in the
    bindings-resolution layer.
    """
    return _BINDING_SOURCE_TO_READINESS.get(source, "ledger source")


class _BindingReportLike(Protocol):
    """Structural view of a modelo bindings report.

    ``_profile_resolved_binding_ids`` needs only the modelo ``code``;
    ``filing_year`` and ``period`` are read defensively via ``getattr``
    because an unscoped (no ``--year``) report carries neither.
    """

    @property
    def code(self) -> str: ...


def _profile_resolved_binding_ids(report: _BindingReportLike) -> frozenset[str]:
    """Return binding ids the active profile already resolves for a report's scope.

    Backs ``bindings list --missing``: a binding the active profile
    satisfies is no longer something the operator owes. Resolution
    needs a concrete filing year; a report with no resolved
    ``filing_year`` (the unscoped, no-``--year`` listing) yields an
    empty set and ``--missing`` then drops only constant bindings. A
    bucket with no active profile likewise yields an empty set.
    """

    filing_year = getattr(report, "filing_year", None)
    if filing_year is None:
        return frozenset()
    from ...application.modelo._binding_readiness import profile_resolvable_binding_ids
    from ...domain.user_profile import ProfileNotFoundError

    try:
        bucket_id = _active_bucket_id()
    except typer.BadParameter:
        return frozenset()
    try:
        return profile_resolvable_binding_ids(
            modelo=str(report.code),
            bucket_id=bucket_id,
            filing_year=int(filing_year),
            period=getattr(report, "period", None),
        )
    except (RegistrySnapshotError, RegistryValidationError, ProfileNotFoundError):
        return frozenset()


def _parse_kv_spec[T](
    spec: str,
    *,
    flag: str,
    key_label: str = "KEY",
    value_label: str = "VALUE",
    transform: Callable[[str], T],
    key_validator: Callable[[str, str], None] | None = None,
) -> tuple[str, T]:
    """Parse a ``KEY=VALUE`` CLI spec into ``(key, transform(value))``.

    Centralises the shape every override flag shares: split on the
    first ``=``, require a non-empty key, hand the right-hand side to
    a flag-specific transform. ``flag``/``key_label``/``value_label``
    feed the :class:`typer.BadParameter` messages so each call site
    keeps its own operator-facing wording.

    If ``key_validator`` is provided it receives ``(key, spec)`` and
    must raise :class:`typer.BadParameter` if the key is malformed.
    """

    if "=" not in spec:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.kv_format_error",
                flag=flag,
                key_label=key_label,
                value_label=value_label,
                spec=spec,
            )
        )
    key, _, value = spec.partition("=")
    key = key.strip()
    if not key:
        raise typer.BadParameter(tr("cli.app.modelo.work.kv_empty_key_error", flag=flag, spec=spec))
    if key_validator is not None:
        key_validator(key, spec)
    return key, transform(value)


def _declared_period_tokens(modelo: str | None) -> tuple[str, ...]:
    """Return the registry-declared period tokens for one modelo.

    Pulls ``period_selector.periods`` from every revision of the modelo
    so the CLI period-validation error can enumerate exactly the tokens
    AEAT accepts for that form (``0A`` for an annual modelo, ``1T``..``4T``
    for a quarterly one, etc.). Returns an empty tuple when the modelo is
    unknown or unspecified — the caller falls back to the generic shape
    hint.
    """

    if not modelo or not modelo.strip():
        return ()
    try:
        from ...core.resources import resources

        authority = resources().modelos.authority
        definition = authority.validate_modelo(modelo.strip())
    except Exception:
        return ()
    return tuple(
        sorted({token for revision in definition.revisions.values() for token in revision.period_selector.periods})
    )


def _resolve_year_period(year: int, period: str, *, modelo: str | None = None) -> tuple[int, str]:
    """Normalise CLI ``--year/--period`` into ``(filing_year, registry_period)``.

    Operators pass user-facing tokens (``Q1``, ``annual``, ``01``); the
    registry expects ``1T``/``0A``/``01``. Bridge that by reconstructing
    the canonical ``YYYY[Qn|-MM]`` string and delegating to the
    registry parser.

    ``--year`` and ``--period`` are composed internally; a token that is
    itself a four-digit year (the common ``--period 2024`` confusion)
    would compose to ``2024-2024`` and fail with an opaque message. When
    ``modelo`` is supplied the error instead explains the composition
    and enumerates the registry-declared period tokens for that modelo.
    """

    token = period.strip()
    if not token:
        raise typer.BadParameter(tr("cli.common.errors.period_empty"))
    lowered = token.lower()
    # When the token matches a registry-declared period for the modelo
    # verbatim (case-insensitively) it is already the registry period —
    # return it directly. This is the only path that resolves the
    # non-date census / event tokens ("alta", "modificacion", "baja",
    # "AD-HOC") declared by census modelos (036, 308, ...); for quarterly
    # / annual modelos it short-circuits to the same value the
    # composition branches below would produce.
    declared = _declared_period_tokens(modelo)
    declared_match = next((d for d in declared if d.lower() == lowered), None)
    if declared_match is not None:
        return year, declared_match
    if lowered in {"annual", "anual", "0a"}:
        composed = f"{year}"
    elif lowered in {"q1", "1t", "1"}:
        composed = f"{year}Q1"
    elif lowered in {"q2", "2t", "2"}:
        composed = f"{year}Q2"
    elif lowered in {"q3", "3t", "3"}:
        composed = f"{year}Q3"
    elif lowered in {"q4", "4t", "4"}:
        composed = f"{year}Q4"
    elif lowered.isdigit() and len(lowered) == 2:
        composed = f"{year}-{lowered}"
    elif lowered.isdigit() and len(lowered) == 4:
        # A bare four-digit token is itself a year — the operator
        # likely repeated the filing year into --period. Composing it
        # would yield "<year>-<token>"; refuse with a clear hint.
        raise typer.BadParameter(_period_token_error(year, token, modelo))
    else:
        composed = f"{year}{token}" if token.upper().startswith("Q") else f"{year}-{token}"
    try:
        return parse_modelo_period(composed)
    except RegistryValidationError as exc:
        raise typer.BadParameter(_period_token_error(year, token, modelo, fallback=str(exc))) from exc


def _period_token_error(
    year: int,
    token: str,
    modelo: str | None,
    *,
    fallback: str | None = None,
) -> str:
    """Build an operator-facing period-token error.

    Explains that ``--year`` and ``--period`` are composed and lists the
    registry-declared period tokens for the modelo when known. Falls
    back to ``fallback`` (the raw registry message) only when no
    modelo-specific token set is available.
    """

    declared = _declared_period_tokens(modelo)
    if declared:
        return tr(
            "cli.app.modelo.work.period_token_invalid",
            default=(
                f"--period {token!r} is not a valid period token for modelo "
                f"{modelo}. --year and --period are composed separately: pass "
                f"--year {year} for the filing year and one of the declared "
                f"period tokens for --period. Valid tokens: {', '.join(declared)}."
            ),
            token=token,
            modelo=modelo or "",
            year=year,
            tokens=", ".join(declared),
        )
    if fallback is not None:
        return fallback
    return tr(
        "cli.app.modelo.work.period_token_unrecognised",
        default=(
            f"--period {token!r} is not a recognised period token. --year and "
            f"--period are composed separately: pass --year {year} for the "
            f"filing year and a period token (0A for annual, Qn for a quarter, "
            f"or MM for a month) for --period."
        ),
        token=token,
        year=year,
    )


def _bare_period_error(modelo: str, period: str, *, fallback: str) -> str:
    """Build an operator-facing error for an invalid bare ``--period`` token.

    Used by surfaces (``describe``, ``casillas``) that take a bare
    period rather than a composed ``--year/--period`` pair. When the
    modelo's declared period tokens are known the error enumerates them;
    otherwise it falls back to the raw registry shape hint.
    """

    declared = _declared_period_tokens(modelo)
    if not declared:
        return fallback
    return tr(
        "cli.app.modelo.describe.period_token_invalid",
        default=(
            f"--period {period!r} is not a valid period token for modelo {modelo}. Valid tokens: {', '.join(declared)}."
        ),
        period=period,
        modelo=modelo,
        tokens=", ".join(declared),
    )


def _validate_binding_key(key: str, spec: str) -> None:
    """Validate a ``--binding`` key against :data:`BindingId` constraints."""

    if len(key) > _BINDING_MAX_LEN or not re.fullmatch(_REF_RE, key):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_binding_key",
                default=(
                    f"--binding key {key!r} is not a valid BindingId "
                    f"(pattern: {_REF_RE!r}, max {_BINDING_MAX_LEN} chars); "
                    f"got {spec!r}"
                ),
            )
        )


def _parse_binding_override(spec: str) -> tuple[str, str]:
    """Parse a ``--binding KEY=VALUE`` spec into a ``(key, value)`` pair.

    The key is validated against :data:`BindingId` constraints at the
    CLI boundary; the value is passed through unchanged so the
    bindings-resolution layer can coerce it per source type.
    """

    return _parse_kv_spec(
        spec,
        flag="--binding",
        transform=lambda value: value,
        key_validator=_validate_binding_key,
    )


# ---------------------------------------------------------------------------
# --row TYPE FIELD=value FIELD=value parsing helpers
#
# Supports multi-row entry for informational modelos whose filing
# content is a list of records rather than scalar casilla values.
# Supported types: miembro (M184 atribución member), vinculada (M232
# operación vinculada).  Each ``--row`` flag takes a string of the
# form ``TYPE FIELD=value [FIELD=value ...]``.
# ---------------------------------------------------------------------------

_ROW_TYPES_SUPPORTED: frozenset[str] = frozenset({"miembro", "vinculada", "operador", "contraparte"})
_ROW_DECIMAL_FIELDS: frozenset[str] = frozenset(
    {"porcentaje", "importe", "importe_Q1", "importe_Q2", "importe_Q3", "importe_Q4"}
)


def _parse_row_spec(spec: str) -> ModeloDetailRow:
    """Parse a ``--row TYPE FIELD=value ...`` spec into a typed row model.

    The first whitespace-separated token is the row type (``miembro`` or
    ``vinculada``). Remaining tokens are ``KEY=VALUE`` pairs.  Raises
    :class:`typer.BadParameter` on any parse or validation error.
    """

    parts = spec.split()
    if not parts:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_empty_spec",
                default="--row spec cannot be empty; expected TYPE FIELD=value [...]",
            )
        )
    row_type = parts[0].lower()
    if row_type not in _ROW_TYPES_SUPPORTED:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_unknown_type",
                default=(
                    f"--row type {row_type!r} is not recognised; "
                    f"supported types: {sorted(_ROW_TYPES_SUPPORTED)}"
                ),
                row_type=row_type,
                supported=", ".join(sorted(_ROW_TYPES_SUPPORTED)),
            )
        )
    kv_raw: dict[str, str] = {}
    for token in parts[1:]:
        if "=" not in token:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.row_kv_format_error",
                    default=f"--row field {token!r} must be in KEY=VALUE format",
                    token=token,
                )
            )
        key, _, value = token.partition("=")
        if not key:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.row_empty_key",
                    default=f"--row field key cannot be empty in {token!r}",
                    token=token,
                )
            )
        kv_raw[key] = value
    try:
        kv_pairs: dict[str, str | Decimal] = {
            k: Decimal(v) if k in _ROW_DECIMAL_FIELDS else v for k, v in kv_raw.items()
        }
        if row_type == "miembro":
            return Modelo184MemberRow(row_type="miembro", **kv_pairs)  # type: ignore[arg-type]
        elif row_type == "vinculada":
            return Modelo232VinculadaRow(row_type="vinculada", **kv_pairs)  # type: ignore[arg-type]
        elif row_type == "operador":
            row_m349 = Modelo349OperadorRow(row_type="operador", **kv_pairs)  # type: ignore[arg-type]
            # NIF format check is advisory at parse time — invalid format raises BadParameter.
            nif = str(kv_pairs.get("nif_comunitario", ""))
            pais = str(kv_pairs.get("codigo_pais", ""))
            if nif and pais and not validate_m349_nif_format(nif, pais):
                raise typer.BadParameter(
                    tr(
                        "cli.app.modelo.work.row_m349_invalid_nif",
                        default=(
                            f"--row operador: nif_comunitario {nif!r} does not match "
                            f"the expected NIF-IVA format for country {pais!r} "
                            f"(Council Directive 2006/112/EC Annex XI)"
                        ),
                        nif=nif,
                        pais=pais,
                    )
                )
            return row_m349
        else:
            return Modelo347ContraparteRow(row_type="contraparte", **kv_pairs)  # type: ignore[arg-type]
    except typer.BadParameter:
        raise
    except (ValidationError, TypeError, ValueError, ArithmeticError) as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_validation_error",
                default=f"--row {row_type!r} failed validation: {exc}",
                row_type=row_type,
                error=str(exc),
            )
        ) from exc


def _validate_m184_share_sum(rows: tuple[ModeloDetailRow, ...]) -> None:
    """Raise BadParameter when M184 member shares do not sum to 100%.

    Only checked when at least one miembro row is present and all
    miembro rows have been supplied (cannot check partial sets).
    The AEAT rule: the sum of all member share_percentages MUST equal
    exactly 100% per filing.
    """

    member_rows = [r for r in rows if isinstance(r, Modelo184MemberRow)]
    if not member_rows:
        return
    total = sum(r.porcentaje for r in member_rows)
    if total != Decimal("100"):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.row_m184_shares_not_100",
                default=(
                    f"M184 miembro rows: share percentages must sum to exactly 100%; "
                    f"got {total} across {len(member_rows)} rows"
                ),
                total=str(total),
                count=str(len(member_rows)),
            )
        )


def _validate_m347_threshold(rows: tuple[ModeloDetailRow, ...]) -> None:
    """Raise BadParameter when any M347 contraparte row is below the €3,005.06 threshold.

    RD 1065/2007 art. 31.1: only counterparties with annual operations exceeding
    €3,005.06 must be declared.  The check applies per-row, not as a sum across
    rows, because each row is one declared counterparty.
    """

    contraparte_rows = [r for r in rows if isinstance(r, Modelo347ContraparteRow)]
    for row in contraparte_rows:
        total = row.importe_total
        if total <= M347_THRESHOLD_EUR:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.row_m347_below_threshold",
                    default=(
                        f"M347 contraparte row (nif={row.nif!r}): importe total {total} "
                        f"does not exceed the €{M347_THRESHOLD_EUR} threshold "
                        f"required by RD 1065/2007 art. 31.1"
                    ),
                    nif=row.nif,
                    total=str(total),
                    threshold=str(M347_THRESHOLD_EUR),
                )
            )


@bindings_app.command("list", help=tr("cli.app.modelo.bindings.list_help"))
def bindings_list(
    ctx: typer.Context,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.bindings.modelo_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.app.modelo.bindings.year_help")),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.app.modelo.bindings.period_help")),
    ] = None,
    missing: Annotated[
        bool,
        typer.Option("--missing", help=tr("cli.app.modelo.bindings.missing_help")),
    ] = False,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help=tr("cli.app.modelo.bindings.as_of_help")),
    ] = None,
) -> None:
    """List bindings across modelos. All filters are optional refinements.

    With no filter, the full configured-binding set across every modelo
    in the registry is returned. ``--modelo`` narrows to one modelo;
    ``--year`` + ``--period`` further narrow to that revision. ``--year``
    alone resolves the revision covering that filing year — the same
    revision a work unit created for the same modelo / year resolves —
    so the reported binding ids match the calculation. ``--missing``
    filters to the bindings not yet resolvable from current state: it
    drops constant-valued bindings and any binding the active profile
    already satisfies.
    """

    service = _service()
    targets = tuple(str(m.id) for m in service._authority.modelos) if modelo is None else (modelo,)
    per_modelo_reports = []
    for target in targets:
        try:
            if year is not None and period is not None:
                resolved_year, resolved_period = _resolve_year_period(year, period, modelo=target)
                report = _run_query(
                    lambda code=target, fy=resolved_year, rp=resolved_period: service.bindings_for_scope(
                        code,
                        filing_year=fy,
                        period=rp,
                        as_of=_as_of(as_of),
                    )
                )
            elif year is not None:
                # --year alone: resolve the revision covering that year
                # rather than the latest revision, so a multi-revision
                # modelo (e.g. Modelo 100) reports the right binding ids.
                report = _run_query(
                    lambda code=target, fy=year: service.bindings_for_year(
                        code,
                        filing_year=fy,
                        as_of=_as_of(as_of),
                    )
                )
            else:
                report = _run_query(lambda code=target: service.bindings(code, period=period, as_of=_as_of(as_of)))
        except Exception:
            if modelo is not None:
                raise
            continue
        per_modelo_reports.append(report)
    merged_rows: list[dict[str, object]] = []
    text_rows: list[str] = []
    for report in per_modelo_reports:
        rows = report.rows
        if missing:
            profile_resolved = _profile_resolved_binding_ids(report)
            rows = tuple(
                row for row in rows if row.source != "constant_value" and row.binding_id not in profile_resolved
            )
        for row in rows:
            merged_rows.append(
                {
                    "modelo": report.code,
                    "revision": report.revision,
                    "filing_year": report.filing_year,
                    "period": report.period,
                    "binding_id": row.binding_id,
                    "source": row.source,
                    "readiness": _readiness_for_source(row.source),
                    "typed_enum": row.typed_enum,
                    "input_channel": row.input_channel,
                    "borrador_capable": row.borrador_capable,
                }
            )
            text_rows.append(
                f"{report.code}\t{report.revision}\t{report.period or '-'}\t"
                f"{row.binding_id}\t{row.source}\t{_readiness_for_source(row.source)}\t{row.typed_enum or '-'}\t"
                f"{row.input_channel}\t{row.borrador_capable}"
            )
    payload = {
        "operation": "registry.modelo.bindings.list",
        "modelo_filter": modelo,
        "year_filter": year,
        "period_filter": period,
        "missing_filter": missing,
        "binding_count": len(merged_rows),
        "bindings": merged_rows,
    }
    lines = [
        "operation\tregistry.modelo.bindings.list",
        f"modelo_filter\t{modelo or '-'}",
        f"year_filter\t{year if year is not None else '-'}",
        f"period_filter\t{period or '-'}",
        f"missing_filter\t{missing}",
        f"binding_count\t{len(merged_rows)}",
        "modelo\trevision\tperiod\tbinding_id\tsource\treadiness\ttyped_enum\tinput_channel\tborrador_capable",
    ]
    lines.extend(text_rows)
    _emit(ctx, payload, lines)


@bindings_app.command("preview", help=tr("cli.app.modelo.bindings.preview_help"))
def bindings_preview(
    ctx: typer.Context,
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.bindings.modelo_help")),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", help=tr("cli.app.modelo.bindings.year_help")),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help=tr("cli.app.modelo.bindings.period_help")),
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option(
            "--binding",
            help=tr("cli.app.modelo.bindings.override_help"),
        ),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--as-of", help=tr("cli.app.modelo.bindings.as_of_help")),
    ] = None,
) -> None:
    """Resolve temporary ``--binding`` overrides without mutating state.

    The override map is parsed at the CLI boundary; the registry
    binding catalogue is loaded for the active modelo / year /
    period and any override targeting a known binding id is
    echoed back resolved. Unknown override keys fail with a
    suggestion list sourced from the same catalogue.
    """

    _require_binding_scope(modelo=modelo, year=year, period=period)
    assert modelo is not None
    assert year is not None
    assert period is not None
    overrides = dict(_parse_binding_override(spec) for spec in (binding or ()))
    resolved_year, resolved_period = _resolve_year_period(year, period, modelo=modelo)
    report = _run_query(
        lambda: _service().bindings_for_scope(
            modelo, filing_year=resolved_year, period=resolved_period, as_of=_as_of(as_of)
        )
    )
    known_ids = {row.binding_id for row in report.rows}
    unknown_keys = sorted(set(overrides) - known_ids)
    if unknown_keys:
        suggestion = ", ".join(sorted(known_ids))
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.bindings.unknown_keys",
                keys=unknown_keys,
                code=report.code,
                revision=report.revision,
                period=report.period,
                suggestion=suggestion,
            )
        )
    payload = {
        "operation": "registry.modelo.bindings.preview",
        "modelo": report.code,
        "revision": report.revision,
        "filing_year": report.filing_year,
        "period": report.period,
        "override_count": len(overrides),
        "binding_count": len(report.rows),
        "bindings": [
            {
                "binding_id": row.binding_id,
                "source": row.source,
                "readiness": _readiness_for_source(row.source),
                "typed_enum": row.typed_enum,
                "override": overrides.get(row.binding_id),
            }
            for row in report.rows
        ],
    }
    lines = [
        "operation\tregistry.modelo.bindings.preview",
        f"modelo\t{report.code}",
        f"revision\t{report.revision}",
        f"filing_year\t{report.filing_year}",
        f"period\t{report.period}",
        f"override_count\t{len(overrides)}",
        f"binding_count\t{len(report.rows)}",
        "binding_id\tsource\treadiness\toverride",
    ]
    lines.extend(
        "\t".join(
            (
                row.binding_id,
                row.source,
                _readiness_for_source(row.source),
                overrides.get(row.binding_id) or "-",
            )
        )
        for row in report.rows
    )
    _emit(ctx, payload, lines)


def _require_binding_scope(*, modelo: str | None, year: int | None, period: str | None) -> None:
    """Report every missing required binding-scope option at once."""

    missing = [
        option
        for option, value in (("--modelo", modelo), ("--year", year), ("--period", period))
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        raise typer.BadParameter(tr("cli.app.modelo.bindings.missing_required_options", options=", ".join(missing)))


@app.command("formulas")
def formulas(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Argument(help=tr("cli.app.modelo.formulas.modelo_help"))],
    period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.formulas.period_help"))] = None,
    as_of: Annotated[str | None, typer.Option("--as-of", help=tr("cli.app.modelo.formulas.as_of_help"))] = None,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            help=tr(
                "cli.app.modelo.formulas.explain_help",
                default=(
                    "Include the legal_refs and source_refs that ground each formula "
                    "in the text output. The JSON payload always carries them."
                ),
            ),
        ),
    ] = False,
) -> None:
    report = _run_query(lambda: _service().formulas(modelo, period=period, as_of=_as_of(as_of)))
    if explain:
        lines = [
            "formula_id\ttarget\tinputs\tlegal_refs\tsource_refs",
            *[
                f"{row.formula_id}\t{row.target}\t"
                f"{', '.join((*row.input_casillas, *row.input_bindings, *row.input_parameters))}\t"
                f"{', '.join(row.legal_refs)}\t"
                f"{', '.join(row.source_refs)}"
                for row in report.rows
            ],
        ]
    else:
        lines = [
            "formula_id\ttarget\tinputs",
            *[
                f"{row.formula_id}\t{row.target}\t"
                f"{', '.join((*row.input_casillas, *row.input_bindings, *row.input_parameters))}"
                for row in report.rows
            ],
        ]
    _emit(ctx, report, lines)


def _parse_typed_cli_observations[ObservationT: BaseModel](
    values: list[str] | None,
    *,
    model: type[ObservationT],
    flag: str,
) -> tuple[ObservationT, ...]:
    """Parse a list of raw JSON strings into typed observation models.

    Each string must be a JSON object conforming to *model*'s schema.
    ``typer.BadParameter`` is raised on JSON syntax errors, non-object
    JSON, or pydantic validation failures so the CLI error boundary
    presents a clear operator-facing refusal instead of an opaque
    traceback.
    """
    parsed: list[ObservationT] = []
    for raw in values or ():
        try:
            top = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_parse_error", flag=flag, pos=exc.pos)) from exc
        if not isinstance(top, dict):
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_not_object", flag=flag))
        try:
            # model_validate_json uses pydantic's JSON-mode coercions (string →
            # Decimal, string → StrEnum) even when the model declares strict=True
            # at the Python-object boundary.
            parsed.append(model.model_validate_json(raw))
        except ValidationError as exc:
            details = "; ".join(f"{'.'.join(str(s) for s in e['loc'])}: {e['msg']}" for e in exc.errors())
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.aggregate.json_validation_error",
                    flag=flag,
                    details=details,
                )
            ) from exc
    return tuple(parsed)


@app.command(
    "aggregate",
    help=tr(
        "cli.app.modelo.aggregate_help",
        default=(
            "Run the backend per-modelo aggregation service from explicit canonical observations "
            "(ledger_transaction, purchase_invoice_evidence, payable_invoice, collectible_invoice)."
        ),
    ),
)
def aggregate_modelo(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.modelo.aggregate.modelo_help"))],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.modelo.aggregate.period_help"))],
    retencion_observation: Annotated[
        list[str] | None,
        typer.Option(
            "--retencion-observation",
            help=tr("cli.app.modelo.aggregate.retencion_observation_help"),
        ),
    ] = None,
    counterpart_observation: Annotated[
        list[str] | None,
        typer.Option(
            "--counterpart-observation",
            help=tr("cli.app.modelo.aggregate.counterpart_observation_help"),
        ),
    ] = None,
    foreign_asset_observation: Annotated[
        list[str] | None,
        typer.Option(
            "--foreign-asset-observation",
            help=tr("cli.app.modelo.aggregate.foreign_asset_observation_help"),
        ),
    ] = None,
) -> None:
    """Delegate per-modelo aggregation execution to the backend service."""

    command = PerModeloAggregationCommand(
        modelo=modelo,
        period=period,
        retencion_observations=_parse_typed_cli_observations(
            retencion_observation,
            model=RetencionObservation,
            flag="--retencion-observation",
        ),
        counterpart_observations=_parse_typed_cli_observations(
            counterpart_observation,
            model=CounterpartObservation,
            flag="--counterpart-observation",
        ),
        foreign_asset_observations=_parse_typed_cli_observations(
            foreign_asset_observation,
            model=ForeignAssetIngestObservation,
            flag="--foreign-asset-observation",
        ),
    )
    result = aggregate_per_modelo(command)
    payload = {
        "operation": "modelo.aggregate",
        **result.model_dump(mode="json"),
    }
    source_kinds = ", ".join(source_kind.value for source_kind in result.source_kinds) or "-"
    lines = [
        "operation\tmodelo.aggregate",
        f"modelo\t{result.modelo}",
        f"period\t{result.period}",
        f"provider\t{result.provider.value}",
        f"observation_count\t{result.log_fields.observation_count}",
        f"source_kinds\t{source_kinds}",
        f"result_row_count\t{result.log_fields.result_row_count}",
    ]
    _emit(ctx, payload, lines)


work_app = typer.Typer(
    name="work",
    help=tr("cli.app.modelo.work.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(work_app, name="work")


def _work_unit_payload(unit: WorkUnit) -> WorkUnitPayload:
    from ._modelo_payloads import WorkUnitPayload as _WorkUnitPayload

    return _WorkUnitPayload(
        work_unit_id=unit.work_unit_id,
        bucket_id=unit.bucket_id,
        modelo=str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
        revision_id=unit.revision_id,
        name=unit.name,
        state=unit.state.value,
        created_at=unit.created_at.isoformat(),
        updated_at=unit.updated_at.isoformat(),
        discarded_at=unit.discarded_at.isoformat() if unit.discarded_at else None,
        discarded_by=unit.discarded_by,
        discard_reason=unit.discard_reason,
        causante_ccaa=unit.causante_ccaa.value if unit.causante_ccaa is not None else None,
    )


def _work_unit_lines(unit: WorkUnit) -> list[str]:
    lines = [
        f"work_unit_id\t{unit.work_unit_id}",
        f"bucket_id\t{unit.bucket_id}",
        f"modelo\t{unit.modelo}",
        f"filing_year\t{unit.filing_year}",
        f"period\t{unit.period}",
        f"revision_id\t{unit.revision_id}",
        f"name\t{unit.name}",
        f"state\t{unit.state.value}",
        f"created_at\t{unit.created_at.isoformat()}",
        f"updated_at\t{unit.updated_at.isoformat()}",
    ]
    if unit.discarded_at is not None:
        lines.append(f"discarded_at\t{unit.discarded_at.isoformat()}")
    if unit.discarded_by is not None:
        lines.append(f"discarded_by\t{unit.discarded_by}")
    if unit.discard_reason is not None:
        lines.append(f"discard_reason\t{unit.discard_reason}")
    if unit.causante_ccaa is not None:
        lines.append(f"causante_ccaa\t{unit.causante_ccaa.value}")
    lines.extend(_work_unit_plazo_lines(unit))
    return lines


def _work_unit_plazo_lines(unit: WorkUnit) -> list[str]:
    """Return plazo voluntario and extemporaneidad lines for the work unit.

    Appends zero lines when the registry has no deadline window for the
    unit's (modelo, filing_year, period) combination — a benign data gap
    that must not surface as an error.  When the plazo is known and
    already closed, appends recargo Art. 27 LGT information so the
    operator can see the applicable surcharge before filing.
    """
    from ...domain.deadlines._plazo import resolve_filing_closes_on
    from ...domain.deadlines._recargo import build_recovery_for_overdue

    closes_on = resolve_filing_closes_on(str(unit.modelo), unit.filing_year, unit.period)
    if closes_on is None:
        return []

    today = date.today()
    out: list[str] = [f"plazo_closes_on\t{closes_on.isoformat()}"]

    if today <= closes_on:
        days_remaining = (closes_on - today).days
        out.append(
            tr(
                "cli.app.modelo.work.plazo_days_remaining",
                default="days_remaining\t{days_remaining}",
                days_remaining=days_remaining,
            )
        )
        return out

    days_late = (today - closes_on).days
    if days_late < 1:
        return out

    out.append(f"days_overdue\t{days_late}")
    try:
        recovery = build_recovery_for_overdue(
            days_late=days_late,
            modelo=str(unit.modelo),
            period=unit.period,
        )
    except (ValueError, Exception):
        out.append(
            tr(
                "cli.app.modelo.work.plazo_vencido_warning",
                default=(
                    "AVISO: plazo voluntario vencido. Presenta con recargo "
                    "Art. 27 LGT antes de recibir requerimiento de la AEAT."
                ),
            )
        )
        return out

    band = recovery.recargo_band
    out.extend([
        f"recargo_band\t{band.id}",
        f"recargo_pct\t{band.surcharge_pct}",
        f"recargo_interest_applies\t{band.interest_applies}",
        f"recargo_legal_ref\t{band.legal_ref}",
        tr(
            "cli.app.modelo.work.plazo_vencido_warning",
            default=(
                "AVISO: plazo voluntario vencido. Presenta con recargo "
                "Art. 27 LGT antes de recibir requerimiento de la AEAT."
            ),
        ),
    ])
    return out


_FILING_YEAR_MIN = 2000
_FILING_YEAR_MAX = 2099
"""Filing-year bounds enforced by :class:`WorkUnit` (``ge=2000, le=2099``).

Validating the bound at the CLI boundary turns an out-of-range year
into a clean, translated, value-naming refusal instead of a generic
pydantic-validation boundary error.
"""


def _validate_filing_year(year: int) -> None:
    """Refuse a filing year outside the registry-supported range.

    ``--year 1899`` previously composed the token ``1899-Q1``, passed
    the period regex, then failed deep in :class:`WorkUnit` validation
    and surfaced only the generic English "command input failed
    validation" boundary error. The refusal now names the bad year and
    renders in the operator's language.
    """

    if not _FILING_YEAR_MIN <= year <= _FILING_YEAR_MAX:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.year_out_of_range",
                year=year,
                minimum=_FILING_YEAR_MIN,
                maximum=_FILING_YEAR_MAX,
            )
        )


def _revision_covers_year(revision_id: str, year: int, definition: object) -> bool:
    """Return True when the revision's period_selector applies to *year*.

    Revisions declare their year scope through ``PeriodSelector``:
    - ``years = [2024]`` — explicit year list
    - ``year_from = 2019, year_to = 2023`` — closed range
    - ``year_from = 2024`` (no ``year_to``) — open-ended from that year

    A revision with no year constraints (``year_from`` is None and
    ``years`` is empty) is treated as applicable to every year.
    """

    rev = definition.revisions.get(revision_id)  # type: ignore[union-attr]
    if rev is None:
        return False
    selector = rev.period_selector
    if selector.years:
        return year in selector.years
    if selector.year_from is None:
        # No year constraint — applies to all years.
        return True
    if selector.year_to is None:
        return year >= selector.year_from
    return selector.year_from <= year <= selector.year_to


def _validate_registry_target(modelo: str, revision_id: str, year: int) -> None:
    """Refuse a work-unit create that names an unknown modelo or revision.

    Without this gate ``modelo work create --modelo 999 --revision
    nonexistent`` provisions a work unit that ``calculate`` then
    silently treats as a Modelo 303 default. Both axes are checked
    against the validated registry authority — the single source of
    truth for modelo / revision identity — and refused cleanly with a
    translated error naming the unknown value.

    Additionally, the revision's ``period_selector`` is checked against
    the supplied filing year.  A 2026 revision (e.g. DANA rules) applied
    to a 2024 filing silently uses wrong parameters; this guard refuses
    the cross-year combination with an explicit message.
    """

    from ...core.resources import resources

    authority = resources().modelos.authority
    modelo_code = modelo.strip()
    try:
        definition = authority.modelo(modelo_code)
    except RegistrySnapshotError as exc:
        known = ", ".join(sorted(str(item.id) for item in authority.modelos))
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.unknown_modelo",
                modelo=modelo_code,
                known=known,
            )
        ) from exc
    revision = revision_id.strip()
    if revision not in definition.revisions:
        declared = ", ".join(sorted(str(item) for item in definition.revisions))
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.unknown_revision",
                revision=revision,
                modelo=modelo_code,
                declared=declared,
            )
        )
    if not _revision_covers_year(revision, year, definition):
        # Build a human-readable description of which years each revision covers.
        applicable = ", ".join(
            rev_id
            for rev_id in sorted(definition.revisions)
            if _revision_covers_year(rev_id, year, definition)
        ) or tr(
            "cli.app.modelo.work.revision_year_mismatch_no_match",
            default="ninguna revisión cubre ese ejercicio",
        )
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.revision_year_mismatch",
                revision=revision,
                modelo=modelo_code,
                filing_year=year,
                applicable=applicable,
            )
        )


def _guard_modelo_applicability(modelo: str, *, allow_not_applicable: bool) -> None:
    """Refuse a ``work create`` for a modelo the active profile cannot file.

    Round-4 finding M4: ``work create --modelo 202`` succeeded for a
    natural person with no guard, provisioning a work unit for a modelo
    the operator's taxpayer model positively excludes — the engine
    would then be asked to run an IS cuota for a natural person.

    The guard consults :func:`derive_modelo_applicability` against the
    active profile's three-axis taxpayer model (corporate-entity ADR §4
    routing contract). A ``NOT_APPLICABLE`` verdict (e.g. Modelo 202
    for a natural person, Modelo 100 for a sociedad limitada) or an
    ``ATTRIBUTION_PASS_THROUGH`` verdict (a cuota self-assessment asked
    of an attribution entity, which runs no cuota of its own) is
    refused with the registry-grounded rationale. An ``INCOMPLETE``
    verdict — undeclared taxpayer model, or a modelo the seed table
    cannot yet decide — does not block: the operator may not have
    declared their type yet, and the seed coverage is intentionally
    narrow; refusing there would be a confident wrong answer of the
    opposite kind.

    The ``--allow-not-applicable`` escape hatch lets an operator who
    has a genuine reason override the refusal; the override is recorded
    in the create payload so the audit trail shows the guard was
    bypassed deliberately.
    """

    from ...application.workflow._persistence import workflow_state_repository
    from ...domain.calculations.registry.applicability import (
        ApplicabilityVerdict,
        derive_modelo_applicability,
    )
    from ._common import _profile_to_taxpayer
    from ._errors import CliRefusedBoundaryError

    state = workflow_state_repository().load()
    profile = _profile_to_taxpayer(state)
    applicability = derive_modelo_applicability(profile, modelo.strip())
    blocking = {
        ApplicabilityVerdict.NOT_APPLICABLE,
        ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
    }
    if applicability.verdict not in blocking:
        return
    if allow_not_applicable:
        return
    raise CliRefusedBoundaryError(
        tr(
            "cli.app.modelo.work.create_not_applicable_refused",
            default=(
                "Modelo {modelo} no aplica al tipo de contribuyente del "
                "perfil activo: {reason} Si tiene un motivo para crear la "
                "unidad de trabajo de todas formas, repita el comando con "
                "--allow-not-applicable."
            ),
            modelo=modelo.strip(),
            reason=applicability.reason,
        )
    )


#: Modelos that are not yet fully supported for work-unit creation.
#: Includes both registry-registered stubs (casilla/formula authoring
#: incomplete) and autonomic/non-resident modelos that are filed outside
#: the national AEAT CLI surface.  ``work create`` is refused with a
#: legally-grounded message that names the obligation and the operative
#: filing surface.
_STUB_ONLY_MODELOS: frozenset[str] = frozenset(
    {"151", "210", "600", "620", "650", "660", "714", "721"}
)

#: Maps each stub-only modelo code to its dedicated locale key so that the
#: refusal message cites the correct legal authorities for that modelo.
_STUB_MODELO_LOCALE_KEYS: dict[str, str] = {
    "151": "cli.app.modelo.work.create_stub_modelo_151_refused",
    "210": "cli.app.modelo.work.create_stub_modelo_210_refused",
    "600": "cli.app.modelo.work.create_stub_modelo_600_refused",
    "620": "cli.app.modelo.work.create_stub_modelo_620_refused",
    "650": "cli.app.modelo.work.create_stub_modelo_650_refused",
    "660": "cli.app.modelo.work.create_stub_modelo_660_refused",
    "714": "cli.app.modelo.work.create_stub_modelo_714_refused",
    "721": "cli.app.modelo.work.create_stub_modelo_refused",
}

# Parity guard: every frozenset entry must have a locale key mapping.
# This fires at import time during tests rather than silently at runtime.
assert set(_STUB_MODELO_LOCALE_KEYS) == _STUB_ONLY_MODELOS, (
    f"_STUB_MODELO_LOCALE_KEYS keys {set(_STUB_MODELO_LOCALE_KEYS)} "
    f"do not match _STUB_ONLY_MODELOS {_STUB_ONLY_MODELOS}"
)


def _guard_stub_modelo(modelo: str) -> None:
    """Refuse ``work create`` for stub and autonomic modelos.

    Stubs registered in the AEAT registry (casilla/formula authoring
    incomplete):

    - Modelo 721 (declaración informativa sobre monedas virtuales situadas
      en el extranjero): Legal refs: Ley 11/2021 Art. 13 / DA 10ª,
      Orden HFP/887/2023, RD 1065/2007 Art. 42 quáter.

    - Modelo 151 (régimen especial impatriados, "Ley Beckham"): Legal refs:
      Ley 35/2006 Art. 93 LIRPF, RD 439/2007 Art. 113, Orden EHA/2887/2008.

    - Modelo 714 (Impuesto sobre el Patrimonio): Legal refs: Ley 19/1991
      Art. 28, Orden HAC/1023/2021.

    Autonomic / non-resident modelos (filed outside national AEAT CLI):

    - Modelo 210 (IRNR no residentes): RD Legislativo 5/2004 (TRLIRNR),
      Art. 28.  Filed via AEAT Sede Electrónica G320.

    - Modelo 600 (ITP-AJD transmisiones patrimoniales): Ley 28/1990
      ITPyAJD.  Filed at the Hacienda of the CCAA where the asset is
      located (impuesto cedido).

    - Modelo 620 (ITP-AJD transmisiones medios de transporte usados):
      Ley 28/1990 ITPyAJD.  Filed at the Hacienda of the CCAA where the
      asset is located (impuesto cedido).

    - Modelo 650 (ISD Sucesiones): Ley 29/1987 LISyD, Art. 67 RISD
      (plazo 6 meses, prorrogable 6 meses).  Filed at the autonomic
      Hacienda of the CCAA where the causante had habitual residence
      (Ley 22/2009 Art. 32).

    - Modelo 660 (ISD informativa caudal relicto): Ley 29/1987 LISyD.
      Accompanies Modelo 650 for sociedades o conjunto declarations.

    Without this guard the CLI would attempt registry lookups for modelos
    it does not model, leaving the taxpayer with no path to a valid filing.
    Legal refs carried in the error match the governing statute.
    """

    from ._errors import CliRefusedBoundaryError

    modelo_code = modelo.strip()
    if modelo_code not in _STUB_ONLY_MODELOS:
        return

    # Literal tr() call per stub so the locale scaffold can discover each
    # key and populate all four locale files.
    _refusals: dict[str, str] = {
        "151": tr("cli.app.modelo.work.create_stub_modelo_151_refused", modelo=modelo_code),
        "210": tr("cli.app.modelo.work.create_stub_modelo_210_refused", modelo=modelo_code),
        "600": tr("cli.app.modelo.work.create_stub_modelo_600_refused", modelo=modelo_code),
        "620": tr("cli.app.modelo.work.create_stub_modelo_620_refused", modelo=modelo_code),
        "650": tr("cli.app.modelo.work.create_stub_modelo_650_refused", modelo=modelo_code),
        "660": tr("cli.app.modelo.work.create_stub_modelo_660_refused", modelo=modelo_code),
        "714": tr("cli.app.modelo.work.create_stub_modelo_714_refused", modelo=modelo_code),
        "721": tr("cli.app.modelo.work.create_stub_modelo_refused", modelo=modelo_code),
    }
    raise CliRefusedBoundaryError(_refusals[modelo_code])


#: Registry-validation translated-message keys that signal an
#: unsatisfied calculation input the operator can supply with
#: ``--binding`` / ``--relation``. The first ``work calculate`` of a
#: modelo that consumes a binding fails with one of these; the guidance
#: helper turns the bare refusal into a self-correcting message.
_MISSING_INPUT_TRANSLATED_MESSAGES: frozenset[str] = frozenset(
    {
        "errors.calc.binding_value_missing",
        "errors.calc.bound_casilla_binding_value_missing",
        "errors.calc.enum_binding_value_missing",
        "errors.calc.relation_value_missing",
    }
)


def _missing_binding_guidance(error: RegistryValidationError, work_unit_id: str) -> str:
    """Return the missing-binding refusal enriched with operator guidance.

    The registry engine names the unsatisfied binding / relation but
    leaves the operator with no path forward. When the failure is a
    missing-input class, append the ``--binding KEY=VALUE`` syntax and a
    concrete ``bindings list --missing`` command scoped to the work
    unit's modelo / year / period so the next attempt can succeed.
    Non-input registry-validation errors fall through unchanged.
    """

    base = tr(error.translated_message, **(error.context or {})) if error.translated_message is not None else str(error)
    if error.translated_message not in _MISSING_INPUT_TRANSLATED_MESSAGES:
        return base

    discover_command = "aeat app modelo bindings list --missing"
    # Loading the work unit only refines the discovery command with the
    # concrete modelo / year / period. It is best-effort enrichment: any
    # failure (missing unit, no active session) degrades to the generic
    # bindings-list command rather than masking the original refusal.
    try:
        unit: WorkUnit | None = get_work_unit(work_unit_id)
    except Exception:
        unit = None
    if unit is not None:
        discover_command = (
            f"aeat app modelo bindings list --modelo {unit.modelo} "
            f"--year {unit.filing_year} --period {unit.period} --missing"
        )
    return tr(
        "cli.app.modelo.work.missing_binding_guidance",
        default=(
            "{base} Supply the value with --binding KEY=VALUE on this "
            "command, or run `{discover}` to list every binding the "
            "calculation still needs."
        ),
        base=base,
        discover=discover_command,
    )


@work_app.command("create", help=tr("cli.app.modelo.work.create_help"))
def work_create(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
    ],
    period: Annotated[
        str,
        typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
    ],
    revision: Annotated[
        str,
        typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
    ],
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option("--name", help=tr("cli.app.modelo.work.name_help")),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    allow_not_applicable: Annotated[
        bool,
        typer.Option(
            "--allow-not-applicable",
            help=tr(
                "cli.app.modelo.work.allow_not_applicable_help",
                default=(
                    "Crear la unidad de trabajo aunque el modelo no aplique al tipo de contribuyente del perfil activo."
                ),
            ),
        ),
    ] = False,
    causante_ccaa_raw: Annotated[
        str | None,
        typer.Option(
            "--causante-ccaa",
            help=tr(
                "cli.app.modelo.work.causante_ccaa_help",
                default=(
                    "CCAA de residencia habitual del causante (ISD Modelo 650/660) o CCAA donde se ubica el bien "
                    "transmitido (ITPyAJD Modelo 600/620). Determina la Hacienda competente (Ley 22/2009 Art. 32). "
                    "País Vasco y Navarra son regímenes forales; consulta la Hacienda autonómica correspondiente."
                ),
            ),
        ),
    ] = None,
) -> None:
    """Create or load a modelo work unit. Idempotent on the four-axis key."""

    # User-input validation order: stub guard runs before registry lookup
    # because several stub modelos (210, 600, 620, 650, 660) are not
    # registry-registered; _validate_registry_target would refuse them
    # with a generic "Modelo desconocido" before the legally-grounded
    # refusal fires.  Registry-registered stubs (151, 714, 721) are
    # intercepted equally early.
    _validate_filing_year(year)
    # Foral guard: parse before the stub guard so the operator receives a
    # domain-correct ForalRegimeError rather than a generic "modelo not yet
    # supported" message when a foral CCAA is supplied.  The
    # command_error_boundary decorator surfaces AeatError (including
    # ForalRegimeError) on stderr and exits; no try/except needed here.
    causante_ccaa = parse_tax_region(causante_ccaa_raw) if causante_ccaa_raw is not None else None
    _guard_stub_modelo(modelo)
    _validate_registry_target(modelo, revision, year)
    resolved_year, resolved_period = _resolve_year_period(year, period, modelo=modelo)
    _require_active_profile()
    # Round-4 M4: refuse a work unit for a modelo the active profile's
    # taxpayer model positively excludes (a natural person has no
    # Modelo 202; an attribution entity runs no cuota). The guard runs
    # once the profile is known and before the bucket database is
    # opened by create_work_unit.
    _guard_modelo_applicability(modelo, allow_not_applicable=allow_not_applicable)
    # --bucket-id is an explicit override; without it the work unit binds
    # to the active profile's bucket (never the literal string "default").
    resolved_bucket = bucket_id if bucket_id is not None else _active_bucket_id()
    resolved_actor = actor or _resolve_default_actor()

    # create_work_unit is idempotent on the four-axis key but returns a
    # bare WorkUnit, losing the create-vs-reuse distinction. Resolve the
    # pre-existing unit here so the operator is told plainly whether a
    # new unit was provisioned or an existing one returned.
    existing_units = list_work_units(bucket_id=resolved_bucket, include_discarded=True)
    prior = next(
        (
            candidate
            for candidate in existing_units
            if str(candidate.modelo) == modelo
            and candidate.filing_year == resolved_year
            and candidate.period == resolved_period
            and candidate.revision_id == revision
        ),
        None,
    )
    reused = prior is not None

    unit = create_work_unit(
        bucket_id=resolved_bucket,
        modelo=modelo,
        filing_year=resolved_year,
        period=resolved_period,
        revision_id=revision,
        name=name,
        actor=resolved_actor,
        causante_ccaa=causante_ccaa,
    )

    # A --name supplied on a reuse is not silently dropped: it is applied
    # as a rename so the operator's intent is honoured, and the result
    # reports the rename. On a fresh create the name is already set.
    name_applied: str | None = None
    if reused and name is not None and name.strip() and name.strip() != unit.name:
        unit = rename_work_unit(unit.work_unit_id, name, actor=resolved_actor)
        name_applied = unit.name

    status = "reused" if reused else "created"
    if reused:
        if name_applied is not None:
            status_message = tr(
                "cli.app.modelo.work.create_reused_renamed",
                default=(
                    "Existing work unit returned (idempotent on modelo/year/period/revision); "
                    "nothing new was created. The supplied --name was applied as a rename "
                    "to %{name}."
                ),
                name=name_applied,
            )
        elif name is not None and name.strip():
            status_message = tr(
                "cli.app.modelo.work.create_reused_name_match",
                default=(
                    "Existing work unit returned (idempotent on modelo/year/period/revision); "
                    "nothing new was created. The supplied --name matches the stored name."
                ),
            )
        else:
            status_message = tr(
                "cli.app.modelo.work.create_reused",
                default=(
                    "Existing work unit returned (idempotent on modelo/year/period/revision); "
                    "nothing new was created. Rename it with `aeat app modelo work rename`."
                ),
            )
        operation = "modelo.work.reuse"
    else:
        status_message = tr(
            "cli.app.modelo.work.create_created",
            default="New work unit created.",
        )
        operation = "modelo.work.create"

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkCreateResult

    result = WorkCreateResult.model_validate(
        {
            "operation": operation,
            "status": status,
            "status_message": status_message,
            "name_applied": name_applied,
            "applicability_guard_bypassed": allow_not_applicable,
            **_work_unit_payload(unit).model_dump(mode="python"),
        }
    )
    lines = [
        f"operation\t{operation}",
        f"status\t{status}",
        *_work_unit_lines(unit),
        status_message,
    ]
    # Pre-calificación Art. 96.3 LIRPF: when the operator creates a Modelo 100
    # work unit and the profile declares multiple pagadores with secondary income
    # exceeding €1,500, surface the filing-obligation advisory so they know the
    # income-threshold exemption does not apply.
    if modelo == "100":
        from ...application.overview import build_filing_obligation_advisories as _build_filing_obligation_advisories
        from ...application.user_profile._projections import record_to_values
        from ...application.workflow._models import resolve_active_bucket_id

        _bucket = resolve_active_bucket_id()
        if _bucket is not None:
            from ...application.user_profile._orchestration import profile_storage_session
            from ...application.user_profile._profile_repository import ProfileRepository

            with profile_storage_session(_bucket):
                _rec = ProfileRepository().load(_bucket)
            _raw = record_to_values(_rec.record) if _rec is not None else None
            for _advisory_key in _build_filing_obligation_advisories(_raw):
                lines.append(tr(_advisory_key))
    _emit_envelope(ctx, command=operation, result=result, lines=lines)


@work_app.command("list", help=tr("cli.app.modelo.work.list_help"))
def work_list(
    ctx: typer.Context,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = None,
    include_discarded: Annotated[
        bool,
        typer.Option(
            "--include-discarded",
            help=tr("cli.app.modelo.work.include_discarded_help"),
        ),
    ] = False,
) -> None:
    """List modelo work units. Discarded units are excluded unless asked."""

    _require_active_profile()
    units = list_work_units(bucket_id=bucket_id, include_discarded=include_discarded)
    from ._common import _emit_envelope
    from ._modelo_payloads import WorkListResult

    result = WorkListResult.model_validate(
        {
            "bucket_id_filter": bucket_id,
            "include_discarded": include_discarded,
            "work_unit_count": len(units),
            "work_units": [_work_unit_payload(unit) for unit in units],
        }
    )
    lines = [
        "operation\tmodelo.work.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"include_discarded\t{include_discarded}",
        f"work_unit_count\t{len(units)}",
        "work_unit_id\tbucket_id\tmodelo\tyear\tperiod\trevision_id\tstate\tname",
    ]
    lines.extend(
        "\t".join(
            (
                unit.work_unit_id,
                unit.bucket_id,
                str(unit.modelo),
                str(unit.filing_year),
                unit.period,
                unit.revision_id,
                unit.state.value,
                unit.name,
            )
        )
        for unit in units
    )
    _emit_envelope(ctx, command="modelo.work.list", result=result, lines=lines)


@work_app.command("status", help=tr("cli.app.modelo.work.status_help"))
def work_status(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
) -> None:
    """View one work unit's metadata."""

    work_unit_id = _validate_work_unit_id(work_unit_id)
    _require_active_profile()
    try:
        unit = get_work_unit(work_unit_id)
    except WorkUnitNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc
    from ._common import _emit_envelope
    from ._modelo_payloads import WorkStatusResult

    result = WorkStatusResult.model_validate(_work_unit_payload(unit).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.status", *_work_unit_lines(unit)]
    _emit_envelope(ctx, command="modelo.work.status", result=result, lines=lines)


@work_app.command("rename", help=tr("cli.app.modelo.work.rename_help"))
def work_rename(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help=tr("cli.app.modelo.work.name_help")),
    ],
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
) -> None:
    """Update one work unit's display name (preserves work_unit_id)."""

    work_unit_id = _validate_work_unit_id(work_unit_id)
    _require_active_profile()
    try:
        unit = rename_work_unit(work_unit_id, name, actor=actor or _resolve_default_actor())
    except (WorkUnitNotFoundError, WorkUnitMutationRefusedError) as exc:
        raise _bad_parameter_from_error(exc) from exc
    from ._common import _emit_envelope
    from ._modelo_payloads import WorkRenameResult

    result = WorkRenameResult.model_validate(_work_unit_payload(unit).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.rename", *_work_unit_lines(unit)]
    _emit_envelope(ctx, command="modelo.work.rename", result=result, lines=lines)


@work_app.command("discard", help=tr("cli.app.modelo.work.discard_help"))
def work_discard(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    reason: Annotated[
        str | None,
        typer.Option("--reason", help=tr("cli.app.modelo.work.reason_help")),
    ] = None,
    confirmed: Annotated[
        bool,
        typer.Option("--yes", help=tr("cli.app.modelo.work.discard_yes_help")),
    ] = False,
) -> None:
    """Transition a work unit to discarded state.

    The discard is an audit-grade state transition: revision
    payloads are preserved, the work unit is marked discarded
    with actor + reason captured, and subsequent mutations are
    rejected. Discarded units are excluded from default
    ``aeat app modelo work list`` output.

    The transition is gated by ``--yes``, symmetric with
    ``config profile delete``: an unconfirmed run is refused with
    the exact re-run command.
    """

    work_unit_id = _validate_work_unit_id(work_unit_id)
    if not confirmed:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.discard_requires_yes",
                work_unit_id=work_unit_id,
            )
        )
    _require_active_profile()
    try:
        unit = discard_work_unit(work_unit_id, actor=actor or _resolve_default_actor(), reason=reason)
    except (WorkUnitNotFoundError, WorkUnitAlreadyDiscardedError) as exc:
        raise _bad_parameter_from_error(exc) from exc
    from ._common import _emit_envelope
    from ._modelo_payloads import WorkDiscardResult

    result = WorkDiscardResult.model_validate(_work_unit_payload(unit).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.discard", *_work_unit_lines(unit)]
    _emit_envelope(ctx, command="modelo.work.discard", result=result, lines=lines)


filing_record_app = typer.Typer(
    name="filing-record",
    help=tr("cli.app.modelo.filing_record.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(filing_record_app, name="filing-record")


def _calculation_revision_payload(rev: CalculationRevision) -> CalculationRevisionPayload:
    from ._modelo_payloads import CalculationRevisionPayload, ObservationPayload

    # Typed CasillaObservation envelope carrying full per-casilla
    # provenance (formula_id, operand_refs, operand_values,
    # legal_refs, source_refs). Without this projection the CLI
    # JSON would strip every regulatory grounding signal.
    observations = tuple(
        ObservationPayload(
            casilla_id=obs.casilla_id,
            value=str(obs.value),
            formula_id=obs.formula_id,
            operand_refs=tuple(obs.operand_refs),
            operand_values=tuple(str(v) for v in obs.operand_values),
            legal_refs=tuple(obs.legal_refs),
            source_refs=tuple(obs.source_refs),
        )
        for obs in rev.observations
    )
    return CalculationRevisionPayload(
        calculation_revision_id=rev.calculation_revision_id,
        work_unit_id=rev.work_unit_id,
        state=rev.state.value,
        casilla_values={k: str(v) for k, v in rev.casilla_values.items()},
        observations=observations,
        # Headline result summary: registry-declared result-to-pay /
        # result-to-refund total plus the modelo's key computed
        # casillas, so the JSON consumer gets the same lead figures the
        # text surface shows.
        result_summary=_result_summary_payload(rev),
        binding_overrides={key: str(value) for key, value in rev.binding_overrides.items()},
        inputs_snapshot=dict(rev.inputs_snapshot),
        created_at=rev.created_at.isoformat(),
        updated_at=rev.updated_at.isoformat(),
        verified_at=rev.verified_at.isoformat() if rev.verified_at else None,
        verified_by=rev.verified_by,
        filed_at=rev.filed_at.isoformat() if rev.filed_at else None,
        filed_by=rev.filed_by,
        superseded_at=rev.superseded_at.isoformat() if rev.superseded_at else None,
    )


def _result_summary_lines(rev: CalculationRevision) -> list[str]:
    """Return the headline-result summary block for a calculation revision.

    Leads ``work calculate`` / ``work revision`` text output: a flat
    dump of every casilla (2235 rows for Modelo 100) buries the figures
    an operator looks for. The summary surfaces the registry-declared
    result-to-pay / result-to-refund total and the modelo's key
    computed casillas above the full table. Returns an empty list when
    no registry-grounded summary is available; the full table then
    stands alone.
    """

    from ...application.modelo import calculation_result_summary

    summary = calculation_result_summary(rev)
    if summary is None or not summary.rows:
        return []
    header = tr(
        "cli.app.modelo.work.result_summary_header",
        default="result summary  %{modelo} %{year} %{period}",
        modelo=summary.modelo,
        year=summary.filing_year,
        period=summary.period,
    )
    lines = [header, "role\tcasilla\tvalue\tlabel"]
    for row in summary.rows:
        lines.append(f"{row.role}\t{row.casilla_id}\t{row.value}\t{row.label}")
    return lines


def _result_summary_payload(rev: CalculationRevision) -> tuple[ResultSummaryRowPayload, ...]:
    """Return the headline-result summary rows for the JSON payload."""

    from ...application.modelo import calculation_result_summary
    from ._modelo_payloads import ResultSummaryRowPayload

    summary = calculation_result_summary(rev)
    if summary is None:
        return ()
    return tuple(
        ResultSummaryRowPayload(
            role=row.role,
            casilla_id=row.casilla_id,
            value=str(row.value),
            label=row.label,
        )
        for row in summary.rows
    )


def _calculation_revision_lines(rev: CalculationRevision) -> list[str]:
    lines = [
        f"calculation_revision_id\t{rev.calculation_revision_id}",
        f"work_unit_id\t{rev.work_unit_id}",
        f"state\t{rev.state.value}",
        f"created_at\t{rev.created_at.isoformat()}",
        f"updated_at\t{rev.updated_at.isoformat()}",
    ]
    if rev.verified_at is not None:
        lines.append(f"verified_at\t{rev.verified_at.isoformat()}")
        lines.append(f"verified_by\t{rev.verified_by}")
    if rev.filed_at is not None:
        lines.append(f"filed_at\t{rev.filed_at.isoformat()}")
        lines.append(f"filed_by\t{rev.filed_by}")
    if rev.superseded_at is not None:
        lines.append(f"superseded_at\t{rev.superseded_at.isoformat()}")
    # The headline result summary leads the casilla table so the key
    # figures are readable without scanning the full dump.
    summary_lines = _result_summary_lines(rev)
    if summary_lines:
        lines.extend(summary_lines)
    for casilla, value in sorted(rev.casilla_values.items()):
        lines.append(f"casilla\t{casilla}\t{value}")
    return lines


def _filing_record_payload(record: ModeloRecord) -> ModeloRecordPayload:
    from ._modelo_payloads import ExternalEvidencePayload, ModeloRecordPayload

    external_evidence: ExternalEvidencePayload | None = None
    if record.external_evidence is not None:
        external_evidence = ExternalEvidencePayload(
            kind=record.external_evidence.kind.value,
            reference_id=record.external_evidence.reference_id,
            imported_at=record.external_evidence.imported_at.isoformat(),
        )
    return ModeloRecordPayload(
        filing_record_id=record.filing_record_id,
        work_unit_id=record.work_unit_id,
        calculation_revision_id=record.calculation_revision_id,
        bucket_id=record.bucket_id,
        modelo=str(record.modelo),
        filing_year=record.filing_year,
        period=record.period,
        filed_at=record.filed_at.isoformat(),
        filed_by=record.filed_by,
        notes=record.notes,
        aeat_accepted=record.aeat_accepted,
        status=record.status.value,
        superseded_at=record.superseded_at.isoformat() if record.superseded_at else None,
        superseded_by_filing_record_id=record.superseded_by_filing_record_id,
        external_evidence=external_evidence,
        amends_filing_record_id=record.amends_filing_record_id,
        kind="internal_filing",
        live_submission=False,
    )


def _filing_record_lines(record: ModeloRecord) -> list[str]:
    lines = [
        f"filing_record_id\t{record.filing_record_id}",
        f"work_unit_id\t{record.work_unit_id}",
        f"calculation_revision_id\t{record.calculation_revision_id}",
        f"bucket_id\t{record.bucket_id}",
        f"modelo\t{record.modelo}",
        f"filing_year\t{record.filing_year}",
        f"period\t{record.period}",
        f"filed_at\t{record.filed_at.isoformat()}",
        f"filed_by\t{record.filed_by}",
        f"status\t{record.status.value}",
        f"aeat_accepted\t{str(record.aeat_accepted).lower()}",
    ]
    if record.notes is not None:
        lines.append(f"notes\t{record.notes}")
    if record.superseded_at is not None:
        lines.append(f"superseded_at\t{record.superseded_at.isoformat()}")
    if record.superseded_by_filing_record_id is not None:
        lines.append(f"superseded_by_filing_record_id\t{record.superseded_by_filing_record_id}")
    if record.external_evidence is not None:
        lines.append(f"external_evidence.kind\t{record.external_evidence.kind.value}")
        lines.append(f"external_evidence.reference_id\t{record.external_evidence.reference_id}")
        lines.append(f"external_evidence.imported_at\t{record.external_evidence.imported_at.isoformat()}")
    if record.amends_filing_record_id is not None:
        lines.append(f"amends_filing_record_id\t{record.amends_filing_record_id}")
    lines.append("kind\tinternal_filing")
    lines.append("live_submission\tfalse")
    return lines


def _validate_casilla_key(key: str, spec: str) -> None:
    """Validate a ``--casilla`` key against :data:`CasillaId` constraints."""

    if len(key) > _CASILLA_MAX_LEN or not re.fullmatch(_CASILLA_RE, key):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_casilla_key",
                default=(
                    f"--casilla key {key!r} is not a valid CasillaId "
                    f"(pattern: {_CASILLA_RE!r}, max {_CASILLA_MAX_LEN} chars); "
                    f"got {spec!r}"
                ),
            )
        )


# Casilla data_types that accept a Decimal override via --casilla.
# Non-numeric types (text, boolean, nif, date, etc.) must be supplied
# through --binding or profile sources, not as raw decimal overrides.
_NUMERIC_CASILLA_DATA_TYPES: frozenset[str] = frozenset(
    {"decimal", "money", "integer", "ratio"}
)


def _guard_casilla_data_type(casilla_id: str, revision: object) -> None:
    """Raise BadParameter when the casilla is non-numeric.

    Supplying a decimal value for a text, boolean, or identifier casilla
    silently produces wrong results because the engine stores the Decimal
    but the casilla's formula chain treats its absence as zero.  Surface
    the misuse early with the label and the correct input channel.
    """
    casilla_def = next(
        (c for c in revision.casillas if str(c.id) == casilla_id),
        None,
    )
    if casilla_def is None:
        return  # unknown casilla will fail later in the engine
    if casilla_def.data_type not in _NUMERIC_CASILLA_DATA_TYPES:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.casilla_non_numeric_data_type",
                key=casilla_id,
                data_type=casilla_def.data_type,
                label=casilla_def.label,
            )
        )


def _parse_casilla_override(spec: str) -> tuple[str, str]:
    return _parse_kv_spec(
        spec,
        flag="--casilla",
        key_label="ID",
        transform=str.strip,
        key_validator=_validate_casilla_key,
    )


def _casilla_revision_for_work_unit(work_unit_id: str) -> ModeloRevision:
    """Return the registry revision for a work unit's modelo + filing scope.

    Loads the work unit from the active profile's bucket, then fetches
    the registry snapshot for its ``(modelo, filing_year, period)``
    triple. The result is used by :func:`_normalise_casilla_key` so
    bare-numeric ``--casilla`` tokens can be resolved against the real
    casilla catalogue before the calculation is dispatched.
    """

    unit = get_work_unit(work_unit_id)
    authority = _service()._authority
    snapshot = authority.snapshot(
        str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
    )
    return snapshot.revision


#: Semantic role that identifies the INSS maternidad/paternidad exempt casilla.
_INSS_EXENTA_SEMANTIC_ROLE = "irpf_rendimiento_trabajo_prestacion_inss_maternidad_paternidad_exenta"

#: Semantic role that identifies the Art. 81 deducción maternidad casilla (0611).
_DEDUCCION_MATERNIDAD_SEMANTIC_ROLE = "irpf_deduccion_maternidad"

#: Semantic role that identifies the trabajo reducción casilla (0011, DT 12ª/DT 25ª LIRPF).
_REDUCCION_TRABAJO_SEMANTIC_ROLE = "irpf_rendimiento_trabajo_reduccion"


def _resolve_inss_exenta_casilla_id(work_unit_id: str) -> str:
    """Return the casilla id for the INSS maternidad/paternidad exempt slot.

    Looks up the casilla by its registry ``semantic_role`` so the
    correct id is resolved for every M100 revision regardless of the
    physical casilla number (0058 for 2024, 0059 for 2025).

    Raises :exc:`typer.BadParameter` when no matching casilla is found
    (e.g. when ``--prestacion-inss-exenta`` is used against a modelo
    that does not declare the exempt-INSS casilla).
    """

    try:
        revision = _casilla_revision_for_work_unit(work_unit_id)
    except WorkUnitNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    for casilla in revision.casillas:
        if getattr(casilla, "semantic_role", None) == _INSS_EXENTA_SEMANTIC_ROLE:
            return casilla.id

    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.prestacion_inss_exenta_casilla_not_found",
            modelo=revision.id if hasattr(revision, "id") else "unknown",
            default=(
                "--prestacion-inss-exenta is not supported for this modelo revision; "
                "no Art. 7.h exempt-INSS casilla is declared. "
                "Use --casilla to supply inputs directly."
            ),
        )
    )


def _resolve_deduccion_maternidad_casilla_id(work_unit_id: str) -> str:
    """Return the casilla id for the Art. 81 deducción maternidad slot (0611).

    Looks up by ``semantic_role`` so future M100 revisions that renumber the
    casilla still resolve correctly.

    Raises :exc:`typer.BadParameter` when no matching casilla is found.
    """

    try:
        revision = _casilla_revision_for_work_unit(work_unit_id)
    except WorkUnitNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    for casilla in revision.casillas:
        if getattr(casilla, "semantic_role", None) == _DEDUCCION_MATERNIDAD_SEMANTIC_ROLE:
            return casilla.id

    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.deduccion_maternidad_casilla_not_found",
            default=(
                "--meses-trabajo-con-hijo-menor-3 is not supported for this modelo revision; "
                "no Art. 81 deducción maternidad casilla is declared. "
                "Use --casilla to supply inputs directly."
            ),
        )
    )


def _resolve_reduccion_trabajo_casilla_id(work_unit_id: str) -> str:
    """Return the casilla id for the rendimiento trabajo reducción slot (0011).

    Looks up by ``semantic_role`` so future M100 revisions that renumber the
    casilla still resolve correctly.

    Raises :exc:`typer.BadParameter` when no matching casilla is found (e.g.
    when ``--rescate-plan-pensiones-capital`` is used against a modelo that
    does not declare the reducción slot).
    """

    try:
        revision = _casilla_revision_for_work_unit(work_unit_id)
    except WorkUnitNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    for casilla in revision.casillas:
        if getattr(casilla, "semantic_role", None) == _REDUCCION_TRABAJO_SEMANTIC_ROLE:
            return casilla.id

    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.rescate_plan_pensiones_casilla_not_found",
            default=(
                "--rescate-plan-pensiones-capital is not supported for this modelo revision; "
                "no DT 12ª trabajo reducción casilla is declared. "
                "Use --casilla to supply inputs directly."
            ),
        )
    )


def _compute_dt12_reduccion_plan_pensiones(
    *,
    gross_rescate: Decimal,
    aportaciones_pre_2007: Decimal,
    aportaciones_totales: Decimal,
) -> Decimal:
    """Compute the DT 12ª LIRPF 40% reducción for a plan-de-pensiones capital rescate.

    Formula (LIRPF DT 12ª): ``pre_2007 / totales * gross_rescate * 40%``.
    The result is rounded to 2 decimal places (money-2 per registry convention).

    Raises :exc:`ValueError` when ``aportaciones_totales`` is zero or negative
    (division by zero guard) or when any input is negative.
    """

    if aportaciones_totales <= Decimal(0):
        raise ValueError(
            f"aportaciones_totales must be positive; got {aportaciones_totales}"
        )
    if gross_rescate < Decimal(0):
        raise ValueError(f"gross_rescate must be non-negative; got {gross_rescate}")
    if aportaciones_pre_2007 < Decimal(0):
        raise ValueError(f"aportaciones_pre_2007 must be non-negative; got {aportaciones_pre_2007}")

    reduccion = (aportaciones_pre_2007 / aportaciones_totales) * gross_rescate * Decimal("0.40")
    # money-2 rounding matches the registry convention for all M100 casillas.
    return reduccion.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_SAL_RESERVA_ESPECIAL_SEMANTIC_ROLE = "is_sal_reserva_especial_dotacion"


def _resolve_sal_reserva_especial_casilla_id(work_unit_id: str) -> str:
    """Return the casilla id for the SAL reserva especial dotacion slot.

    Looks up by ``semantic_role`` so it resolves across M200 revision changes.

    Raises :exc:`typer.BadParameter` when no matching casilla is found (e.g.
    when used against a modelo other than M200).
    """

    try:
        revision = _casilla_revision_for_work_unit(work_unit_id)
    except WorkUnitNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    for casilla in revision.casillas:
        if getattr(casilla, "semantic_role", None) == _SAL_RESERVA_ESPECIAL_SEMANTIC_ROLE:
            return casilla.id

    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.sal_reserva_casilla_not_found",
            default=(
                "--sal-beneficio-neto is not supported for this modelo revision; "
                "no SAL reserva especial casilla is declared. "
                "Use --casilla to supply inputs directly."
            ),
        )
    )


def _compute_sal_reserva_especial_dotacion(
    *,
    beneficio_neto: Decimal,
    reserva_dotada: Decimal,
    capital_social: Decimal,
) -> Decimal:
    """Compute the Ley 44/2015 Art. 14 SAL/SLL reserva especial dotacion.

    Formula: dotacion = min(beneficio_neto * 10%, cap_headroom), where
    cap_headroom = max(0, capital_social * 50% - reserva_dotada).

    Once the accumulated reserva equals or exceeds 50% of capital social
    the dotacion is zero (cap reached). The result is rounded to 2
    decimal places (money-2 per registry convention).

    Raises :exc:`ValueError` when capital_social is zero or negative,
    or when any input is negative.
    """

    if capital_social <= Decimal(0):
        raise ValueError(
            f"capital_social must be positive; got {capital_social}"
        )
    if beneficio_neto < Decimal(0):
        raise ValueError(
            f"beneficio_neto must be non-negative; got {beneficio_neto}"
        )
    if reserva_dotada < Decimal(0):
        raise ValueError(
            f"reserva_dotada must be non-negative; got {reserva_dotada}"
        )

    cap = (capital_social * Decimal("0.50")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    headroom = max(Decimal("0.00"), cap - reserva_dotada)
    dotacion_obligatoria = (beneficio_neto * Decimal("0.10")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    dotacion = min(dotacion_obligatoria, headroom)
    return dotacion.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_meses_trabajo_hijo_spec(spec: str) -> tuple[str, int]:
    """Parse one ``HIJO_ID=MESES`` token from ``--meses-trabajo-con-hijo-menor-3``.

    Returns ``(hijo_id_str, meses_int)``.  Raises :exc:`typer.BadParameter` on
    malformed input or out-of-range meses (must be 0–12).
    """

    if "=" not in spec:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.meses_trabajo_hijo_bad_format",
                spec=spec,
                default="--meses-trabajo-con-hijo-menor-3 requires HIJO_ID=MESES format; got: {spec}",
            )
        )
    hijo_id, _, meses_raw = spec.partition("=")
    hijo_id = hijo_id.strip()
    meses_raw = meses_raw.strip()
    try:
        meses = int(meses_raw)
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.meses_trabajo_hijo_not_integer",
                spec=spec,
                default="--meses-trabajo-con-hijo-menor-3 MESES must be an integer 0–12; got: {spec}",
            )
        ) from exc
    if not (0 <= meses <= 12):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.meses_trabajo_hijo_out_of_range",
                spec=spec,
                meses=meses,
                default="--meses-trabajo-con-hijo-menor-3 MESES must be 0–12; got {meses} in: {spec}",
            )
        )
    return hijo_id, meses


def _compute_deduccion_maternidad_0611(meses_por_hijo: list[tuple[str, int]]) -> int:
    """Compute Art. 81 LIRPF deducción maternidad from per-hijo meses pairs.

    Formula: ``sum(min(meses × 100, 1_200))`` for each ``(hijo_id, meses)`` pair.
    Returns an integer euros amount.
    """
    return sum(min(meses * 100, 1200) for _, meses in meses_por_hijo)


def _normalise_casilla_key(key: str, revision: ModeloRevision) -> str:
    """Resolve a bare-numeric ``--casilla`` key to its qualified CasillaId.

    When the operator supplies a bare integer token (e.g. ``"69"`` or
    ``"552"``), this function searches ``revision.casillas`` for entries
    whose ``number`` attribute is numerically equal to the supplied token
    (leading zeros stripped on both sides for comparison).

    - Exactly one match → return the qualified ``casilla.id``
      (e.g. ``"iva.resultado"`` or ``"DP200014:00552"``).
    - Multiple matches → raise :class:`typer.BadParameter` naming each
      candidate id so the operator can supply the unambiguous form.
    - No match → raise :class:`typer.BadParameter` listing the casilla
      prefixes available for this revision (S60 improved error).
    - Non-numeric key → return unchanged (already qualified or format
      validation will reject it).
    """

    if not _BARE_NUMERIC_RE.fullmatch(key):
        return key

    # Strip leading zeros for numeric equality; "69", "069", "00069" all match.
    key_numeric = key.lstrip("0") or "0"
    matches = [c for c in revision.casillas if ((c.number or "").lstrip("0") or "0") == key_numeric]
    if len(matches) == 1:
        return str(matches[0].id)

    if len(matches) > 1:
        candidates = ", ".join(str(c.id) for c in sorted(matches, key=lambda c: str(c.id)))
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.casilla_bare_numeric_ambiguous",
                default=(
                    f"--casilla {key!r} matches multiple casillas in this revision: "
                    f"{candidates}. Supply the qualified PREFIX:NNNNN form to disambiguate."
                ),
                key=key,
                candidates=candidates,
            )
        )

    # No match — build a helpful suggestion listing the available
    # segmento prefixes so the operator knows the key shape for
    # this revision (S60).
    prefixes: list[str] = sorted({str(c.id).split(":")[0] for c in revision.casillas if ":" in str(c.id)})
    prefix_hint = f" Available prefixes for this revision: {', '.join(prefixes)}." if prefixes else ""
    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.casilla_bare_numeric_unknown",
            default=(
                f"--casilla {key!r} does not match any casilla number in this revision."
                f"{prefix_hint} Use `aeat app modelo casillas <MODELO>` to list valid casilla IDs."
            ),
            key=key,
            prefix_hint=prefix_hint,
        )
    )


@work_app.command("calculate", help=tr("cli.app.modelo.work.calculate_help"))
def work_calculate(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
    casilla: Annotated[
        list[str] | None,
        typer.Option(
            "--casilla",
            help=tr("cli.app.modelo.work.casilla_help"),
        ),
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option(
            "--binding",
            help=tr("cli.app.modelo.work.override_help"),
        ),
    ] = None,
    borrador_snapshot_id: Annotated[
        str | None,
        typer.Option(
            "--borrador",
            help=tr(
                "cli.app.modelo.work.borrador_help",
                default=(
                    "Modelo 100 borrador snapshot id (full or unambiguous "
                    "prefix). Snapshot binding values flow into the calculation "
                    "for registry bindings marked aeat_prefilled; caller --binding "
                    "overrides always take precedence."
                ),
            ),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    relation: Annotated[
        list[str] | None,
        typer.Option(
            "--relation",
            help=tr(
                "cli.app.modelo.work.relation_help",
                default=(
                    "Prior-period relation value as KEY=VALUE. "
                    "The KEY is a registry relation id; the VALUE is a "
                    "decimal. Repeat to supply multiple relations."
                ),
            ),
        ),
    ] = None,
    row: Annotated[
        list[str] | None,
        typer.Option(
            "--row",
            help=tr(
                "cli.app.modelo.work.row_help",
                default=(
                    "Typed detail row for multi-record informational modelos. "
                    "Format: TYPE FIELD=value [FIELD=value ...]. "
                    "TYPE is 'miembro' (M184 atribución member) or "
                    "'vinculada' (M232 operación vinculada). "
                    "Repeat to add multiple rows. "
                    "M184 example: --row 'miembro nif=12345678A porcentaje=40 importe=10000'. "
                    "M232 example: --row 'vinculada nif=A12345678 tipo_operacion=01 importe=50000'."
                ),
            ),
        ),
    ] = None,
    prestacion_inss_exenta: Annotated[
        str | None,
        typer.Option(
            "--prestacion-inss-exenta",
            help=tr(
                "cli.app.modelo.work.prestacion_inss_exenta_help",
                default=(
                    "Importe íntegro de prestaciones INSS maternidad/paternidad "
                    "exentas (Art. 7.h LIRPF). Se registra en casilla 0058 (rev. 2024) "
                    "o 0059 (rev. 2025) y se descuenta del total de ingresos computables. "
                    "Introduce el importe bruto recibido de la Seguridad Social por "
                    "baja de maternidad o paternidad. NO lo incluyas en --casilla 0003."
                ),
            ),
        ),
    ] = None,
    meses_trabajo_con_hijo_menor_3: Annotated[
        list[str] | None,
        typer.Option(
            "--meses-trabajo-con-hijo-menor-3",
            help=tr(
                "cli.app.modelo.work.meses_trabajo_con_hijo_menor_3_help",
                default=(
                    "Meses trabajados mientras el hijo menor de 3 años estaba en la unidad "
                    "familiar (Art. 81 LIRPF deducción maternidad). Formato: HIJO_ID=MESES. "
                    "Repetible por cada hijo. HIJO_ID es un identificador libre (p. ej. 0, 1, 'laia'). "
                    "Se calcula sum(min(MESES × 100, 1200)) y se inyecta en casilla 0611. "
                    "Ejemplo: --meses-trabajo-con-hijo-menor-3 0=12 --meses-trabajo-con-hijo-menor-3 1=6 "
                    "→ 0611 = 1800."
                ),
            ),
        ),
    ] = None,
    rescate_plan_pensiones_capital: Annotated[
        str | None,
        typer.Option(
            "--rescate-plan-pensiones-capital",
            help=tr(
                "cli.app.modelo.work.rescate_plan_pensiones_capital_help",
                default=(
                    "Importe bruto del rescate del plan de pensiones en forma de capital "
                    "(DT 12ª LIRPF). Úsalo junto con "
                    "--rescate-plan-pensiones-aportaciones-pre-2007 y "
                    "--rescate-plan-pensiones-aportaciones-totales para que el asistente "
                    "calcule automáticamente la reducción del 40% y la inyecte en casilla 0011."
                ),
            ),
        ),
    ] = None,
    rescate_plan_pensiones_aportaciones_pre_2007: Annotated[
        str | None,
        typer.Option(
            "--rescate-plan-pensiones-aportaciones-pre-2007",
            help=tr(
                "cli.app.modelo.work.rescate_plan_pensiones_aportaciones_pre_2007_help",
                default=(
                    "Aportaciones realizadas al plan de pensiones hasta el 31-dic-2006 "
                    "(base prorrateo DT 12ª LIRPF). Necesario junto con "
                    "--rescate-plan-pensiones-capital y "
                    "--rescate-plan-pensiones-aportaciones-totales."
                ),
            ),
        ),
    ] = None,
    rescate_plan_pensiones_aportaciones_totales: Annotated[
        str | None,
        typer.Option(
            "--rescate-plan-pensiones-aportaciones-totales",
            help=tr(
                "cli.app.modelo.work.rescate_plan_pensiones_aportaciones_totales_help",
                default=(
                    "Total de aportaciones al plan de pensiones (denominador del prorrateo "
                    "DT 12ª LIRPF). Necesario junto con "
                    "--rescate-plan-pensiones-capital y "
                    "--rescate-plan-pensiones-aportaciones-pre-2007."
                ),
            ),
        ),
    ] = None,
    sal_beneficio_neto: Annotated[
        str | None,
        typer.Option(
            "--sal-beneficio-neto",
            help=tr(
                "cli.app.modelo.work.sal_beneficio_neto_help",
                default=(
                    "Beneficio neto del ejercicio de la Sociedad Laboral (SAL/SLL) "
                    "(Ley 44/2015 Art. 14). Se aplica el 10% para calcular la dotación "
                    "obligatoria a la reserva especial, limitada por el umbral del 50% del "
                    "capital social. Úsalo junto con --sal-reserva-dotada y --sal-capital-social."
                ),
            ),
        ),
    ] = None,
    sal_reserva_dotada: Annotated[
        str | None,
        typer.Option(
            "--sal-reserva-dotada",
            help=tr(
                "cli.app.modelo.work.sal_reserva_dotada_help",
                default=(
                    "Reserva especial acumulada en ejercicios anteriores (Ley 44/2015 Art. 14). "
                    "Se usa para comprobar si ya se ha alcanzado el límite del 50% del capital social. "
                    "Necesario junto con --sal-beneficio-neto y --sal-capital-social."
                ),
            ),
        ),
    ] = None,
    sal_capital_social: Annotated[
        str | None,
        typer.Option(
            "--sal-capital-social",
            help=tr(
                "cli.app.modelo.work.sal_capital_social_help",
                default=(
                    "Capital social de la Sociedad Laboral (Ley 44/2015 Art. 14). "
                    "Denominador del test del 50%: la dotación se anula cuando la reserva "
                    "acumulada alcanza el 50% del capital social. "
                    "Necesario junto con --sal-beneficio-neto y --sal-reserva-dotada."
                ),
            ),
        ),
    ] = None,
    autoconsumo_promotor_base: Annotated[
        str | None,
        typer.Option(
            "--autoconsumo-promotor-base",
            help=tr(
                "cli.app.modelo.work.autoconsumo_promotor_base_help",
                default=(
                    "Base imponible del autoconsumo del promotor inmobiliario "
                    "(Art. 9.1.c + Art. 79.4 LISIVA): coste de construcción o "
                    "rehabilitación de inmuebles afectados al patrimonio de arrendamiento. "
                    "El asistente aplica automáticamente el 21% (Art. 90 LISIVA) para "
                    "calcular la cuota devengada. Sólo aplicable a Modelo 303."
                ),
            ),
        ),
    ] = None,
    output_language: str | None = typer.Option(
        None,
        "--output-language",
        "--language",
        click_type=_OUTPUT_LANGUAGE_CLI,
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Persist a new draft calculation revision for the work unit."""

    activate_subcommand_output_language(ctx, output_language)
    work_unit_id = _validate_work_unit_id(work_unit_id)
    _require_active_profile()
    from ...application.modelo import (
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    )

    casilla_specs = list(casilla or ())
    casilla_pairs = dict(_parse_casilla_override(spec) for spec in casilla_specs)
    if casilla_pairs:
        # Resolve bare-numeric tokens against the casilla catalogue before
        # the decimal conversion pass so the application layer only sees
        # qualified CasillaIds.
        try:
            revision = _casilla_revision_for_work_unit(work_unit_id)
        except WorkUnitNotFoundError as exc:
            raise _bad_parameter_from_error(exc) from exc
        casilla_pairs = {_normalise_casilla_key(k, revision): v for k, v in casilla_pairs.items()}
        for resolved_key in casilla_pairs:
            _guard_casilla_data_type(resolved_key, revision)
    casilla_inputs: dict[str, Decimal] = {}
    for k, v in casilla_pairs.items():
        try:
            casilla_inputs[k] = Decimal(v)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(tr("cli.app.modelo.work.casilla_not_decimal", key=k, value=v)) from exc

    # --prestacion-inss-exenta injects the Art. 7.h exempt INSS amount into the
    # revision-specific casilla (0058 for 2024, 0059 for 2025).  The casilla is
    # looked up by semantic_role so it resolves correctly for any future revision
    # that carries the same role.
    if prestacion_inss_exenta is not None:
        try:
            inss_decimal = Decimal(prestacion_inss_exenta)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.prestacion_inss_exenta_not_decimal",
                    value=prestacion_inss_exenta,
                    default="--prestacion-inss-exenta must be a decimal amount; received: {value}",
                )
            ) from exc
        inss_casilla_id = _resolve_inss_exenta_casilla_id(work_unit_id)
        casilla_inputs[inss_casilla_id] = inss_decimal

    # --meses-trabajo-con-hijo-menor-3 computes the Art. 81 LIRPF deducción
    # maternidad as sum(min(meses × 100, 1_200)) per eligible child and
    # injects the result into the revision-specific casilla 0611, resolved
    # by semantic_role so future revisions that renumber the casilla still
    # work correctly.
    if meses_trabajo_con_hijo_menor_3:
        meses_pairs = [
            _parse_meses_trabajo_hijo_spec(spec)
            for spec in meses_trabajo_con_hijo_menor_3
        ]
        deduccion_amount = _compute_deduccion_maternidad_0611(meses_pairs)
        maternidad_casilla_id = _resolve_deduccion_maternidad_casilla_id(work_unit_id)
        casilla_inputs[maternidad_casilla_id] = Decimal(deduccion_amount)

    # --rescate-plan-pensiones-* computes the DT 12ª LIRPF 40% reducción for a
    # capital lump-sum pension rescate and injects it into the revision-specific
    # casilla 0011, resolved by semantic_role.  All three flags must be supplied
    # together; partial supply raises BadParameter.
    rescate_supplied = (
        rescate_plan_pensiones_capital,
        rescate_plan_pensiones_aportaciones_pre_2007,
        rescate_plan_pensiones_aportaciones_totales,
    )
    if any(rescate_supplied):
        if not all(rescate_supplied):
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.rescate_plan_pensiones_incomplete",
                    default=(
                        "--rescate-plan-pensiones-capital, "
                        "--rescate-plan-pensiones-aportaciones-pre-2007, and "
                        "--rescate-plan-pensiones-aportaciones-totales must all be supplied together."
                    ),
                )
            )
        try:
            dt12_gross = Decimal(rescate_plan_pensiones_capital)  # type: ignore[arg-type]
            dt12_pre_2007 = Decimal(rescate_plan_pensiones_aportaciones_pre_2007)  # type: ignore[arg-type]
            dt12_totales = Decimal(rescate_plan_pensiones_aportaciones_totales)  # type: ignore[arg-type]
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.rescate_plan_pensiones_not_decimal",
                    default="--rescate-plan-pensiones-* values must be decimals.",
                )
            ) from exc
        try:
            dt12_reduccion = _compute_dt12_reduccion_plan_pensiones(
                gross_rescate=dt12_gross,
                aportaciones_pre_2007=dt12_pre_2007,
                aportaciones_totales=dt12_totales,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        reduccion_casilla_id = _resolve_reduccion_trabajo_casilla_id(work_unit_id)
        casilla_inputs[reduccion_casilla_id] = dt12_reduccion

    # --sal-beneficio-neto / --sal-reserva-dotada / --sal-capital-social compute
    # the Ley 44/2015 Art. 14 SAL/SLL reserva especial obligatory dotacion and
    # inject it into the revision-specific SAL casilla, resolved by semantic_role.
    # All three flags must be supplied together; partial supply raises BadParameter.
    sal_supplied = (sal_beneficio_neto, sal_reserva_dotada, sal_capital_social)
    if any(sal_supplied):
        if not all(sal_supplied):
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.sal_reserva_incomplete",
                    default=(
                        "--sal-beneficio-neto, --sal-reserva-dotada, and "
                        "--sal-capital-social must all be supplied together."
                    ),
                )
            )
        try:
            sal_bn = Decimal(sal_beneficio_neto)  # type: ignore[arg-type]
            sal_rd = Decimal(sal_reserva_dotada)  # type: ignore[arg-type]
            sal_cs = Decimal(sal_capital_social)  # type: ignore[arg-type]
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.sal_reserva_not_decimal",
                    default="--sal-* values must be decimals.",
                )
            ) from exc
        try:
            sal_dotacion = _compute_sal_reserva_especial_dotacion(
                beneficio_neto=sal_bn,
                reserva_dotada=sal_rd,
                capital_social=sal_cs,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        sal_casilla_id = _resolve_sal_reserva_especial_casilla_id(work_unit_id)
        casilla_inputs[sal_casilla_id] = sal_dotacion

    # --autoconsumo-promotor-base injects the Art. 9.1.c LISIVA construction-cost
    # base directly into the profile binding for M303.  The registry formula
    # modelo-303-autoconsumo-promotor-cuota multiplies it by 0.21 (Art. 90 LISIVA).
    _AUTOCONSUMO_PROMOTOR_BINDING = "modelo-303-autoconsumo-promotor-base"
    autoconsumo_decimal: Decimal | None = None
    if autoconsumo_promotor_base is not None:
        try:
            autoconsumo_decimal = Decimal(autoconsumo_promotor_base)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.work.autoconsumo_promotor_base_not_decimal",
                    value=autoconsumo_promotor_base,
                    default="--autoconsumo-promotor-base must be a decimal amount; received: {value}",
                )
            ) from exc

    binding_pairs = dict(_parse_binding_override(spec) for spec in (binding or ()))
    binding_values: dict[str, Decimal] = {}
    enum_binding_values: dict[str, str] = {}
    for k, v in binding_pairs.items():
        try:
            binding_values[k] = Decimal(v)
        except (InvalidOperation, ValueError):
            # Non-decimal binding overrides flow into the enum-binding
            # channel (e.g. profile-sourced enums like CCAA).
            enum_binding_values[k] = v
    if autoconsumo_decimal is not None:
        binding_values[_AUTOCONSUMO_PROMOTOR_BINDING] = autoconsumo_decimal
    relation_values: dict[str, Decimal] = {}
    for spec in relation or ():
        key, raw_value = _parse_kv_spec(spec, flag="--relation", transform=lambda value: value)
        try:
            relation_values[key] = Decimal(raw_value)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(tr("cli.app.modelo.work.relation_not_decimal", key=key, value=raw_value)) from exc
    detail_rows: tuple[ModeloDetailRow, ...] = tuple(_parse_row_spec(spec) for spec in (row or ()))
    if detail_rows:
        _validate_m184_share_sum(detail_rows)
        _validate_m347_threshold(detail_rows)

    try:
        revision = calculate_modelo_revision_from_bucket_aggregation(
            work_unit_id,
            actor=actor or _resolve_default_actor(),
            casilla_inputs=casilla_inputs,
            binding_values=binding_values or None,
            enum_binding_values=enum_binding_values or None,
            borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
            relation_values=relation_values or None,
            detail_rows=detail_rows,
        )
    except RegistryValidationError as exc:
        # A formula that consumes an unsatisfied binding / enum-binding /
        # relation raises RegistryValidationError. The bare message names
        # the missing key but gives the operator no path forward; append
        # the --binding KEY=VALUE syntax and the bindings-list discovery
        # command so the first calculate failure is self-correcting.
        raise typer.BadParameter(_missing_binding_guidance(exc, work_unit_id)) from exc
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    # The casilla table alone gives the operator no signal that the
    # result was persisted. Each calculate writes a `borrador` revision
    # that survives the session; the confirmation line states that
    # explicitly and names the verbs to resume or re-inspect it.
    saved_confirmation = tr(
        "cli.app.modelo.work.calculate_saved",
        default=(
            "Saved as draft calculation revision %{revision_id} "
            "(state: %{state}). It is persisted and can be resumed later; "
            "list revisions with `aeat app modelo work revisions %{work_unit_id}` "
            "and re-inspect this one with `aeat app modelo work revision %{revision_id}`."
        ),
        revision_id=revision.calculation_revision_id,
        state=revision.state.value,
        work_unit_id=revision.work_unit_id,
    )
    # For Modelo 202 derive and surface the Art. 40.2 / 40.3 modality so
    # the operator knows which pago-fraccionado lane applies. The verdict
    # is gated by the LIS Art. 40.3 INCN threshold (6.000.000 EUR over
    # the prior 12 months).  derive_modelo_202_modality returns INCOMPLETE
    # when the profile does not declare an INCN or is not a legal entity.
    modality_payload: dict[str, object] = {}
    modality_lines: list[str] = []
    unit_for_modality = get_work_unit(revision.work_unit_id)
    if str(unit_for_modality.modelo) == "202":
        from ...application.workflow._persistence import workflow_state_repository
        from ...domain.calculations.registry.applicability import derive_modelo_202_modality

        _wf_state = workflow_state_repository().load()
        _profile_202 = _profile_to_taxpayer(_wf_state)
        _verdict = derive_modelo_202_modality(_profile_202)
        modality_payload = {
            "modality": _verdict.modality.value,
            "modality_reason": _verdict.reason,
        }
        modality_lines = [f"modality\t{_verdict.modality.value}"]

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkCalculateResult

    result = WorkCalculateResult.model_validate(
        {
            "saved": True,
            "saved_confirmation": saved_confirmation,
            **_calculation_revision_payload(revision).model_dump(mode="python"),
            **modality_payload,
        }
    )
    plazo_lines = _work_unit_plazo_lines(unit_for_modality)
    lines = [
        "operation\tmodelo.work.calculate",
        *_calculation_revision_lines(revision),
        *modality_lines,
        *plazo_lines,
        saved_confirmation,
    ]
    _emit_envelope(ctx, command="modelo.work.calculate", result=result, lines=lines)


@work_app.command(
    "compare-taxation",
    help=tr("cli.app.modelo.work.compare_taxation_help"),
)
def work_compare_taxation(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
    output_language: str | None = typer.Option(
        None,
        "--output-language",
        help=tr(
            "cli.app.modelo.work.output_language_help",
            default="Override the output language (e.g. es, en, ca).",
        ),
    ),
) -> None:
    """Compare conjunta vs. individual IRPF cuota for an existing Modelo 100 work unit.

    Runs the registry formula engine twice — once with
    ``declaration_type=2`` (tributación conjunta) and once with
    ``declaration_type=1`` (tributación individual) — over the
    same casilla inputs and profile bindings derived from the stored
    work unit. Outputs the cuota resultante autoliquidación (0595)
    and cuota diferencial (0610) for each mode plus the delta and a
    recommendation.

    This is an ephemeral operation: no revision is persisted.
    """
    from ._common import _emit_envelope, activate_subcommand_output_language

    activate_subcommand_output_language(ctx, output_language)

    from ...application.modelo import (
        TaxationComparisonError,
        WorkUnitNotFoundError,
        compare_taxation_for_work_unit,
    )

    try:
        comparison = compare_taxation_for_work_unit(work_unit_id)
    except WorkUnitNotFoundError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.compare_taxation_work_unit_not_found",
                work_unit_id=work_unit_id,
                default="Work unit {work_unit_id} not found; check 'aeat app modelo work list'.",
            )
        ) from exc
    except TaxationComparisonError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.compare_taxation_error",
                detail=str(exc),
                default="Taxation comparison failed: {detail}",
            )
        ) from exc

    from ._modelo_payloads import WorkCompareTaxationResult

    result = WorkCompareTaxationResult(
        filing_year=comparison.filing_year,
        modelo=comparison.modelo,
        revision=comparison.revision,
        conjunta_cuota_resultante=str(comparison.conjunta_cuota_resultante),
        individual_cuota_resultante=str(comparison.individual_cuota_resultante),
        conjunta_resultado=str(comparison.conjunta_resultado),
        individual_resultado=str(comparison.individual_resultado),
        delta_resultado=str(comparison.delta_resultado),
        recommendation=comparison.recommendation.value,
        recommendation_reason=comparison.recommendation_reason,
    )
    lines = [
        "operation\tmodelo.work.compare_taxation",
        f"filing_year\t{comparison.filing_year}",
        f"modelo\t{comparison.modelo}",
        f"revision\t{comparison.revision}",
        f"conjunta_cuota_resultante\t{comparison.conjunta_cuota_resultante}",
        f"individual_cuota_resultante\t{comparison.individual_cuota_resultante}",
        f"conjunta_resultado\t{comparison.conjunta_resultado}",
        f"individual_resultado\t{comparison.individual_resultado}",
        f"delta_resultado\t{comparison.delta_resultado}",
        f"recommendation\t{comparison.recommendation.value}",
        tr(
            "cli.app.modelo.work.compare_taxation_recommendation_line",
            recommendation=comparison.recommendation.value,
            reason=comparison.recommendation_reason,
            default="RECOMENDACIÓN: {recommendation} — {reason}",
        ),
    ]
    _emit_envelope(ctx, command="modelo.work.compare_taxation", result=result, lines=lines)


@work_app.command("revisions", help=tr("cli.app.modelo.work.revisions_help"))
def work_revisions(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ] = None,
) -> None:
    """List calculation revisions, optionally filtered to one work unit."""

    if work_unit_id is not None:
        work_unit_id = _validate_work_unit_id(work_unit_id)
    _require_active_profile()
    revisions = list_calculation_revisions(work_unit_id=work_unit_id)
    from ._common import _emit_envelope
    from ._modelo_payloads import WorkRevisionsResult

    result = WorkRevisionsResult.model_validate(
        {
            "work_unit_id_filter": work_unit_id,
            "revision_count": len(revisions),
            "revisions": [_calculation_revision_payload(rev) for rev in revisions],
        }
    )
    lines = [
        "operation\tmodelo.work.revisions",
        f"work_unit_id_filter\t{work_unit_id or ''}",
        f"revision_count\t{len(revisions)}",
        "calculation_revision_id\twork_unit_id\tstate\tcreated_at",
    ]
    lines.extend(
        f"{rev.calculation_revision_id}\t{rev.work_unit_id}\t{rev.state.value}\t{rev.created_at.isoformat()}"
        for rev in revisions
    )
    _emit_envelope(ctx, command="modelo.work.revisions", result=result, lines=lines)


@work_app.command("revision", help=tr("cli.app.modelo.work.revision_show_help"))
def work_revision(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
    ],
) -> None:
    """Show one stored calculation revision's persisted casilla values.

    Read-only: the persisted revision is rendered as-is, never
    recomputed. Use ``work revisions`` to discover a revision id.
    """

    calculation_revision_id = _validate_calculation_revision_id(calculation_revision_id)
    _require_active_profile()
    try:
        revision = get_calculation_revision(calculation_revision_id)
    except CalculationRevisionNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc
    modality_payload_r: dict[str, object] = {}
    modality_lines_r: list[str] = []
    unit_for_modality_r = get_work_unit(revision.work_unit_id)
    if str(unit_for_modality_r.modelo) == "202":
        from ...application.workflow._persistence import workflow_state_repository
        from ...domain.calculations.registry.applicability import derive_modelo_202_modality

        _wf_state_r = workflow_state_repository().load()
        _profile_202_r = _profile_to_taxpayer(_wf_state_r)
        _verdict_r = derive_modelo_202_modality(_profile_202_r)
        modality_payload_r = {
            "modality": _verdict_r.modality.value,
            "modality_reason": _verdict_r.reason,
        }
        modality_lines_r = [f"modality\t{_verdict_r.modality.value}"]

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkRevisionResult

    result = WorkRevisionResult.model_validate(
        {
            **_calculation_revision_payload(revision).model_dump(mode="python"),
            **modality_payload_r,
        }
    )
    lines = [
        "operation\tmodelo.work.revision",
        *_calculation_revision_lines(revision),
        *modality_lines_r,
    ]
    _emit_envelope(ctx, command="modelo.work.revision", result=result, lines=lines)


@work_app.command(
    "history",
    help=tr(
        "cli.app.modelo.work.history_help",
        default="Show every bucket event scoped to one work unit's full lifecycle.",
    ),
)
def work_history(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.modelo.work.history_work_unit_id_help",
                default="Work unit id whose lifecycle to render.",
            ),
        ),
    ],
) -> None:
    """Assemble the chronological event stream for one work unit.

    Read-only aggregate over the bucket-event history catalogue and
    the four catalogues (work unit, calculation revision, verification
    report, filing record). Emits no bucket event.
    """

    from ...application.modelo import assemble_work_unit_history

    work_unit_id = _validate_work_unit_id(work_unit_id)
    _require_active_profile()
    history = assemble_work_unit_history(work_unit_id)
    payload = {
        "operation": "modelo.work.history",
        "bucket_id": history.bucket_id,
        "work_unit_id": history.work_unit_id,
        "event_count": len(history.events),
        "events": [
            {
                "event_id": event.event_id,
                "occurred_at": event.occurred_at.isoformat(),
                "event_type": event.event_type.value,
                "object_type": event.object_type.value,
                "object_id": event.object_id,
                "actor": event.actor,
                "payload": event.payload,
            }
            for event in history.events
        ],
    }
    lines = [
        "operation\tmodelo.work.history",
        f"bucket_id\t{history.bucket_id}",
        f"work_unit_id\t{history.work_unit_id}",
        f"event_count\t{len(history.events)}",
        "occurred_at\tevent_type\tobject_type\tobject_id\tactor",
    ]
    lines.extend(
        "\t".join(
            (
                event.occurred_at.isoformat(),
                event.event_type.value,
                event.object_type.value,
                event.object_id,
                event.actor,
            ),
        )
        for event in history.events
    )
    _emit(ctx, payload, lines)


def _verification_report_payload(report: VerificationReport) -> VerificationReportPayload:
    from ._modelo_payloads import FindingPayload, VerificationReportPayload

    return VerificationReportPayload(
        verification_report_id=report.verification_report_id,
        calculation_revision_id=report.calculation_revision_id,
        completeness_status=report.completeness_status.value,
        granted_verificado_completo=report.granted_verificado_completo,
        resolved_casillas=list(report.resolved_casillas),
        missing_required_casillas=list(report.missing_required_casillas),
        run_at=report.run_at.isoformat(),
        verified_by=report.verified_by,
        findings=[
            FindingPayload(
                kind=f.kind.value,
                severity=f.severity.value,
                casilla_id=f.casilla_id,
                expectation_id=f.expectation_id,
                message=f.message,
                next_action=f.next_action,
                legal_refs=list(f.legal_refs),
                source_refs=list(f.source_refs),
            )
            for f in report.findings
        ],
    )


def _verification_report_lines(report: VerificationReport) -> list[str]:
    lines = [
        f"verification_report_id\t{report.verification_report_id}",
        f"calculation_revision_id\t{report.calculation_revision_id}",
        f"completeness_status\t{report.completeness_status.value}",
        f"granted_verificado_completo\t{str(report.granted_verificado_completo).lower()}",
        f"run_at\t{report.run_at.isoformat()}",
        f"verified_by\t{report.verified_by}",
        f"resolved_casilla_count\t{len(report.resolved_casillas)}",
        f"missing_required_casilla_count\t{len(report.missing_required_casillas)}",
        f"finding_count\t{len(report.findings)}",
    ]
    for casilla in report.missing_required_casillas:
        lines.append(f"missing_casilla\t{casilla}")
    for finding in report.findings:
        next_action = finding.next_action or ""
        casilla = finding.casilla_id or ""
        lines.append(
            "\t".join(
                (
                    "finding",
                    finding.kind.value,
                    finding.severity.value,
                    casilla,
                    finding.message,
                    next_action,
                )
            )
        )
        if finding.legal_refs:
            lines.append(f"finding_legal_refs\t{casilla}\t{', '.join(finding.legal_refs)}")
        if finding.source_refs:
            lines.append(f"finding_source_refs\t{casilla}\t{', '.join(finding.source_refs)}")
    if not report.granted_verificado_completo:
        lines.append(
            f"next_action\taeat app modelo work verification-report list"
            f" {report.calculation_revision_id}"
        )
    return lines


@work_app.command("verify", help=tr("cli.app.modelo.work.verify_help"))
def work_verify(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
    ],
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    output_language: str | None = typer.Option(
        None,
        "--output-language",
        "--language",
        click_type=_OUTPUT_LANGUAGE_CLI,
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Verify a draft calculation revision against the verified-complete contract.

    Produces a structured verification report. On success, the
    revision transitions to ``verificado_completo``. On failure, the
    revision is not mutated and the report explains the missing
    inputs or blocking findings.
    """

    activate_subcommand_output_language(ctx, output_language)
    _require_active_profile()
    # ModeloWorkflowGateError is intentionally NOT wrapped in
    # typer.BadParameter: it is a workflow-state refusal (e.g.
    # NO_PENDING_OBLIGATION), not a user-input error. Letting it
    # propagate to the command error boundary renders it through its
    # registered REFUSED code rather than a Click "Invalid value:"
    # header that misframes a workflow gate as a bad CLI argument.
    try:
        from ...application.workflow._persistence import workflow_state_repository

        workflow_profile = _profile_to_taxpayer(workflow_state_repository().load())
        report = verify_modelo_revision(
            calculation_revision_id,
            actor=actor or _resolve_default_actor(),
            workflow_profile=workflow_profile,
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkVerifyResult

    result = WorkVerifyResult.model_validate(_verification_report_payload(report).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.verify", *_verification_report_lines(report)]
    _emit_envelope(ctx, command="modelo.work.verify", result=result, lines=lines)

    if not report.granted_verificado_completo:
        raise typer.Exit(code=1)


@work_app.command("file", help=tr("cli.app.modelo.work.file_help"))
def work_file(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
    ],
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", help=tr("cli.app.modelo.work.notes_help")),
    ] = None,
    output_language: str | None = typer.Option(
        None,
        "--output-language",
        "--language",
        click_type=_OUTPUT_LANGUAGE_CLI,
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Mark a verified modelo revision as internally filed. Does NOT submit to AEAT."""

    activate_subcommand_output_language(ctx, output_language)
    _require_active_profile()
    # ModeloWorkflowGateError is a workflow-state refusal, not a
    # user-input error — it propagates to the command error boundary
    # so it renders through its registered REFUSED code rather than a
    # Click "Invalid value:" header.
    try:
        from ...application.workflow._persistence import workflow_state_repository

        workflow_profile = _profile_to_taxpayer(workflow_state_repository().load())
        record = file_modelo_revision(
            calculation_revision_id,
            actor=actor or _resolve_default_actor(),
            workflow_profile=workflow_profile,
            notes=notes,
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkFileResult

    result = WorkFileResult.model_validate(_filing_record_payload(record).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.file", *_filing_record_lines(record)]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit_envelope(ctx, command="modelo.work.file", result=result, lines=lines)


_WORKFLOW_RUN_ID_RE = r"[0-9a-f]{16}"


def _resolve_workflow_run_id(target: str) -> str:
    """Resolve a ``work resume`` argument to a 16-character run id.

    The operator may pass either the run id directly, or the
    64-character work-unit id — the only identifier most operators
    have to hand. A run id is a hash an operator cannot derive, so a
    work-unit id is resolved to the latest persisted run for that
    work unit's ``(modelo, period)``.

    Raises:
        typer.BadParameter: When ``target`` is neither a 16-character
            run id nor a 64-character work-unit id, when the work
            unit does not exist, or when no run targets it yet.
    """

    from ...application.modelo import workflow_period_for_work_unit
    from ...application.workflow import WorkflowError, find_latest_run_for_period

    stripped = target.strip()
    if re.fullmatch(_WORKFLOW_RUN_ID_RE, stripped):
        return stripped
    if re.fullmatch(_WORK_UNIT_ID_RE, stripped):
        try:
            unit = get_work_unit(stripped)
        except WorkUnitNotFoundError as exc:
            raise _bad_parameter_from_error(exc) from exc
        try:
            run = find_latest_run_for_period(
                modelo=unit.modelo,
                period=workflow_period_for_work_unit(unit),
            )
        except WorkflowError as exc:
            raise _bad_parameter_from_error(exc) from exc
        return run.run_id
    raise typer.BadParameter(
        tr(
            "cli.app.modelo.work.resume_invalid_target",
            default=(
                "resume target must be a 16-character workflow run id or a "
                "64-character work-unit id; got {target!r}. "
                "Run `aeat app modelo work runs` to list run ids."
            ),
            target=target,
        )
    )


@work_app.command(
    "runs",
    help=tr(
        "cli.app.modelo.work.runs_help",
        default=(
            "List persisted workflow runs with their run ids, newest first. "
            "Use a run id with `aeat app modelo work resume`. Local-only: "
            "never contacts AEAT."
        ),
    ),
)
def work_runs(ctx: typer.Context) -> None:
    """List persisted workflow runs so an operator can discover run ids."""

    from ...application.workflow import list_runs

    runs = list_runs()
    payload = {
        "operation": "modelo.work.runs",
        "run_count": len(runs),
        "runs": [
            {
                "run_id": run.run_id,
                "modelo": run.obligation.modelo if run.obligation is not None else None,
                "period": run.obligation.period if run.obligation is not None else None,
                "final_stage": run.final_stage.value,
                "aborted_reason": (run.aborted_reason.value if run.aborted_reason is not None else None),
                "started_at": run.started_at.isoformat(),
            }
            for run in runs
        ],
    }
    lines = [
        "operation\tmodelo.work.runs",
        f"run_count\t{len(runs)}",
        "run_id\tmodelo\tperiod\tfinal_stage\taborted_reason\tstarted_at",
    ]
    lines.extend(
        "\t".join(
            (
                run.run_id,
                run.obligation.modelo if run.obligation is not None else "-",
                run.obligation.period if run.obligation is not None else "-",
                run.final_stage.value,
                run.aborted_reason.value if run.aborted_reason is not None else "-",
                run.started_at.isoformat(),
            )
        )
        for run in runs
    )
    _emit(ctx, payload, lines)


@work_app.command(
    "resume",
    help=tr(
        "cli.app.modelo.work.resume_help",
        default=(
            "Validate that an aborted workflow run may be retried. Emits the "
            "(modelo, period, obligation) context the engine would consume to "
            "drive a fresh attempt. Accepts a workflow run id or a work-unit "
            "id. Local-only: never contacts AEAT."
        ),
    ),
)
def work_resume(
    ctx: typer.Context,
    target: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.modelo.work.resume_target_help",
                default=(
                    "16-character workflow run id, or the 64-character "
                    "work-unit id (its latest run is resolved automatically). "
                    "Run `aeat app modelo work runs` to list run ids."
                ),
            ),
        ),
    ],
) -> None:
    """Surface the workflow-resume preconditions and resumable context."""

    from ...application.workflow import (
        WorkflowError,
        WorkflowResumeRefusedError,
        resume_modelo_workflow,
    )

    workflow_run_id = _resolve_workflow_run_id(target)

    try:
        result = resume_modelo_workflow(workflow_run_id)
    except (WorkflowResumeRefusedError, WorkflowError) as exc:
        raise _bad_parameter_from_error(exc) from exc

    payload = {
        "operation": "modelo.work.resume",
        "prior_workflow_run_id": result.resumed_from_run_id,
        "modelo": result.modelo,
        "period": result.period,
        "aborted_reason": result.aborted_reason.value,
        "obligation": result.obligation.model_dump(mode="json"),
    }
    lines = [
        "operation\tmodelo.work.resume",
        f"prior_workflow_run_id\t{result.resumed_from_run_id}",
        f"modelo\t{result.modelo}",
        f"period\t{result.period}",
        f"aborted_reason\t{result.aborted_reason.value}",
        f"opens_on\t{result.obligation.opens_on.isoformat()}",
        f"closes_on\t{result.obligation.closes_on.isoformat()}",
        f"obligation_status\t{result.obligation.status.value}",
    ]
    _emit(ctx, payload, lines)


def _parse_amendment_casilla(spec: str) -> tuple[str, Decimal]:
    def _to_decimal(value: str) -> Decimal:
        try:
            return Decimal(value.strip())
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(tr("cli.app.modelo.work.set_not_decimal", value=value)) from exc

    return _parse_kv_spec(
        spec,
        flag="--set",
        key_label="CASILLA",
        value_label="DECIMAL",
        transform=_to_decimal,
        key_validator=_validate_casilla_key,
    )


@work_app.command("amend", help=tr("cli.app.modelo.work.amend_help"))
def work_amend(
    ctx: typer.Context,
    from_filing_record_id: Annotated[
        str | None,
        typer.Option(
            "--from-filing-record",
            help=tr("cli.app.modelo.work.from_filing_record_help"),
        ),
    ] = None,
    kind: Annotated[
        str | None,
        typer.Option(
            "--kind",
            help=tr("cli.app.modelo.work.amendment_kind_help"),
        ),
    ] = None,
    reason: Annotated[
        str | None,
        typer.Option(
            "--reason",
            help=tr("cli.app.modelo.work.amendment_reason_help"),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    set_overrides: Annotated[
        list[str] | None,
        typer.Option("--set", help=tr("cli.app.modelo.work.set_override_help")),
    ] = None,
) -> None:
    """Build a complementaria amendment over an externally-filed return.

    The four required inputs (``--from-filing-record``, ``--kind``,
    ``--reason``, and at least one ``--set``) are batch-validated so a
    run missing several flags reports every absent one in a single
    refusal instead of forcing the operator to rediscover them one
    invocation at a time.
    """

    missing: list[str] = []
    if not from_filing_record_id or not from_filing_record_id.strip():
        missing.append("--from-filing-record")
    if not kind or not kind.strip():
        missing.append("--kind")
    if not reason or not reason.strip():
        missing.append("--reason")
    if not set_overrides:
        missing.append("--set")
    if missing:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.amend_missing_options",
                missing=", ".join(missing),
            )
        )

    # The batch check above guarantees all four required inputs are
    # present and non-blank; narrow the optional types for the calls.
    assert from_filing_record_id is not None
    assert kind is not None
    assert reason is not None

    _require_active_profile()
    try:
        amendment_kind = CalculationRevisionAmendmentKind(kind.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.invalid_amendment_kind",
                choices=", ".join(repr(k.value) for k in CalculationRevisionAmendmentKind),
                kind=kind,
            )
        ) from exc

    overrides: dict[str, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _parse_amendment_casilla(spec)
        overrides[key] = value
    if not overrides:
        raise typer.BadParameter(tr("cli.app.modelo.work.amend_set_required"))

    try:
        record = amend_modelo_revision(
            from_filing_record_id=from_filing_record_id,
            overrides=overrides,
            amendment_kind=amendment_kind,
            reason=reason,
            actor=actor or _resolve_default_actor(),
        )
    except (
        ModeloRecordNotFoundError,
        AmendmentEvidenceMissingError,
        AmendmentTargetStateError,
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    from ._common import _emit_envelope
    from ._modelo_payloads import WorkAmendResult

    result = WorkAmendResult.model_validate(
        {
            "amendment_kind": amendment_kind.value,
            "amends_filing_record_id": from_filing_record_id,
            **_filing_record_payload(record).model_dump(mode="python"),
        }
    )
    lines = [
        "operation\tmodelo.work.amend",
        f"amendment_kind\t{amendment_kind.value}",
        f"amends_filing_record_id\t{from_filing_record_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit_envelope(ctx, command="modelo.work.amend", result=result, lines=lines)


@filing_record_app.command("list", help=tr("cli.app.modelo.filing_record.list_help"))
def filing_record_list(
    ctx: typer.Context,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.filing_record.bucket_id_help")),
    ] = None,
    include_superseded: Annotated[
        bool,
        typer.Option(
            "--include-superseded",
            help=tr("cli.app.modelo.filing_record.include_superseded_help"),
        ),
    ] = False,
) -> None:
    """List filing records. Superseded records are excluded unless asked."""

    records = list_filing_records(bucket_id=bucket_id, include_superseded=include_superseded)
    payload = {
        "operation": "modelo.filing_record.list",
        "bucket_id_filter": bucket_id,
        "include_superseded": include_superseded,
        "record_count": len(records),
        "records": [_filing_record_payload(record) for record in records],
    }
    lines = [
        "operation\tmodelo.filing_record.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"include_superseded\t{include_superseded}",
        f"record_count\t{len(records)}",
        "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by",
    ]
    lines.extend(
        "\t".join(
            (
                record.filing_record_id,
                record.bucket_id,
                str(record.modelo),
                str(record.filing_year),
                record.period,
                record.status.value,
                record.filed_at.isoformat(),
                record.filed_by,
            )
        )
        for record in records
    )
    _emit(ctx, payload, lines)


verification_report_app = typer.Typer(
    name="verification-report",
    help=tr("cli.app.modelo.verification_report.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(verification_report_app, name="verification-report")


@verification_report_app.command("list", help=tr("cli.app.modelo.verification_report.list_help"))
def verification_report_list(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str | None,
        typer.Option(
            "--calculation-revision-id",
            help=tr("cli.app.modelo.work.calculation_revision_id_help"),
        ),
    ] = None,
) -> None:
    """List verification reports, optionally filtered to one revision."""

    reports = list_verification_reports(calculation_revision_id=calculation_revision_id)
    payload = {
        "operation": "modelo.verification_report.list",
        "calculation_revision_id_filter": calculation_revision_id,
        "report_count": len(reports),
        "reports": [_verification_report_payload(r) for r in reports],
    }
    lines = [
        "operation\tmodelo.verification_report.list",
        f"calculation_revision_id_filter\t{calculation_revision_id or ''}",
        f"report_count\t{len(reports)}",
        "verification_report_id\tcalculation_revision_id\tcompleteness_status\tgranted\trun_at\tverified_by",
    ]
    lines.extend(
        "\t".join(
            (
                r.verification_report_id,
                r.calculation_revision_id,
                r.completeness_status.value,
                str(r.granted_verificado_completo).lower(),
                r.run_at.isoformat(),
                r.verified_by,
            )
        )
        for r in reports
    )
    _emit(ctx, payload, lines)


@verification_report_app.command("view", help=tr("cli.app.modelo.verification_report.view_help"))
def verification_report_show(
    ctx: typer.Context,
    verification_report_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.verification_report.verification_report_id_help")),
    ],
) -> None:
    """View one verification report by id."""

    try:
        report = get_verification_report(verification_report_id)
    except VerificationReportNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    payload = {
        "operation": "modelo.verification_report.show",
        **_verification_report_payload(report).model_dump(mode="python"),
    }
    lines = ["operation\tmodelo.verification_report.show", *_verification_report_lines(report)]
    _emit(ctx, payload, lines)


@filing_record_app.command("view", help=tr("cli.app.modelo.filing_record.view_help"))
def filing_record_show(
    ctx: typer.Context,
    filing_record_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.filing_record.filing_record_id_help")),
    ],
) -> None:
    """View one filing record by id."""

    try:
        record = get_filing_record(filing_record_id)
    except ModeloRecordNotFoundError as exc:
        raise _bad_parameter_from_error(exc) from exc

    payload = {
        "operation": "modelo.filing_record.show",
        **_filing_record_payload(record).model_dump(mode="python"),
    }
    lines = ["operation\tmodelo.filing_record.show", *_filing_record_lines(record)]
    _emit(ctx, payload, lines)


@filing_record_app.command("import", help=tr("cli.app.modelo.filing_record.import_help"))
def filing_record_import(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
    evidence_kind: Annotated[
        str,
        typer.Option(
            "--evidence-kind",
            help=tr("cli.app.modelo.filing_record.evidence_kind_help"),
        ),
    ],
    evidence_reference_id: Annotated[
        str,
        typer.Option(
            "--evidence-id",
            help=tr("cli.app.modelo.filing_record.evidence_reference_id_help"),
        ),
    ],
    actor: Annotated[
        str,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = "aeat-import",
    set_overrides: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help=tr("cli.app.modelo.filing_record.import_casilla_help"),
        ),
    ] = None,
) -> None:
    """Persist an externally-filed return as a baseline filing record."""

    work_unit_id = _validate_work_unit_id(work_unit_id)
    from ...application.modelo import (
        ExternalModeloImportError,
        import_external_filing_evidence,
    )
    from ...domain.modelos._filing_record import ExternalEvidenceKind

    try:
        kind = ExternalEvidenceKind(evidence_kind)
    except ValueError as exc:
        canonical = ", ".join(repr(k.value) for k in ExternalEvidenceKind)
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.filing_record.invalid_evidence_kind",
                canonical=canonical,
                kind=evidence_kind,
            )
        ) from exc

    casilla_values: dict[str, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _parse_amendment_casilla(spec)
        casilla_values[key] = value
    if not casilla_values:
        raise typer.BadParameter(tr("cli.app.modelo.filing_record.import_set_required"))

    try:
        record = import_external_filing_evidence(
            work_unit_id=work_unit_id,
            casilla_values=casilla_values,
            evidence_kind=kind,
            evidence_reference_id=evidence_reference_id,
            actor=actor or _resolve_default_actor(),
        )
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        ExternalModeloImportError,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    payload = {
        "operation": "modelo.filing_record.import",
        "evidence_kind": kind.value,
        "evidence_reference_id": evidence_reference_id,
        **_filing_record_payload(record).model_dump(mode="python"),
    }
    lines = [
        "operation\tmodelo.filing_record.import",
        f"evidence_kind\t{kind.value}",
        f"evidence_reference_id\t{evidence_reference_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(imported AEAT-attested baseline)")
    _emit(ctx, payload, lines)


def _service() -> RegistryQueryService:
    from ...core.resources import resources

    return RegistryQueryService(resources().modelos.authority)


def _as_of(raw: str | None) -> date | None:
    if raw is None:
        return None
    return _parse_iso_date(raw, label="--as-of")


# ─────────────────────────────────────────────────────────────────────────
# Evidence bundle audit
# ─────────────────────────────────────────────────────────────────────────


audit_app = typer.Typer(
    name="audit",
    help=tr(
        "cli.app.modelo.audit.group_help",
        default="Evidence bundle audit verbs (show/check/export/replay).",
    ),
    no_args_is_help=True,
)
app.add_typer(audit_app, name="audit")


def _evidence_bundle_service():
    from ...application.evidence import EvidenceBundleService

    return EvidenceBundleService()


def _active_bucket_id() -> str:
    from ...application.workflow._models import active_bucket_id_or_raise

    try:
        return active_bucket_id_or_raise()
    except Exception as exc:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile")) from exc


@audit_app.command(
    "show",
    help=tr(
        "cli.app.modelo.audit.show_help",
        default="Render an evidence bundle's manifest and referenced records.",
    ),
)
def audit_show(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
) -> None:
    bucket_id = _active_bucket_id()
    bundle = _evidence_bundle_service().show(bucket_id=bucket_id, bundle_id=bundle_id)
    payload = bundle.model_dump(mode="json")
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{bundle.bundle_id}",
        f"work_unit_id\t{bundle.work_unit_id}",
        f"manifest_version\t{bundle.manifest_version}",
        f"verification_state\t{bundle.verification_state.value}",
        f"records\t{len(bundle.records)}",
    ]
    _emit(ctx, payload, lines)


@audit_app.command(
    "check",
    help=tr(
        "cli.app.modelo.audit.check_help",
        default="Re-verify the evidence bundle's integrity (report-only).",
    ),
)
def audit_check(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
) -> None:
    bucket_id = _active_bucket_id()
    report = _evidence_bundle_service().check(bucket_id=bucket_id, bundle_id=bundle_id)
    payload = report.model_dump(mode="json")
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{report.bundle_id}",
        f"verification_state\t{report.verification_state.value}",
        f"completeness_ratio\t{report.completeness_ratio}",
        f"findings\t{len(report.findings)}",
    ]
    _emit(ctx, payload, lines)


@audit_app.command(
    "export",
    help=tr(
        "cli.app.modelo.audit.export_help",
        default="Write a ZIP archive of the bundle (manifest emitted last).",
    ),
)
def audit_export(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr("cli.app.modelo.audit.output_help", default="Output ZIP path."),
        ),
    ],
    force_incomplete: Annotated[
        bool,
        typer.Option(
            "--force-incomplete",
            help=tr(
                "cli.app.modelo.audit.force_incomplete_help",
                default="Allow export when verification is incomplete.",
            ),
        ),
    ] = False,
) -> None:
    bucket_id = _active_bucket_id()
    service = _evidence_bundle_service()
    output_path = service.export(
        bucket_id=bucket_id,
        bundle_id=bundle_id,
        output_path=output,
        force_incomplete=force_incomplete,
    )
    bundle = service.show(bucket_id=bucket_id, bundle_id=bundle_id)
    payload: dict[str, object] = {
        "bucket_id": bucket_id,
        "bundle_id": bundle.bundle_id,
        "output": str(output_path),
        "verification_state": bundle.verification_state.value,
        "records": len(bundle.records),
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{bundle.bundle_id}",
        f"output\t{output_path}",
        f"verification_state\t{bundle.verification_state.value}",
    ]
    _emit(ctx, payload, lines)


@audit_app.command(
    "replay",
    help=tr(
        "cli.app.modelo.audit.replay_help",
        default="Replay the bundle's evidence case (never contacts AEAT).",
    ),
)
def audit_replay(
    ctx: typer.Context,
    bundle_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.audit.bundle_id_help", default="Evidence bundle id.")),
    ],
) -> None:
    bucket_id = _active_bucket_id()
    report = _evidence_bundle_service().replay(bucket_id=bucket_id, bundle_id=bundle_id)
    payload = report.model_dump(mode="json")
    lines = [
        f"bucket\t{bucket_id}",
        f"bundle_id\t{report.bundle_id}",
        f"verification_state\t{report.verification_state.value}",
        f"completeness_ratio\t{report.completeness_ratio}",
        f"findings\t{len(report.findings)}",
    ]
    _emit(ctx, payload, lines)


# ─────────────────────────────────────────────────────────────────────────
# History verb (W72 modelo-grammar-reconcile, apex §4.3)
# ─────────────────────────────────────────────────────────────────────────


@app.command(
    "history",
    help=tr(
        "cli.app.modelo.history_help",
        default="Chronological modelo lifecycle audit (calculate/verify/file/amend/...) for one modelo.",
    ),
)
def modelo_history(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option(
            "--modelo",
            help=tr("cli.app.modelo.history.modelo_help", default="Modelo code (e.g. 100, 303)."),
        ),
    ],
    year: Annotated[
        int | None,
        typer.Option(
            "--year",
            help=tr("cli.app.modelo.history.year_help", default="Optional filing year filter."),
        ),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option(
            "--period",
            help=tr(
                "cli.app.modelo.history.period_help",
                default="Optional period filter (e.g. Q1, annual).",
            ),
        ),
    ] = None,
) -> None:
    """Stream the bucket-event history for one modelo across all lifecycle stages."""

    from ...domain.buckets import BucketEventHistoryRepository, BucketEventType

    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    modelo_event_types = {
        BucketEventType.MODELO_CALCULATION_CREATED,
        BucketEventType.MODELO_VERIFICATION_PASSED,
        BucketEventType.MODELO_VERIFICATION_REFUSED,
        BucketEventType.MODELO_FILED,
        BucketEventType.MODELO_FILED_SUPERSEDED,
        BucketEventType.MODELO_AMENDED,
        BucketEventType.MODELO_FILING_IMPORTED,
        BucketEventType.MODELO_WORK_UNIT_DISCARDED,
        BucketEventType.MODELO_AUDIT_VERIFIED,
        BucketEventType.MODELO_AUDIT_EXPORTED,
    }
    matches: list = []
    for event in catalogue.events.values():
        if event.event_type not in modelo_event_types:
            continue
        payload_map = dict(event.payload)
        if payload_map.get("modelo", "") != modelo:
            continue
        if year is not None and payload_map.get("year", "").strip() != str(year):
            continue
        if period is not None and payload_map.get("period", "") != period:
            continue
        matches.append(event)
    matches.sort(key=lambda e: e.occurred_at)
    payload = {
        "modelo": modelo,
        "year": year,
        "period": period,
        "count": len(matches),
        "events": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type.value,
                "occurred_at": e.occurred_at.isoformat(),
                "actor": e.actor,
                "object_type": e.object_type.value,
                "object_id": e.object_id,
                "payload": dict(e.payload),
            }
            for e in matches
        ],
    }
    lines = [f"modelo\t{modelo}", f"count\t{len(matches)}"]
    for e in matches:
        lines.append(f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_id}\t{e.actor}")
    _emit(ctx, payload, lines)


def _render_reconciliation_report(ctx: typer.Context, report: ModeloReconciliationReport) -> None:
    """Render a :class:`ModeloReconciliationReport` to the active emitter."""

    payload = report.model_dump(mode="json")
    lines = [
        f"work_unit_id\t{report.work_unit_id}",
        f"bucket\t{report.bucket_id}",
        f"source_kind\t{report.source_kind.value}",
        f"source_path\t{report.source_path}",
        f"verdict\t{report.verdict.value}",
        f"diffs\t{len(report.diffs)}",
    ]
    for diff in report.diffs:
        lines.append(
            f"diff\t{diff.field_name}\twork_unit={diff.work_unit_value}\tevidence={diff.evidence_value}",
        )
    _emit(ctx, payload, lines)


@app.command(
    "reconcile",
    help=tr(
        "cli.app.modelo.reconcile.help",
        default=(
            "Reconcile a modelo work unit against external evidence (justificante PDF). "
            "Local-only; never contacts AEAT."
        ),
    ),
)
def modelo_reconcile_verb(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
            ),
        ),
    ],
    from_justificante: Annotated[
        Path | None,
        typer.Option(
            "--from-justificante",
            help=tr(
                "cli.app.modelo.reconcile.from_justificante_help",
                default="Path to the AEAT justificante PDF to reconcile against.",
            ),
        ),
    ] = None,
    from_declaration: Annotated[
        Path | None,
        typer.Option(
            "--from-declaration",
            help=tr(
                "cli.app.modelo.reconcile.from_declaration_help",
                default="Path to the filed declaration PDF to reconcile against.",
            ),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
) -> None:
    """Reconcile a modelo work unit against an external evidence source.

    Exactly one of ``--from-justificante`` or ``--from-declaration`` must be
    supplied. The CLI enforces the exclusivity here; the application
    service performs the reconciliation, emits the bucket event, and
    returns the verdict. The verb is local-only per the app-modelo-shape
    ADR amendment.
    """

    from ...application.modelo._reconcile import (
        ModeloReconciliationCommand,
        ModeloReconciliationSourceKind,
        modelo_reconcile,
    )

    if from_justificante is None and from_declaration is None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.reconcile.errors.missing_source",
                default="Supply --from-justificante PATH or --from-declaration PATH.",
            ),
        )
    if from_justificante is not None and from_declaration is not None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.reconcile.errors.exclusive_source",
                default="--from-justificante and --from-declaration are mutually exclusive.",
            ),
        )

    source_kind = (
        ModeloReconciliationSourceKind.JUSTIFICANTE
        if from_justificante is not None
        else ModeloReconciliationSourceKind.DECLARATION
    )
    source_path = from_justificante if from_justificante is not None else from_declaration
    assert source_path is not None  # exhaustive by the exclusivity check above

    resolved_actor = actor.strip() if actor else _resolve_default_actor()
    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=source_kind,
            source_path=source_path,
            actor=resolved_actor,
        ),
    )
    _render_reconciliation_report(ctx, report)


@app.command(
    "reconcile-from-justificante",
    help=tr(
        "cli.app.modelo.reconcile_from_justificante.help",
        default=(
            "Reconcile a modelo work unit against a justificante PDF. Sugar for "
            'operators who think "reconcile from this justificante" rather than '
            '"reconcile, source = justificante". Shares the modelo_reconcile '
            "application service entry point with the flag-based form. Local-only; "
            "never contacts AEAT."
        ),
    ),
)
def modelo_reconcile_from_justificante_verb(
    ctx: typer.Context,
    justificante_path: Annotated[
        Path,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile_from_justificante.justificante_path_help",
                default="Path to the AEAT justificante PDF to reconcile against.",
            ),
        ),
    ],
    work_unit_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.modelo.reconcile_from_justificante.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    """Reconcile a work unit against the supplied justificante PDF."""

    from ...application.modelo._reconcile import (
        ModeloReconciliationCommand,
        ModeloReconciliationSourceKind,
        modelo_reconcile,
    )

    report = modelo_reconcile(
        ModeloReconciliationCommand(
            work_unit_id=work_unit_id,
            source_kind=ModeloReconciliationSourceKind.JUSTIFICANTE,
            source_path=justificante_path,
        ),
    )
    _render_reconciliation_report(ctx, report)


@app.command(
    "export",
    help=tr(
        "cli.app.modelo.export.help",
        default=(
            "Export a verified-complete or filed modelo revision to a local "
            "AEAT-compatible fichero-BOE file. Local-only; never contacts AEAT."
        ),
    ),
)
def modelo_export_verb(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.modelo.export.work_unit_id_help",
                default="Work unit id (SHA-256 or unambiguous prefix).",
            ),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            help=tr(
                "cli.app.modelo.export.output_help",
                default="Path to write the fichero-BOE artefact to.",
            ),
        ),
    ],
    revision: Annotated[
        str | None,
        typer.Option(
            "--revision",
            help=tr(
                "cli.app.modelo.export.revision_help",
                default=(
                    "Calculation revision id to export; defaults to the work unit's "
                    "most recent verified-complete or filed revision."
                ),
            ),
        ),
    ] = None,
    actor: Annotated[
        str | None,
        typer.Option(
            "--by",
            help=tr(
                "cli.app.modelo.export.actor_help",
                default="Operator label recorded into the MODELO_EXPORTED event.",
            ),
        ),
    ] = None,
) -> None:
    """Export a verified-complete or filed modelo revision to disk."""

    from ...application.modelo import ModeloIvaWalletReconciliationBlocked
    from ...application.modelo._export import (
        ModeloExportCommand,
        ModeloExportCrossBucketRefusedError,
        ModeloExportNoActiveBucketError,
        export_modelo_revision,
    )
    from ...application.workflow._persistence import workflow_state_repository

    workflow_state = workflow_state_repository().load()
    workflow_profile = _profile_to_taxpayer(workflow_state)

    target_revision_id = revision
    if target_revision_id is None:
        from ...domain.modelos._calculation_revision import CalculationRevisionState

        revisions = list_calculation_revisions(work_unit_id=work_unit_id)
        # FILED is the canonical current answer; VERIFICADO_COMPLETO
        # covers pre-file export. FILED_SUPERSEDED is intentionally
        # excluded from default-pick because exporting a superseded
        # revision risks the operator submitting an obsolete fichero;
        # operators that genuinely want a superseded revision must
        # pass --revision explicitly.
        filed = [r for r in revisions if r.state is CalculationRevisionState.PRESENTADO]
        verified = [r for r in revisions if r.state is CalculationRevisionState.VERIFICADO_COMPLETO]
        exportable = filed or verified
        if not exportable:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.export.errors.no_exportable_revision",
                    default=(
                        "Work unit has no verified-complete or filed calculation "
                        "revision to export. Run `aeat app modelo verify` first."
                    ),
                ),
            )
        target_revision_id = max(exportable, key=lambda rev: rev.created_at).calculation_revision_id

    try:
        result = export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=target_revision_id,
                output_path=output,
                actor=actor or _resolve_default_actor(),
            ),
            workflow_profile=workflow_profile,
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
        ModeloExportCrossBucketRefusedError,
        ModeloExportNoActiveBucketError,
        ModeloIvaWalletReconciliationBlocked,
    ) as exc:
        raise _bad_parameter_from_error(exc) from exc

    payload = result.model_dump(mode="json")
    lines = [
        "operation\tmodelo.export",
        f"work_unit_id\t{result.work_unit_id}",
        f"calculation_revision_id\t{result.calculation_revision_id}",
        f"bucket\t{result.bucket_id}",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period}",
        f"output_path\t{result.output_path}",
        f"byte_size\t{result.byte_size}",
        f"file_sha256\t{result.file_sha256}",
        f"format\t{result.format}",
        f"bucket_event_id\t{result.bucket_event_id}",
    ]
    _emit(ctx, payload, lines)


@app.command(
    "project",
    help=tr(
        "cli.app.modelo.project_help",
        default=(
            "Project a year-end Modelo 100 from quarterly Modelo 130 filings. "
            "Reads all M130 work-unit revisions for --year, aggregates rendimiento neto "
            "and pagos fraccionados, and runs the M100 registry calculation to surface "
            "the projected cuota íntegra and net obligation."
        ),
    ),
)
def modelo_project(
    ctx: typer.Context,
    year: Annotated[
        int,
        typer.Option(
            "--year",
            help=tr("cli.app.modelo.project.year_help", default="Filing year (e.g. 2024)."),
        ),
    ],
    ccaa: Annotated[
        str,
        typer.Option(
            "--ccaa",
            help=tr(
                "cli.app.modelo.project.ccaa_help",
                default=(
                    "Autonomous community tax residence key for the M100 autonomic scale "
                    "(e.g. cataluna, comunidad-valenciana). Must match the registry enum."
                ),
            ),
        ),
    ],
    casilla: Annotated[
        list[str] | None,
        typer.Option(
            "--casilla",
            help=tr(
                "cli.app.modelo.project.casilla_help",
                default=(
                    "Additional M100 casilla override as ID=VALUE (e.g. 0513=1150 for "
                    "age supplement). Repeat for multiple overrides."
                ),
            ),
        ),
    ] = None,
    binding: Annotated[
        list[str] | None,
        typer.Option(
            "--binding",
            help=tr(
                "cli.app.modelo.project.binding_help",
                default=(
                    "Additional M100 binding override as KEY=VALUE. Repeat for multiple. "
                    "Retenciones bindings (renta-YYYY-modelo-111-retenciones-periodicas etc.) "
                    "default to zero when not supplied."
                ),
            ),
        ),
    ] = None,
) -> None:
    """Project a year-end Modelo 100 from the active profile's M130 quarterly filings."""

    _require_active_profile()

    from ...application.modelo import list_work_units as _list_work_units
    from ...domain.calculations.registry import calculate_registry_snapshot
    from ...domain.modelos._work_unit import WorkUnitState

    # -- Collect M130 work units for the requested year --------------------------
    all_units = _list_work_units()
    m130_units = [
        u for u in all_units if str(u.modelo) == "130" and u.filing_year == year and u.state is WorkUnitState.BORRADOR
    ]

    if not m130_units:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.project.no_m130_units",
                default=f"No Modelo 130 work units found for year {year}. "
                "Create and calculate M130 work units first with "
                "`aeat app modelo work create --modelo 130`.",
            )
        )

    # -- Gather latest calculation revisions for each M130 work unit -------------
    _quarters = {"1T", "2T", "3T", "4T"}
    m130_quarters: dict[str, CalculationRevision] = {}
    for unit in m130_units:
        revisions = list_calculation_revisions(work_unit_id=unit.work_unit_id)
        if not revisions:
            continue
        # Use the most recent revision (list is sorted by created_at).
        latest = revisions[-1]
        period = unit.period
        if period in _quarters:
            m130_quarters[period] = latest

    if not m130_quarters:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.project.no_m130_revisions",
                default=f"Modelo 130 work units for year {year} have no calculation revisions. "
                "Run `aeat app modelo work calculate <work_unit_id>` for each quarter first.",
            )
        )

    # -- Aggregate M130 outputs across quarters ----------------------------------
    # M130 casilla 03: rendimiento neto (accrual base for the quarter, not cumulative).
    # M130 casilla 19: resultado final (amount paid in the quarter).
    # M130 casilla 01: ingresos (quarterly revenue).
    # M130 casilla 02: gastos (quarterly expenses).
    quarters_filed = len(m130_quarters)
    total_rendimiento_neto = sum(
        (rev.casilla_values.get("03", Decimal("0")) for rev in m130_quarters.values()),
        Decimal("0"),
    )
    total_pagos_fraccionados = sum(
        (rev.casilla_values.get("19", Decimal("0")) for rev in m130_quarters.values()),
        Decimal("0"),
    )
    total_ingresos = sum(
        (rev.casilla_values.get("01", Decimal("0")) for rev in m130_quarters.values()),
        Decimal("0"),
    )
    total_gastos = sum(
        (rev.casilla_values.get("02", Decimal("0")) for rev in m130_quarters.values()),
        Decimal("0"),
    )

    # Extrapolate to full year when fewer than 4 quarters are available.
    # Linear extrapolation: annualise by (4 / quarters_filed).
    if quarters_filed < 4:
        factor = Decimal(4) / Decimal(quarters_filed)
        projected_rendimiento_neto = (total_rendimiento_neto * factor).quantize(Decimal("0.01"))
        is_extrapolated = True
    else:
        projected_rendimiento_neto = total_rendimiento_neto
        is_extrapolated = False

    # -- Build M100 snapshot inputs and bindings ---------------------------------
    authority = _service()._authority
    try:
        m100_snapshot = authority.snapshot("100", filing_year=year, period="0A")
    except RegistrySnapshotError as exc:
        raise _bad_parameter_from_error(exc) from exc

    # Casilla overrides from --casilla flags.
    casilla_specs = list(casilla or ())
    casilla_pairs = dict(_parse_casilla_override(spec) for spec in casilla_specs)
    extra_inputs: dict[str, Decimal] = {}
    for k, v in casilla_pairs.items():
        try:
            extra_inputs[k] = Decimal(v)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(tr("cli.app.modelo.work.casilla_not_decimal", key=k, value=v)) from exc

    # Binding overrides from --binding flags.
    binding_pairs = dict(_parse_binding_override(spec) for spec in (binding or ()))
    extra_bindings: dict[str, Decimal] = {}
    extra_enum_bindings: dict[str, str] = {}
    for k, v in binding_pairs.items():
        try:
            extra_bindings[k] = Decimal(v)
        except (InvalidOperation, ValueError):
            extra_enum_bindings[k] = v

    # M100 inputs: inject M130 rendimiento neto as EDS ingresos de explotación
    # (casilla 0171, manual-kind). With all gastos casillas at zero the formula
    # chain 0171 → 0180 → 0224 → 0226 → 0231 → 0235 → 0432 → 0435 → 0500 → 0505
    # propagates the projected net income through base liquidable general.
    # Casilla 0505 is computed (max(0, 0500 − 0527)); supplying it directly as an
    # input raises RegistryValidationError — hence the injection at the leaf casilla.
    # Pagos fraccionados go to 0604 (manual-kind, actividades económicas).
    m100_inputs: dict[str, Decimal] = {
        "0171": projected_rendimiento_neto,  # EDS ingresos explotación (projection leaf)
        "0604": total_pagos_fraccionados,  # pagos fraccionados M130 (manual, actual paid)
        **extra_inputs,
    }

    # Default retenciones bindings to zero; caller may override via --binding.
    _retenciones_binding_ids = (
        f"renta-{year}-modelo-111-retenciones-periodicas",
        f"renta-{year}-modelo-115-retenciones-periodicas",
        f"renta-{year}-modelo-123-retenciones-periodicas",
        f"renta-{year}-modelo-193-retenciones-anuales",
    )
    m100_bindings: dict[str, Decimal] = {
        f"renta-{year}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        **{bid: Decimal("0") for bid in _retenciones_binding_ids},
        **extra_bindings,
    }
    m100_enum_bindings: dict[str, str] = {
        f"renta-{year}-profile-tax-residence-ccaa": ccaa,
        **extra_enum_bindings,
    }

    # -- Run M100 registry snapshot calculation ----------------------------------
    try:
        engine_result = calculate_registry_snapshot(
            m100_snapshot,
            inputs=m100_inputs,
            date_context={"filing_period": date(year, 12, 31)},
            binding_values=m100_bindings,
            enum_binding_values=m100_enum_bindings,
        )
    except RegistryValidationError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.project.m100_calculation_error",
                default=f"M100 projection calculation failed: {exc}",
            )
        ) from exc

    cuota_estatal = engine_result.values.get("0545", Decimal("0"))
    cuota_autonomica = engine_result.values.get("0546", Decimal("0"))
    cuota_liquida_estatal = engine_result.values.get("0595", Decimal("0"))
    cuota_liquida_autonomica = engine_result.values.get("0596", Decimal("0"))
    cuota_resultante = engine_result.values.get("0597", Decimal("0"))

    payload: dict[str, object] = {
        "operation": "modelo.project",
        "year": year,
        "ccaa": ccaa,
        "quarters_filed": quarters_filed,
        "quarters_available": sorted(m130_quarters.keys()),
        "is_extrapolated": is_extrapolated,
        "m130_accumulated": {
            "ingresos": str(total_ingresos),
            "gastos": str(total_gastos),
            "rendimiento_neto": str(total_rendimiento_neto),
            "pagos_fraccionados": str(total_pagos_fraccionados),
        },
        "m100_projection": {
            "base_liquidable_general_0505": str(projected_rendimiento_neto),
            "pagos_fraccionados_0604": str(total_pagos_fraccionados),
            "cuota_integra_estatal_0545": str(cuota_estatal),
            "cuota_integra_autonomica_0546": str(cuota_autonomica),
            "cuota_liquida_estatal_0595": str(cuota_liquida_estatal),
            "cuota_liquida_autonomica_0596": str(cuota_liquida_autonomica),
            "cuota_resultante_0597": str(cuota_resultante),
        },
    }

    extrapolation_note = f" (extrapolated from {quarters_filed}Q)" if is_extrapolated else ""
    lines = [
        "operation\tmodelo.project",
        f"year\t{year}",
        f"ccaa\t{ccaa}",
        f"quarters_filed\t{quarters_filed}/4{extrapolation_note}",
        f"m130_ingresos\t{total_ingresos}",
        f"m130_gastos\t{total_gastos}",
        f"m130_rendimiento_neto\t{total_rendimiento_neto}",
        f"m130_pagos_fraccionados\t{total_pagos_fraccionados}",
        "---",
        f"m100_base_liquidable_general\t{projected_rendimiento_neto}",
        f"m100_cuota_integra_estatal\t{cuota_estatal}",
        f"m100_cuota_integra_autonomica\t{cuota_autonomica}",
        f"m100_cuota_liquida_estatal\t{cuota_liquida_estatal}",
        f"m100_cuota_liquida_autonomica\t{cuota_liquida_autonomica}",
        f"m100_cuota_resultante\t{cuota_resultante}",
    ]
    _emit(ctx, payload, lines)


@app.command(
    "compare",
    help=tr(
        "cli.app.modelo.compare_help",
        default=(
            "Compare two filing-year calculation revisions for the same modelo. "
            "Emits per-casilla delta rows (year_b - year_a) grouped by section. "
            "Uses the most recent VERIFICADO_COMPLETO revision for each year; "
            "falls back to the latest BORRADOR when no verified revision exists, "
            "and flags the affected year as a draft in the output."
        ),
    ),
)
def modelo_compare(
    ctx: typer.Context,
    year: Annotated[
        list[int] | None,
        typer.Option(
            "--year",
            help=tr(
                "cli.app.modelo.compare.year_help",
                default=("Filing year to include in the comparison. Specify exactly twice: --year 2024 --year 2025."),
            ),
        ),
    ] = None,
    modelo: Annotated[
        str,
        typer.Option(
            "--modelo",
            help=tr(
                "cli.app.modelo.compare.modelo_help",
                default="Modelo number to compare (e.g. 100, 130).",
            ),
        ),
    ] = "100",
) -> None:
    """Compare two filing-year revisions for the same modelo casilla-by-casilla."""

    _require_active_profile()

    from ...application.modelo import list_work_units as _list_work_units
    from ...domain.modelos._calculation_revision import CalculationRevisionState

    years = list(year or ())
    if len(years) != 2:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.compare.need_two_years",
                default="Exactly two --year values are required (e.g. --year 2024 --year 2025).",
            )
        )
    year_a, year_b = sorted(years)

    # -- Resolve the best revision for each year --------------------------------
    def _best_revision(
        filing_year: int,
    ) -> tuple[CalculationRevision, bool, str]:
        """Return (revision, is_draft_fallback, period) for *filing_year*.

        Prefers the most recent VERIFICADO_COMPLETO revision; falls back to the
        most recent BORRADOR when no verified revision is available.
        The period is taken from the owning work unit for snapshot lookup.
        Raises typer.BadParameter if no revision of either kind exists.
        """
        all_units = _list_work_units()
        units_for_year = [u for u in all_units if str(u.modelo) == modelo and u.filing_year == filing_year]
        if not units_for_year:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.compare.no_work_units",
                    modelo=modelo,
                    filing_year=filing_year,
                )
            )

        # Build a map from work_unit_id to period for snapshot derivation.
        period_by_unit: dict[str, str] = {u.work_unit_id: u.period for u in units_for_year}

        all_revisions: list[CalculationRevision] = []
        for unit in units_for_year:
            all_revisions.extend(list_calculation_revisions(work_unit_id=unit.work_unit_id))

        if not all_revisions:
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.compare.no_revisions",
                    modelo=modelo,
                    filing_year=filing_year,
                )
            )

        verified = [r for r in all_revisions if r.state is CalculationRevisionState.VERIFICADO_COMPLETO]
        if verified:
            best = max(verified, key=lambda r: r.created_at)
            return best, False, period_by_unit.get(best.work_unit_id, "0A")

        # Draft fallback: most recent BORRADOR.
        borradores = [r for r in all_revisions if r.state is CalculationRevisionState.BORRADOR]
        if borradores:
            best = max(borradores, key=lambda r: r.created_at)
            return best, True, period_by_unit.get(best.work_unit_id, "0A")

        raise typer.BadParameter(
            tr(
                "cli.app.modelo.compare.no_usable_revisions",
                modelo=modelo,
                filing_year=filing_year,
            )
        )

    rev_a, draft_a, period_a = _best_revision(year_a)
    rev_b, draft_b, period_b = _best_revision(year_b)

    # -- Resolve casilla metadata from the snapshot ---------------------------
    # We use the year_b snapshot as the primary label/section source; fall back
    # to year_a for casillas that appear only in the older revision.
    try:
        authority = _service()._authority
        snap_b = authority.snapshot(modelo, filing_year=year_b, period=period_b)
        snap_a = authority.snapshot(modelo, filing_year=year_a, period=period_a)
    except RegistrySnapshotError as exc:
        raise _bad_parameter_from_error(exc) from exc

    # Build lookup: casilla_id -> CasillaDefinition (prefer year_b).
    casilla_meta: dict[str, object] = {}
    for snap in (snap_a, snap_b):
        for cdef in snap.revision.casillas:
            casilla_meta[cdef.id] = cdef

    def _meta(casilla_id: str) -> tuple[str, str]:
        """Return (label, primary_section) for a casilla id."""
        cdef = casilla_meta.get(casilla_id)
        if cdef is None:
            return casilla_id, ""
        label = getattr(cdef, "label", str(casilla_id))
        sections = getattr(cdef, "section", ())
        primary_section = sections[0] if sections else ""
        return label, primary_section

    # -- Build delta rows -----------------------------------------------------
    all_casilla_ids = sorted(set(rev_a.casilla_values) | set(rev_b.casilla_values))

    delta_rows: list[dict[str, object]] = []
    for cid in all_casilla_ids:
        val_a = rev_a.casilla_values.get(cid, Decimal("0"))
        val_b = rev_b.casilla_values.get(cid, Decimal("0"))
        delta = val_b - val_a
        label, section = _meta(cid)
        if val_a != Decimal("0"):
            pct_change: str | None = str((delta / val_a * Decimal("100")).quantize(Decimal("0.01")))
        else:
            pct_change = None

        delta_rows.append(
            {
                "casilla_id": cid,
                "label": label,
                "section": section,
                "year_a_value": str(val_a),
                "year_b_value": str(val_b),
                "delta": str(delta),
                "pct_change": pct_change,
            }
        )

    # Group by section for structured output.
    sections_seen: list[str] = []
    by_section: dict[str, list[dict[str, object]]] = {}
    for row in delta_rows:
        sec = str(row["section"])
        if sec not in by_section:
            sections_seen.append(sec)
            by_section[sec] = []
        by_section[sec].append(row)

    payload: dict[str, object] = {
        "operation": "modelo.compare",
        "modelo": modelo,
        "year_a": year_a,
        "year_b": year_b,
        "year_a_revision_id": rev_a.calculation_revision_id,
        "year_b_revision_id": rev_b.calculation_revision_id,
        "year_a_is_draft": draft_a,
        "year_b_is_draft": draft_b,
        "sections": [
            {
                "section": sec,
                "rows": by_section[sec],
            }
            for sec in sections_seen
        ],
        "delta_rows": delta_rows,
    }

    # Tab-delimited text: header + one row per casilla with non-zero delta.
    draft_note_a = " (BORRADOR)" if draft_a else ""
    draft_note_b = " (BORRADOR)" if draft_b else ""
    lines = [
        "operation\tmodelo.compare",
        f"modelo\t{modelo}",
        f"year_a\t{year_a}{draft_note_a}",
        f"year_b\t{year_b}{draft_note_b}",
        "---",
        "casilla_id\tlabel\tsection\tyear_a\tyear_b\tdelta\tpct_change",
    ]
    for row in delta_rows:
        if row["delta"] == "0" and row["year_a_value"] == "0" and row["year_b_value"] == "0":
            continue
        pct = row["pct_change"] if row["pct_change"] is not None else "n/a"
        lines.append(
            f"{row['casilla_id']}\t{row['label']}\t{row['section']}"
            f"\t{row['year_a_value']}\t{row['year_b_value']}\t{row['delta']}\t{pct}"
        )
    _emit(ctx, payload, lines)


iva_wallet_app = typer.Typer(
    name="iva-wallet",
    help=tr(
        "cli.app.modelo.iva_wallet.group_help",
        default="Local IVA compensation wallet balance commands.",
    ),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(iva_wallet_app, name="iva-wallet")


@iva_wallet_app.command(
    "balance",
    help=tr(
        "cli.app.modelo.iva_wallet.balance_help",
        default=(
            "Show aggregated IVA compensation carry-forward balance computed from local "
            "Modelo 303 history. Reports total_balance, lot_count, and next_expiry_year "
            "(source_filing_year + 4 for the earliest ACTIVE lot with remaining balance)."
        ),
    ),
)
def iva_wallet_balance_cmd(
    ctx: typer.Context,
    as_of_year: Annotated[
        int,
        typer.Option(
            "--as-of-year",
            min=2000,
            max=2099,
            help=tr(
                "cli.app.modelo.iva_wallet.as_of_year_help",
                default="Reference year for carry-forward age and expiry calculations.",
            ),
        ),
    ],
) -> None:
    """Report the aggregated IVA wallet balance without contacting AEAT."""

    from ...application.calculations._iva_wallet_balance import query_iva_wallet_balance

    report = query_iva_wallet_balance(as_of_year=as_of_year)
    payload = report.model_dump(mode="json")
    lines = [
        "operation\tmodelo.iva-wallet.balance",
        f"as_of_year\t{report.as_of_year}",
        f"total_balance\t{report.total_balance}",
        f"lot_count\t{report.lot_count}",
        f"next_expiry_year\t{report.next_expiry_year}",
        f"unallocated_applied_amount\t{report.unallocated_applied_amount}",
    ]
    _emit(ctx, payload, lines)


@iva_wallet_app.command(
    "seed",
    help=tr(
        "cli.app.modelo.iva_wallet.seed_help",
        default=(
            "Declare a Modelo 303 carry-forward balance for a period that pre-dates "
            "local history. Use this once to seed the first period so subsequent "
            "M303 prefill resolves modelo-303-compensacion-pendiente-anteriores correctly. "
            "Refuses if a record already exists for the period."
        ),
    ),
)
def iva_wallet_seed_cmd(
    ctx: typer.Context,
    filing_year: Annotated[
        int,
        typer.Option(
            "--filing-year",
            min=2000,
            max=2099,
            help=tr(
                "cli.app.modelo.iva_wallet.seed_filing_year_help",
                default="Filing year of the Modelo 303 period to seed.",
            ),
        ),
    ],
    period: Annotated[
        str,
        typer.Option(
            "--period",
            help=tr(
                "cli.app.modelo.iva_wallet.seed_period_help",
                default="Period of the Modelo 303 filing (e.g. 4T, 3T).",
            ),
        ),
    ],
    amount: Annotated[
        str,
        typer.Option(
            "--amount",
            help=tr(
                "cli.app.modelo.iva_wallet.seed_amount_help",
                default=(
                    "Carry-forward balance amount in EUR (decimal, e.g. 1200.50). "
                    "This is the compensación pendiente de periodos anteriores for the "
                    "NEXT period after the seeded one."
                ),
            ),
        ),
    ],
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help=tr(
                "cli.app.modelo.iva_wallet.seed_confirm_help",
                default=(
                    "Required confirmation flag. Acknowledge that seeding declares a "
                    "carry-forward balance and filing accuracy depends on the value supplied."
                ),
            ),
        ),
    ] = False,
) -> None:
    """Declare a Modelo 303 carry-forward balance for bootstrapping local history."""

    from decimal import Decimal, InvalidOperation

    from ...application.calculations._iva_compensation_history import (
        IvaCompensationSeedConflictError,
        seed_iva_compensation_period,
    )

    if not confirm:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_confirm_required",
                default=(
                    "Pass --confirm to acknowledge: this declares the M303 carry-forward "
                    "balance for the specified period. Filing accuracy depends on correct seeding."
                ),
            )
        )

    try:
        seed_amount = Decimal(amount)
    except InvalidOperation as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_invalid_amount",
                amount=amount,
                default=f"Amount {amount!r} is not a valid decimal.",
            )
        ) from exc

    if seed_amount < Decimal("0"):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_negative_amount",
                default="Amount must be non-negative.",
            )
        )

    bucket_id = _active_bucket_id()

    from ...application.modelo._actions import _taxpayer_nif_for_bucket

    taxpayer_nif = _taxpayer_nif_for_bucket(bucket_id)
    if taxpayer_nif is None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_no_nif",
                default="Active profile has no identity.tax_id configured. Set it via config profile.",
            )
        )

    try:
        state = seed_iva_compensation_period(
            taxpayer_nif=taxpayer_nif,
            filing_year=filing_year,
            period=period,
            amount=seed_amount,
        )
    except IvaCompensationSeedConflictError as exc:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.iva_wallet.seed_conflict",
                filing_year=filing_year,
                period=period,
                default=(
                    f"A compensation state for {filing_year}/{period} already exists. "
                    "Seeding is refused to prevent overwriting."
                ),
            )
        ) from exc

    payload = {
        "operation": "modelo.iva-wallet.seed",
        "filing_year": state.filing_year,
        "period": state.period,
        "taxpayer_nif": state.taxpayer_nif,
        "amount": str(state.available_end_amount),
        "status": state.status,
    }
    lines = [
        "operation\tmodelo.iva-wallet.seed",
        f"filing_year\t{state.filing_year}",
        f"period\t{state.period}",
        f"taxpayer_nif\t{state.taxpayer_nif}",
        f"amount\t{state.available_end_amount}",
        f"status\t{state.status}",
    ]
    _emit(ctx, payload, lines)


__all__ = ["app"]
