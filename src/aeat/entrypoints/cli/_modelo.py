"""User-facing modelo registry introspection commands."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Annotated, Any, Literal

import typer

from ...application.modelo import (
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    create_work_unit,
    discard_work_unit,
    get_work_unit,
    list_work_units,
    rename_work_unit,
)
from ...core.config import PROJECT_ROOT
from ...domain.calculations.registry import RegistryQueryService, ValidatedRegistryAuthority
from ...domain.calculations.registry._errors import RegistrySnapshotError
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
        raise typer.BadParameter(
            f"--binding must be KEY=VALUE; got {spec!r}"
        )
    key, _, value = spec.partition("=")
    key = key.strip()
    if not key:
        raise typer.BadParameter(
            f"--binding key must be non-empty; got {spec!r}"
        )
    return key, value


@bindings_app.command("list", help=tr("cli.app.modelo.bindings.list_help"))
def bindings_list(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option("--modelo", help=tr("cli.app.modelo.bindings.modelo_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.app.modelo.bindings.year_help")),
    ],
    period: Annotated[
        str,
        typer.Option("--period", help=tr("cli.app.modelo.bindings.period_help")),
    ],
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

    scoped_period = f"{year}-{period}" if not period.startswith(str(year)) else period
    report = _run_query(
        lambda: _service().bindings(modelo, period=scoped_period, as_of=_as_of(as_of))
    )
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
        f"{row.binding_id}\t{row.source}\t{_readiness_for_source(row.source)}\t{row.typed_enum or '-'}"
        for row in rows
    )
    _emit(ctx, payload, lines)


@bindings_app.command("preview", help=tr("cli.app.modelo.bindings.preview_help"))
def bindings_preview(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option("--modelo", help=tr("cli.app.modelo.bindings.modelo_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.app.modelo.bindings.year_help")),
    ],
    period: Annotated[
        str,
        typer.Option("--period", help=tr("cli.app.modelo.bindings.period_help")),
    ],
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

    overrides = dict(_parse_binding_override(spec) for spec in (binding or ()))
    scoped_period = f"{year}-{period}" if not period.startswith(str(year)) else period
    report = _run_query(
        lambda: _service().bindings(modelo, period=scoped_period, as_of=_as_of(as_of))
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


def _service() -> RegistryQueryService:
    authority = ValidatedRegistryAuthority.load(PROJECT_ROOT / "registry" / "aeat", source_root=PROJECT_ROOT)
    return RegistryQueryService(authority)


def _as_of(raw: str | None) -> date | None:
    if raw is None:
        return None
    return _parse_iso_date(raw, label="--as-of")


__all__ = ["app"]
