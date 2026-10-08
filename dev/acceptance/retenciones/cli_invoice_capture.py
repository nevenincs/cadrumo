"""Public received-invoice and withholding allocation inputs for installed acceptance."""

from __future__ import annotations

import json

from dev.acceptance.installed_cli import InstalledCli

from .cli_observations import _money_text, _percentage_text, _require_result, _required_text
from .scenario import (
    InstalledPeriodicCliSlice,
    Modelo180PropertyInput,
    Modelo190AnnualDetailInput,
    PaymentAllocation,
)


def _capture_invoice_withholding(*, cli: InstalledCli, slice_: InstalledPeriodicCliSlice, year: int) -> str:
    """Capture one invoice's allocations only through the public typed CLI flag."""
    invoice_id = _create_received_invoice(cli, slice_=slice_)
    for allocation in slice_.allocations:
        request = _invoice_withholding_request(slice_=slice_, invoice_id=invoice_id, allocation=allocation)
        _require_result(
            cli,
            (
                "app",
                "modelo",
                "aggregate",
                "--modelo",
                slice_.modelo,
                "--year",
                str(year),
                "--period",
                slice_.period,
                "--received-invoice-retencion",
                json.dumps(request, separators=(",", ":"), sort_keys=True),
            ),
            stage=f"{slice_.slice_id}:capture",
        )
    return invoice_id


def _invoice_withholding_request(
    *,
    slice_: InstalledPeriodicCliSlice,
    invoice_id: str,
    allocation: PaymentAllocation,
) -> dict[str, object]:
    """Render evidence facts without admitting a caller-derived recognition date."""
    request: dict[str, object] = {
        "invoice_id": invoice_id,
        "income_kind": slice_.income_kind,
        "scheme": slice_.scheme,
        "recipient_tax_status": "resident",
        "recipient_tax_regime": "irpf",
        "payment_event_id": allocation.payment_event_id,
        "payment_occurred_on": allocation.paid_on.isoformat(),
        "allocation_id": allocation.allocation_id,
        "allocated_base": _money_text(allocation.allocated_base),
        "allocated_withholding": _money_text(allocation.allocated_withholding),
        "allocated_settlement": _money_text(allocation.allocated_settlement),
        "idempotency_key": f"{slice_.slice_id}:{allocation.allocation_id}",
    }
    if slice_.modelo_180_property is not None:
        request["modelo_180_property"] = _modelo_180_property_payload(slice_.modelo_180_property)
    if slice_.modelo_190_detail is not None:
        request["modelo_190_detail"] = _modelo_190_detail_payload(
            detail=slice_.modelo_190_detail,
            slice_=slice_,
            invoice_id=invoice_id,
            allocation=allocation,
        )
    return request


def _modelo_180_property_payload(detail: Modelo180PropertyInput) -> dict[str, object]:
    """Render only the accepted explicit property-attribution evidence."""
    return {
        "property_key": detail.property_key,
        "situation": detail.situation,
        "cadastral_reference": detail.cadastral_reference,
        "recipient_province_code": detail.recipient_province_code,
        "modality": detail.modality,
        "accrual_year": detail.accrual_year,
        "withholding_percentage": _money_text(detail.withholding_percentage),
        "address": {
            "province_code": detail.province_code,
            "municipality_code": "079",
            "municipality": "Madrid",
            "locality": "Madrid",
            "postal_code": detail.postal_code,
            "street_type": "CL",
            "street_name": "Ejemplo",
            "number_type": "NUM",
            "house_number": "1",
        },
    }


def _modelo_190_detail_payload(
    *,
    detail: Modelo190AnnualDetailInput,
    slice_: InstalledPeriodicCliSlice,
    invoice_id: str,
    allocation: PaymentAllocation,
) -> dict[str, object]:
    """Render the typed annual detail that the producer checks against evidence."""
    zero = "0.00"
    return {
        "source_id": invoice_id,
        "source_allocation_id": allocation.allocation_id,
        "perceptor_tax_id": slice_.counterparty_nif,
        "perceptor_legal_name": slice_.counterparty_name,
        "transaction_date": allocation.paid_on.isoformat(),
        "clave": detail.clave,
        "subclave": detail.subclave,
        "province_code": detail.province_code,
        "territorial_deduction_clave": detail.territorial_deduction_clave,
        "percibido_dinerario": _money_text(allocation.allocated_base),
        "retencion_practicada": _money_text(allocation.allocated_withholding),
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
        "base_retenciones": _money_text(allocation.allocated_base),
        "porcentaje_retencion": _percentage_text(slice_.invoice_withholding_rate),
    }


def _create_received_invoice(cli: InstalledCli, *, slice_: InstalledPeriodicCliSlice) -> str:
    """Create the canonical invoice through the installed public CLI."""
    result = _require_result(
        cli,
        (
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            "received",
            "--counterparty-name",
            slice_.counterparty_name,
            "--counterparty-nif",
            slice_.counterparty_nif,
            "--invoice-number",
            slice_.invoice_number,
            "--invoice-date",
            slice_.invoice_date.isoformat(),
            "--taxable-base",
            _money_text(slice_.invoice_base),
            "--iva-rate",
            _percentage_text(slice_.invoice_iva_rate),
            "--country-code",
            "ES",
            "--retention-rate",
            str(slice_.invoice_withholding_rate),
            "--retention-amount",
            _money_text(slice_.invoice_withholding),
            "--iva-category",
            "domestic_general",
        ),
        stage=f"{slice_.slice_id}:invoice_create",
    )
    return _required_text(result, key="invoice_id", stage=f"{slice_.slice_id}:invoice_create")
