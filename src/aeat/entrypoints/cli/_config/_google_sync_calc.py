"""Google Sheets calculation sync commands for ``aeat config google``.

Use of :class:`RegistrySnapshot` for compliance.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from ....adapters.outbound.google import GoogleAuthError
from ....adapters.outbound.google._calc_sheets_apply import (
    CalcSheetsApplyResult,
    apply_export_plan,
)
from ....adapters.outbound.google._profile_binding import resolve_active_profile
from ....adapters.outbound.storage import OutboundStorageError
from ....adapters.outbound.storage._factory import (
    _build_google_credentials,
    _resolve_drive_root_folder_id,
)
from ....application.storage.calc_sheets import (
    OperatorInputs,
    RelationValues,
    build_export_plan,
)
from ....core.config import load_settings
from ....core.decimal import coerce_decimal
from ....core.i18n import tr
from ....domain.calculations.registry import (
    RegistrySnapshotError,
    RegistryValidationError,
)
from ....domain.calculations.registry import bundled_authority as _bundled_authority
from .._common import _emit_envelope
from .._errors import CliRefusedBoundaryError
from ._google_errors import _google_refusal
from ._google_payloads import (
    GoogleSyncCalcExportResult,
    GoogleSyncCalcPullResult,
    GoogleSyncCalcVerifyDivergencePayload,
    GoogleSyncCalcVerifyResult,
)

if TYPE_CHECKING:
    from ....adapters.outbound.google._calc_sheets_pull import PullResult, RowSetEdit
    from ....domain.calculations.registry import (
        RegistryCalculationResult,
        RegistrySnapshot,
    )


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


def _resolve_credentials_and_root(profile: str) -> tuple[object, str]:
    """Hydrate refreshable Google credentials + the configured Drive root."""
    settings = load_settings()
    credentials = _build_google_credentials(profile=profile)
    root_folder_id = _resolve_drive_root_folder_id(profile=profile, settings=settings)
    if not root_folder_id:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.root_folder_required",
        )
    return credentials, root_folder_id


def _load_snapshot(modelo: str, period: str, year: int):
    authority = _bundled_authority()
    if modelo not in {candidate.id for candidate in authority.modelos}:
        available = ", ".join(sorted(candidate.id for candidate in authority.modelos))
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.unknown_modelo",
            context={"modelo": modelo, "available": available},
        )
    try:
        return authority.snapshot(modelo, filing_year=year, period=period)
    except (RegistrySnapshotError, RegistryValidationError) as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.export.snapshot_failure",
            context={"modelo": modelo, "period": period, "year": year, "detail": str(exc)},
        ) from exc


@calc_app.command("export", help=tr("cli.config.google.sync.calc.export_help"))
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
) -> None:
    """Export the registry calculation surface for a modelo + period to a Google Sheets workbook."""
    from ....application.calculations import resolve_relations_from_local_store

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    try:
        credentials, root_folder_id = _resolve_credentials_and_root(active)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    snapshot = _load_snapshot(modelo, period, year)
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

    try:
        result: CalcSheetsApplyResult = apply_export_plan(
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


@calc_app.command("verify", help=tr("cli.config.google.sync.calc.verify_help"))
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

    from ....application.storage.calc_sheets._parity_harness import (
        OperatorInputScenario,
        verify_modelo_parity,
    )

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    try:
        credentials, root_folder_id = _resolve_credentials_and_root(active)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    snapshot = _load_snapshot(modelo, period, year)

    if scenario_path is None:
        scenario = OperatorInputScenario(scenario_label="empty-defaults")
    else:
        raw = json.loads(scenario_path.read_text(encoding="utf-8"))

        def _to_decimal_map(node: object) -> dict[str, Decimal]:
            if not isinstance(node, dict):
                return {}
            return {str(k): coerce_decimal(v) or Decimal("0") for k, v in node.items()}

        scenario = OperatorInputScenario(
            inputs_by_number=_to_decimal_map(raw.get("inputs_by_number")),
            bindings=_to_decimal_map(raw.get("bindings")),
            enum_bindings={str(k): str(v) for k, v in (raw.get("enum_bindings") or {}).items()},
            relation_values=_to_decimal_map(raw.get("relation_values")),
            expected_by_number=_to_decimal_map(raw.get("expected_by_number")),
            scenario_label=str(raw.get("scenario_label") or scenario_path.stem),
        )

    report = verify_modelo_parity(snapshot, scenario, credentials=credentials, root_folder_id=root_folder_id)

    verify_result = GoogleSyncCalcVerifyResult(
        profile=active,
        modelo=report.modelo_id,
        revision=report.revision_id,
        period=report.period,
        year=report.filing_year,
        spreadsheet_id=report.spreadsheet_id,
        spreadsheet_url=report.spreadsheet_url,
        verdict=report.verdict,
        aeat_oracle_present=report.aeat_oracle_present,
        computed_count=len(report.casillas),
        divergence_count=len(report.divergences),
        divergences=[
            GoogleSyncCalcVerifyDivergencePayload(
                casilla=c.casilla_number,
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
        lines.append(f"divergence\t{div.casilla_number}\tlocal={div.local}\tsheets={div.sheets}\taeat={div.aeat}")
    _emit_envelope(ctx, command="config.google.sync.calc.verify", result=verify_result, lines=tuple(lines))


@calc_app.command("pull", help=tr("cli.config.google.sync.calc.pull_help"))
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
    compute: bool = typer.Option(
        False,
        "--compute/--no-compute",
        help=tr("cli.config.google.sync.calc.pull.compute_help"),
    ),
    assemble_observations: bool = typer.Option(
        False,
        "--assemble-observations/--no-assemble-observations",
        help=tr("cli.config.google.sync.calc.pull.assemble_observations_help"),
    ),
) -> None:
    """Read operator-edited cells back from a workbook into typed records."""
    from ....adapters.outbound.google._calc_sheets_pull import (
        compute_from_pull,
        pull_operator_edits,
    )

    try:
        active = resolve_active_profile()
    except GoogleAuthError as exc:
        raise _google_refusal(exc) from exc

    try:
        credentials, _ = _resolve_credentials_and_root(active)
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

    snapshot = _load_snapshot(modelo, period, year)

    try:
        result: PullResult = pull_operator_edits(
            snapshot,
            spreadsheet_id=spreadsheet_id,
            credentials=credentials,
        )
    except (GoogleAuthError, OutboundStorageError) as exc:
        raise _google_refusal(exc) from exc

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

    computed_casillas = _compute_pull_casillas(
        snapshot=snapshot,
        result=result,
        enabled=compute,
        compute_from_pull=compute_from_pull,
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
                "casilla": e.casilla_number,
                "label": e.label,
                "value": str(e.value) if e.value is not None else None,
            }
            for e in populated_operator
        ],
        "binding_edits": [
            {"binding": e.binding, "value": str(e.value) if e.value is not None else None} for e in populated_bindings
        ],
        "relation_edits": [
            {"relation": e.relation, "value": str(e.value) if e.value is not None else None}
            for e in populated_relations
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
        "computed": computed_casillas,
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
        lines.append(f"casilla\t{e.casilla_number}\t{e.value}\t{e.label}")
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
    for entry in computed_casillas:
        lines.append(f"computed\t{entry['casilla_id']}\t{entry['value']}\t{entry['formula_id']}")
    pull_result = GoogleSyncCalcPullResult.model_validate(payload)
    _emit_envelope(ctx, command="config.google.sync.calc.pull", result=pull_result, lines=tuple(lines))


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


def _compute_pull_casillas(
    *,
    snapshot: RegistrySnapshot,
    result: PullResult,
    enabled: bool,
    compute_from_pull: Callable[[RegistrySnapshot, PullResult], RegistryCalculationResult],
) -> list[dict[str, object]]:
    """Compute casillas from the pulled edits, refusing stale workbook stamps."""
    if not enabled:
        return []
    if result.metadata_match != "matches":
        raise CliRefusedBoundaryError(
            translated_message="cli.config.google.sync.calc.pull.compute_refused_stale",
            context={"metadata_match": result.metadata_match},
        )
    try:
        calc = compute_from_pull(snapshot, result)
    except OutboundStorageError as exc:
        raise _google_refusal(exc) from exc
    return [
        {
            "casilla_id": entry.target,
            "value": str(entry.value),
            "formula_id": entry.formula_id,
            "legal_refs": list(entry.legal_refs),
            "source_refs": list(entry.source_refs),
        }
        for entry in calc.entries
    ]


def register_google_sync_calc_commands(sync_app: typer.Typer) -> None:
    """Register the Google Sheets calculation sync subgroup."""
    sync_app.add_typer(calc_app, name="calc")


__all__ = [
    "calc_app",
    "google_sync_calc_export",
    "google_sync_calc_pull",
    "google_sync_calc_verify",
    "register_google_sync_calc_commands",
]
