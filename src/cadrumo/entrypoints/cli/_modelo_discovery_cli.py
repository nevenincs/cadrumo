# ruff: noqa: E501 - localized guidance and tabular wire lines are atomic
"""Behavior handlers for modelo registry discovery commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import typer

from ...application.modelo.data_inventory import data_inventory_checklist
from ...application.modelo.registry_discovery import (
    registry_bindings,
    registry_bindings_for_scope,
    registry_bindings_for_year,
    registry_casilla,
    registry_casilla_for_registry_scope,
    registry_casillas,
    registry_casillas_for_registry_scope,
    registry_describe_modelo,
    registry_describe_modelo_for_registry_scope,
    registry_formulas,
    registry_formulas_for_registry_scope,
    registry_list_modelos,
    registry_modelo_codes,
    registry_support_matrix,
)
from ...application.modelo.work_create_policy import (
    ceded_autonomic_modelo_locale_key,
)
from ...application.state_projection import CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.i18n.render import tr
from ...core.period import Period
from ...core.tax_domain import TaxDomain
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.calculations.registry.query_reports import (
    ModeloBindingsReport,
    ModeloCasillasReport,
)
from ...domain.calculations.registry.schema_input_kind import InputKind
from . import _modelo_discovery_rendering as discovery_rendering
from ._date_parsing import _parse_iso_date
from ._modelo_behavior_support import bare_period_error, resolve_year_period
from ._modelo_bindings_payloads import (
    BindingPreviewRowPayload,
    ModeloBindingsListResult,
    ModeloBindingsPreviewResult,
)
from ._modelo_cli_support import bad_parameter_from_error, parse_binding_override
from ._modelo_payloads import (
    FormulaPayload,
    FormulasResult,
    ModeloCasillaResult,
    ModeloCasillasResult,
    ModeloRequiresResult,
)
from ._modelo_rendering import binding_encoded_option_lines, binding_encoded_option_payloads
from ._modelo_support_matrix_payloads import ModeloSupportMatrixResult
from .common import emit_envelope
from .modelo_aux_payloads import ModeloDescribeResult, ModeloListResult


@dataclass(frozen=True, slots=True)
class _DiscoveryDeps:
    resolve_year_period: Callable[..., Period]
    bare_period_error: Callable[..., str]
    parse_binding_override: Callable[[str], tuple[str, str]]
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]


deps = _DiscoveryDeps(
    resolve_year_period=resolve_year_period,
    bare_period_error=bare_period_error,
    parse_binding_override=parse_binding_override,
    bad_parameter_from_error=bad_parameter_from_error,
)


@dataclass(frozen=True, slots=True)
class _RegistryDiscoveryScope:
    filing_year: int
    period: str


def _as_of(raw: str | None) -> date | None:
    if raw is None:
        return None
    return _parse_iso_date(raw, label="--as-of")


def guard_ceded_autonomic_modelo(modelo: str) -> None:
    """Refuse a discovery lookup for a ceded autonomic modelo with a redirect.

    ITP-AJD (``600`` / ``620``) and ISD (``650`` / ``660``) are ceded autonomic
    taxes managed by each Comunidad Autónoma, not AEAT modelos in the
    calculation registry, so a bare registry lookup would surface a generic
    not-present error. This guard raises the instructive autonomic-redirect
    refusal instead, naming the ceded tax and its regional filing route, and is
    a no-op for every registry-backed or genuinely unknown code.
    """
    from .errors import CliRefusedBoundaryError

    modelo_code = modelo.strip()
    locale_key = ceded_autonomic_modelo_locale_key(modelo_code)
    if locale_key is None:
        return
    raise CliRefusedBoundaryError(translated_message=locale_key, context={"modelo": modelo_code})


def _run_query[QueryResultT](
    call: Callable[[], QueryResultT],
    *,
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> QueryResultT:
    try:
        return call()
    except (ValueError, RegistrySnapshotError) as exc:
        raise bad_parameter_from_error(exc) from exc


def _required_period_with_year(*, year: int | None, period: str | None) -> str | None:
    """Return the period a ``--year`` scope requires, or ``None`` when no year was given."""
    if year is None:
        return None
    if period is None or not period.strip():
        raise typer.BadParameter("--year requires --period")
    return period


def _resolve_discovery_year_period(
    *, modelo: str, year: int | None, period: str | None, deps: _DiscoveryDeps
) -> _RegistryDiscoveryScope | None:
    required_period = _required_period_with_year(year=year, period=period)
    if year is None or required_period is None:
        return None
    resolved = deps.resolve_year_period(year, required_period, modelo=modelo)
    return _RegistryDiscoveryScope(filing_year=resolved.filing_year, period=resolved.registry_token)


def _bindings_report_for_target(
    target: str, *, year: int | None, period: str | None, as_of: date | None, deps: _DiscoveryDeps
):
    if year is not None and period is not None:
        typed_period = deps.resolve_year_period(year, period, modelo=target)
        return _run_query(
            lambda: registry_bindings_for_scope(target, period=typed_period, as_of=as_of),
            bad_parameter_from_error=deps.bad_parameter_from_error,
        )
    if year is not None:
        return _run_query(
            lambda: registry_bindings_for_year(target, filing_year=year, as_of=as_of),
            bad_parameter_from_error=deps.bad_parameter_from_error,
        )
    return _run_query(
        lambda: registry_bindings(target, period=period, as_of=as_of),
        bad_parameter_from_error=deps.bad_parameter_from_error,
    )


def _required_binding_scope(*, modelo: str | None, year: int | None, period: str | None) -> tuple[str, int, str]:
    """Return the complete binding scope, refusing an incomplete option set."""
    missing = [
        option
        for option, value in (("--modelo", modelo), ("--year", year), ("--period", period))
        if value is None or (isinstance(value, str) and (not value.strip()))
    ]
    if missing or modelo is None or year is None or period is None:
        raise typer.BadParameter(tr("cli.app.modelo.bindings.missing_required_options", options=", ".join(missing)))
    return modelo, year, period


__all__ = [
    "bindings_list",
    "bindings_resolve",
    "casilla",
    "casillas",
    "describe_modelo",
    "formulas",
    "list_modelos",
    "requires",
    "support_matrix",
]


def list_modelos(ctx: typer.Context, year: int | None = None, domain: TaxDomain | None = None) -> None:
    report = _run_query(
        lambda: registry_list_modelos(year=year, domain=domain), bad_parameter_from_error=deps.bad_parameter_from_error
    )
    modelos = [discovery_rendering.modelo_row_payload(row) for row in report.modelos]
    result = ModeloListResult(
        year_filter=year,
        domain_filter=domain.value if domain is not None else None,
        modelo_count=len(report.modelos),
        modelos=modelos,
    )
    lines = [
        "code\ttitle\tcadence\tdomain\trevisions\tlocal_work\tlocal_work_guidance",
        *[
            f"{row.code}\t{row.title}\t{row.cadence}\t{row.tax_domain}\t{row.revision_count}\t{row.local_work_status}\t{row.local_work_guidance or '-'}"
            for row in modelos
        ],
    ]
    emit_envelope(ctx, command="modelo.list", result=result, lines=lines)


def describe_modelo(
    ctx: typer.Context, modelo: str, year: int | None = None, period: str | None = None, as_of: str | None = None
) -> None:
    guard_ceded_autonomic_modelo(modelo)
    try:
        resolved_scope = _resolve_discovery_year_period(modelo=modelo, year=year, period=period, deps=deps)
        if resolved_scope is not None:
            report = registry_describe_modelo_for_registry_scope(
                modelo, filing_year=resolved_scope.filing_year, period=resolved_scope.period, as_of=_as_of(as_of)
            )
        else:
            report = registry_describe_modelo(modelo, period=period, as_of=_as_of(as_of))
    except (ValueError, RegistrySnapshotError) as exc:
        message = str(exc)
        if period is not None and "period" in message.lower():
            raise typer.BadParameter(deps.bare_period_error(modelo, period, fallback=message)) from exc
        raise typer.BadParameter(tr("cli.app.modelo.describe.period_error", message=message)) from exc
    result = ModeloDescribeResult.from_report(report)
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
    emit_envelope(ctx, command="modelo.describe", result=result, lines=lines)


def _casillas_report(
    *,
    modelo: str,
    year: int | None,
    period: str | None,
    as_of: str | None,
    input_kind: InputKind | None,
    required: bool,
    form_number: str | None,
) -> ModeloCasillasReport:
    def _query() -> ModeloCasillasReport:
        resolved_scope = _resolve_discovery_year_period(modelo=modelo, year=year, period=period, deps=deps)
        if resolved_scope is not None:
            return registry_casillas_for_registry_scope(
                modelo,
                filing_year=resolved_scope.filing_year,
                period=resolved_scope.period,
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

    return _run_query(_query, bad_parameter_from_error=deps.bad_parameter_from_error)


def casillas(
    ctx: typer.Context,
    modelo: str,
    year: int | None = None,
    period: str | None = None,
    as_of: str | None = None,
    input_kind: InputKind | None = None,
    required: bool = False,
    form_number: str | None = None,
    casilla_number: str | None = None,
    explain: bool = False,
) -> None:
    guard_ceded_autonomic_modelo(modelo)
    report = _casillas_report(
        modelo=modelo,
        year=year,
        period=period,
        as_of=as_of,
        input_kind=input_kind,
        required=required,
        form_number=form_number,
    )
    number_filter = casilla_number.strip() if casilla_number is not None else None
    if number_filter:
        report = report.model_copy(
            update={
                "rows": tuple(
                    row for row in report.rows if row.number == number_filter or row.casilla_id == number_filter
                )
            }
        )
    result = ModeloCasillasResult(
        modelo=report.code,
        revision=report.revision,
        casilla_count=len(report.rows),
        rows=discovery_rendering.casilla_row_payloads(report),
    )
    lines = discovery_rendering.casillas_lines(report, explain=explain)
    emit_envelope(ctx, command="modelo.casillas", result=result, lines=lines)


def casilla(
    ctx: typer.Context,
    modelo: str,
    casilla_id: str,
    year: int | None = None,
    period: str | None = None,
    as_of: str | None = None,
) -> None:
    guard_ceded_autonomic_modelo(modelo)

    def _query():
        resolved_scope = _resolve_discovery_year_period(modelo=modelo, year=year, period=period, deps=deps)
        if resolved_scope is not None:
            return registry_casilla_for_registry_scope(
                modelo,
                casilla_id,
                filing_year=resolved_scope.filing_year,
                period=resolved_scope.period,
                as_of=_as_of(as_of),
            )
        return registry_casilla(modelo, casilla_id, period=period, as_of=_as_of(as_of))

    report = _run_query(_query, bad_parameter_from_error=deps.bad_parameter_from_error)
    label = report.label
    result = ModeloCasillaResult(
        modelo=report.code,
        revision=report.revision,
        filing_year=report.filing_year,
        period=report.period,
        casilla_id=report.casilla_id,
        number=report.number,
        label=label,
        help_text=report.help_text,
        section=tuple(report.section),
        data_type=report.data_type,
        input_kind=str(report.input_kind),
        required=bool(report.required),
        legal_refs=tuple(report.legal_refs),
        source_refs=tuple(report.source_refs),
        binding=report.binding,
        formula_id=report.formula_id,
        formula_expression=dict(report.formula_expression) if report.formula_expression is not None else None,
    )
    lines = [
        f"modelo\t{report.code}",
        f"revision\t{report.revision}",
        f"casilla_id\t{report.casilla_id}",
        f"number\t{report.number}",
        f"input_kind\t{report.input_kind}",
        f"required\t{str(bool(report.required)).lower()}",
        f"data_type\t{report.data_type}",
        f"label\t{label}",
        f"section\t{' > '.join(report.section)}",
        f"legal_refs\t{', '.join(report.legal_refs)}",
        f"source_refs\t{', '.join(report.source_refs)}",
        f"binding\t{report.binding or '-'}",
        f"formula_id\t{report.formula_id or '-'}",
    ]
    help_text = report.help_text
    if help_text:
        lines.append(f"help\t{help_text}")
    if report.formula_expression is not None:
        lines.append(f"formula_expression\t{report.formula_expression}")
    emit_envelope(ctx, command="modelo.casilla", result=result, lines=lines)


def requires(ctx: typer.Context, modelo: str, year: int, period: str) -> None:
    guard_ceded_autonomic_modelo(modelo)
    typed_period = deps.resolve_year_period(year, period, modelo=modelo)

    def _query():
        return data_inventory_checklist(
            modelo=modelo,
            filing_year=typed_period.filing_year,
            period=typed_period,
            bucket_id=resolve_active_bucket_id(),
        )

    checklist = _run_query(_query, bad_parameter_from_error=deps.bad_parameter_from_error)
    result = ModeloRequiresResult(
        modelo=checklist.modelo,
        revision=checklist.revision_id,
        filing_year=checklist.filing_year,
        period=checklist.period,
        required_manual=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.required_manual
        ],
        optional_manual=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.optional_manual
        ],
        ledger_derivable=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.ledger_derivable
        ],
        profile_derivable=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.profile_derivable
        ],
        previous_filing=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.previous_filing
        ],
        relation_prefill=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.relation_prefill
        ],
        live_observation=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.live_observation
        ],
        unbucketed_sources=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.unbucketed_sources
        ],
        unresolved_profile_bindings=list(checklist.unresolved_profile_bindings),
        unresolved_profile_keys=list(checklist.unresolved_profile_keys),
        profile_checked=checklist.profile_checked,
    )
    lines = [
        f"modelo\t{checklist.modelo}",
        f"revision\t{checklist.revision_id}",
        f"filing_year\t{checklist.filing_year}",
        f"period\t{checklist.period}",
        *discovery_rendering.data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_required", default="required_manual"), checklist.required_manual
        ),
        *discovery_rendering.data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_optional", default="optional_manual"), checklist.optional_manual
        ),
        *discovery_rendering.data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_ledger", default="ledger_derivable"), checklist.ledger_derivable
        ),
        *discovery_rendering.data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_profile", default="profile_derivable"), checklist.profile_derivable
        ),
        *discovery_rendering.data_inventory_section_lines("previous_filing", checklist.previous_filing),
        *discovery_rendering.data_inventory_section_lines("relation_prefill", checklist.relation_prefill),
        *discovery_rendering.data_inventory_section_lines("live_observation", checklist.live_observation),
        *discovery_rendering.data_inventory_section_lines("unbucketed_sources", checklist.unbucketed_sources),
    ]
    notices = discovery_rendering.requires_notices(checklist)
    lines.extend(discovery_rendering.notice_text_lines(notices))
    emit_envelope(ctx, command="modelo.requires", result=result, lines=lines, notices=notices)


def _binding_reports_for_list(
    *,
    modelo: str | None,
    known_codes: tuple[str, ...],
    year: int | None,
    period: str | None,
    as_of: date | None,
) -> list[ModeloBindingsReport]:
    targets = known_codes if modelo is None else (modelo,)
    reports: list[ModeloBindingsReport] = []
    for target in targets:
        try:
            report = _bindings_report_for_target(target, year=year, period=period, as_of=as_of, deps=deps)
        except Exception:
            if modelo is not None:
                raise
            continue
        reports.append(report)
    return reports


def bindings_list(
    ctx: typer.Context,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    missing: bool = False,
    as_of: str | None = None,
) -> None:
    """List bindings across modelos. All filters are optional refinements."""
    resolved_as_of = _as_of(as_of)
    known_codes = registry_modelo_codes()
    if modelo is not None and modelo not in known_codes:
        # The accepted set is registry-derived, so it cannot be a static Choice on
        # the option. A late refusal is allowed for exactly that reason, but it
        # has to NAME the accepted codes: "not present in the calculation
        # registry" alone leaves the operator guessing which codes exist.
        raise typer.BadParameter(
            f"modelo {modelo!r} is not in the calculation registry. Accepted: {', '.join(known_codes)}."
        )
    per_modelo_reports = _binding_reports_for_list(
        modelo=modelo,
        known_codes=known_codes,
        year=year,
        period=period,
        as_of=resolved_as_of,
    )
    merged_rows, text_rows = discovery_rendering.binding_rows_for_reports(
        per_modelo_reports,
        missing=missing,
        as_of=resolved_as_of,
    )
    result = ModeloBindingsListResult(
        modelo_filter=modelo,
        year_filter=year,
        period_filter=period,
        missing_filter=missing,
        binding_count=len(merged_rows),
        bindings=tuple(merged_rows),
    )
    lines = [
        "operation\tregistry.modelo.bindings.list",
        f"modelo_filter\t{modelo or '-'}",
        f"year_filter\t{(year if year is not None else '-')}",
        f"period_filter\t{period or '-'}",
        f"missing_filter\t{missing}",
        f"binding_count\t{len(merged_rows)}",
        "modelo\trevision\tperiod\tbinding_id\tsource\treadiness\ttyped_enum\tinput_channel\tborrador_capable",
    ]
    notices = discovery_rendering.bindings_list_scope_notices(modelo=modelo, year=year, period=period)
    lines.extend(discovery_rendering.notice_text_lines(notices))
    lines.extend(text_rows)
    emit_envelope(ctx, command="modelo.bindings.list", result=result, lines=lines, notices=notices)


def bindings_resolve(
    ctx: typer.Context,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    binding: list[str] | None = None,
    as_of: str | None = None,
) -> None:
    """Resolve temporary ``--binding`` overrides without mutating state."""
    modelo, year, period = _required_binding_scope(modelo=modelo, year=year, period=period)
    overrides = dict(deps.parse_binding_override(spec) for spec in binding or ())
    typed_period = deps.resolve_year_period(year, period, modelo=modelo)
    report = _run_query(
        lambda: registry_bindings_for_scope(modelo, period=typed_period, as_of=_as_of(as_of)),
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
            )
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
                readiness=tr(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[row.source]),
                typed_enum=row.typed_enum,
                override=overrides.get(row.binding_id),
                legal_refs=row.legal_refs,
                source_refs=row.source_refs,
                relation_inputs=row.relation_inputs,
                encoded_options=binding_encoded_option_payloads(row.encoded_options),
            )
            for row in report.rows
        ],
    )
    lines = [
        "operation\tregistry.modelo.bindings.resolve",
        f"modelo\t{report.code}",
        f"revision\t{report.revision}",
        f"filing_year\t{report.filing_year}",
        f"period\t{report.period}",
        f"override_count\t{len(overrides)}",
        f"binding_count\t{len(report.rows)}",
        "binding_id\tsource\treadiness\toverride",
    ]
    for row in report.rows:
        lines.append(
            "\t".join(
                (
                    row.binding_id,
                    row.source,
                    tr(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[row.source]),
                    overrides.get(row.binding_id) or "-",
                )
            )
        )
        lines.extend(binding_encoded_option_lines(row.binding_id, binding_encoded_option_payloads(row.encoded_options)))
    emit_envelope(ctx, command="modelo.bindings.resolve", result=result, lines=lines)


def formulas(
    ctx: typer.Context,
    modelo: str,
    year: int | None = None,
    period: str | None = None,
    as_of: str | None = None,
    explain: bool = False,
) -> None:
    guard_ceded_autonomic_modelo(modelo)

    def _query():
        resolved_scope = _resolve_discovery_year_period(modelo=modelo, year=year, period=period, deps=deps)
        if resolved_scope is not None:
            return registry_formulas_for_registry_scope(
                modelo, filing_year=resolved_scope.filing_year, period=resolved_scope.period, as_of=_as_of(as_of)
            )
        return registry_formulas(modelo, period=period, as_of=_as_of(as_of))

    report = _run_query(_query, bad_parameter_from_error=deps.bad_parameter_from_error)
    lines = discovery_rendering.formula_lines(report, explain=explain)
    result = FormulasResult(
        code=report.code,
        revision=report.revision,
        filing_year=report.filing_year,
        period=report.period,
        formula_count=len(report.rows),
        rows=tuple(
            FormulaPayload(
                formula_id=row.formula_id,
                target_casilla_id=row.target_casilla_id,
                input_casilla_ids=tuple(row.input_casilla_ids),
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
    emit_envelope(ctx, command="modelo.formulas", result=result, lines=lines)


def support_matrix(ctx: typer.Context) -> None:
    report = registry_support_matrix()
    entries = [discovery_rendering.support_matrix_entry_payload(entry) for entry in report.entries]
    result = ModeloSupportMatrixResult(modelo_count=len(entries), entries=entries)
    lines = [
        f"{'modelo':>6}  {'revs':>4}  {'latest':<12}  {'calc':>4}  {'manifest':>8}  {'boe':>3}  {'xml':>3}  {'extractor':>9}  {'renames':>7}"
    ]
    for entry in entries:
        lines.append(
            f"{entry.modelo_id:>6}  {entry.revision_count:>4}  {entry.latest_revision_id:<12}  {discovery_rendering.mark(entry.calc_grade):>4}  {discovery_rendering.mark(entry.has_completeness_manifest):>8}  {discovery_rendering.mark(entry.has_fixed_width_export):>3}  {discovery_rendering.mark(entry.has_xml_dictionary_export):>3}  {discovery_rendering.mark(entry.has_extractor):>9}  {len(entry.renames):>7}"
        )
    emit_envelope(ctx, command="modelo.support_matrix", result=result, lines=lines)
