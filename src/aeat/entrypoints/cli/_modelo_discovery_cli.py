"""Typer registration for modelo registry discovery commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Annotated

import typer

from ...application.modelo import (
    declared_modelo_period_tokens,
    profile_resolvable_binding_ids,
    registry_bindings,
    registry_bindings_for_scope,
    registry_bindings_for_year,
    registry_casillas,
    registry_casillas_for_scope,
    registry_describe_modelo,
    registry_describe_modelo_for_scope,
    registry_formulas,
    registry_formulas_for_scope,
    registry_list_modelos,
    registry_modelo_codes,
)
from ...core import Period, PeriodError
from ...core.i18n import output_language, tr
from ...domain.calculations.registry import (
    InputKind,
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.user_profile import ProfileNotFoundError
from ._common import _emit_envelope, _parse_iso_date
from ._modelo_payloads import (
    BindingPreviewRowPayload,
    CasillaRowPayload,
    FormulaPayload,
    FormulasResult,
    ModeloBindingsListResult,
    ModeloBindingsPreviewResult,
    ModeloCasillasResult,
    ModeloDescribeResult,
    ModeloListResult,
    ModeloRowPayload,
)


@dataclass(frozen=True, slots=True)
class _DiscoveryDeps:
    resolve_year_period: Callable[..., tuple[int, str]]
    bare_period_error: Callable[..., str]
    parse_binding_override: Callable[[str], tuple[str, str]]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]


def register_discovery_commands(
    app: typer.Typer,
    *,
    resolve_year_period: Callable[..., tuple[int, str]],
    bare_period_error: Callable[..., str],
    parse_binding_override: Callable[[str], tuple[str, str]],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register modelo registry discovery commands."""
    deps = _DiscoveryDeps(
        resolve_year_period=resolve_year_period,
        bare_period_error=bare_period_error,
        parse_binding_override=parse_binding_override,
        bad_parameter_from_error=bad_parameter_from_error,
    )
    bindings_app = typer.Typer(
        name="bindings",
        help=tr("cli.app.modelo.bindings.app_help"),
        no_args_is_help=True,
        add_completion=False,
    )
    app.add_typer(bindings_app, name="bindings")
    _register_list_command(app, deps)
    _register_describe_command(app, deps)
    _register_casillas_command(app, deps)
    _register_bindings_list_command(bindings_app, deps)
    _register_bindings_preview_command(bindings_app, deps)
    _register_formulas_command(app, deps)


def _as_of(raw: str | None) -> date | None:
    if raw is None:
        return None
    return _parse_iso_date(raw, label="--as-of")


def _run_query(call, *, bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]):
    try:
        return call()
    except (ValueError, RegistrySnapshotError) as exc:
        raise bad_parameter_from_error(exc) from exc


def _require_period_with_year(*, year: int | None, period: str | None) -> None:
    if year is not None and (period is None or not period.strip()):
        raise typer.BadParameter("--year requires --period")


def _resolve_discovery_year_period(
    deps: _DiscoveryDeps,
    *,
    modelo: str,
    year: int | None,
    period: str | None,
) -> tuple[int, str] | None:
    _require_period_with_year(year=year, period=period)
    if year is None:
        return None
    assert period is not None
    raw_period = period.strip()
    declared = {token.upper(): token for token in declared_modelo_period_tokens(modelo)}
    try:
        typed_period = Period.from_year_and_code(year, raw_period)
    except PeriodError as exc:
        registry_token = declared.get(raw_period.upper())
        if registry_token is not None:
            return year, registry_token
        fallback = f"period must be a bare registry token; got {period!r}"
        raise typer.BadParameter(deps.bare_period_error(modelo, period, fallback=fallback)) from exc
    return typed_period.year, declared.get(typed_period.registry_token.upper(), typed_period.registry_token)


def _register_list_command(app: typer.Typer, deps: _DiscoveryDeps) -> None:
    @app.command("list", help=tr("cli.app.modelo.list.help"))
    def list_modelos(
        ctx: typer.Context,
        year: Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.list.year_help"))] = None,
    ) -> None:
        report = _run_query(
            lambda: registry_list_modelos(year=year),
            bad_parameter_from_error=deps.bad_parameter_from_error,
        )
        result = ModeloListResult(
            year_filter=year,
            modelo_count=len(report.modelos),
            modelos=[
                ModeloRowPayload(
                    code=row.code,
                    title=row.title,
                    cadence=row.cadence,
                    tax_domain=row.tax_domain,
                    revision_count=row.revision_count,
                )
                for row in report.modelos
            ],
        )
        lines = [
            "code\ttitle\tcadence\tdomain\trevisions",
            *[
                f"{row.code}\t{row.title}\t{row.cadence}\t{row.tax_domain}\t{row.revision_count}"
                for row in report.modelos
            ],
        ]
        _emit_envelope(ctx, command="modelo.list", result=result, lines=lines)


def _register_describe_command(app: typer.Typer, deps: _DiscoveryDeps) -> None:
    @app.command("describe", help=tr("cli.app.modelo.describe.help"))
    def describe_modelo(
        ctx: typer.Context,
        modelo: Annotated[str, typer.Argument(help=tr("cli.app.modelo.describe.modelo_help"))],
        year: Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.list.year_help"))] = None,
        period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.describe.period_help"))] = None,
        as_of: Annotated[str | None, typer.Option("--as-of", help=tr("cli.app.modelo.describe.as_of_help"))] = None,
    ) -> None:
        try:
            resolved_scope = _resolve_discovery_year_period(deps, modelo=modelo, year=year, period=period)
            if resolved_scope is not None:
                report = registry_describe_modelo_for_scope(
                    modelo,
                    filing_year=resolved_scope[0],
                    period=resolved_scope[1],
                    as_of=_as_of(as_of),
                )
            else:
                report = registry_describe_modelo(modelo, period=period, as_of=_as_of(as_of))
        except (ValueError, RegistrySnapshotError) as exc:
            message = str(exc)
            if period is not None and "period" in message.lower():
                raise typer.BadParameter(deps.bare_period_error(modelo, period, fallback=message)) from exc
            raise typer.BadParameter(tr("cli.app.modelo.describe.period_error", message=message)) from exc

        result = ModeloDescribeResult(
            code=report.code,
            title=report.title,
            official_name=report.official_name,
            tax_domain=report.tax_domain,
            cadence=report.cadence,
            revision=report.revision,
            filing_year=report.filing_year,
            period=report.period,
            revision_ids=list(report.revision_ids),
            periods=list(report.periods),
            casilla_count=report.casilla_count,
            binding_count=report.binding_count,
            formula_count=report.formula_count,
        )
        lines = [
            f"{tr('cli.app.modelo.describe.label_modelo')}\t{report.code}",
            f"{tr('cli.app.modelo.describe.label_title')}\t{report.title}",
            f"{tr('cli.app.modelo.describe.label_official_name')}\t{report.official_name}",
            f"{tr('cli.app.modelo.describe.label_tax_domain')}\t{report.tax_domain}",
            f"{tr('cli.app.modelo.describe.label_cadence')}\t{report.cadence}",
            f"{tr('cli.app.modelo.describe.label_revision')}\t{report.revision}",
            f"{tr('cli.app.modelo.describe.label_revision_ids')}\t{', '.join(report.revision_ids)}",
            f"{tr('cli.app.modelo.describe.label_periods')}\t{', '.join(report.periods)}",
            f"{tr('cli.app.modelo.describe.label_casillas')}\t{report.casilla_count}",
            f"{tr('cli.app.modelo.describe.label_bindings')}\t{report.binding_count}",
            f"{tr('cli.app.modelo.describe.label_formulas')}\t{report.formula_count}",
        ]
        _emit_envelope(ctx, command="modelo.describe", result=result, lines=lines)


def _register_casillas_command(app: typer.Typer, deps: _DiscoveryDeps) -> None:
    @app.command("casillas", help=tr("cli.app.modelo.casillas.help"))
    def casillas(
        ctx: typer.Context,
        modelo: Annotated[str, typer.Argument(help=tr("cli.app.modelo.casillas.modelo_help"))],
        year: Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.list.year_help"))] = None,
        period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.modelo.casillas.period_help"))] = None,
        as_of: Annotated[str | None, typer.Option("--as-of", help=tr("cli.app.modelo.casillas.as_of_help"))] = None,
        input_kind: Annotated[
            InputKind | None,
            typer.Option("--input-kind", help=tr("cli.app.modelo.casillas.input_kind_help")),
        ] = None,
        required: Annotated[
            bool,
            typer.Option("--required", help=tr("cli.app.modelo.casillas.required_help")),
        ] = False,
        form_number: Annotated[
            str | None,
            typer.Option("--form-number", help=tr("cli.app.modelo.casillas.form_number_help")),
        ] = None,
        explain: Annotated[
            bool,
            typer.Option(
                "--explain",
                help=tr(
                    "cli.app.modelo.casillas.explain_help", default="Include localized help text in the text output.",
                ),
            ),
        ] = False,
    ) -> None:
        def _query():
            resolved_scope = _resolve_discovery_year_period(deps, modelo=modelo, year=year, period=period)
            if resolved_scope is not None:
                return registry_casillas_for_scope(
                    modelo,
                    filing_year=resolved_scope[0],
                    period=resolved_scope[1],
                    as_of=_as_of(as_of),
                    input_kind=input_kind,
                    required=True if required else None,
                    form_number=form_number,
                )
            return registry_casillas(
                modelo,
                period=period,
                as_of=_as_of(as_of),
                input_kind=input_kind,
                required=True if required else None,
                form_number=form_number,
            )

        report = _run_query(
            _query,
            bad_parameter_from_error=deps.bad_parameter_from_error,
        )
        lang = output_language()
        result = ModeloCasillasResult(
            modelo=report.code,
            revision=report.revision,
            casilla_count=len(report.rows),
            rows=[
                CasillaRowPayload(
                    casilla_id=row.casilla_id,
                    number=row.number,
                    input_kind=row.input_kind,
                    required=bool(row.required),
                    label=row.localized_labels.get(lang, row.label),
                    localized_labels=dict(row.localized_labels),
                    localized_help=dict(row.localized_help),
                )
                for row in report.rows
            ],
        )
        if explain:
            lines = [
                "casilla_id\tnumber\tinput\trequired\tlabel\thelp",
                *[
                    (
                        f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t"
                        f"{str(row.required).lower()}\t{row.localized_labels.get(lang, row.label)}\t"
                        f"{row.localized_help.get(lang) or '-'}"
                    )
                    for row in report.rows
                ],
            ]
        else:
            lines = [
                "casilla_id\tnumber\tinput\trequired\tlabel",
                *[
                    (
                        f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t"
                        f"{str(row.required).lower()}\t{row.localized_labels.get(lang, row.label)}"
                    )
                    for row in report.rows
                ],
            ]
        _emit_envelope(ctx, command="modelo.casillas", result=result, lines=lines)


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
    return _BINDING_SOURCE_TO_READINESS.get(source, "ledger source")


def _active_bucket_id() -> str:
    from ...core import require_active_bucket_id

    try:
        return require_active_bucket_id()
    except Exception as exc:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile")) from exc


def _profile_resolved_binding_ids(report) -> frozenset[str]:
    filing_year = getattr(report, "filing_year", None)
    if filing_year is None:
        return frozenset()
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


def _bindings_report_for_target(
    target: str,
    *,
    year: int | None,
    period: str | None,
    as_of: str | None,
    deps: _DiscoveryDeps,
):
    if year is not None and period is not None:
        resolved_year, resolved_period = deps.resolve_year_period(year, period, modelo=target)
        return _run_query(
            lambda: registry_bindings_for_scope(
                target,
                filing_year=resolved_year,
                period=resolved_period,
                as_of=_as_of(as_of),
            ),
            bad_parameter_from_error=deps.bad_parameter_from_error,
        )
    if year is not None:
        return _run_query(
            lambda: registry_bindings_for_year(
                target,
                filing_year=year,
                as_of=_as_of(as_of),
            ),
            bad_parameter_from_error=deps.bad_parameter_from_error,
        )
    return _run_query(
        lambda: registry_bindings(target, period=period, as_of=_as_of(as_of)),
        bad_parameter_from_error=deps.bad_parameter_from_error,
    )


def _binding_list_rows_for_report(report, *, missing: bool) -> tuple[list[dict[str, object]], list[str]]:
    rows = report.rows
    if missing:
        profile_resolved = _profile_resolved_binding_ids(report)
        rows = tuple(row for row in rows if row.source != "constant_value" and row.binding_id not in profile_resolved)

    merged_rows: list[dict[str, object]] = []
    text_rows: list[str] = []
    for row in rows:
        readiness = _readiness_for_source(row.source)
        merged_rows.append(
            {
                "modelo": report.code,
                "revision": report.revision,
                "filing_year": report.filing_year,
                "period": report.period,
                "binding_id": row.binding_id,
                "source": row.source,
                "readiness": readiness,
                "typed_enum": row.typed_enum,
                "input_channel": row.input_channel,
                "borrador_capable": row.borrador_capable,
            },
        )
        text_rows.append(
            f"{report.code}\t{report.revision}\t{report.period or '-'}\t"
            f"{row.binding_id}\t{row.source}\t{readiness}\t{row.typed_enum or '-'}\t"
            f"{row.input_channel}\t{row.borrador_capable}",
        )
    return merged_rows, text_rows


def _register_bindings_list_command(bindings_app: typer.Typer, deps: _DiscoveryDeps) -> None:
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
        """List bindings across modelos. All filters are optional refinements."""
        targets = registry_modelo_codes() if modelo is None else (modelo,)
        per_modelo_reports = []
        for target in targets:
            try:
                report = _bindings_report_for_target(target, year=year, period=period, as_of=as_of, deps=deps)
            except Exception:
                if modelo is not None:
                    raise
                continue
            per_modelo_reports.append(report)
        merged_rows: list[dict[str, object]] = []
        text_rows: list[str] = []
        for report in per_modelo_reports:
            report_rows, report_text_rows = _binding_list_rows_for_report(report, missing=missing)
            merged_rows.extend(report_rows)
            text_rows.extend(report_text_rows)
        result = ModeloBindingsListResult(
            modelo_filter=modelo,
            year_filter=year,
            period_filter=period,
            missing_filter=missing,
            binding_count=len(merged_rows),
            bindings=merged_rows,
        )
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
        _emit_envelope(ctx, command="modelo.bindings.list", result=result, lines=lines)


def _require_binding_scope(*, modelo: str | None, year: int | None, period: str | None) -> None:
    missing = [
        option
        for option, value in (("--modelo", modelo), ("--year", year), ("--period", period))
        if value is None or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        raise typer.BadParameter(tr("cli.app.modelo.bindings.missing_required_options", options=", ".join(missing)))


def _register_bindings_preview_command(bindings_app: typer.Typer, deps: _DiscoveryDeps) -> None:
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
        """Resolve temporary ``--binding`` overrides without mutating state."""
        _require_binding_scope(modelo=modelo, year=year, period=period)
        assert modelo is not None
        assert year is not None
        assert period is not None
        overrides = dict(deps.parse_binding_override(spec) for spec in (binding or ()))
        resolved_year, resolved_period = deps.resolve_year_period(year, period, modelo=modelo)
        report = _run_query(
            lambda: registry_bindings_for_scope(
                modelo,
                filing_year=resolved_year,
                period=resolved_period,
                as_of=_as_of(as_of),
            ),
            bad_parameter_from_error=deps.bad_parameter_from_error,
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
                ),
            )
        result = ModeloBindingsPreviewResult(
            modelo=report.code,
            revision=report.revision,
            filing_year=report.filing_year,
            period=report.period,
            override_count=len(overrides),
            binding_count=len(report.rows),
            bindings=[
                BindingPreviewRowPayload(
                    binding_id=row.binding_id,
                    source=row.source,
                    readiness=_readiness_for_source(row.source),
                    typed_enum=row.typed_enum,
                    override=overrides.get(row.binding_id),
                )
                for row in report.rows
            ],
        )
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
                ),
            )
            for row in report.rows
        )
        _emit_envelope(ctx, command="modelo.bindings.preview", result=result, lines=lines)


def _register_formulas_command(app: typer.Typer, deps: _DiscoveryDeps) -> None:
    @app.command("formulas", help=tr("cli.app.modelo.formulas.help"))
    def formulas(
        ctx: typer.Context,
        modelo: Annotated[str, typer.Argument(help=tr("cli.app.modelo.formulas.modelo_help"))],
        year: Annotated[int | None, typer.Option("--year", help=tr("cli.app.modelo.list.year_help"))] = None,
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
        def _query():
            resolved_scope = _resolve_discovery_year_period(deps, modelo=modelo, year=year, period=period)
            if resolved_scope is not None:
                return registry_formulas_for_scope(
                    modelo,
                    filing_year=resolved_scope[0],
                    period=resolved_scope[1],
                    as_of=_as_of(as_of),
                )
            return registry_formulas(modelo, period=period, as_of=_as_of(as_of))

        report = _run_query(
            _query,
            bad_parameter_from_error=deps.bad_parameter_from_error,
        )
        lines = _formula_lines(report, explain=explain)
        result = FormulasResult(
            code=report.code,
            revision=report.revision,
            filing_year=report.filing_year,
            period=report.period,
            formula_count=len(report.rows),
            rows=tuple(
                FormulaPayload(
                    formula_id=row.formula_id,
                    target=row.target,
                    input_casillas=tuple(row.input_casillas),
                    input_bindings=tuple(row.input_bindings),
                    input_parameters=tuple(row.input_parameters),
                    input_relations=tuple(row.input_relations),
                    expression=dict(row.expression) if hasattr(row, "expression") else {},
                    legal_refs=tuple(row.legal_refs),
                    source_refs=tuple(row.source_refs),
                )
                for row in report.rows
            ),
        )
        _emit_envelope(ctx, command="modelo.formulas", result=result, lines=lines)


def _formula_lines(report, *, explain: bool) -> list[str]:
    if explain:
        return [
            "formula_id\ttarget\tinputs\tlegal_refs\tsource_refs",
            *[
                f"{row.formula_id}\t{row.target}\t"
                f"{', '.join((*row.input_casillas, *row.input_bindings, *row.input_parameters))}\t"
                f"{', '.join(row.legal_refs)}\t"
                f"{', '.join(row.source_refs)}"
                for row in report.rows
            ],
        ]
    return [
        "formula_id\ttarget\tinputs",
        *[
            f"{row.formula_id}\t{row.target}\t"
            f"{', '.join((*row.input_casillas, *row.input_bindings, *row.input_parameters))}"
            for row in report.rows
        ],
    ]


__all__ = ["register_discovery_commands"]
