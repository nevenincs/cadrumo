"""User-facing modelo registry introspection commands."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import suppress
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Protocol

import typer

from ...application.aggregation import (
    PerModeloAggregationCommand,
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
from ...core.i18n import tr
from ...domain.calculations.registry import RegistryQueryService
from ...domain.calculations.registry._errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry._ids import _CASILLA_RE, _REF_RE
from ...domain.calculations.registry._queries import parse_modelo_period
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionAmendmentKind
from ...domain.modelos._filing_record import ModeloRecord
from ...domain.modelos._verification_report import VerificationReport
from ...domain.modelos._work_unit import WorkUnit
from ._common import _emit, _parse_iso_date, _profile_to_taxpayer

if TYPE_CHECKING:
    from ...application.modelo._reconcile import ModeloReconciliationReport

InputKind = Literal["manual", "bound", "computed", "informational"]

_WORK_UNIT_ID_RE = r"^[0-9a-f]{64}$"
"""SHA-256 hex digest expected as the canonical work-unit identifier."""

_CASILLA_MAX_LEN = 64
_BINDING_MAX_LEN = 128


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
            raise typer.BadParameter(
                _bare_period_error(modelo, period, fallback=message)
            ) from exc
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
        raise typer.BadParameter(
            tr("cli.app.modelo.work.kv_empty_key_error", flag=flag, spec=spec)
        )
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
        sorted(
            {
                token
                for revision in definition.revisions.values()
                for token in revision.period_selector.periods
            }
        )
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
            f"--period {period!r} is not a valid period token for modelo "
            f"{modelo}. Valid tokens: {', '.join(declared)}."
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
                row
                for row in rows
                if row.source != "constant_value" and row.binding_id not in profile_resolved
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


def _parse_json_object_options(values: list[str] | None, *, flag: str) -> tuple[dict[str, object], ...]:
    parsed: list[dict[str, object]] = []
    for raw in values or ():
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(
                tr("cli.app.modelo.aggregate.json_parse_error", flag=flag, pos=exc.pos)
            ) from exc
        if not isinstance(value, dict):
            raise typer.BadParameter(tr("cli.app.modelo.aggregate.json_not_object", flag=flag))
        parsed.append(value)
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

    command = PerModeloAggregationCommand.model_validate_json(
        json.dumps(
            {
                "modelo": modelo,
                "period": period,
                "retencion_observations": _parse_json_object_options(
                    retencion_observation,
                    flag="--retencion-observation",
                ),
                "counterpart_observations": _parse_json_object_options(
                    counterpart_observation,
                    flag="--counterpart-observation",
                ),
                "foreign_asset_observations": _parse_json_object_options(
                    foreign_asset_observation,
                    flag="--foreign-asset-observation",
                ),
            }
        )
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


def _work_unit_payload(unit: WorkUnit) -> dict[str, object]:
    return {
        "work_unit_id": unit.work_unit_id,
        "bucket_id": unit.bucket_id,
        "modelo": str(unit.modelo),
        "filing_year": unit.filing_year,
        "period": unit.period,
        "revision_id": unit.revision_id,
        "name": unit.name,
        "state": unit.state.value,
        "created_at": unit.created_at.isoformat(),
        "updated_at": unit.updated_at.isoformat(),
        "discarded_at": unit.discarded_at.isoformat() if unit.discarded_at else None,
        "discarded_by": unit.discarded_by,
        "discard_reason": unit.discard_reason,
    }


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
    return lines


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


def _validate_registry_target(modelo: str, revision_id: str) -> None:
    """Refuse a work-unit create that names an unknown modelo or revision.

    Without this gate ``modelo work create --modelo 999 --revision
    nonexistent`` provisions a work unit that ``calculate`` then
    silently treats as a Modelo 303 default. Both axes are checked
    against the validated registry authority — the single source of
    truth for modelo / revision identity — and refused cleanly with a
    translated error naming the unknown value.
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

    from ...application.overview._applicability import (
        ApplicabilityVerdict,
        derive_modelo_applicability,
    )
    from ...application.workflow._persistence import workflow_state_repository
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


#: Registry-validation translated-message keys that signal an
#: unsatisfied calculation input the operator can supply with
#: ``--binding`` / ``--relation``. The first ``work calculate`` of a
#: modelo that consumes a binding fails with one of these; the guidance
#: helper turns the bare refusal into a self-correcting message.
_MISSING_INPUT_TRANSLATED_MESSAGES: frozenset[str] = frozenset(
    {
        "errors.calc.binding_value_missing",
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

    base = (
        tr(error.translated_message, **(error.context or {}))
        if error.translated_message is not None
        else str(error)
    )
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
                    "Crear la unidad de trabajo aunque el modelo no aplique "
                    "al tipo de contribuyente del perfil activo."
                ),
            ),
        ),
    ] = False,
) -> None:
    """Create or load a modelo work unit. Idempotent on the four-axis key."""

    # User-input validation (filing year, registry target, period
    # token) runs first so an operator gets that feedback even before a
    # profile exists. The no-active-profile guard fires only once the
    # arguments are sound, immediately before the bucket database is
    # opened by create_work_unit.
    _validate_filing_year(year)
    _validate_registry_target(modelo, revision)
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

    payload = {
        "operation": operation,
        "status": status,
        "status_message": status_message,
        "name_applied": name_applied,
        "applicability_guard_bypassed": allow_not_applicable,
        **_work_unit_payload(unit),
    }
    lines = [
        f"operation\t{operation}",
        f"status\t{status}",
        *_work_unit_lines(unit),
        status_message,
    ]
    _emit(ctx, payload, lines)


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
    payload = {
        "operation": "modelo.work.list",
        "bucket_id_filter": bucket_id,
        "include_discarded": include_discarded,
        "work_unit_count": len(units),
        "work_units": [_work_unit_payload(unit) for unit in units],
    }
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
    _emit(ctx, payload, lines)


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
    payload = {
        "operation": "modelo.work.status",
        **_work_unit_payload(unit),
    }
    lines = ["operation\tmodelo.work.status", *_work_unit_lines(unit)]
    _emit(ctx, payload, lines)


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
    payload = {
        "operation": "modelo.work.rename",
        **_work_unit_payload(unit),
    }
    lines = ["operation\tmodelo.work.rename", *_work_unit_lines(unit)]
    _emit(ctx, payload, lines)


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
    payload = {
        "operation": "modelo.work.discard",
        **_work_unit_payload(unit),
    }
    lines = ["operation\tmodelo.work.discard", *_work_unit_lines(unit)]
    _emit(ctx, payload, lines)


filing_record_app = typer.Typer(
    name="filing-record",
    help=tr("cli.app.modelo.filing_record.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(filing_record_app, name="filing-record")


def _calculation_revision_payload(rev: CalculationRevision) -> dict[str, object]:
    return {
        "calculation_revision_id": rev.calculation_revision_id,
        "work_unit_id": rev.work_unit_id,
        "state": rev.state.value,
        "casilla_values": {k: str(v) for k, v in rev.casilla_values.items()},
        # Typed CasillaObservation envelope carrying full per-casilla
        # provenance (formula_id, operand_refs, operand_values,
        # legal_refs, source_refs). Without this projection the CLI
        # JSON would strip every regulatory grounding signal.
        "observations": [
            {
                "casilla_id": obs.casilla_id,
                "value": str(obs.value),
                "formula_id": obs.formula_id,
                "operand_refs": list(obs.operand_refs),
                "operand_values": [str(v) for v in obs.operand_values],
                "legal_refs": list(obs.legal_refs),
                "source_refs": list(obs.source_refs),
            }
            for obs in rev.observations
        ],
        # Headline result summary: registry-declared result-to-pay /
        # result-to-refund total plus the modelo's key computed
        # casillas, so the JSON consumer gets the same lead figures the
        # text surface shows.
        "result_summary": _result_summary_payload(rev),
        "binding_overrides": dict(rev.binding_overrides),
        "inputs_snapshot": dict(rev.inputs_snapshot),
        "created_at": rev.created_at.isoformat(),
        "updated_at": rev.updated_at.isoformat(),
        "verified_at": rev.verified_at.isoformat() if rev.verified_at else None,
        "verified_by": rev.verified_by,
        "filed_at": rev.filed_at.isoformat() if rev.filed_at else None,
        "filed_by": rev.filed_by,
        "superseded_at": rev.superseded_at.isoformat() if rev.superseded_at else None,
    }


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


def _result_summary_payload(rev: CalculationRevision) -> list[dict[str, object]]:
    """Return the headline-result summary rows for the JSON payload."""

    from ...application.modelo import calculation_result_summary

    summary = calculation_result_summary(rev)
    if summary is None:
        return []
    return [
        {
            "role": row.role,
            "casilla_id": row.casilla_id,
            "value": str(row.value),
            "label": row.label,
        }
        for row in summary.rows
    ]


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


def _filing_record_payload(record: ModeloRecord) -> dict[str, object]:
    external_evidence: dict[str, object] | None
    if record.external_evidence is None:
        external_evidence = None
    else:
        external_evidence = {
            "kind": record.external_evidence.kind.value,
            "reference_id": record.external_evidence.reference_id,
            "imported_at": record.external_evidence.imported_at.isoformat(),
        }
    return {
        "filing_record_id": record.filing_record_id,
        "work_unit_id": record.work_unit_id,
        "calculation_revision_id": record.calculation_revision_id,
        "bucket_id": record.bucket_id,
        "modelo": str(record.modelo),
        "filing_year": record.filing_year,
        "period": record.period,
        "filed_at": record.filed_at.isoformat(),
        "filed_by": record.filed_by,
        "notes": record.notes,
        "aeat_accepted": record.aeat_accepted,
        "status": record.status.value,
        "superseded_at": record.superseded_at.isoformat() if record.superseded_at else None,
        "superseded_by_filing_record_id": record.superseded_by_filing_record_id,
        "external_evidence": external_evidence,
        "amends_filing_record_id": record.amends_filing_record_id,
        "kind": "internal_filing",
        "live_submission": False,
    }


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


def _parse_casilla_override(spec: str) -> tuple[str, str]:
    return _parse_kv_spec(
        spec,
        flag="--casilla",
        key_label="ID",
        transform=str.strip,
        key_validator=_validate_casilla_key,
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
) -> None:
    """Persist a new draft calculation revision for the work unit."""

    work_unit_id = _validate_work_unit_id(work_unit_id)
    _require_active_profile()
    from ...application.modelo import (
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
        ModeloIvaWalletReconciliationBlocked,
    )

    casilla_pairs = dict(_parse_casilla_override(spec) for spec in (casilla or ()))
    casilla_inputs: dict[str, Decimal] = {}
    for k, v in casilla_pairs.items():
        try:
            casilla_inputs[k] = Decimal(v)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(
                tr("cli.app.modelo.work.casilla_not_decimal", key=k, value=v)
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
    relation_values: dict[str, Decimal] = {}
    for spec in relation or ():
        key, raw_value = _parse_kv_spec(spec, flag="--relation", transform=lambda value: value)
        try:
            relation_values[key] = Decimal(raw_value)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(
                tr("cli.app.modelo.work.relation_not_decimal", key=key, value=raw_value)
            ) from exc

    try:
        revision = calculate_modelo_revision_from_bucket_aggregation(
            work_unit_id,
            actor=actor or _resolve_default_actor(),
            casilla_inputs=casilla_inputs,
            binding_values=binding_values or None,
            enum_binding_values=enum_binding_values or None,
            borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
            relation_values=relation_values or None,
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
    payload = {
        "operation": "modelo.work.calculate",
        "saved": True,
        "saved_confirmation": saved_confirmation,
        **_calculation_revision_payload(revision),
    }
    lines = [
        "operation\tmodelo.work.calculate",
        *_calculation_revision_lines(revision),
        saved_confirmation,
    ]
    _emit(ctx, payload, lines)


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
    payload = {
        "operation": "modelo.work.revisions",
        "work_unit_id_filter": work_unit_id,
        "revision_count": len(revisions),
        "revisions": [_calculation_revision_payload(rev) for rev in revisions],
    }
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
    _emit(ctx, payload, lines)


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
    payload = {
        "operation": "modelo.work.revision",
        **_calculation_revision_payload(revision),
    }
    lines = ["operation\tmodelo.work.revision", *_calculation_revision_lines(revision)]
    _emit(ctx, payload, lines)


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


def _verification_report_payload(report: VerificationReport) -> dict[str, object]:
    return {
        "verification_report_id": report.verification_report_id,
        "calculation_revision_id": report.calculation_revision_id,
        "completeness_status": report.completeness_status.value,
        "granted_verificado_completo": report.granted_verificado_completo,
        "resolved_casillas": list(report.resolved_casillas),
        "missing_required_casillas": list(report.missing_required_casillas),
        "run_at": report.run_at.isoformat(),
        "verified_by": report.verified_by,
        "findings": [
            {
                "kind": f.kind.value,
                "severity": f.severity.value,
                "casilla_id": f.casilla_id,
                "expectation_id": f.expectation_id,
                "message": f.message,
                "next_action": f.next_action,
            }
            for f in report.findings
        ],
    }


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
) -> None:
    """Verify a draft calculation revision against the verified-complete contract.

    Produces a structured verification report. On success, the
    revision transitions to ``verificado_completo``. On failure, the
    revision is not mutated and the report explains the missing
    inputs or blocking findings.
    """

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

    payload = {
        "operation": "modelo.work.verify",
        **_verification_report_payload(report),
    }
    lines = ["operation\tmodelo.work.verify", *_verification_report_lines(report)]
    _emit(ctx, payload, lines)

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
) -> None:
    """Mark a verified modelo revision as internally filed. Does NOT submit to AEAT."""

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

    payload = {
        "operation": "modelo.work.file",
        **_filing_record_payload(record),
    }
    lines = ["operation\tmodelo.work.file", *_filing_record_lines(record)]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit(ctx, payload, lines)


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
                f"64-character work-unit id; got {target!r}. "
                "Run `aeat app modelo work runs` to list run ids."
            ),
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
            raise typer.BadParameter(
                tr("cli.app.modelo.work.set_not_decimal", value=value)
            ) from exc

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

    payload = {
        "operation": "modelo.work.amend",
        "amendment_kind": amendment_kind.value,
        "amends_filing_record_id": from_filing_record_id,
        **_filing_record_payload(record),
    }
    lines = [
        "operation\tmodelo.work.amend",
        f"amendment_kind\t{amendment_kind.value}",
        f"amends_filing_record_id\t{from_filing_record_id}",
        *_filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit(ctx, payload, lines)


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
        **_verification_report_payload(report),
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
        **_filing_record_payload(record),
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
        **_filing_record_payload(record),
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
            "operators who think \"reconcile from this justificante\" rather than "
            "\"reconcile, source = justificante\". Shares the modelo_reconcile "
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


__all__ = ["app"]
