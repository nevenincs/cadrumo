# ruff: noqa: E501 - localized guidance and tabular wire lines are atomic
"""Behavior handlers for modelo registry discovery commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import typer

from ...application.modelo._binding_readiness import profile_resolvable_binding_ids
from ...application.modelo._data_inventory import (
    DataInventoryCasilla,
    DataInventoryChecklist,
    data_inventory_checklist,
)
from ...application.modelo._work_create_policy import (
    ceded_autonomic_modelo_locale_key,
    modelo_work_create_refusal_locale_key,
)
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
from ...application.operator_actions import ActionReference
from ...application.state_projection import CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS
from ...core.tax_domain import TaxDomain
from ...core.operator_action_enums import ActionArgumentSource, ActionArgumentStatus
from ...core.period import Period
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity, ResolvedActionArgument
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.query_reports import ModeloListRow
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.support_matrix import ModeloEntry
from ...domain.user_profile.errors import ProfileNotFoundError
from ._common import emit_envelope, resolve_notice_action
from ._date_parsing import _parse_iso_date
from ._modelo_behavior_support import bare_period_error, resolve_year_period
from ._modelo_cli_support import bad_parameter_from_error, parse_binding_override
from ._modelo_payloads import (
    BindingListRowPayload,
    BindingPreviewRowPayload,
    CasillaRowPayload,
    DataInventoryCasillaPayload,
    FormulaPayload,
    FormulasResult,
    ModeloBindingsListResult,
    ModeloBindingsPreviewResult,
    ModeloCasillaResult,
    ModeloCasillasResult,
    ModeloDescribeResult,
    ModeloListResult,
    ModeloPortalCompatibilityRefPayload,
    ModeloRenamePayload,
    ModeloRequiresResult,
    ModeloRowPayload,
    ModeloSupportMatrixEntryPayload,
    ModeloSupportMatrixResult,
)
from ._modelo_rendering import binding_encoded_option_lines, binding_encoded_option_payloads


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


def _run_query(call, *, bad_parameter_from_error: Callable[[BaseException], typer.BadParameter]):
    try:
        return call()
    except (ValueError, RegistrySnapshotError) as exc:
        raise bad_parameter_from_error(exc) from exc


def _require_period_with_year(*, year: int | None, period: str | None) -> None:
    if year is not None and (period is None or not period.strip()):
        raise typer.BadParameter("--year requires --period")


def _resolve_discovery_year_period(
    *, modelo: str, year: int | None, period: str | None, deps: _DiscoveryDeps
) -> _RegistryDiscoveryScope | None:
    _require_period_with_year(year=year, period=period)
    if year is None:
        return None
    assert period is not None
    resolved = deps.resolve_year_period(year, period, modelo=modelo)
    return _RegistryDiscoveryScope(filing_year=resolved.filing_year, period=resolved.registry_token)


def _data_inventory_casilla_payload(entry: DataInventoryCasilla) -> DataInventoryCasillaPayload:
    return DataInventoryCasillaPayload(
        casilla_id=entry.casilla_id,
        number=entry.number,
        label=entry.label,
        legal_refs=entry.legal_refs,
        source_refs=entry.source_refs,
        binding_id=entry.binding_id,
        binding_source=entry.binding_source,
    )


def _data_inventory_section_lines(title: str, rows: tuple[DataInventoryCasilla, ...]) -> list[str]:
    if not rows:
        return [f"{title}\t(none)"]
    lines = [f"{title}\t{len(rows)}"]
    for entry in rows:
        label = entry.label
        suffix = f"\t({entry.binding_source})" if entry.binding_source else ""
        lines.append(f"  {entry.number}\t{label}{suffix}")
    return lines


def _requires_notices(checklist: DataInventoryChecklist) -> tuple[Notice, ...]:
    notices = [
        notice
        for notice in (_profile_requirement_notice(checklist), _unbucketed_source_notice(checklist))
        if notice is not None
    ]
    return tuple(notices)


def _profile_requirement_notice(checklist: DataInventoryChecklist) -> Notice | None:
    if not checklist.profile_checked:
        return Notice(
            severity=NoticeSeverity.INFO,
            code="modelo.requires.no_active_profile",
            message=tr(
                "cli.app.modelo.requires.no_active_profile",
                default="No active profile is set, so profile-dependent coefficients (e.g. home-office usage ratio) could not be checked for gaps.",
            ),
            context={"modelo": str(checklist.modelo)},
        )
    if not checklist.unresolved_profile_bindings:
        return None
    binding_ids = ", ".join(sorted(str(binding_id) for binding_id in checklist.unresolved_profile_bindings))
    missing = _unresolved_profile_requirements(checklist) or binding_ids
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.requires.missing_profile_coefficient",
        message=tr(
            "cli.app.modelo.requires.missing_profile_coefficient",
            default="The active profile has not set the following coefficient(s) needed for this modelo: {missing}.",
            missing=missing,
        ),
        context={"modelo": str(checklist.modelo), "missing_bindings": binding_ids},
    )


def _unbucketed_source_notice(checklist: DataInventoryChecklist) -> Notice | None:
    if not checklist.unbucketed_sources:
        return None
    source_kinds = ", ".join(sorted({entry.binding_source or "" for entry in checklist.unbucketed_sources}))
    binding_ids = ", ".join(
        sorted(str(entry.binding_id) for entry in checklist.unbucketed_sources if entry.binding_id is not None)
    )
    casilla_ids = ", ".join(sorted({str(entry.casilla_id) for entry in checklist.unbucketed_sources}))
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.requires.unbucketed_binding_source",
        message=tr("cli.app.modelo.requires.unbucketed_binding_source"),
        context={
            "modelo": str(checklist.modelo),
            "source_kinds": source_kinds,
            "binding_ids": binding_ids,
            "casilla_ids": casilla_ids,
        },
    )


def _unresolved_profile_requirements(checklist: DataInventoryChecklist) -> str:
    """Render the unresolved bindings' profile facts as grounded requirements.

    A binding id names the registry's internal consumer of a profile fact, not
    the fact the operator has to supply, so the message is built from the
    profile keys those bindings consume and resolved through the same schema
    and registry grounding the modelo readiness gate uses.

    Returns the empty string when no key resolves, which lets the caller fall
    back to the binding ids rather than emit a warning naming nothing.
    """
    from ...application.user_profile.preflight import format_profile_path_requirements
    from ...domain.calculations.registry.profile_grounding import build_profile_grounding_index
    from ...domain.user_profile.loader import load_user_profile_schema

    if not checklist.unresolved_profile_keys:
        return ""
    return ", ".join(
        format_profile_path_requirements(
            checklist.unresolved_profile_keys,
            schema=load_user_profile_schema(),
            grounding_index=build_profile_grounding_index(bundled_authority()),
        )
    )


def _relation_input_guidance_lines(rows) -> tuple[str, ...]:
    """Registry-derived ``--relation`` guidance for relation-fed bindings.

    Every binding whose value is materialised by one or more registry
    relations (``relation_inputs`` is non-empty) is supplied through
    ``--relation RELATION_ID=VALUE`` rather than ``--binding``. The feeding
    relation ids come from the resolved revision (each
    :class:`RelationDefinition` declares
    its ``target_binding``), so this guidance generalises to any modelo
    instead of enumerating a per-form channel table.
    """
    relation_fed = tuple(row for row in rows if row.relation_inputs)
    if not relation_fed:
        return ()
    lines = [
        "relation_guidance\t"
        + tr(
            "cli.app.modelo.bindings.relation_input_guidance",
            default="Some bindings below are fed by registry relations (cross-modelo or cross-period fold-ins), not direct --binding values. Supply each with --relation RELATION_ID=VALUE before calculating.",
        )
    ]
    for row in relation_fed:
        for relation_id in row.relation_inputs:
            lines.append(
                "relation_input\t"
                + tr(
                    "cli.app.modelo.bindings.relation_input_channel",
                    default="{binding_id}\tfed by relation {relation_id}\tuse --relation {relation_id}=VALUE",
                    binding_id=str(row.binding_id),
                    relation_id=str(relation_id),
                )
            )
    return tuple(lines)


def _profile_resolved_binding_ids(report, *, as_of: date | None) -> frozenset[str]:
    filing_year = report.filing_year
    if filing_year is None:
        return frozenset[str]()
    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return frozenset[str]()
    try:
        return _text_frozenset(
            profile_resolvable_binding_ids(
                modelo=str(report.code),
                bucket_id=bucket_id,
                filing_year=int(filing_year),
                period=report.filing_period,
                as_of=as_of,
                revision_id=str(report.revision),
            )
        )
    except (RegistrySnapshotError, RegistryValidationError, ProfileNotFoundError):
        return frozenset[str]()


def _text_frozenset(value: object) -> frozenset[str]:
    """Validate the application binding-id collection at the CLI boundary."""
    if not isinstance(value, (set, frozenset, tuple, list)):
        raise TypeError("binding-id projection must be a collection")
    values: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise TypeError("binding-id projection must contain text")
        values.add(item)
    return frozenset(values)


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


def _binding_list_rows_for_report(
    report, *, missing: bool, as_of: date | None
) -> tuple[list[BindingListRowPayload], list[str]]:
    rows = report.rows
    if missing:
        profile_resolved = _profile_resolved_binding_ids(report, as_of=as_of)
        rows = tuple(row for row in rows if row.binding_id not in profile_resolved and row.operator_input_required)
    merged_rows: list[BindingListRowPayload] = []
    text_rows: list[str] = []
    for row in rows:
        readiness = tr(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[row.source])
        encoded_options = binding_encoded_option_payloads(row.encoded_options)
        merged_rows.append(
            BindingListRowPayload(
                modelo=report.code,
                revision=report.revision,
                filing_year=report.filing_year,
                period=report.period,
                binding_id=row.binding_id,
                source=row.source,
                readiness=readiness,
                typed_enum=row.typed_enum,
                input_channel=row.input_channel,
                borrador_capable=row.borrador_capable,
                legal_refs=row.legal_refs,
                source_refs=row.source_refs,
                relation_inputs=row.relation_inputs,
                encoded_options=encoded_options,
            )
        )
        text_rows.append(
            f"{report.code}\t{report.revision}\t{report.period or '-'}\t{row.binding_id}\t{row.source}\t{readiness}\t{row.typed_enum or '-'}\t{row.input_channel}\t{row.borrador_capable}"
        )
        text_rows.extend(binding_encoded_option_lines(row.binding_id, encoded_options))
    if missing:
        text_rows.extend(_relation_input_guidance_lines(rows))
    return (merged_rows, text_rows)


def _binding_scope_missing_filters(*, year: int | None, period: str | None) -> tuple[str, ...]:
    return tuple(
        (
            option
            for option, value in (("--year", year), ("--period", period))
            if value is None or (isinstance(value, str) and (not value.strip()))
        )
    )


def _binding_scope_action_bindings(
    *, modelo: str | None, year: int | None, period: str | None
) -> tuple[ResolvedActionArgument, ...]:
    argument_values: tuple[tuple[str, str | int | None], ...] = (("modelo", modelo), ("year", year), ("period", period))
    return tuple(
        (
            ResolvedActionArgument(
                argument_name=argument_name,
                status=ActionArgumentStatus.RESOLVED,
                value=value,
                source=ActionArgumentSource.VERDICT_CONTEXT,
                source_key=argument_name,
            )
            for argument_name, value in argument_values
            if value is not None and (not isinstance(value, str) or value.strip())
        )
    )


def _binding_scope_notice_context(
    *, modelo: str | None, year: int | None, period: str | None, missing_filters: tuple[str, ...]
) -> dict[str, str]:
    return {
        "modelo_filter": modelo or "",
        "year_filter": "" if year is None else str(year),
        "period_filter": period or "",
        "missing_filters": ", ".join(missing_filters),
    }


def _bindings_list_scope_notices(*, modelo: str | None, year: int | None, period: str | None) -> tuple[Notice, ...]:
    missing_filters = _binding_scope_missing_filters(year=year, period=period)
    if not missing_filters:
        return ()
    missing = ", ".join(missing_filters)
    message = tr("cli.app.modelo.bindings.unscoped_revision_warning", missing_filters=missing)
    return (
        Notice(
            severity=NoticeSeverity.WARNING,
            code="modelo.bindings.list.unscoped_revision",
            message=message,
            action=resolve_notice_action(
                action=ActionReference(action_id="operator.modelo.bindings.list"),
                argument_bindings=_binding_scope_action_bindings(modelo=modelo, year=year, period=period),
            ),
            context=_binding_scope_notice_context(
                modelo=modelo, year=year, period=period, missing_filters=missing_filters
            ),
        ),
    )


def _notice_text_lines(notices: tuple[Notice, ...]) -> list[str]:
    lines: list[str] = []
    for notice in notices:
        notice_action = notice.action
        action_reference = notice_action.action if notice_action is not None else None
        target = action_reference.target_command_key if action_reference is not None else "-"
        bindings = (
            ",".join(f"{binding.argument_name}={binding.value}" for binding in notice_action.argument_bindings)
            if notice_action is not None
            else "-"
        )
        lines.append(
            f"notice\t{notice.severity.value}\t{notice.code}\t{notice.message}\taction_target={target}\taction_bindings={bindings or '-'}"
        )
    return lines


def _require_binding_scope(*, modelo: str | None, year: int | None, period: str | None) -> None:
    missing = [
        option
        for option, value in (("--modelo", modelo), ("--year", year), ("--period", period))
        if value is None or (isinstance(value, str) and (not value.strip()))
    ]
    if missing:
        raise typer.BadParameter(tr("cli.app.modelo.bindings.missing_required_options", options=", ".join(missing)))


def _formula_lines(report, *, explain: bool) -> list[str]:
    if explain:
        return [
            "formula_id\ttarget_casilla_id\tinputs\tlegal_refs\tsource_refs",
            *[
                f"{row.formula_id}\t{row.target_casilla_id}\t{', '.join((*row.input_casilla_ids, *row.input_bindings, *row.input_parameters))}\t{', '.join(row.legal_refs)}\t{', '.join(row.source_refs)}"
                for row in report.rows
            ],
        ]
    return [
        "formula_id\ttarget_casilla_id\tinputs",
        *[
            f"{row.formula_id}\t{row.target_casilla_id}\t{', '.join((*row.input_casilla_ids, *row.input_bindings, *row.input_parameters))}"
            for row in report.rows
        ],
    ]


def _mark(value: bool) -> str:
    return "Y" if value else "-"


def _support_matrix_entry_payload(entry: ModeloEntry) -> ModeloSupportMatrixEntryPayload:
    return ModeloSupportMatrixEntryPayload(
        modelo_id=entry.modelo_id,
        title=entry.title,
        calculation_class=entry.calculation_class,
        revision_count=entry.revision_count,
        latest_revision_id=entry.latest_revision_id,
        latest_revision_valid_from=entry.latest_revision_valid_from.isoformat(),
        supported_revision_ids=list(entry.supported_revision_ids),
        calc_grade=entry.calc_grade,
        has_completeness_manifest=entry.has_completeness_manifest,
        has_fixed_width_export=entry.has_fixed_width_export,
        has_xml_dictionary_export=entry.has_xml_dictionary_export,
        has_extractor=entry.has_extractor,
        extraction_profile_count=entry.extraction_profile_count,
        renames=[
            ModeloRenamePayload(
                continuidad_id=rename.continuidad_id,
                from_revision=rename.from_revision,
                to_revision=rename.to_revision,
                evolution_kind=rename.evolution_kind,
            )
            for rename in entry.renames
        ],
        portal_compatibility_refs=[
            ModeloPortalCompatibilityRefPayload(id=ref.id, surface=ref.surface, evidence_tier=ref.evidence_tier)
            for ref in entry.portal_compatibility_refs
        ],
    )


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


def _modelo_row_payload(row: ModeloListRow) -> ModeloRowPayload:
    locale_key = modelo_work_create_refusal_locale_key(row.code)
    local_work_supported = locale_key is None
    return ModeloRowPayload(
        code=row.code,
        title=row.title,
        cadence=row.cadence,
        tax_domain=row.tax_domain,
        revision_count=row.revision_count,
        local_work_supported=local_work_supported,
        local_work_status="supported-model-level" if local_work_supported else "unsupported-local-work",
        local_work_guidance=None if locale_key is None else tr(locale_key, modelo=row.code),
    )


def list_modelos(ctx: typer.Context, year: int | None = None, domain: TaxDomain | None = None) -> None:
    report = _run_query(
        lambda: registry_list_modelos(year=year, domain=domain), bad_parameter_from_error=deps.bad_parameter_from_error
    )
    modelos = [_modelo_row_payload(row) for row in report.modelos]
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

    def _query():
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

    report = _run_query(_query, bad_parameter_from_error=deps.bad_parameter_from_error)
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
        rows=[
            CasillaRowPayload(
                casilla_id=row.casilla_id,
                number=row.number,
                input_kind=row.input_kind,
                required=bool(row.required),
                label=row.label,
                help_text=row.help_text,
                legal_refs=tuple(row.legal_refs),
                source_refs=tuple(row.source_refs),
            )
            for row in report.rows
        ],
    )
    if explain:
        lines = [
            "casilla_id\tnumber\tinput\trequired\tlabel\thelp\tlegal_refs\tsource_refs",
            *[
                f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t{str(row.required).lower()}\t{row.label}\t{row.help_text or '-'}\t{', '.join(row.legal_refs)}\t{', '.join(row.source_refs)}"
                for row in report.rows
            ],
        ]
    else:
        lines = [
            "casilla_id\tnumber\tinput\trequired\tlabel",
            *[
                f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t{str(row.required).lower()}\t{row.label}"
                for row in report.rows
            ],
        ]
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
        required_manual=[_data_inventory_casilla_payload(entry) for entry in checklist.required_manual],
        optional_manual=[_data_inventory_casilla_payload(entry) for entry in checklist.optional_manual],
        ledger_derivable=[_data_inventory_casilla_payload(entry) for entry in checklist.ledger_derivable],
        profile_derivable=[_data_inventory_casilla_payload(entry) for entry in checklist.profile_derivable],
        previous_filing=[_data_inventory_casilla_payload(entry) for entry in checklist.previous_filing],
        relation_prefill=[_data_inventory_casilla_payload(entry) for entry in checklist.relation_prefill],
        live_observation=[_data_inventory_casilla_payload(entry) for entry in checklist.live_observation],
        unbucketed_sources=[_data_inventory_casilla_payload(entry) for entry in checklist.unbucketed_sources],
        unresolved_profile_bindings=list(checklist.unresolved_profile_bindings),
        unresolved_profile_keys=list(checklist.unresolved_profile_keys),
        profile_checked=checklist.profile_checked,
    )
    lines = [
        f"modelo\t{checklist.modelo}",
        f"revision\t{checklist.revision_id}",
        f"filing_year\t{checklist.filing_year}",
        f"period\t{checklist.period}",
        *_data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_required", default="required_manual"), checklist.required_manual
        ),
        *_data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_optional", default="optional_manual"), checklist.optional_manual
        ),
        *_data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_ledger", default="ledger_derivable"), checklist.ledger_derivable
        ),
        *_data_inventory_section_lines(
            tr("cli.app.modelo.requires.section_profile", default="profile_derivable"), checklist.profile_derivable
        ),
        *_data_inventory_section_lines("previous_filing", checklist.previous_filing),
        *_data_inventory_section_lines("relation_prefill", checklist.relation_prefill),
        *_data_inventory_section_lines("live_observation", checklist.live_observation),
        *_data_inventory_section_lines("unbucketed_sources", checklist.unbucketed_sources),
    ]
    notices = _requires_notices(checklist)
    lines.extend(_notice_text_lines(notices))
    emit_envelope(ctx, command="modelo.requires", result=result, lines=lines, notices=notices)


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
    targets = known_codes if modelo is None else (modelo,)
    per_modelo_reports = []
    for target in targets:
        try:
            report = _bindings_report_for_target(target, year=year, period=period, as_of=resolved_as_of, deps=deps)
        except Exception:
            if modelo is not None:
                raise
            continue
        per_modelo_reports.append(report)
    merged_rows: list[BindingListRowPayload] = []
    text_rows: list[str] = []
    for report in per_modelo_reports:
        report_rows, report_text_rows = _binding_list_rows_for_report(report, missing=missing, as_of=resolved_as_of)
        merged_rows.extend(report_rows)
        text_rows.extend(report_text_rows)
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
    notices = _bindings_list_scope_notices(modelo=modelo, year=year, period=period)
    lines.extend(_notice_text_lines(notices))
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
    _require_binding_scope(modelo=modelo, year=year, period=period)
    assert modelo is not None
    assert year is not None
    assert period is not None
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
    entries = [_support_matrix_entry_payload(entry) for entry in report.entries]
    result = ModeloSupportMatrixResult(modelo_count=len(entries), entries=entries)
    lines = [
        f"{'modelo':>6}  {'revs':>4}  {'latest':<12}  {'calc':>4}  {'manifest':>8}  {'boe':>3}  {'xml':>3}  {'extractor':>9}  {'renames':>7}"
    ]
    for entry in entries:
        lines.append(
            f"{entry.modelo_id:>6}  {entry.revision_count:>4}  {entry.latest_revision_id:<12}  {_mark(entry.calc_grade):>4}  {_mark(entry.has_completeness_manifest):>8}  {_mark(entry.has_fixed_width_export):>3}  {_mark(entry.has_xml_dictionary_export):>3}  {_mark(entry.has_extractor):>9}  {len(entry.renames):>7}"
        )
    emit_envelope(ctx, command="modelo.support_matrix", result=result, lines=lines)
