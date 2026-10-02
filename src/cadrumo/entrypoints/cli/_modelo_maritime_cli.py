"""Behavior handlers for modelo maritime preview commands.

This module is the transport boundary for
``aeat app modelo work preview-maritime-exemption``. The command body keeps CLI
responsibilities narrow: parse Decimal options, submit through the exact-profile
worker bridge, then serialise the returned worker projection into
:class:`WorkPreviewMaritimeExemptionResult`.

See Also:
    :mod:`maritime_preview_operation`:
        Registered profile-bound preview consumed by this CLI adapter.
    :class:`CasillaObservationPayload`:
        JSON payload row carrying the legal/source references emitted by the
        maritime resolver.

The worker projection preserves the canonical observation order and grounding.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

import typer

from ...application.modelo.maritime_preview_operation import (
    MaritimePreviewObservation,
    ModeloMaritimePreviewProjection,
)
from ...core.casilla_id import CasillaId
from ...core.errors.error_codes import resolve_error_message
from ...core.errors.hierarchy import RecordedRegisteredError
from ...core.external_constants import OutputLanguage
from ._modelo_cli_support import optional_decimal_option
from ._modelo_payloads import CasillaObservationPayload, WorkPreviewMaritimeExemptionResult
from .common import activate_subcommand_output_language, emit_envelope
from .runtime_modelo_maritime_preview import preview_modelo_maritime_exemption


def _parse_maritime_amounts(
    *,
    annual_salary: str | None,
    gross_navigation_income: str | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Parse the two optional euro inputs using their field-specific contracts."""
    return (
        optional_decimal_option(
            annual_salary,
            translation_key="cli.app.modelo.work.preview_maritime_exemption_annual_salary_not_decimal",
            default=(
                "--annual-salary must be a decimal amount; received: {value}. "
                "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
            ),
        ),
        optional_decimal_option(
            gross_navigation_income,
            translation_key="cli.app.modelo.work.preview_maritime_exemption_gross_navigation_income_not_decimal",
            default=(
                "--gross-navigation-income must be a decimal amount; received: {value}. "
                "Use a dot decimal separator with no thousands grouping, e.g. 1234.56."
            ),
        ),
    )


def _maritime_observation_payloads(
    observations: Sequence[MaritimePreviewObservation],
) -> list[CasillaObservationPayload]:
    """Project grounded backend observations into the CLI payload shape."""
    return [
        CasillaObservationPayload(
            casilla_id=observation.casilla_id,
            value=str(observation.value),
            formula_id=observation.formula_id,
            legal_refs=tuple(observation.legal_refs),
            source_refs=tuple(observation.source_refs),
        )
        for observation in observations
    ]


def _maritime_casilla_values(projection: ModeloMaritimePreviewProjection) -> dict[CasillaId, str]:
    """Project the worker's complete casilla map into the established CLI shape."""
    return {row.casilla_id: row.value for row in projection.casilla_values}


def _maritime_observation_lines(observations: Sequence[MaritimePreviewObservation]) -> list[str]:
    """Render each grounded observation in the stable text-line order."""
    return [
        "observation\t"
        + "\t".join(
            (
                f"casilla={observation.casilla_id}",
                f"value={observation.value}",
                f"legal_refs={'; '.join(observation.legal_refs)}",
                f"source_refs={','.join(observation.source_refs)}",
            )
        )
        for observation in observations
    ]


def _maritime_result_payload(
    projection: ModeloMaritimePreviewProjection,
    *,
    retmar_warning: str | None,
    casilla_values: dict[CasillaId, str],
    observation_payloads: list[CasillaObservationPayload],
) -> WorkPreviewMaritimeExemptionResult:
    """Build the typed result from backend facts and grounded observations."""
    return WorkPreviewMaritimeExemptionResult(
        worker_class=projection.worker_class,
        vessel_flag=projection.vessel_flag,
        waters_type=projection.waters_type,
        vessel_registry=projection.vessel_registry,
        retmar_registered=projection.retmar_registered,
        retmar_mandatory_filing=projection.retmar_mandatory_filing,
        retmar_warning=retmar_warning,
        casilla_values=casilla_values,
        observations=observation_payloads,
    )


def _maritime_text_lines(
    projection: ModeloMaritimePreviewProjection,
    *,
    retmar_warning: str | None,
    casilla_values: Mapping[CasillaId, str],
    observation_payloads: Sequence[CasillaObservationPayload],
) -> list[str]:
    """Render the stable text projection from the same typed values as JSON."""
    lines: list[str] = [
        "operation\tmodelo.work.preview_maritime_exemption",
        f"worker_class\t{projection.worker_class or '-'}",
        f"vessel_flag\t{projection.vessel_flag or '-'}",
        f"waters_type\t{projection.waters_type or '-'}",
        f"vessel_registry\t{projection.vessel_registry or '-'}",
        f"retmar_registered\t{str(projection.retmar_registered).lower()}",
        f"observation_count\t{len(observation_payloads)}",
    ]
    lines.extend(_maritime_observation_lines(projection.observations))
    lines.extend(f"casilla_value\t{key}\t{value}" for key, value in casilla_values.items())
    if retmar_warning is not None:
        lines.append(f"retmar_warning\t{retmar_warning}")
    return lines


def work_preview_maritime_exemption(
    ctx: typer.Context,
    annual_salary: str | None = None,
    qualifying_days: int | None = None,
    gross_navigation_income: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Resolve and render the maritime exemption preview for the active profile.

    Decimal parsing and text rendering stay at the CLI boundary. Legal pathway
    selection, profile fact extraction, RETMAR warning handling, and typed
    observation construction stay in the registered application operation.
    """
    activate_subcommand_output_language(ctx, output_language)
    annual_salary_decimal, gross_navigation_decimal = _parse_maritime_amounts(
        annual_salary=annual_salary,
        gross_navigation_income=gross_navigation_income,
    )
    projection = preview_modelo_maritime_exemption(
        ctx,
        annual_salary=annual_salary_decimal,
        qualifying_days=qualifying_days,
        gross_navigation_income=gross_navigation_decimal,
    )
    retmar_warning = (
        resolve_error_message(
            RecordedRegisteredError(
                projection.retmar_warning.code,
                context={"legal_ref": projection.retmar_warning.legal_ref},
            ),
        )
        if projection.retmar_warning is not None
        else None
    )
    observation_payloads = _maritime_observation_payloads(projection.observations)
    casilla_values = _maritime_casilla_values(projection)
    payload = _maritime_result_payload(
        projection,
        retmar_warning=retmar_warning,
        casilla_values=casilla_values,
        observation_payloads=observation_payloads,
    )
    lines = _maritime_text_lines(
        projection,
        retmar_warning=retmar_warning,
        casilla_values=casilla_values,
        observation_payloads=observation_payloads,
    )
    emit_envelope(ctx, command="modelo.work.preview_maritime_exemption", result=payload, lines=lines)
