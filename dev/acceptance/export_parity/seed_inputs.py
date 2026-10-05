"""Independent synthetic public inputs for export-parity seed stages."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

from .scenario import (
    ASSETS,
    ReceivedInvoice,
    m303_compensation_pending_after,
)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _rate(value: Decimal) -> str:
    return f"{value.normalize():f}"


def _m303_opening_balance_args(year: int, period: str) -> tuple[str, ...]:
    """The IVA wallet opening balance a Modelo 303 filed outside the store left for later periods."""
    return (
        "app",
        "modelo",
        "iva-wallet",
        "seed",
        "--filing-year",
        str(year),
        "--period",
        period,
        "--amount",
        _money(m303_compensation_pending_after(year, period)),
        "--confirm",
    )


def _is_investment_good(item: ReceivedInvoice) -> bool:
    return any(asset.asset_id == item.asset_id and asset.is_iva_investment_good for asset in ASSETS)


def _investment_asset_args(item: ReceivedInvoice) -> tuple[str, ...]:
    """Name the bienes-inversion record an investment deduction must reciprocate."""
    if item.asset_id is None or not _is_investment_good(item):
        return ()
    return ("--investment-asset-id", item.asset_id)


def _binding_ids(document: object) -> Iterator[str]:
    if isinstance(document, dict):
        for key, value in document.items():
            if key == "binding_id" and isinstance(value, str):
                yield value
            else:
                yield from _binding_ids(value)
    elif isinstance(document, list):
        for item in document:
            yield from _binding_ids(item)


def _modelo_190_detail(item: ReceivedInvoice, request: dict[str, object]) -> dict[str, object]:
    zero = "0.00"
    return {
        "source_id": request["invoice_id"],
        "source_allocation_id": request["allocation_id"],
        "perceptor_tax_id": item.counterparty.tax_id,
        "perceptor_legal_name": item.counterparty.name,
        "transaction_date": item.payment_date.isoformat(),
        "clave": "G",
        "subclave": "01",
        "province_code": "28",
        "territorial_deduction_clave": 0,
        "percibido_dinerario": _money(item.base),
        "retencion_practicada": _money(item.withholding),
        "incapacity_cash_perception": zero,
        "incapacity_cash_withholding": zero,
        "incapacity_kind_value": zero,
        "incapacity_kind_ingreso_a_cuenta": zero,
        "incapacity_kind_repercutido": zero,
        "foral_retention_estatal": zero,
        "foral_retention_navarra": zero,
        "foral_retention_araba": zero,
        "foral_retention_gipuzkoa": zero,
        "foral_retention_bizkaia": zero,
        "base_retenciones": _money(item.base),
        "porcentaje_retencion": "15.00",
    }


def _modelo_180_property(year: int) -> dict[str, object]:
    return {
        "property_key": "office-madrid",
        "situation": "1",
        "cadastral_reference": "1234567VK4713C0001XY",
        "recipient_province_code": "28",
        "modality": "1",
        "accrual_year": year,
        "withholding_percentage": "19.00",
        "address": {
            "province_code": "28",
            "municipality_code": "079",
            "municipality": "Madrid",
            "locality": "Madrid",
            "postal_code": "28001",
            "street_type": "CL",
            "street_name": "Ejemplo",
            "number_type": "NUM",
            "house_number": "1",
        },
    }
