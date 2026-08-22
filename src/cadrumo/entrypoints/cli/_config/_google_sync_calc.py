"""Google Sheets calculation sync commands for ``aeat config google``.

Google calc commands resolve a
:class:`RegistrySnapshot` before exporting
or pulling sheet rows against the live calculation schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from pydantic import TypeAdapter, ValidationError

from ....adapters.outbound.google import (
    CalcSheetsApplyResult,
    CalcSheetsExportPreview,
    GoogleAuthError,
    apply_export_plan,
    preview_export_plan,
    relation_edit_payload,
    resolve_active_profile,
)
from ....adapters.outbound.storage import (
    OutboundStorageError,
    build_google_credentials,
    resolve_drive_root_folder_id,
)
from ....adapters.persistence.profile.sync_runs import SyncRunRecordRepository
from ....application.storage.calc_sheets import (
    OperatorInputs,
    RelationValues,
    SheetExportPlan,
    TabName,
    build_export_plan,
    export_modelo_to_sheets,
)
from ....core import CasillaId, Period, validated_casilla_id
from ....core.config import load_settings
from ....core.decimal import coerce_decimal
from ....core.i18n import tr
from ....domain.calculations.registry import (
    BindingId,
    RegistrySnapshotError,
    RegistryValidationError,
    RelationId,
)
from ....domain.calculations.registry import bundled_authority as _bundled_authority
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from .._errors import CliRefusedBoundaryError
from ._execution_policies import (
    GOOGLE_CALCULATION_HANDOFF,
    GOOGLE_CALCULATION_READ,
    GOOGLE_CALCULATION_WRITE,
    declare_metadata_group,
)
from ._google_errors import _google_refusal
from ._google_payloads import (
    GoogleSyncCalcComputeCasillaPayload,
    GoogleSyncCalcComputeResult,
    GoogleSyncCalcExportResult,
    GoogleSyncCalcPullRelationEditPayload,
    GoogleSyncCalcPullResult,
    GoogleSyncCalcVerifyDivergencePayload,
    GoogleSyncCalcVerifyResult,
)

if TYPE_CHECKING:
    from ....adapters.outbound.google import (
        PullResult,
        RowSetEdit,
    )
    from ....domain.calculations.registry import RegistrySnapshot


calc_app = typer.Typer(
    name="calc",
    help=tr("cli.config.google.sync.calc.help"),
    no_args_is_help=True,
)

_ModeloArg = Annotated[str, typer.Option(..., "--modelo", help=tr("cli.config.google.sync.calc.export.modelo_help"))]
_PeriodArg = Annotated[str, typer.Option(..., "--period", help=tr("cli.config.google.sync.calc.export.period_help"))]
_YearArg = Annotated[
    int,
    typer.Option(..., "--year", help=tr("cli.config.google.sync.calc.export.year_help"), min=2000, max=2099),
]


def resolve_credentials_and_root(profile: str) -> tuple[object, str]:
    """Hydrate refreshable Google credentials + the configured Drive root."""
    settings = load_settings()
    credentials = build_google_credentials(profile=profile)
    root_folder_id = resolve_drive_root_folder_id(profile=profile, settings=settings)
    if not root_folder_id:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.root_folder_required",
        )
    return credentials, root_folder_id


def filing_period_or_refusal(*, modelo: str, period: str, year: int) -> Period:
    try:
        return Period.from_year_and_code(year, period)
    except ValueError as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.snapshot_failure",
            context={"modelo": modelo, "period": period, "year": year},
        ) from exc


def load_snapshot(modelo: str, period: Period) -> RegistrySnapshot:
    authority = _bundled_authority()
    if modelo not in {candidate.id for candidate in authority.modelos}:
        available = ", ".join(sorted(candidate.id for candidate in authority.modelos))
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.unknown_modelo",
            context={"modelo": modelo, "available": available},
        )
    try:
        return authority.snapshot(modelo, filing_year=period.filing_year, period=period.registry_token)
    except (RegistrySnapshotError, RegistryValidationError) as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.snapshot_failure",
            context={
                "modelo": modelo,
                "period": period.registry_token,
                "year": period.filing_year,
            },
        ) from exc


def _pull_operator_edits_for_command(
    *,
    modelo: str,
    period: str,
    year: int,
    spreadsheet_id: str,
) -> tuple[str, RegistrySnapshot, PullResult]:
    """Resolve the active profile, credentials, and snapshot, then pull operator edits.

    Shared by the ``pull`` and ``compute`` commands: each surface refuses on the
    same :class:`GoogleAuthError` / :class:`OutboundStorageError` boundaries with
    identical translated messages, so the resolution is one implementation.
    """
    from ....adapters.outbound.google import pull_operator_edits

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    try:
        credentials, _ = resolve_credentials_and_root(active)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    snapshot = load_snapshot(modelo, filing_period_or_refusal(modelo=modelo, period=period, year=year))

    try:
        result: PullResult = pull_operator_edits(
            snapshot,
            spreadsheet_id=spreadsheet_id,
            credentials=credentials,
        )
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    return active, snapshot, result


@calc_app.command("export", help=tr("cli.config.google.sync.calc.export_help"))
@command_execution_policy(GOOGLE_CALCULATION_HANDOFF)
def google_sync_calc_export(
    ctx: typer.Context,
    modelo: _ModeloArg,
    period: _PeriodArg,
    year: _YearArg,
    prefill_relations: bool = typer.Option(
        False,
        "--prefill-relations/--no-prefill-relations",
        help=tr("cli.config.google.sync.calc.export.prefill_relations_help"),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=tr("cli.config.google.sync.calc.export.dry_run_help"),
    ),
) -> None:
    """Export the registry calculation surface for a modelo + period to a Google Sheets workbook."""
    from ....application.calculations import resolve_relations_from_local_store
    from ....application.user_profile import resolve_active_capability
    from ....core import ServiceCapability

    if not resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.capability_disabled",
        )

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    try:
        credentials, root_folder_id = resolve_credentials_and_root(active)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    filing_period = filing_period_or_refusal(modelo=modelo, period=period, year=year)
    snapshot = load_snapshot(modelo, filing_period)
    if prefill_relations:
        plan = build_export_plan(
            snapshot,
            operator_inputs=OperatorInputs(),
            relation_resolver=resolve_relations_from_local_store,
        )
    else:
        plan = build_export_plan(
            snapshot,
            operator_inputs=OperatorInputs(),
            relation_values=RelationValues(),
        )

    if dry_run:
        _emit_calc_export_preview(
            ctx,
            active=active,
            snapshot=snapshot,
            plan=plan,
            credentials=credentials,
            root_folder_id=root_folder_id,
        )
        return

    try:
        result: CalcSheetsApplyResult = export_modelo_to_sheets(
            plan,
            credentials=credentials,
            root_folder_id=root_folder_id,
            sync_run_repository=SyncRunRecordRepository(),
            apply_export_plan=apply_export_plan,
        )
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    export_result = GoogleSyncCalcExportResult(
        profile=active,
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        period=snapshot.period,
        year=snapshot.filing_year,
        engine_version=plan.metadata.engine_version,
        registry_sha=plan.metadata.registry_sha,
        root_folder_id=root_folder_id,
        folder_id=result.folder_id,
        spreadsheet_id=result.spreadsheet_id,
        spreadsheet_url=result.spreadsheet_url,
        value_cells_written=result.value_cells_written,
        formula_cells_written=result.formula_cells_written,
        protected_ranges_written=result.protected_ranges_written,
        tab_count=result.tab_count,
    )
    _emit_envelope(
        ctx,
        command="config.google.sync.calc.export",
        result=export_result,
        lines=(
            "operation\tconfig.google.sync.calc.export",
            f"profile\t{active}",
            f"modelo\t{snapshot.modelo.id}",
            f"revision\t{snapshot.revision.id}",
            f"period\t{snapshot.period}",
            f"year\t{snapshot.filing_year}",
            f"engine_version\t{plan.metadata.engine_version}",
            f"registry_sha\t{plan.metadata.registry_sha}",
            f"folder_id\t{result.folder_id}",
            f"spreadsheet_id\t{result.spreadsheet_id}",
            f"spreadsheet_url\t{result.spreadsheet_url}",
            f"value_cells_written\t{result.value_cells_written}",
            f"formula_cells_written\t{result.formula_cells_written}",
            f"protected_ranges_written\t{result.protected_ranges_written}",
            f"tab_count\t{result.tab_count}",
        ),
    )


def _emit_calc_export_preview(
    ctx: typer.Context,
    *,
    active: str,
    snapshot: RegistrySnapshot,
    plan: SheetExportPlan,
    credentials: object,
    root_folder_id: str,
) -> None:
    """Preview an export and emit it, without ever calling ``apply_export_plan``.

    ``dry_run`` state is primary result data, never a notice: whether the
    preview found an existing target to diff against, what it would clear,
    and what would change ARE the output this branch exists to produce.
    """
    try:
        preview: CalcSheetsExportPreview = preview_export_plan(
            plan,
            credentials=credentials,
            root_folder_id=root_folder_id,
        )
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    export_result = GoogleSyncCalcExportResult(
        profile=active,
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        period=snapshot.period,
        year=snapshot.filing_year,
        engine_version=plan.metadata.engine_version,
        registry_sha=plan.metadata.registry_sha,
        root_folder_id=root_folder_id,
        dry_run=True,
        spreadsheet_exists=preview.spreadsheet_exists,
        folder_id=preview.folder_id,
        spreadsheet_id=preview.spreadsheet_id,
        spreadsheet_url=preview.spreadsheet_url,
        value_cells_written=len(plan.value_cells),
        formula_cells_written=len(plan.formula_cells),
        protected_ranges_written=len(plan.protected_ranges),
        tab_count=len(TabName),
        ranges_to_clear=list(preview.ranges_to_clear),
        value_cells_changed=preview.value_cells_changed,
        value_cells_unchanged=preview.value_cells_unchanged,
        formula_cells_to_write=preview.formula_cells_to_write,
    )
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.export",
        f"profile\t{active}",
        f"modelo\t{snapshot.modelo.id}",
        f"revision\t{snapshot.revision.id}",
        f"period\t{snapshot.period}",
        f"year\t{snapshot.filing_year}",
        "dry_run\tTrue",
        f"spreadsheet_exists\t{preview.spreadsheet_exists}",
        f"ranges_to_clear\t{len(preview.ranges_to_clear)}",
        f"value_cells_changed\t{preview.value_cells_changed}",
        f"value_cells_unchanged\t{preview.value_cells_unchanged}",
        f"formula_cells_to_write\t{preview.formula_cells_to_write}",
    ]
    for address in preview.ranges_to_clear:
        lines.append(f"range_to_clear\t{address}")
    _emit_envelope(ctx, command="config.google.sync.calc.export", result=export_result, lines=tuple(lines))


@calc_app.command("verify", help=tr("cli.config.google.sync.calc.verify_help"))
@command_execution_policy(GOOGLE_CALCULATION_READ)
def google_sync_calc_verify(
    ctx: typer.Context,
    modelo: _ModeloArg,
    period: _PeriodArg,
    year: _YearArg,
    scenario_path: Path | None = typer.Option(
        None,
        "--scenario",
        help=tr("cli.config.google.sync.calc.verify.scenario_help"),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
) -> None:
    """Run a three-way parity check across AEAT oracle, local Decimal runtime, and Sheets."""
    from decimal import Decimal

    from ....application.storage.calc_sheets import (
        OperatorInputScenario,
        verify_modelo_parity,
    )
    from ....application.user_profile import resolve_active_capability
    from ....core import ServiceCapability

    # `verify` creates a Drive spreadsheet and writes cells, so it is a Google
    # export egress and is gated on the same capability as `export`.
    if not resolve_active_capability(ServiceCapability.GOOGLE_EXPORT).enabled:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.capability_disabled",
        )

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    try:
        credentials, root_folder_id = resolve_credentials_and_root(active)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    snapshot = load_snapshot(modelo, filing_period_or_refusal(modelo=modelo, period=period, year=year))

    if scenario_path is None:
        scenario = OperatorInputScenario(scenario_label="empty-defaults")
    else:
        raw = json.loads(scenario_path.read_text(encoding="utf-8"))
        binding_id_adapter: TypeAdapter[str] = TypeAdapter(BindingId)
        relation_id_adapter: TypeAdapter[str] = TypeAdapter(RelationId)

        def _decimal_value(value: object) -> Decimal:
            return coerce_decimal(value) or Decimal("0")

        def _binding_id(value: object) -> BindingId:
            try:
                return binding_id_adapter.validate_python(value)
            except ValidationError as exc:
                raise RegistryValidationError(f"scenario binding key must be canonical: {value!r}") from exc

        def _relation_id(value: object) -> RelationId:
            try:
                return relation_id_adapter.validate_python(value)
            except ValidationError as exc:
                raise RegistryValidationError(f"scenario relation key must be canonical: {value!r}") from exc

        def _to_casilla_decimal_map(node: object) -> dict[CasillaId, Decimal]:
            if not isinstance(node, dict):
                return {}
            return {
                validated_casilla_id(k, surface="google sync calc scenario casilla.id"): _decimal_value(v)
                for k, v in node.items()
            }

        def _to_binding_decimal_map(node: object) -> dict[BindingId, Decimal]:
            if not isinstance(node, dict):
                return {}
            return {_binding_id(k): _decimal_value(v) for k, v in node.items()}

        def _to_enum_binding_map(node: object) -> dict[BindingId, str]:
            if not isinstance(node, dict):
                return {}
            return {_binding_id(k): str(v) for k, v in node.items()}

        def _to_relation_decimal_map(node: object) -> dict[RelationId, Decimal]:
            if not isinstance(node, dict):
                return {}
            return {_relation_id(k): _decimal_value(v) for k, v in node.items()}

        scenario = OperatorInputScenario(
            inputs_by_casilla_id=_to_casilla_decimal_map(raw.get("inputs_by_casilla_id")),
            bindings=_to_binding_decimal_map(raw.get("bindings")),
            enum_bindings=_to_enum_binding_map(raw.get("enum_bindings")),
            relation_values=_to_relation_decimal_map(raw.get("relation_values")),
            expected_by_casilla_id=_to_casilla_decimal_map(raw.get("expected_by_casilla_id")),
            scenario_label=str(raw.get("scenario_label") or scenario_path.stem),
        )

    report = verify_modelo_parity(snapshot, scenario, credentials=credentials, root_folder_id=root_folder_id)

    verify_result = GoogleSyncCalcVerifyResult(
        profile=active,
        modelo=report.modelo_id,
        revision=report.revision_id,
        period=report.period.registry_token,
        year=report.filing_year,
        spreadsheet_id=report.spreadsheet_id,
        spreadsheet_url=report.spreadsheet_url,
        verdict=report.verdict,
        aeat_oracle_present=report.aeat_oracle_present,
        computed_count=len(report.casillas),
        divergence_count=len(report.divergences),
        divergences=[
            GoogleSyncCalcVerifyDivergencePayload(
                casilla_id=c.casilla_id,
                label=c.label,
                local=str(c.local) if c.local is not None else None,
                sheets=str(c.sheets) if c.sheets is not None else None,
                aeat=str(c.aeat) if c.aeat is not None else None,
            )
            for c in report.divergences
        ],
    )
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.verify",
        f"profile\t{active}",
        f"modelo\t{report.modelo_id}",
        f"revision\t{report.revision_id}",
        f"period\t{report.period}",
        f"year\t{report.filing_year}",
        f"spreadsheet_url\t{report.spreadsheet_url}",
        f"verdict\t{report.verdict}",
        f"aeat_oracle_present\t{report.aeat_oracle_present}",
        f"computed_count\t{len(report.casillas)}",
        f"divergence_count\t{len(report.divergences)}",
    ]
    for div in report.divergences:
        lines.append(f"divergence\t{div.casilla_id}\tlocal={div.local}\tsheets={div.sheets}\taeat={div.aeat}")
    _emit_envelope(ctx, command="config.google.sync.calc.verify", result=verify_result, lines=tuple(lines))


@calc_app.command("pull", help=tr("cli.config.google.sync.calc.pull_help"))
@command_execution_policy(GOOGLE_CALCULATION_WRITE)
def google_sync_calc_pull(
    ctx: typer.Context,
    modelo: _ModeloArg,
    period: _PeriodArg,
    year: _YearArg,
    spreadsheet_id: str = typer.Option(
        ...,
        "--spreadsheet-id",
        help=tr("cli.config.google.sync.calc.pull.spreadsheet_id_help"),
        min=1,
    ),
    assemble_observations: bool = typer.Option(
        False,
        "--assemble-observations/--no-assemble-observations",
        help=tr("cli.config.google.sync.calc.pull.assemble_observations_help"),
    ),
) -> None:
    """Read operator-edited cells back from a workbook into typed records."""
    active, snapshot, result = _pull_operator_edits_for_command(
        modelo=modelo,
        period=period,
        year=year,
        spreadsheet_id=spreadsheet_id,
    )

    populated_operator = [e for e in result.operator_edits if e.value is not None]
    populated_bindings = [e for e in result.binding_edits if e.value is not None]
    populated_relations = [e for e in result.relation_edits if e.value is not None]
    populated_row_sets = [rs for rs in result.row_set_edits if rs.cells]
    row_set_cells_total = sum(len(rs.cells) for rs in populated_row_sets)

    assembled_groupings, assembled_observation_count = _assemble_pull_observations(
        populated_row_sets=populated_row_sets,
        snapshot=snapshot,
        enabled=assemble_observations,
    )

    payload: dict[str, object] = {
        "operation": "config.google.sync.calc.pull",
        "profile": active,
        "modelo": snapshot.modelo.id,
        "revision": snapshot.revision.id,
        "period": snapshot.period,
        "year": snapshot.filing_year,
        "spreadsheet_id": result.spreadsheet_id,
        "metadata_match": result.metadata_match,
        "metadata": {
            "modelo_id": result.metadata.modelo_id,
            "revision_id": result.metadata.revision_id,
            "filing_year": result.metadata.filing_year,
            "period": result.metadata.period,
            "engine_version": result.metadata.engine_version,
            "registry_sha": result.metadata.registry_sha,
            "exported_at": result.metadata.exported_at,
        },
        "cells_read": result.cells_read,
        "operator_edits_total": len(result.operator_edits),
        "operator_edits_populated": len(populated_operator),
        "binding_edits_populated": len(populated_bindings),
        "relation_edits_populated": len(populated_relations),
        "operator_edits": [
            {
                "casilla_id": e.casilla_id,
                "label": e.label,
                "value": str(e.value) if e.value is not None else None,
            }
            for e in populated_operator
        ],
        "binding_edits": [
            {"binding": e.binding, "value": str(e.value) if e.value is not None else None} for e in populated_bindings
        ],
        "relation_edits": [
            GoogleSyncCalcPullRelationEditPayload.model_validate(relation_edit_payload(e)) for e in populated_relations
        ],
        "row_set_edits_populated": len(populated_row_sets),
        "row_set_cells_populated": row_set_cells_total,
        "assembled_groupings": assembled_groupings,
        "assembled_observation_count": assembled_observation_count,
        "row_set_edits": [
            {
                "grouping": rs.grouping,
                "cells": [
                    {
                        "binding": c.binding,
                        "row_index": c.row_index,
                        "value": str(c.value) if c.value is not None else None,
                    }
                    for c in rs.cells
                ],
            }
            for rs in populated_row_sets
        ],
    }
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.pull",
        f"profile\t{active}",
        f"modelo\t{snapshot.modelo.id}",
        f"revision\t{snapshot.revision.id}",
        f"period\t{snapshot.period}",
        f"year\t{snapshot.filing_year}",
        f"spreadsheet_id\t{result.spreadsheet_id}",
        f"metadata_match\t{result.metadata_match}",
        f"metadata.modelo_id\t{result.metadata.modelo_id}",
        f"metadata.revision_id\t{result.metadata.revision_id}",
        f"metadata.registry_sha\t{result.metadata.registry_sha}",
        f"cells_read\t{result.cells_read}",
        f"operator_edits_populated\t{len(populated_operator)}",
        f"binding_edits_populated\t{len(populated_bindings)}",
        f"relation_edits_populated\t{len(populated_relations)}",
        f"row_set_edits_populated\t{len(populated_row_sets)}",
        f"row_set_cells_populated\t{row_set_cells_total}",
    ]
    for e in populated_operator:
        lines.append(f"casilla_id\t{e.casilla_id}\t{e.value}\t{e.label}")
    for e in populated_bindings:
        lines.append(f"binding\t{e.binding}\t{e.value}")
    for e in populated_relations:
        lines.append(f"relation\t{e.relation}\t{e.value}")
    for rs in populated_row_sets:
        for c in rs.cells:
            lines.append(f"row_set\t{rs.grouping}\t{c.row_index}\t{c.binding}\t{c.value}")
    for assembled in assembled_groupings:
        lines.append(
            f"assembled\t{assembled['grouping']}\t{assembled['source_kind']}\t{assembled['observation_count']}",
        )
    pull_result = GoogleSyncCalcPullResult.model_validate(payload)
    _emit_envelope(ctx, command="config.google.sync.calc.pull", result=pull_result, lines=tuple(lines))


@calc_app.command("compute", help=tr("cli.config.google.sync.calc.compute_help"))
@command_execution_policy(GOOGLE_CALCULATION_WRITE)
def google_sync_calc_compute(
    ctx: typer.Context,
    modelo: _ModeloArg,
    period: _PeriodArg,
    year: _YearArg,
    spreadsheet_id: str = typer.Option(
        ...,
        "--spreadsheet-id",
        help=tr("cli.config.google.sync.calc.compute.spreadsheet_id_help"),
        min=1,
    ),
) -> None:
    """Compute casilla values from a workbook's operator edits; persist nothing."""
    from ....adapters.outbound.google import compute_from_pull

    active, snapshot, result = _pull_operator_edits_for_command(
        modelo=modelo,
        period=period,
        year=year,
        spreadsheet_id=spreadsheet_id,
    )

    if result.metadata_match != "matches":
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.compute.refused_stale",
            context={"metadata_match": result.metadata_match},
        )

    try:
        calc = compute_from_pull(snapshot, result)
    except OutboundStorageError as exc:
        raise _google_refusal(exc) from exc

    computed_casilla_entries = [
        GoogleSyncCalcComputeCasillaPayload(
            casilla_id=entry.target_casilla_id,
            value=str(entry.value),
            formula_id=entry.formula_id,
            legal_refs=list(entry.legal_refs),
            source_refs=list(entry.source_refs),
        )
        for entry in calc.entries
    ]

    populated_operator = [e for e in result.operator_edits if e.value is not None]
    populated_bindings = [e for e in result.binding_edits if e.value is not None]
    populated_relations = [e for e in result.relation_edits if e.value is not None]

    compute_result = GoogleSyncCalcComputeResult(
        profile=active,
        modelo=snapshot.modelo.id,
        revision=snapshot.revision.id,
        period=snapshot.period,
        year=snapshot.filing_year,
        spreadsheet_id=result.spreadsheet_id,
        metadata_match=result.metadata_match,
        cells_read=result.cells_read,
        operator_edits_populated=len(populated_operator),
        binding_edits_populated=len(populated_bindings),
        relation_edits_populated=len(populated_relations),
        computed=computed_casilla_entries,
    )
    lines: list[str] = [
        "operation\tconfig.google.sync.calc.compute",
        f"profile\t{active}",
        f"modelo\t{snapshot.modelo.id}",
        f"revision\t{snapshot.revision.id}",
        f"period\t{snapshot.period}",
        f"year\t{snapshot.filing_year}",
        f"spreadsheet_id\t{result.spreadsheet_id}",
        f"metadata_match\t{result.metadata_match}",
        f"cells_read\t{result.cells_read}",
        f"operator_edits_populated\t{len(populated_operator)}",
        f"binding_edits_populated\t{len(populated_bindings)}",
        f"relation_edits_populated\t{len(populated_relations)}",
    ]
    for entry in computed_casilla_entries:
        lines.append(f"computed\t{entry.casilla_id}\t{entry.value}\t{entry.formula_id}")
    _emit_envelope(ctx, command="config.google.sync.calc.compute", result=compute_result, lines=tuple(lines))


def _assemble_pull_observations(
    *,
    populated_row_sets: list[RowSetEdit],
    snapshot: RegistrySnapshot,
    enabled: bool,
) -> tuple[list[dict[str, object]], int]:
    """Per-grouping assemble-observations fan-out for the pull command."""
    if not enabled:
        return [], 0
    from ....application.calculations import assemble_observations_for_grouping

    groupings: list[dict[str, object]] = []
    total = 0
    for row_set in populated_row_sets:
        try:
            source_kind, observations = assemble_observations_for_grouping(
                row_set.grouping,
                row_set.cells,
                snapshot.revision,
                filing_year=snapshot.filing_year,
            )
        except OutboundStorageError as exc:
            raise _google_refusal(exc) from exc
        total += len(observations)
        groupings.append(
            {
                "grouping": row_set.grouping,
                "source_kind": source_kind,
                "observation_count": len(observations),
                "observations": [obs.model_dump(mode="json") for obs in observations],
            },
        )
    return groupings, total


def register_google_sync_calc_commands(sync_app: typer.Typer) -> None:
    """Register the Google Sheets calculation sync subgroup."""
    sync_app.add_typer(calc_app, name="calc")


declare_metadata_group(calc_app)

__all__ = [
    "calc_app",
    "google_sync_calc_compute",
    "google_sync_calc_export",
    "google_sync_calc_pull",
    "google_sync_calc_verify",
    "register_google_sync_calc_commands",
]
