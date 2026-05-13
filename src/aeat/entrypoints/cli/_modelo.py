"""User-facing modelo registry introspection commands."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

import typer

from ...application.modelo import (
    AmendmentEvidenceMissingError,
    AmendmentTargetStateError,
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    FilingRecordNotFoundError,
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
from ...core.config import PROJECT_ROOT
from ...domain.calculations.registry import RegistryQueryService, ValidatedRegistryAuthority
from ...domain.calculations.registry._errors import RegistrySnapshotError
from ...domain.modelos._calculation_revision import CalculationRevision, CalculationRevisionAmendmentKind
from ...domain.modelos._filing_record import FilingRecord
from ...domain.modelos._verification_report import VerificationReport
from ...domain.modelos._work_unit import WorkUnit
from ._common import _emit, _parse_iso_date
from ._i18n import tr

InputKind = Literal["manual", "bound", "computed", "informational"]

app = typer.Typer(
    name="modelo",
    help=tr("cli.app.modelo.app_help"),
    no_args_is_help=True,
)


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
) -> None:
    report = _run_query(
        lambda: _service().casillas(
            modelo,
            period=period,
            as_of=_as_of(as_of),
            input_kind=input_kind,
            required=True if required else None,
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


def _parse_binding_override(spec: str) -> tuple[str, str]:
    """Parse a ``--binding KEY=VALUE`` spec into a ``(key, value)`` pair.

    Scalar, list, and mapping values must survive resolution — the
    parsing here is intentionally permissive at the CLI boundary;
    the raw value flows through unchanged so the bindings-
    resolution layer downstream can coerce it per source type.
    """
    if "=" not in spec:
        raise typer.BadParameter(f"--binding must be KEY=VALUE; got {spec!r}")
    key, _, value = spec.partition("=")
    key = key.strip()
    if not key:
        raise typer.BadParameter(f"--binding key must be non-empty; got {spec!r}")
    return key, value


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
    """List required and available binding keys for a modelo / year / period.

    With ``--missing`` the list is filtered to bindings whose source
    is not constant-valued (every non-``constant_value`` binding
    requires runtime data from the bucket / ledger / profile /
    prior filing / live observation to resolve).
    """

    _require_binding_scope(modelo=modelo, year=year, period=period)
    assert modelo is not None
    assert year is not None
    assert period is not None
    scoped_period = f"{year}-{period}" if not period.startswith(str(year)) else period
    report = _run_query(lambda: _service().bindings(modelo, period=scoped_period, as_of=_as_of(as_of)))
    rows = report.rows
    if missing:
        rows = tuple(row for row in rows if row.source != "constant_value")
    payload = {
        "operation": "registry.modelo.bindings.list",
        "modelo": report.code,
        "revision": report.revision,
        "filing_year": report.filing_year,
        "period": report.period,
        "missing_filter": missing,
        "binding_count": len(rows),
        "bindings": [
            {
                "binding_id": row.binding_id,
                "source": row.source,
                "readiness": _readiness_for_source(row.source),
                "typed_enum": row.typed_enum,
            }
            for row in rows
        ],
    }
    lines = [
        "operation\tregistry.modelo.bindings.list",
        f"modelo\t{report.code}",
        f"revision\t{report.revision}",
        f"filing_year\t{report.filing_year}",
        f"period\t{report.period}",
        f"missing_filter\t{missing}",
        f"binding_count\t{len(rows)}",
        "binding_id\tsource\treadiness\ttyped_enum",
    ]
    lines.extend(
        f"{row.binding_id}\t{row.source}\t{_readiness_for_source(row.source)}\t{row.typed_enum or '-'}" for row in rows
    )
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
    scoped_period = f"{year}-{period}" if not period.startswith(str(year)) else period
    report = _run_query(lambda: _service().bindings(modelo, period=scoped_period, as_of=_as_of(as_of)))
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
) -> None:
    report = _run_query(lambda: _service().formulas(modelo, period=period, as_of=_as_of(as_of)))
    _emit(
        ctx,
        report,
        [
            "formula_id\ttarget\tinputs",
            *[
                f"{row.formula_id}\t{row.target}\t"
                f"{', '.join((*row.input_casillas, *row.input_bindings, *row.input_parameters))}"
                for row in report.rows
            ],
        ],
    )


work_app = typer.Typer(
    name="work",
    help=tr("cli.app.modelo.work.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(work_app, name="work")


def _work_unit_payload(unit: WorkUnit) -> dict[str, Any]:
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
    """Show one work unit's metadata."""

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
) -> None:
    """Update one work unit's display name (preserves work_unit_id)."""

    try:
        unit = rename_work_unit(work_unit_id, name)
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
        str,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ],
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

    try:
        unit = discard_work_unit(work_unit_id, actor=actor, reason=reason)
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


def _calculation_revision_payload(rev: CalculationRevision) -> dict[str, Any]:
    return {
        "calculation_revision_id": rev.calculation_revision_id,
        "work_unit_id": rev.work_unit_id,
        "state": rev.state.value,
        "casilla_values": {k: str(v) for k, v in rev.casilla_values.items()},
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


def _filing_record_payload(record: FilingRecord) -> dict[str, Any]:
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
    lines.append("kind\tinternal_filing")
    lines.append("live_submission\tfalse")
    return lines


def _parse_casilla_override(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise typer.BadParameter(f"--casilla must be ID=VALUE; got {spec!r}")
    key, _, value = spec.partition("=")
    key = key.strip()
    if not key:
        raise typer.BadParameter(f"--casilla key must be non-empty; got {spec!r}")
    return key, value.strip()


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
) -> None:
    """Persist a new draft calculation revision for the work unit."""

    from ...application.modelo import CalculationRegistryUnavailableError

    casilla_pairs = dict(_parse_casilla_override(spec) for spec in (casilla or ()))
    casilla_inputs: dict[str, Decimal] = {}
    for k, v in casilla_pairs.items():
        try:
            casilla_inputs[k] = Decimal(v)
        except (InvalidOperation, ValueError) as exc:
            raise typer.BadParameter(f"--casilla value for {k!r} is not a decimal: {v!r}") from exc
    binding_pairs = dict(_parse_casilla_override(spec) for spec in (binding or ()))
    binding_values: dict[str, Decimal] = {}
    enum_binding_values: dict[str, str] = {}
    for k, v in binding_pairs.items():
        try:
            binding_values[k] = Decimal(v)
        except (InvalidOperation, ValueError):
            # Non-decimal binding overrides flow into the enum-binding
            # channel (e.g. profile-sourced enums like CCAA).
            enum_binding_values[k] = v

    try:
        revision = calculate_modelo_revision(
            work_unit_id,
            casilla_inputs=casilla_inputs,
            binding_values=binding_values or None,
            enum_binding_values=enum_binding_values or None,
        )
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        CalculationRegistryUnavailableError,
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


def _verification_report_payload(report: VerificationReport) -> dict[str, Any]:
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
        str,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ],
) -> None:
    """Verify a draft calculation revision against the verified-complete contract.

    Produces a structured verification report. On success, the
    revision transitions to ``verified_complete``. On failure, the
    revision is not mutated and the report explains the missing
    inputs or blocking findings.
    """

    try:
        report = verify_modelo_revision(calculation_revision_id, actor=actor)
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
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
        str,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ],
    notes: Annotated[
        str | None,
        typer.Option("--notes", help=tr("cli.app.modelo.work.notes_help")),
    ] = None,
) -> None:
    """Mark a verified modelo revision as internally filed. Does NOT submit to AEAT."""

    try:
        record = file_modelo_revision(
            calculation_revision_id,
            actor=actor,
            notes=notes,
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
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


def _parse_amendment_casilla(spec: str) -> tuple[str, Decimal]:
    if "=" not in spec:
        raise typer.BadParameter(f"--set must be CASILLA=DECIMAL; got {spec!r}")
    key, _, value = spec.partition("=")
    key = key.strip()
    if not key:
        raise typer.BadParameter(f"--set key must be non-empty; got {spec!r}")
    try:
        decimal_value = Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise typer.BadParameter(f"--set value must be a decimal; got {value!r}") from exc
    return key, decimal_value


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
        str,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ],
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
            actor=actor,
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


@verification_report_app.command("show", help=tr("cli.app.modelo.verification_report.show_help"))
def verification_report_show(
    ctx: typer.Context,
    verification_report_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.verification_report.verification_report_id_help")),
    ],
) -> None:
    """Show one verification report by id."""

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


@filing_record_app.command("show", help=tr("cli.app.modelo.filing_record.show_help"))
def filing_record_show(
    ctx: typer.Context,
    filing_record_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.filing_record.filing_record_id_help")),
    ],
) -> None:
    """Show one filing record by id."""

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

    from ...application.modelo import (
        ExternalFilingImportError,
        import_external_filing_evidence,
    )
    from ...domain.modelos._filing_record import ExternalEvidenceKind

    try:
        kind = ExternalEvidenceKind(evidence_kind.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            f"--evidence-kind must be one of "
            f"{', '.join(repr(k.value) for k in ExternalEvidenceKind)}; got {evidence_kind!r}"
        ) from exc

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
            actor=actor,
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
    authority = ValidatedRegistryAuthority.load(PROJECT_ROOT / "registry" / "aeat", source_root=PROJECT_ROOT)
    return RegistryQueryService(authority)


def _as_of(raw: str | None) -> date | None:
    if raw is None:
        return None
    return _parse_iso_date(raw, label="--as-of")


__all__ = ["app"]
