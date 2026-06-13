"""Shared support for split adapter tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.resources import resources
from .....domain.calculations.registry import (
    CasillaObservation as CasillaObservation,
)
from .....domain.calculations.registry import (
    RegistryModeloObservation as RegistryModeloObservation,
)
from .....domain.calculations.registry import (
    RegistryValidationError,
    calculate_registry_snapshot,
)
from .....domain.calculations.registry import (
    resolve_relation_values_from_observations as resolve_relation_values_from_observations,
)
from .....tests import FIXTURES_DIR
from .. import DeclaracionParseError, parse_declaracion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_COMPUTED_CASILLAS_M130 = frozenset(
    {"03", "04", "07", "09", "11", "12", "13", "14", "17", "19", "saldo-negativo-fin-periodo"},
)

_COMPUTED_CASILLAS_M111 = frozenset({"28", "30"})


def _registry_snapshot(modelo: str, filing_year: int, period: str):
    """Resolve a validated registry snapshot from the committed authority."""
    return resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period)


_DR303_PROJECTION_CASILLAS = frozenset({"03", "06", "09", "11", "13", "27", "29", "33", "37", "45"})

_COMPUTED_CASILLAS_M303 = frozenset(
    {
        "iva.cuota-devengada-total",
        "iva.cuota-deducible-total",
        "iva.resultado-regimen-general",
        *_DR303_PROJECTION_CASILLAS,
        "64",  # suma de resultados (46 + 58 + 76) — Orden HAC/819/2024 art. 1
        "66",  # atribuible Estado (64 × 65 / 100) — Orden HAC/819/2024 art. 1
        "iva.compensacion-aplicada-periodo",
        "iva.compensacion-pendiente-periodos-posteriores",
        "iva.resultado",  # resultado autoliquidación (66 + 77 + 68 - 78)
        "71",  # resultado final (69 - 70 + 109) — Orden HAC/819/2024 art. 1
        "iva.compensacion-generada-periodo",
        "iva.compensacion-disponible-fin-periodo",
    },
)

_M303_2023_ONWARDS_PARAMS = [
    ("2023-1T", 2023, "1T"),
    ("2023-2T", 2023, "2T"),
    ("2023-3T", 2023, "3T"),
    ("2023-4T", 2023, "4T"),
    ("2024-1T", 2024, "1T"),
    ("2024-2T", 2024, "2T"),
    ("2024-3T", 2024, "3T"),
    ("2024-4T", 2024, "4T"),
]


def _build_m303_engine_result(pdf_stem: str, year: int, period: str):  # type: ignore[return]
    """Parse the corpus PDF and run the registry engine.  Returns (extracted, engine_values)."""
    pdf_path = FIXTURES_DIR / "justificantes" / "303" / f"{pdf_stem}.pdf"
    try:
        filing = parse_declaracion(
            pdf_path,
            modelo_override="303",
            año_override=year,
            period_override=period,
        )
    except DeclaracionParseError as exc:
        pytest.fail(f"PARSER-GAP [{pdf_stem}]: parse_declaracion raised — M303 extraction failed.\n  error: {exc}")

    extracted = {v.casilla_id: v.printed_value for v in filing.values}

    inputs: dict[str, Decimal] = {}
    for casilla_id, value in extracted.items():
        if casilla_id in _COMPUTED_CASILLAS_M303:
            continue
        if not isinstance(value, Decimal):
            continue
        inputs[casilla_id] = value

    # Box 65 — % atribuible Estado; bound to the profile-derived
    # ``tax_residence.state_attribution_ratio`` via casilla.binding. The engine's
    # _initial_values only auto-hydrates BOUND casillas from binding_values when
    # the binding's source is ``previous_filing``; profile-sourced bound casillas
    # expect the application-layer resolver to have populated ``inputs`` with the
    # resolved value before reaching the calculator. This test path bypasses
    # the application layer, so we supply C65 via both channels: inputs hydrates
    # the casilla value for the formula multiplier; binding_values satisfies
    # any explicit binding-fact lookups.
    # Grounded in Orden HAC/819/2024 art. 1 (casilla 65 instrucciones).
    inputs["65"] = Decimal("100")

    _extracted_comp = extracted.get("iva.compensacion-pendiente-periodos-anteriores", Decimal("0"))
    _comp = _extracted_comp if isinstance(_extracted_comp, Decimal) else Decimal("0")
    binding_values: dict[str, Decimal] = {
        "modelo-303-compensacion-pendiente-anteriores": _comp,
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }

    _period_month = {"1T": 1, "2T": 4, "3T": 7, "4T": 10}[period]
    snapshot = _registry_snapshot("303", year, period)
    try:
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": date(year, _period_month, 1)},
            binding_values=binding_values,
        )
    except RegistryValidationError as exc:
        pytest.fail(
            f"BINDING-GAP [{pdf_stem}]: calculate_registry_snapshot raised RegistryValidationError.\n"
            f"  error: {exc}\n"
            f"  inputs supplied: {sorted(inputs)}\n"
            f"  binding_values supplied: {sorted(binding_values)}",
        )
    return extracted, dict(result.values), inputs


_COMPUTED_CASILLAS_M390 = frozenset(
    {"iva.anual.cuota-devengada-total", "iva.anual.cuota-deducible-total", "iva.anual.resultado-regimen-general"},
)

_M390_PREVIOUS_FILING_BINDING_IDS = (
    "modelo-390-prev-303-cuota-devengada-total",
    "modelo-390-prev-303-cuota-deducible-total",
    "modelo-390-prev-303-resultado-regimen-general",
    "modelo-390-prev-303-compensacion-ultimo-periodo",
    "modelo-390-prev-303-compensacion-generada-ejercicio-no-97",
)

_COMPUTED_CASILLAS_M115 = frozenset({"03", "05"})

_COMPUTED_CASILLAS_M123_2019 = frozenset({"06-legacy", "08-legacy"})

_COMPUTED_CASILLAS_M123_2024 = frozenset({"03", "06", "09", "12", "14"})

_COMPUTED_CASILLAS_M131 = frozenset({"04", "06", "07", "10", "13", "15", "saldo-negativo-fin-periodo"})


def _period_to_date(year: int, period: str) -> date:
    """Convert a filing year and AEAT period string to the last date of that period.

    Used as the ``filing_period`` date context for ``calculate_registry_snapshot``.
    """
    period_upper = period.upper()
    if period_upper == "1T":
        return date(year, 3, 31)
    if period_upper == "2T":
        return date(year, 6, 30)
    if period_upper == "3T":
        return date(year, 9, 30)
    if period_upper in ("4T", "0A"):
        return date(year, 12, 31)
    if len(period_upper) == 2 and period_upper.isdigit():
        month = int(period_upper)
        import calendar

        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)
    return date(year, 12, 31)
