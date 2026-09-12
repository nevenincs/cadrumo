# ruff: noqa: E501 - localized guidance and tabular wire lines are atomic
"""Payload and text projections for modelo registry discovery commands."""

from __future__ import annotations

from datetime import date

from ...application.modelo.binding_readiness import profile_resolvable_binding_ids
from ...application.modelo.data_inventory import DataInventoryCasilla, DataInventoryChecklist
from ...application.modelo.work_create_policy import modelo_work_create_refusal_locale_key
from ...application.operator_actions.models import ActionReference
from ...application.state_projection import CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS
from ...core.bucket_pointer import resolve_active_bucket_id
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity, ResolvedActionArgument
from ...core.operator_action_enums import ActionArgumentSource, ActionArgumentStatus
from ...core.type_guards import is_object_collection
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.query_reports import (
    ModeloBindingQueryRow,
    ModeloBindingsReport,
    ModeloCasillasReport,
    ModeloFormulasReport,
    ModeloListRow,
)
from ...domain.calculations.registry.support_matrix import ModeloEntry
from ...domain.user_profile.errors import ProfileNotFoundError
from ._modelo_bindings_payloads import BindingListRowPayload
from ._modelo_payloads import (
    CasillaRowPayload,
    DataInventoryCasillaPayload,
)
from ._modelo_rendering import binding_encoded_option_lines, binding_encoded_option_payloads
from ._modelo_support_matrix_payloads import (
    ModeloPortalCompatibilityRefPayload,
    ModeloRenamePayload,
    ModeloSupportMatrixEntryPayload,
)
from .common import resolve_notice_action
from .modelo_aux_payloads import ModeloRowPayload


def data_inventory_casilla_payload(entry: DataInventoryCasilla) -> DataInventoryCasillaPayload:
    return DataInventoryCasillaPayload(
        casilla_id=entry.casilla_id,
        number=entry.number,
        label=entry.label,
        legal_refs=entry.legal_refs,
        source_refs=entry.source_refs,
        binding_id=entry.binding_id,
        binding_source=entry.binding_source,
    )


def data_inventory_section_lines(title: str, rows: tuple[DataInventoryCasilla, ...]) -> list[str]:
    if not rows:
        return [f"{title}\t(none)"]
    lines = [f"{title}\t{len(rows)}"]
    for entry in rows:
        label = entry.label
        suffix = f"\t({entry.binding_source})" if entry.binding_source else ""
        lines.append(f"  {entry.number}\t{label}{suffix}")
    return lines


def requires_notices(checklist: DataInventoryChecklist) -> tuple[Notice, ...]:
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


def _relation_input_guidance_lines(rows: tuple[ModeloBindingQueryRow, ...]) -> tuple[str, ...]:
    """Registry-derived ``--relation`` guidance for relation-fed bindings.

    Every binding whose value is materialised by one or more registry
    relations (``relation_inputs`` is non-empty) is supplied through
    ``--relation RELATION_ID=VALUE`` rather than ``--binding``. The feeding
    relation ids come from the resolved revision (each
    the relation-prefill provider declares
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
        )
    ]
    for row in relation_fed:
        for relation_id in row.relation_inputs:
            lines.append(
                "relation_input\t"
                + tr(
                    "cli.app.modelo.bindings.relation_input_channel",
                    binding_id=str(row.binding_id),
                    relation_id=str(relation_id),
                )
            )
    return tuple(lines)


def _profile_resolved_binding_ids(report: ModeloBindingsReport, *, as_of: date | None) -> frozenset[str]:
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
    if not is_object_collection(value):
        raise TypeError("binding-id projection must be a collection")
    values: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise TypeError("binding-id projection must contain text")
        values.add(item)
    return frozenset(values)


def _binding_list_rows_for_report(
    report: ModeloBindingsReport, *, missing: bool, as_of: date | None
) -> tuple[list[BindingListRowPayload], list[str]]:
    rows = report.rows
    if missing:
        profile_resolved = _profile_resolved_binding_ids(report, as_of=as_of)
        rows = tuple(row for row in rows if row.binding_id not in profile_resolved and row.operator_input_required)
    merged_rows: list[BindingListRowPayload] = []
    text_rows: list[str] = []
    for row in rows:
        readiness = tr(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[row.provider.kind])
        encoded_options = binding_encoded_option_payloads(row.encoded_options)
        merged_rows.append(
            BindingListRowPayload(
                modelo=report.code,
                revision=report.revision,
                filing_year=report.filing_year,
                period=report.period,
                binding_id=row.binding_id,
                source=row.provider.kind,
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
            f"{report.code}\t{report.revision}\t{report.period or '-'}\t{row.binding_id}\t{row.provider.kind}\t{readiness}\t{row.typed_enum or '-'}\t{row.input_channel}\t{row.borrador_capable}"
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


def bindings_list_scope_notices(*, modelo: str | None, year: int | None, period: str | None) -> tuple[Notice, ...]:
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


def notice_text_lines(notices: tuple[Notice, ...]) -> list[str]:
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


def formula_lines(report: ModeloFormulasReport, *, explain: bool) -> list[str]:
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


def mark(value: bool) -> str:
    return "Y" if value else "-"


def support_matrix_entry_payload(entry: ModeloEntry) -> ModeloSupportMatrixEntryPayload:
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


def modelo_row_payload(row: ModeloListRow) -> ModeloRowPayload:
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


def casilla_row_payloads(report: ModeloCasillasReport) -> list[CasillaRowPayload]:
    return [
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
    ]


def casillas_lines(report: ModeloCasillasReport, *, explain: bool) -> list[str]:
    if explain:
        return [
            "casilla_id\tnumber\tinput\trequired\tlabel\thelp\tlegal_refs\tsource_refs",
            *[
                f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t{str(row.required).lower()}\t{row.label}\t{row.help_text or '-'}\t{', '.join(row.legal_refs)}\t{', '.join(row.source_refs)}"
                for row in report.rows
            ],
        ]
    return [
        "casilla_id\tnumber\tinput\trequired\tlabel",
        *[
            f"{row.casilla_id}\t{row.number}\t{row.input_kind}\t{str(row.required).lower()}\t{row.label}"
            for row in report.rows
        ],
    ]


def binding_rows_for_reports(
    reports: list[ModeloBindingsReport], *, missing: bool, as_of: date | None
) -> tuple[list[BindingListRowPayload], list[str]]:
    merged_rows: list[BindingListRowPayload] = []
    text_rows: list[str] = []
    for report in reports:
        report_rows, report_text_rows = _binding_list_rows_for_report(report, missing=missing, as_of=as_of)
        merged_rows.extend(report_rows)
        text_rows.extend(report_text_rows)
    return merged_rows, text_rows
