"""Behavior for modelo work :class:`CalculationRevision` read commands.

The graph-declared commands list stored calculation revisions, show one persisted
revision, and render its typed casilla observations without mutating modelo
state. Selection stays in the injected application-facing resolvers; this
transport module serializes results into
:class:`WorkRevisionsResult`,
:class:`WorkRevisionResult`,
and
:class:`WorkObservationsResult`
schemas before handing them to
:func:`emit_envelope`.
"""

from __future__ import annotations

from collections.abc import Sequence

import typer

from ...application.modelo.revision_inventory_operation import ModeloRevisionInventoryRow
from ...application.modelo.selectors import ModeloCalculationRevisionSelector
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as current_output_language
from ._modelo_cli_support import parse_revision_selector
from ._modelo_payloads import (
    CalculationRevisionSummaryPayload,
    WorkRevisionsResult,
)
from ._modelo_rendering import (
    short_id,
)
from ._modelo_work_revision_payloads import WorkObservationsResult, WorkRevisionResult
from .common import activate_subcommand_output_language, emit_envelope
from .modelo_revision_rendering import calculation_observation_payload_lines
from .runtime_modelo_calculation import calculation_snapshot_lines, calculation_snapshot_payload
from .runtime_modelo_revision import read_modelo_revision_inventory_for_cli, read_modelo_revision_snapshot_for_cli


def _revision_summary_payloads(
    revisions: Sequence[ModeloRevisionInventoryRow],
) -> list[CalculationRevisionSummaryPayload]:
    """Project persisted revisions into compact discovery rows."""
    return [
        CalculationRevisionSummaryPayload(
            short_calculation_revision_id=short_id(revision.calculation_revision_id) or "",
            calculation_revision_id=revision.calculation_revision_id,
            short_work_unit_id=short_id(revision.work_unit_id) or "",
            work_unit_id=revision.work_unit_id,
            state=revision.state,
            created_at=revision.created_at.isoformat(),
        )
        for revision in revisions
    ]


def _work_revisions_result(
    resolved_work_unit_id: str | None,
    revisions: Sequence[ModeloRevisionInventoryRow],
) -> WorkRevisionsResult:
    """Build the typed listing payload without recomputing revision facts."""
    return WorkRevisionsResult.model_validate(
        {
            "work_unit_id_filter": resolved_work_unit_id,
            "revision_count": len(revisions),
            "revisions": _revision_summary_payloads(revisions),
        }
    )


def _work_revision_listing_lines(
    revisions: Sequence[ModeloRevisionInventoryRow],
) -> list[str]:
    """Render revision discovery rows in the application-provided order."""
    return [
        "\t".join(
            (
                short_id(revision.calculation_revision_id) or "",
                revision.calculation_revision_id,
                short_id(revision.work_unit_id) or "",
                revision.work_unit_id,
                revision.state.value,
                revision.created_at.isoformat(),
            )
        )
        for revision in revisions
    ]


def _work_revisions_lines(
    resolved_work_unit_id: str | None,
    revisions: Sequence[ModeloRevisionInventoryRow],
) -> list[str]:
    """Render the stable text envelope for the revision listing."""
    lines = [
        "operation\tmodelo.work.revisions",
        f"work_unit_id_filter\t{resolved_work_unit_id or ''}",
        f"revision_count\t{len(revisions)}",
        "short_calculation_revision_id\tcalculation_revision_id\tshort_work_unit_id\twork_unit_id\tstate\tcreated_at",
    ]
    lines.extend(_work_revision_listing_lines(revisions))
    return lines


__all__ = ["work_observations", "work_revision", "work_revisions"]


def work_revisions(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """List persisted :class:`CalculationRevision` rows for an optional :class:`WorkUnit`."""
    activate_subcommand_output_language(ctx, output_language)
    inventory = read_modelo_revision_inventory_for_cli(
        ctx,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    result = _work_revisions_result(inventory.work_unit_id_filter, inventory.revisions)
    lines = _work_revisions_lines(inventory.work_unit_id_filter, inventory.revisions)
    emit_envelope(ctx, command="modelo.work.revisions", result=result, lines=lines)


def work_revision(
    ctx: typer.Context,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    registry_revision: str | None = None,
    work_unit_id: str | None = None,
    select: str = ModeloCalculationRevisionSelector.CURRENT.value,
    bucket_id: str | None = None,
    verbose: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show one selected :class:`CalculationRevision` as a work-revision result.

    The JSON branch emits
    :class:`WorkRevisionResult`.
    Each computed casilla renders its formula trace inline as
    ``op(refs) = op(values) = value``; ``--verbose`` additionally surfaces
    the full operand lineage line beneath each computed row.
    """
    activate_subcommand_output_language(ctx, output_language)
    snapshot = read_modelo_revision_snapshot_for_cli(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=registry_revision,
        bucket_id=bucket_id,
        selector=parse_revision_selector(select),
    )
    language = OutputLanguage(current_output_language())
    modality_payload: dict[str, object] = {}
    modality_lines: list[str] = []
    modality_summary = snapshot.modality
    if modality_summary is not None:
        modality_payload = {"modality": modality_summary.modality, "modality_reason": modality_summary.reason}
        modality_lines = [f"modality\t{modality_summary.modality}"]
    result = WorkRevisionResult.model_validate(
        {
            **calculation_snapshot_payload(snapshot.calculation, language=language).model_dump(mode="python"),
            **modality_payload,
        }
    )
    lines = [
        "operation\tmodelo.work.revision",
        *calculation_snapshot_lines(snapshot.calculation, language=language, verbose=verbose),
        *modality_lines,
    ]
    emit_envelope(ctx, command="modelo.work.revision", result=result, lines=lines)


def work_observations(
    ctx: typer.Context,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    registry_revision: str | None = None,
    work_unit_id: str | None = None,
    select: str = ModeloCalculationRevisionSelector.CURRENT.value,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show observation provenance for one stored :class:`CalculationRevision`.

    The JSON branch emits
    :class:`ObservationPayload`
    rows through the observations result schema.
    """
    activate_subcommand_output_language(ctx, output_language)
    snapshot = read_modelo_revision_snapshot_for_cli(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=registry_revision,
        bucket_id=bucket_id,
        selector=parse_revision_selector(select),
    )
    language = OutputLanguage(current_output_language())
    revision_payload = calculation_snapshot_payload(snapshot.calculation, language=language)
    result = WorkObservationsResult.model_validate(
        {
            "calculation_revision_id": revision_payload.calculation_revision_id,
            "work_unit_id": revision_payload.work_unit_id,
            "state": revision_payload.state,
            "observation_count": len(revision_payload.observations),
            "observations": revision_payload.observations,
        }
    )
    lines = [
        "operation\tmodelo.work.observations",
        *calculation_observation_payload_lines(revision_payload),
    ]
    emit_envelope(ctx, command="modelo.work.observations", result=result, lines=lines)
