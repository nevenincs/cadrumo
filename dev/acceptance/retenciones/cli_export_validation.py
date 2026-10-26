"""Independent periodic export and calculated casilla observations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from cadrumo.domain.calculations.registry.export_parse import (
    ParsedExportPayload,
    parse_export_payload,
)
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from .cli_contracts import ExportValidationEvidence, RetencionesInstalledCliError
from .cli_observations import _as_decimal, _money_or_integer_text


def _validate_export(
    *,
    layout: ExportLayoutDefinition,
    payload: bytes,
    expected: tuple[tuple[str, Decimal], ...],
    stage: str,
) -> ExportValidationEvidence:
    """Parse actual export bytes through the canonical selected-layout parser."""
    try:
        parsed = parse_export_payload(layout, payload)
    except Exception as exc:
        raise RetencionesInstalledCliError(
            stage=stage,
            diagnostic_code=f"canonical_export_parse_{type(exc).__name__}",
        ) from exc
    return _validate_parsed_casillas(parsed=parsed, expected=expected, stage=stage)


def _validate_parsed_casillas(
    *, parsed: ParsedExportPayload, expected: tuple[tuple[str, Decimal], ...], stage: str
) -> ExportValidationEvidence:
    """Compare only independently authored expected casillas to parsed bytes."""
    expected_by_id = dict(expected)
    actual: dict[str, Decimal] = {}
    for field in parsed.casillas:
        if field.casilla_id is None:
            continue
        try:
            value = _as_decimal(field.value)
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RetencionesInstalledCliError(
                stage=stage,
                diagnostic_code="non_decimal_expected_export_casilla",
            ) from exc
        casilla_id = str(field.casilla_id)
        prior = actual.get(casilla_id)
        if prior is not None and prior != value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="conflicting_export_casilla")
        actual[casilla_id] = value
    for casilla_id, expected_value in expected_by_id.items():
        if actual.get(casilla_id) != expected_value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="export_casilla_mismatch")
    return ExportValidationEvidence(
        layout_id=str(parsed.layout_id),
        parsed_casillas={key: _money_or_integer_text(actual[key]) for key in expected_by_id},
        expected_casillas={key: _money_or_integer_text(value) for key, value in expected_by_id.items()},
    )


def _expected_casillas_from_result(
    result: Mapping[str, Any],
    *,
    expected: tuple[tuple[str, Decimal], ...],
    stage: str,
) -> dict[str, str]:
    """Require canonical work calculation values to match the independent oracle."""
    values = result.get("casilla_values")
    if not isinstance(values, Mapping):
        raise RetencionesInstalledCliError(stage=stage, diagnostic_code="calculation_casillas_missing")
    casilla_values = cast(Mapping[str, object], values)
    observed: dict[str, str] = {}
    for casilla_id, expected_value in expected:
        try:
            value = _as_decimal(casilla_values.get(casilla_id))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="calculation_casilla_invalid") from exc
        if value != expected_value:
            raise RetencionesInstalledCliError(stage=stage, diagnostic_code="calculation_casilla_mismatch")
        observed[casilla_id] = _money_or_integer_text(value)
    return observed
