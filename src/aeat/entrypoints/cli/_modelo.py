"""User-facing modelo registry introspection commands."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import suppress
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated, Literal

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
    FilingRecordNotFoundError,
    ModeloWorkflowGateError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    amend_modelo_revision,
    calculate_modelo_revision,
    create_work_unit,
    discard_work_unit,
    file_modelo_revision,
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
from ...domain.calculations.registry import RegistryQueryService
from ...domain.calculations.registry._errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry._ids import _CASILLA_RE, _REF_RE
from ...domain.calculations.registry._queries import parse_modelo_period
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionAmendmentKind
from ...domain.modelos._filing_record import FilingRecord
from ...domain.modelos._verification_report import VerificationReport
from ...domain.modelos._work_unit import WorkUnit
from ._common import _emit, _parse_iso_date, _profile_to_autonomo
from ._i18n import tr

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


app = typer.Typer(
    name="modelo",
    help=tr("cli.app.modelo.app_help"),
    no_args_is_help=True,
)


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
        active = resolve_active_bucket_id(state)
        if active:
            return active
    return "operator"


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
        raise typer.BadParameter(str(exc)) from exc


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
    report = _run_query(lambda: _service().describe_modelo(modelo, period=period, as_of=_as_of(as_of)))
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
        raise typer.BadParameter(f"{flag} must be {key_label}={value_label}; got {spec!r}")
    key, _, value = spec.partition("=")
    key = key.strip()
    if not key:
        raise typer.BadParameter(f"{flag} key must be non-empty; got {spec!r}")
    if key_validator is not None:
        key_validator(key, spec)
    return key, transform(value)


def _resolve_year_period(year: int, period: str) -> tuple[int, str]:
    """Normalise CLI ``--year/--period`` into ``(filing_year, registry_period)``.

    Operators pass user-facing tokens (``Q1``, ``annual``, ``01``); the
    registry expects ``1T``/``0A``/``01``. Bridge that by reconstructing
    the canonical ``YYYY[Qn|-MM]`` string and delegating to the
    registry parser.
    """

    token = period.strip()
    if not token:
        raise typer.BadParameter(tr("cli.common.errors.period_empty"))
    lowered = token.lower()
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
    else:
        composed = f"{year}{token}" if token.upper().startswith("Q") else f"{year}-{token}"
    try:
        return parse_modelo_period(composed)
    except RegistryValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc


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
    ``--year`` + ``--period`` further narrow to that revision; ``--missing``
    filters to bindings whose source is not constant-valued.
    """

    service = _service()
    targets = tuple(str(m.id) for m in service._authority.modelos) if modelo is None else (modelo,)
    per_modelo_reports = []
    for target in targets:
        try:
            if year is not None and period is not None:
                resolved_year, resolved_period = _resolve_year_period(year, period)
                report = _run_query(
                    lambda code=target, fy=resolved_year, rp=resolved_period: service.bindings_for_scope(
                        code,
                        filing_year=fy,
                        period=rp,
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
            rows = tuple(row for row in rows if row.source != "constant_value")
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
                    "borrador_capable": row.borrador_capable,
                }
            )
            text_rows.append(
                f"{report.code}\t{report.revision}\t{report.period or '-'}\t"
                f"{row.binding_id}\t{row.source}\t{_readiness_for_source(row.source)}\t{row.typed_enum or '-'}\t"
                f"{row.borrador_capable}"
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
        "modelo\trevision\tperiod\tbinding_id\tsource\treadiness\ttyped_enum\tborrador_capable",
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
    resolved_year, resolved_period = _resolve_year_period(year, period)
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
            f"unknown --binding key(s) {unknown_keys!r}; known bindings for "
            f"{report.code}@{report.revision} ({report.period}): {suggestion}"
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
            raise typer.BadParameter(f"{flag} must be a JSON object; invalid JSON at byte {exc.pos}") from exc
        if not isinstance(value, dict):
            raise typer.BadParameter(f"{flag} must be a JSON object")
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
        str,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
    ] = "default",
    name: Annotated[
        str | None,
        typer.Option("--name", help=tr("cli.app.modelo.work.name_help")),
    ] = None,
) -> None:
    """Create or load a modelo work unit. Idempotent on the four-axis key."""

    unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=year,
        period=period,
        revision_id=revision,
        name=name,
    )
    payload = {
        "operation": "modelo.work.create",
        **_work_unit_payload(unit),
    }
    lines = ["operation\tmodelo.work.create", *_work_unit_lines(unit)]
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
    try:
        unit = get_work_unit(work_unit_id)
    except WorkUnitNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
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
    try:
        unit = rename_work_unit(work_unit_id, name, actor=actor or _resolve_default_actor())
    except (WorkUnitNotFoundError, WorkUnitMutationRefusedError) as exc:
        raise typer.BadParameter(str(exc)) from exc
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
) -> None:
    """Transition a work unit to discarded state.

    The discard is an audit-grade state transition: revision
    payloads are preserved, the work unit is marked discarded
    with actor + reason captured, and subsequent mutations are
    rejected. Discarded units are excluded from default
    ``aeat app modelo work list`` output.
    """

    work_unit_id = _validate_work_unit_id(work_unit_id)
    try:
        unit = discard_work_unit(work_unit_id, actor=actor or _resolve_default_actor(), reason=reason)
    except (WorkUnitNotFoundError, WorkUnitAlreadyDiscardedError) as exc:
        raise typer.BadParameter(str(exc)) from exc
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
    for casilla, value in sorted(rev.casilla_values.items()):
        lines.append(f"casilla\t{casilla}\t{value}")
    return lines


def _filing_record_payload(record: FilingRecord) -> dict[str, object]:
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


def _filing_record_lines(record: FilingRecord) -> list[str]:
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
    from ...application.modelo import (
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
    )

    casilla_pairs = dict(_parse_casilla_override(spec) for spec in (casilla or ()))
    casilla_inputs: dict[str, Decimal] = {}
    for k, v in casilla_pairs.items():
        try:
            casilla_inputs[k] = Decimal(v)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(f"--casilla value for {k!r} is not a decimal: {v!r}") from exc
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
                f"--relation value for {key!r} is not a decimal: {raw_value!r}"
            ) from exc

    try:
        revision = calculate_modelo_revision(
            work_unit_id,
            actor=actor or _resolve_default_actor(),
            casilla_inputs=casilla_inputs,
            binding_values=binding_values or None,
            enum_binding_values=enum_binding_values or None,
            borrador_snapshot_id=borrador_snapshot_id.strip() if borrador_snapshot_id else None,
            relation_values=relation_values or None,
        )
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        CalculationRegistryUnavailableError,
        Modelo100BorradorBindingError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

    payload = {
        "operation": "modelo.work.calculate",
        **_calculation_revision_payload(revision),
    }
    lines = ["operation\tmodelo.work.calculate", *_calculation_revision_lines(revision)]
    _emit(ctx, payload, lines)


@work_app.command("revisions", help=tr("cli.app.modelo.work.revisions_help"))
def work_revisions(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str | None,
        typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help")),
    ] = None,
) -> None:
    """List calculation revisions, optionally filtered to one work unit."""

    if work_unit_id is not None:
        work_unit_id = _validate_work_unit_id(work_unit_id)
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
        "granted_verified_complete": report.granted_verified_complete,
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
        f"granted_verified_complete\t{str(report.granted_verified_complete).lower()}",
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
    revision transitions to ``verified_complete``. On failure, the
    revision is not mutated and the report explains the missing
    inputs or blocking findings.
    """

    try:
        from ...application.workflow._persistence import workflow_state_repository

        workflow_profile = _profile_to_autonomo(workflow_state_repository().load())
        report = verify_modelo_revision(
            calculation_revision_id,
            actor=actor or _resolve_default_actor(),
            workflow_profile=workflow_profile,
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        ModeloWorkflowGateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

    payload = {
        "operation": "modelo.work.verify",
        **_verification_report_payload(report),
    }
    lines = ["operation\tmodelo.work.verify", *_verification_report_lines(report)]
    _emit(ctx, payload, lines)

    if not report.granted_verified_complete:
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

    try:
        from ...application.workflow._persistence import workflow_state_repository

        workflow_profile = _profile_to_autonomo(workflow_state_repository().load())
        record = file_modelo_revision(
            calculation_revision_id,
            actor=actor or _resolve_default_actor(),
            workflow_profile=workflow_profile,
            notes=notes,
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        ModeloWorkflowGateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

    payload = {
        "operation": "modelo.work.file",
        **_filing_record_payload(record),
    }
    lines = ["operation\tmodelo.work.file", *_filing_record_lines(record)]
    lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
    _emit(ctx, payload, lines)


@work_app.command(
    "resume",
    help=tr(
        "cli.app.modelo.work.resume_help",
        default=(
            "Validate that an aborted workflow run may be retried. Emits the "
            "(modelo, period, obligation) context the engine would consume to "
            "drive a fresh attempt. Local-only: never contacts AEAT."
        ),
    ),
)
def work_resume(
    ctx: typer.Context,
    workflow_run_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.modelo.work.resume_workflow_run_id_help",
                default="16-character workflow run id (see aeat config workflow runs list).",
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

    try:
        result = resume_modelo_workflow(workflow_run_id)
    except (WorkflowResumeRefusedError, WorkflowError) as exc:
        raise typer.BadParameter(str(exc)) from exc

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
            raise typer.BadParameter(f"--set value must be a decimal; got {value!r}") from exc

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
        str,
        typer.Option(
            "--from-filing-record",
            help=tr("cli.app.modelo.work.from_filing_record_help"),
        ),
    ],
    kind: Annotated[
        str,
        typer.Option(
            "--kind",
            help=tr("cli.app.modelo.work.amendment_kind_help"),
        ),
    ],
    reason: Annotated[
        str,
        typer.Option(
            "--reason",
            help=tr("cli.app.modelo.work.amendment_reason_help"),
        ),
    ],
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    set_overrides: Annotated[
        list[str] | None,
        typer.Option("--set", help=tr("cli.app.modelo.work.set_override_help")),
    ] = None,
) -> None:
    """Build a complementaria amendment over an externally-filed return."""

    try:
        amendment_kind = CalculationRevisionAmendmentKind(kind.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            f"--kind must be one of {', '.join(repr(k.value) for k in CalculationRevisionAmendmentKind)}; got {kind!r}"
        ) from exc

    overrides: dict[str, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _parse_amendment_casilla(spec)
        overrides[key] = value
    if not overrides:
        raise typer.BadParameter("--set is required at least once for an amendment")

    try:
        record = amend_modelo_revision(
            from_filing_record_id=from_filing_record_id,
            overrides=overrides,
            amendment_kind=amendment_kind,
            reason=reason,
            actor=actor or _resolve_default_actor(),
        )
    except (
        FilingRecordNotFoundError,
        AmendmentEvidenceMissingError,
        AmendmentTargetStateError,
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

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
                str(r.granted_verified_complete).lower(),
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
        raise typer.BadParameter(str(exc)) from exc

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
    except FilingRecordNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc

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
        ExternalFilingImportError,
        import_external_filing_evidence,
    )
    from ...domain.modelos._filing_record import ExternalEvidenceKind

    try:
        kind = ExternalEvidenceKind(evidence_kind)
    except ValueError as exc:
        canonical = ", ".join(repr(k.value) for k in ExternalEvidenceKind)
        raise typer.BadParameter(f"--evidence-kind must be one of {canonical}; got {evidence_kind!r}") from exc

    casilla_values: dict[str, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _parse_amendment_casilla(spec)
        casilla_values[key] = value
    if not casilla_values:
        raise typer.BadParameter("--set is required at least once for an import")

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
        ExternalFilingImportError,
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

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


def _audit_bucket_id() -> str:
    from ...application.workflow._models import active_bucket_id_or_raise
    from ...application.workflow._persistence import workflow_state_repository

    try:
        return active_bucket_id_or_raise(workflow_state_repository().load())
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
    bucket_id = _audit_bucket_id()
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
    bucket_id = _audit_bucket_id()
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
    bucket_id = _audit_bucket_id()
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
    bucket_id = _audit_bucket_id()
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


def _render_reconciliation_report(ctx: typer.Context, report: object) -> None:
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

    from ...application.modelo._export import (
        ModeloExportCommand,
        ModeloExportCrossBucketRefusedError,
        ModeloExportNoActiveBucketError,
        export_modelo_revision,
    )
    from ...application.workflow._persistence import workflow_state_repository

    workflow_state = workflow_state_repository().load()
    workflow_profile = _profile_to_autonomo(workflow_state)

    target_revision_id = revision
    if target_revision_id is None:
        from ...domain.modelos._calculation_revision import CalculationRevisionState

        revisions = list_calculation_revisions(work_unit_id=work_unit_id)
        # FILED is the canonical current answer; VERIFIED_COMPLETE
        # covers pre-file export. FILED_SUPERSEDED is intentionally
        # excluded from default-pick because exporting a superseded
        # revision risks the operator submitting an obsolete fichero;
        # operators that genuinely want a superseded revision must
        # pass --revision explicitly.
        filed = [r for r in revisions if r.state is CalculationRevisionState.FILED]
        verified = [r for r in revisions if r.state is CalculationRevisionState.VERIFIED_COMPLETE]
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
    ) as exc:
        raise typer.BadParameter(str(exc)) from exc

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
