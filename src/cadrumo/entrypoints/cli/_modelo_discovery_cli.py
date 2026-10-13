"""Behavior handlers for modelo registry discovery commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID

import typer

from ...application import reference_catalogue as catalogue
from ...application.modelo.query_read_contracts import (
    ModeloBindingOverride,
    ModeloBindingRowV1,
    ModeloBindingsListRequest,
    ModeloBindingsResolveProjection,
    ModeloBindingsResolveRequest,
    ModeloRequiresRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...application.reference_catalogue import (
    CededAutonomicModeloError,
    DiscoveryScopeIncompleteError,
    ReferenceQueryError,
    refuse_ceded_autonomic_modelo,
)
from ...application.state_projection import CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS
from ...core.aggregation import BindingSourceKind
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language, tr
from ...core.period import Period
from ...core.tax_domain import TaxDomain
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.schema_input_kind import InputKind
from . import _modelo_discovery_rendering as discovery_rendering
from ._date_parsing import _parse_iso_date
from ._modelo_behavior_support import bare_period_error, resolve_year_period
from ._modelo_bindings_payloads import (
    BindingEncodedOptionPayload,
    BindingListRowPayload,
    BindingPreviewRowPayload,
    ModeloBindingsListResult,
    ModeloBindingsPreviewResult,
)
from ._modelo_cli_support import bad_parameter_from_error, parse_binding_override
from ._modelo_payloads import ModeloRequiresResult
from ._modelo_rendering import binding_encoded_option_lines
from .common import active_bucket_id_or_refuse, emit_envelope
from .errors import CliRefusedBoundaryError
from .runtime_modelo_query_read import (
    read_modelo_bindings_list,
    read_modelo_bindings_resolve,
    read_modelo_requires,
    to_data_inventory_checklist,
)
from .state_projection_support import authority_operation


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


def _as_of(raw: str | None) -> date | None:
    if raw is None:
        return None
    return _parse_iso_date(raw, label="--as-of")


def _command_error(error: ReferenceQueryError) -> Exception:
    """Render a reference read's coordinate refusal in the command line's own terms."""
    if isinstance(error, CededAutonomicModeloError):
        return CliRefusedBoundaryError(translated_message=error.locale_key, context={"modelo": error.modelo})
    if isinstance(error, DiscoveryScopeIncompleteError):
        return typer.BadParameter("--year requires --period")
    return typer.BadParameter(str(error))


def guard_ceded_autonomic_modelo(modelo: str) -> None:
    """Refuse a discovery lookup for a ceded autonomic modelo with a redirect.

    ITP-AJD (``600`` / ``620``) and ISD (``650`` / ``660``) are ceded autonomic
    taxes managed by each Comunidad Autónoma, not AEAT modelos in the
    calculation registry, so a bare registry lookup would surface a generic
    not-present error. This guard raises the instructive autonomic-redirect
    refusal instead, naming the ceded tax and its regional filing route, and is
    a no-op for every registry-backed or genuinely unknown code.
    """
    try:
        refuse_ceded_autonomic_modelo(modelo)
    except CededAutonomicModeloError as error:
        raise _command_error(error) from error


def _run_query[QueryResultT](
    call: Callable[[], QueryResultT],
    *,
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> QueryResultT:
    try:
        return call()
    except ReferenceQueryError as error:
        raise _command_error(error) from error
    except (ValueError, RegistrySnapshotError) as exc:
        raise bad_parameter_from_error(exc) from exc


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
    result = _run_query(
        lambda: catalogue.list_modelos(year=year, domain=domain, operation=authority_operation(ctx)),
        bad_parameter_from_error=deps.bad_parameter_from_error,
    )
    lines = [
        "code\ttitle\tcadence\tdomain\trevisions\tlocal_work\tlocal_work_guidance",
        *[
            f"{row.code}\t{row.title}\t{row.cadence}\t{row.tax_domain}\t"
            f"{row.revision_count}\t{row.local_work_status}\t{row.local_work_guidance or '-'}"
            for row in result.modelos
        ],
    ]
    emit_envelope(ctx, command="modelo.list", result=result, lines=lines)


def describe_modelo(
    ctx: typer.Context, modelo: str, year: int | None = None, period: str | None = None, as_of: str | None = None
) -> None:
    operation = authority_operation(ctx)
    try:
        result = catalogue.describe_modelo(modelo, year=year, period=period, as_of=_as_of(as_of), operation=operation)
    except ReferenceQueryError as error:
        raise _command_error(error) from error
    except (ValueError, RegistrySnapshotError, RegistryValidationError) as exc:
        message = str(exc)
        if period is not None and "period" in message.lower():
            raise typer.BadParameter(
                deps.bare_period_error(modelo, period, fallback=message, operation=operation)
            ) from exc
        raise typer.BadParameter(tr("cli.app.modelo.describe.period_error", message=message)) from exc
    lines = [
        f"{tr('cli.app.modelo.describe.label_modelo')}\t{result.code}",
        f"{tr('cli.app.modelo.describe.label_title')}\t{result.title}",
        f"{tr('cli.app.modelo.describe.label_official_name')}\t{result.official_name}",
        f"{tr('cli.app.modelo.describe.label_tax_domain')}\t{result.tax_domain}",
        f"{tr('cli.app.modelo.describe.label_cadence')}\t{result.cadence}",
        f"{tr('cli.app.modelo.describe.label_revision')}\t{result.revision}",
        f"{tr('cli.app.modelo.describe.label_revision_ids')}\t{', '.join(result.revision_ids)}",
        f"{tr('cli.app.modelo.describe.label_periods')}\t{', '.join(result.periods)}",
        f"{tr('cli.app.modelo.describe.label_casillas')}\t{result.casilla_count}",
        f"{tr('cli.app.modelo.describe.label_bindings')}\t{result.binding_count}",
        f"{tr('cli.app.modelo.describe.label_formulas')}\t{result.formula_count}",
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
    result = _run_query(
        lambda: catalogue.list_casillas(
            modelo,
            year=year,
            period=period,
            as_of=_as_of(as_of),
            input_kind=input_kind,
            required=required,
            form_number=form_number,
            casilla_number=casilla_number,
            operation=authority_operation(ctx),
        ),
        bad_parameter_from_error=deps.bad_parameter_from_error,
    )
    lines = discovery_rendering.casillas_lines(result, explain=explain)
    emit_envelope(ctx, command="modelo.casillas", result=result, lines=lines)


def casilla(
    ctx: typer.Context,
    modelo: str,
    casilla_id: str,
    year: int | None = None,
    period: str | None = None,
    as_of: str | None = None,
) -> None:
    result = _run_query(
        lambda: catalogue.describe_casilla(
            modelo,
            casilla_id,
            year=year,
            period=period,
            as_of=_as_of(as_of),
            operation=authority_operation(ctx),
        ),
        bad_parameter_from_error=deps.bad_parameter_from_error,
    )
    lines = [
        f"modelo\t{result.modelo}",
        f"revision\t{result.revision}",
        f"casilla_id\t{result.casilla_id}",
        f"number\t{result.number}",
        f"input_kind\t{result.input_kind}",
        f"required\t{str(result.required).lower()}",
        f"data_type\t{result.data_type}",
        f"label\t{result.label}",
        f"section\t{' > '.join(result.section)}",
        f"legal_refs\t{', '.join(result.legal_refs)}",
        f"source_refs\t{', '.join(result.source_refs)}",
        f"binding\t{result.binding or '-'}",
        f"formula_id\t{result.formula_id or '-'}",
    ]
    if result.help_text is not None and result.help_text:
        lines.append(f"help\t{result.help_text}")
    if result.formula_expression is not None:
        lines.append(f"formula_expression\t{result.formula_expression}")
    emit_envelope(ctx, command="modelo.casilla", result=result, lines=lines)


def requires(ctx: typer.Context, modelo: str, year: int, period: str) -> None:
    guard_ceded_autonomic_modelo(modelo)
    typed_period = deps.resolve_year_period(year, period, modelo=modelo)
    operation = authority_operation(ctx)
    projection = read_modelo_requires(
        ctx,
        ModeloRequiresRequest(
            profile_id=UUID(active_bucket_id_or_refuse()),
            modelo=modelo,
            period=PublicPeriod.from_period(typed_period),
            language=OutputLanguage(output_language()),
        ),
        expected_authority_generation=operation.generation.logical_generation,
    )
    checklist = to_data_inventory_checklist(projection)
    result = ModeloRequiresResult(
        authority_generation=projection.authority_generation,
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
        detail_row_fields=[
            discovery_rendering.data_inventory_casilla_payload(entry) for entry in checklist.detail_row_fields
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
        f"authority_generation\t{projection.authority_generation}",
        f"modelo\t{checklist.modelo}",
        f"revision\t{checklist.revision_id}",
        f"filing_year\t{checklist.filing_year}",
        f"period\t{checklist.period}",
        *discovery_rendering.data_inventory_section_lines(
            tr(
                "cli.app.modelo.requires.section_required",
            ),
            checklist.required_manual,
        ),
        *discovery_rendering.data_inventory_section_lines(
            tr(
                "cli.app.modelo.requires.section_optional",
            ),
            checklist.optional_manual,
        ),
        *discovery_rendering.data_inventory_section_lines("detail_row_fields", checklist.detail_row_fields),
        *discovery_rendering.data_inventory_section_lines(
            tr(
                "cli.app.modelo.requires.section_ledger",
            ),
            checklist.ledger_derivable,
        ),
        *discovery_rendering.data_inventory_section_lines(
            tr(
                "cli.app.modelo.requires.section_profile",
            ),
            checklist.profile_derivable,
        ),
        *discovery_rendering.data_inventory_section_lines("previous_filing", checklist.previous_filing),
        *discovery_rendering.data_inventory_section_lines("relation_prefill", checklist.relation_prefill),
        *discovery_rendering.data_inventory_section_lines("live_observation", checklist.live_observation),
        *discovery_rendering.data_inventory_section_lines("unbucketed_sources", checklist.unbucketed_sources),
    ]
    notices = discovery_rendering.requires_notices(checklist, operation=operation)
    lines.extend(discovery_rendering.notice_text_lines(notices))
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
    profile_id = UUID(active_bucket_id_or_refuse())
    request = ModeloBindingsListRequest(
        profile_id=profile_id,
        modelo=modelo,
        year=year,
        period_code=period,
        missing=missing,
        as_of=resolved_as_of,
    )
    operation = authority_operation(ctx)
    try:
        projection = read_modelo_bindings_list(
            ctx, request, expected_authority_generation=operation.generation.logical_generation
        )
    except CliRefusedBoundaryError as error:
        if (
            modelo is None
            or error.context is None
            or error.context.get("reason") != "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
        ):
            raise
        _translate_unknown_binding_modelo(ctx, profile_id, modelo, operation, error)
        raise
    merged_rows: list[BindingListRowPayload] = []
    text_rows: list[str] = []
    for row in projection.bindings:
        _append_binding_list_row(row, merged_rows, text_rows)
    if missing:
        text_rows.extend(discovery_rendering.binding_relation_guidance_lines(projection.bindings))
    result = ModeloBindingsListResult(
        authority_generation=projection.authority_generation,
        modelo_filter=modelo,
        year_filter=year,
        period_filter=period,
        missing_filter=missing,
        binding_count=len(merged_rows),
        bindings=tuple(merged_rows),
    )
    lines = [
        "operation\tregistry.modelo.bindings.list",
        f"authority_generation\t{projection.authority_generation}",
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
    profile_id = UUID(active_bucket_id_or_refuse())
    resolved_as_of = _as_of(as_of)
    request = ModeloBindingsResolveRequest(
        profile_id=profile_id,
        modelo=modelo,
        period=PublicPeriod.from_period(typed_period),
        as_of=resolved_as_of,
        overrides=tuple(ModeloBindingOverride(binding_id=key, value=value) for key, value in overrides.items()),
    )
    operation = authority_operation(ctx)
    try:
        report = read_modelo_bindings_resolve(
            ctx, request, expected_authority_generation=operation.generation.logical_generation
        )
    except CliRefusedBoundaryError as error:
        if (
            not overrides
            or error.context is None
            or error.context.get("reason") != "ERROR_CALCULATIONS_REGISTRY_VALIDATION"
        ):
            raise
        _translate_unknown_binding_overrides(
            ctx, profile_id, modelo, year, period, resolved_as_of, overrides, operation, error
        )
        raise
    result = ModeloBindingsPreviewResult(
        authority_generation=report.authority_generation,
        modelo=report.modelo,
        revision=report.revision,
        filing_year=report.filing_year,
        period=report.period,
        override_count=report.override_count,
        binding_count=report.binding_count,
        bindings=_binding_preview_rows(report),
    )
    lines = [
        "operation\tregistry.modelo.bindings.resolve",
        f"authority_generation\t{report.authority_generation}",
        f"modelo\t{report.modelo}",
        f"revision\t{report.revision}",
        f"filing_year\t{report.filing_year}",
        f"period\t{report.period}",
        f"override_count\t{report.override_count}",
        f"binding_count\t{report.binding_count}",
        "binding_id\tsource\treadiness\toverride",
    ]
    for row in report.bindings:
        _append_binding_preview_text(row, lines)
    emit_envelope(ctx, command="modelo.bindings.resolve", result=result, lines=lines)


def formulas(
    ctx: typer.Context,
    modelo: str,
    year: int | None = None,
    period: str | None = None,
    as_of: str | None = None,
    explain: bool = False,
) -> None:
    result = _run_query(
        lambda: catalogue.list_formulas(
            modelo, year=year, period=period, as_of=_as_of(as_of), operation=authority_operation(ctx)
        ),
        bad_parameter_from_error=deps.bad_parameter_from_error,
    )
    lines = discovery_rendering.formula_lines(result, explain=explain)
    emit_envelope(ctx, command="modelo.formulas", result=result, lines=lines)


def support_matrix(ctx: typer.Context) -> None:
    result = catalogue.read_support_matrix(operation=authority_operation(ctx))
    lines = [
        f"{'modelo':>6}  {'revs':>4}  {'latest':<12}  {'calc':>4}  {'manifest':>8}  "
        f"{'boe':>3}  {'xml':>3}  {'extractor':>9}  {'renames':>7}"
    ]
    for entry in result.entries:
        lines.append(
            f"{entry.modelo_id:>6}  {entry.revision_count:>4}  {entry.latest_revision_id:<12}  "
            f"{discovery_rendering.mark(entry.calc_grade):>4}  "
            f"{discovery_rendering.mark(entry.has_completeness_manifest):>8}  "
            f"{discovery_rendering.mark(entry.has_fixed_width_export):>3}  "
            f"{discovery_rendering.mark(entry.has_xml_dictionary_export):>3}  "
            f"{discovery_rendering.mark(entry.has_extractor):>9}  {len(entry.renames):>7}"
        )
    emit_envelope(ctx, command="modelo.support_matrix", result=result, lines=lines)


def _append_binding_list_row(
    row: ModeloBindingRowV1, merged_rows: list[BindingListRowPayload], text_rows: list[str]
) -> None:
    """Append one grounded row and its encoded-option text in registry order."""
    readiness = tr(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[BindingSourceKind(row.source)])
    encoded_options = tuple(
        BindingEncodedOptionPayload.model_validate(item.model_dump()) for item in row.encoded_options
    )
    merged_rows.append(
        BindingListRowPayload(
            modelo=row.modelo,
            revision=row.revision,
            filing_year=row.filing_year,
            period=row.period,
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
        f"{row.modelo}\t{row.revision}\t{row.period or '-'}\t{row.binding_id}\t"
        f"{row.source}\t{readiness}\t{row.typed_enum or '-'}\t{row.input_channel}\t"
        f"{row.borrador_capable}"
    )
    text_rows.extend(binding_encoded_option_lines(row.binding_id, encoded_options))


def _translate_unknown_binding_modelo(
    ctx: typer.Context,
    profile_id: UUID,
    modelo: str,
    operation: PinnedAuthorityOperation,
    error: CliRefusedBoundaryError,
) -> None:
    """Translate an unknown model only after the registered catalogue confirms it."""
    try:
        catalogue = read_modelo_bindings_list(
            ctx,
            ModeloBindingsListRequest(profile_id=profile_id, catalogue_only=True),
            expected_authority_generation=operation.generation.logical_generation,
        )
    except CliRefusedBoundaryError:
        raise error from None
    if modelo not in catalogue.known_modelos:
        raise typer.BadParameter(
            f"modelo {modelo!r} is not in the calculation registry. Accepted: {', '.join(catalogue.known_modelos)}."
        ) from error


def _translate_unknown_binding_overrides(
    ctx: typer.Context,
    profile_id: UUID,
    modelo: str,
    year: int,
    period: str,
    resolved_as_of: date | None,
    overrides: dict[str, str],
    operation: PinnedAuthorityOperation,
    error: CliRefusedBoundaryError,
) -> None:
    """Translate unknown override keys against the same pinned registry scope."""
    try:
        listing = read_modelo_bindings_list(
            ctx,
            ModeloBindingsListRequest(
                profile_id=profile_id,
                modelo=modelo,
                year=year,
                period_code=period,
                as_of=resolved_as_of,
            ),
            expected_authority_generation=operation.generation.logical_generation,
        )
    except CliRefusedBoundaryError:
        raise error from None
    known_ids = {row.binding_id for row in listing.bindings}
    unknown_keys = sorted(set(overrides) - known_ids)
    if unknown_keys:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.bindings.unknown_keys",
                keys=unknown_keys,
                code=modelo,
                revision=listing.bindings[0].revision if listing.bindings else "",
                period=period,
                suggestion=", ".join(sorted(known_ids)),
            )
        ) from error


def _binding_preview_rows(report: ModeloBindingsResolveProjection) -> list[BindingPreviewRowPayload]:
    """Project every grounded preview row without changing its order or options."""
    return [
        BindingPreviewRowPayload(
            binding_id=row.binding_id,
            source=row.source,
            readiness=tr(
                CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[BindingSourceKind(row.source)]
            ),
            typed_enum=row.typed_enum,
            override=row.override,
            legal_refs=row.legal_refs,
            source_refs=row.source_refs,
            relation_inputs=row.relation_inputs,
            encoded_options=tuple(
                BindingEncodedOptionPayload.model_validate(option.model_dump()) for option in row.encoded_options
            ),
        )
        for row in report.bindings
    ]


def _append_binding_preview_text(row: ModeloBindingRowV1, lines: list[str]) -> None:
    """Append the established readiness, override, and encoded-option rows."""
    readiness = tr(CLAVES_LOCALE_DISPONIBILIDAD_POR_ORIGEN_VINCULACION_LOCALE_KEYS[BindingSourceKind(row.source)])
    lines.append(
        "\t".join(
            (
                row.binding_id,
                row.source,
                readiness,
                row.override or "-",
            )
        )
    )
    lines.extend(
        binding_encoded_option_lines(
            row.binding_id,
            tuple(BindingEncodedOptionPayload.model_validate(option.model_dump()) for option in row.encoded_options),
        )
    )
