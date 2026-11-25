"""Public received-invoice and withholding allocation inputs for installed acceptance."""

from __future__ import annotations

import json
from collections.abc import Iterable

from dev.acceptance.installed_cli import InstalledCli

from .cli_contracts import RetencionesInstalledCliError
from .cli_observations import money_text, percentage_text, require_result, required_text
from .scenario import (
    InstalledPeriodicCliSlice,
    Modelo180PropertyInput,
    Modelo190AnnualDetailInput,
    PaymentAllocation,
)


def declare_perceptor_filing_names(cli: InstalledCli, slices: Iterable[InstalledPeriodicCliSlice]) -> None:
    """Declare each distinct perceptor's entity filing name once, before any annual export.

    The 180/190 export files the name declared for the perceptor's tax id, not
    the free text recorded with the invoice. Every perceptor here is an entity
    (CIF), so its razón social is the whole declared name.
    """
    declared: dict[str, str] = {}
    for slice_ in slices:
        previous = declared.setdefault(slice_.counterparty_nif, slice_.counterparty_name)
        if previous != slice_.counterparty_name:
            raise RetencionesInstalledCliError(stage="filing_name_declare", diagnostic_code="perceptor_name_conflict")
    for tax_identifier, razon_social in declared.items():
        require_result(
            cli,
            (
                "app",
                "ledger",
                "counterparty",
                "filing-name",
                tax_identifier,
                "--kind",
                "entity",
                "--razon-social",
                razon_social,
            ),
            stage="filing_name_declare",
        )


def capture_invoice_withholding(*, cli: InstalledCli, slice_: InstalledPeriodicCliSlice, year: int) -> str:
    """Capture one invoice's allocations only through the public typed CLI flag."""
    invoice_id = _create_received_invoice(cli, slice_=slice_)
    for allocation in slice_.allocations:
        request = _invoice_withholding_request(slice_=slice_, invoice_id=invoice_id, allocation=allocation)
        require_result(
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
        "allocated_base": money_text(allocation.allocated_base),
        "allocated_withholding": money_text(allocation.allocated_withholding),
        "allocated_settlement": money_text(allocation.allocated_settlement),
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
        "withholding_percentage": money_text(detail.withholding_percentage),
        "address": {
            "province_code": detail.province_code,
            "municipality_code": f"{detail.province_code}079",
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
        "percibido_dinerario": money_text(allocation.allocated_base),
        "retencion_practicada": money_text(allocation.allocated_withholding),
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
        "base_retenciones": money_text(allocation.allocated_base),
        "porcentaje_retencion": percentage_text(slice_.invoice_withholding_rate),
    }


def _create_received_invoice(cli: InstalledCli, *, slice_: InstalledPeriodicCliSlice) -> str:
    """Create the canonical invoice through the installed public CLI."""
    result = require_result(
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
            money_text(slice_.invoice_base),
            "--iva-rate",
            percentage_text(slice_.invoice_iva_rate),
            "--country-code",
            "ES",
            "--retention-rate",
            str(slice_.invoice_withholding_rate),
            "--retention-amount",
            money_text(slice_.invoice_withholding),
            "--iva-category",
            "domestic_general",
        ),
        stage=f"{slice_.slice_id}:invoice_create",
    )
    return required_text(result, key="invoice_id", stage=f"{slice_.slice_id}:invoice_create")
