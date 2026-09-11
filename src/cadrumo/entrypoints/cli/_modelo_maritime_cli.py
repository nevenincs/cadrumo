# ruff: noqa: E501 - localized guidance and tabular wire lines are atomic
"""Behavior handlers for modelo maritime preview commands.

This module is the transport boundary for
``aeat app modelo work preview-maritime-exemption``. The command body keeps CLI
responsibilities narrow: parse Decimal options, require an active profile,
delegate profile fact reading and RETMAR retry policy to
:func:`preview_maritime_exemption_for_active_profile`,
then serialise the returned observations into
:class:`WorkPreviewMaritimeExemptionResult`.

See Also:
    :mod:`maritime_preview`:
        Active-profile application service consumed by this CLI adapter.
    :class:`CasillaObservationPayload`:
        JSON payload row carrying the legal/source references emitted by the
        maritime resolver.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

import typer

from ...application.calculations.maritime_exemption_service import MaritimeExemptionResult
from ...application.modelo.maritime_preview import (
    ModeloMaritimeExemptionPreview,
    preview_maritime_exemption_for_active_profile,
)
from ...core.casilla_id import CasillaId
from ...core.errors.error_codes import resolve_error_message
from ...core.external_constants import OutputLanguage
from ...domain.calculations.registry.bindings import CasillaObservation
from ...domain.renta.errors import RentaValidationError
from ._modelo_behavior_support import require_active_profile
from ._modelo_cli_support import bad_parameter_from_error, optional_decimal_option
from ._modelo_payloads import CasillaObservationPayload, WorkPreviewMaritimeExemptionResult
from .common import activate_subcommand_output_language, emit_envelope


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
            default="--annual-salary must be a decimal amount; received: {value}. Use a dot decimal separator with no thousands grouping, e.g. 1234.56.",
        ),
        optional_decimal_option(
            gross_navigation_income,
            translation_key="cli.app.modelo.work.preview_maritime_exemption_gross_navigation_income_not_decimal",
            default="--gross-navigation-income must be a decimal amount; received: {value}. Use a dot decimal separator with no thousands grouping, e.g. 1234.56.",
        ),
    )


def _resolve_maritime_preview(
    *,
    annual_salary: Decimal | None,
    qualifying_days: int | None,
    gross_navigation_income: Decimal | None,
) -> ModeloMaritimeExemptionPreview:
    """Resolve the backend preview and translate only its CLI input failures."""
    try:
        return preview_maritime_exemption_for_active_profile(
            annual_salary=annual_salary,
            qualifying_days=qualifying_days,
            gross_navigation_income=gross_navigation_income,
        )
    except RentaValidationError as exc:
        raise bad_parameter_from_error(exc) from exc


def _maritime_observation_payloads(
    observations: Sequence[CasillaObservation],
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


def _maritime_casilla_values(result: MaritimeExemptionResult) -> dict[CasillaId, str]:
    """Project the backend's derived casilla mapping into string wire values."""
    return {key: str(value) for key, value in result.casilla_values.items()}


def _maritime_observation_lines(observations: Sequence[CasillaObservation]) -> list[str]:
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
    preview: ModeloMaritimeExemptionPreview,
    *,
    retmar_warning: str | None,
    casilla_values: dict[CasillaId, str],
    observation_payloads: list[CasillaObservationPayload],
) -> WorkPreviewMaritimeExemptionResult:
    """Build the typed result from backend facts and grounded observations."""
    facts = preview.facts
    return WorkPreviewMaritimeExemptionResult(
        worker_class=facts.worker_class,
        vessel_flag=facts.vessel_flag,
        waters_type=facts.waters_type,
        vessel_registry=facts.vessel_registry,
        retmar_registered=facts.retmar_registered,
        retmar_mandatory_filing=preview.retmar_mandatory_filing,
        retmar_warning=retmar_warning,
        casilla_values=casilla_values,
        observations=observation_payloads,
    )


def _maritime_text_lines(
    preview: ModeloMaritimeExemptionPreview,
    *,
    retmar_warning: str | None,
    casilla_values: Mapping[CasillaId, str],
    observation_payloads: Sequence[CasillaObservationPayload],
) -> list[str]:
    """Render the stable text projection from the same typed values as JSON."""
    facts = preview.facts
    lines: list[str] = [
        "operation\tmodelo.work.preview_maritime_exemption",
        f"worker_class\t{facts.worker_class or '-'}",
        f"vessel_flag\t{facts.vessel_flag or '-'}",
        f"waters_type\t{facts.waters_type or '-'}",
        f"vessel_registry\t{facts.vessel_registry or '-'}",
        f"retmar_registered\t{str(facts.retmar_registered).lower()}",
        f"observation_count\t{len(observation_payloads)}",
    ]
    lines.extend(_maritime_observation_lines(preview.result.observations))
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

    Decimal parsing stays at the CLI boundary. Legal pathway selection,
    profile fact extraction, RETMAR warning handling, and typed observation
    construction stay in
    :func:`preview_maritime_exemption_for_active_profile`.
    """
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    annual_salary_decimal, gross_navigation_decimal = _parse_maritime_amounts(
        annual_salary=annual_salary,
        gross_navigation_income=gross_navigation_income,
    )
    preview = _resolve_maritime_preview(
        annual_salary=annual_salary_decimal,
        qualifying_days=qualifying_days,
        gross_navigation_income=gross_navigation_decimal,
    )
    retmar_warning = (
        resolve_error_message(preview.retmar_warning_error) if preview.retmar_warning_error is not None else None
    )
    observation_payloads = _maritime_observation_payloads(preview.result.observations)
    casilla_values = _maritime_casilla_values(preview.result)
    payload = _maritime_result_payload(
        preview,
        retmar_warning=retmar_warning,
        casilla_values=casilla_values,
        observation_payloads=observation_payloads,
    )
    lines = _maritime_text_lines(
        preview,
        retmar_warning=retmar_warning,
        casilla_values=casilla_values,
        observation_payloads=observation_payloads,
    )
    emit_envelope(ctx, command="modelo.work.preview_maritime_exemption", result=payload, lines=lines)
