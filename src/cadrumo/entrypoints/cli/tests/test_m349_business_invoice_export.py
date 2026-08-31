"""Modelo 349 export rows from operator invoices through the real CLI."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....application.aggregation import CalculationSourceContext
from ....application.invoices._source_resolver import InvoiceCatalogueSourceResolver
from ....core.period import Period
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.loader import load_modelo_path
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage
from ....tests.user_profile import register_cli_profile, register_minimal_profile

__all__ = ["isolated_profile_storage"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _create_profile() -> None:
    """Register the profile through the shared CLI registration door."""
    register_cli_profile(
        label="m349-business-invoices",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Ana",
            "identity.surnames": "Operadora",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "activities.description": "consultoria intracomunitaria",
        },
    )


def _add_business_invoice(
    *,
    kind: str,
    counterparty_nif: str,
    counterparty_name: str,
    invoice_number: str,
    taxable_base: str,
    operation_type: str,
    country_code: str = "DE",
) -> None:
    result = _invoke(
        [
            "app",
            "ledger",
            "invoice",
            "add",
            "--kind",
            kind,
            "--counterparty-nif",
            counterparty_nif,
            "--counterparty-name",
            counterparty_name,
            "--invoice-number",
            invoice_number,
            "--invoice-date",
            "2026-03-10",
            "--taxable-base",
            taxable_base,
            "--iva-rate",
            "0",
            "--country-code",
            country_code,
            "--operation-type",
            operation_type,
        ],
    )
    assert result.exit_code == 0, result.output


def _exported_records(path: Path, *, expected_records: int | None = None) -> list[str]:
    payload = path.read_bytes()
    if expected_records is None:
        assert len(payload) % 500 == 0, f"unexpected M349 fixed-width length: {len(payload)}"
    else:
        assert len(payload) == expected_records * 500
    text = payload.decode("latin-1")
    return [text[index : index + 500] for index in range(0, len(text), 500)]


def _modelo_349_revision():
    return load_modelo_path(bundled_path("registry", "aeat", "modelos", "349")).revisions["2020-y-siguientes"]


def test_m349_business_invoices_persist_and_export_operador_rows(tmp_path: Path) -> None:
    _create_profile()
    _add_business_invoice(
        kind="issued",
        counterparty_nif="DE123456789",
        counterparty_name="Kunde GmbH",
        invoice_number="EU-2026-001",
        taxable_base="1000.00",
        operation_type="E",
    )
    _add_business_invoice(
        kind="issued",
        counterparty_nif="FR12345678901",
        counterparty_name="Service SARL",
        invoice_number="EU-2026-002",
        taxable_base="8700.00",
        operation_type="S",
        country_code="FR",
    )
    _add_business_invoice(
        kind="received",
        counterparty_nif="DE222222222",
        counterparty_name="Supplier GmbH",
        invoice_number="EU-2026-003",
        taxable_base="16000.00",
        operation_type="A",
    )
    _add_business_invoice(
        kind="received",
        counterparty_nif="IT12345678901",
        counterparty_name="Servizi SRL",
        invoice_number="EU-2026-004",
        taxable_base="3000.00",
        operation_type="I",
        country_code="IT",
    )

    created = _invoke(
        [
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "349",
            "--year",
            "2026",
            "--period",
            "1T",
            "--revision",
            "2020-y-siguientes",
        ],
    )
    assert created.exit_code == 0, created.output

    calculated = _invoke(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            "349",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    assert calculated.exit_code == 0, calculated.output
    assert "casilla\tdecl.numero-operadores\t4" in calculated.output
    assert "casilla\tdecl.importe-operaciones\t28700.00" in calculated.output
    detail_lines = [line for line in calculated.output.splitlines() if line.startswith("detail_row\t")]
    assert len(detail_lines) == 4
    assert any(
        "codigo_pais=DE" in line
        and "nif_comunitario=DE123456789" in line
        and "clave_operacion=E" in line
        and "importe=1000.00" in line
        for line in detail_lines
    ), calculated.output
    assert "casilla\tiva-349-operador-row" not in calculated.output
    assert "casilla\ttipo2." not in calculated.output

    verified = _invoke(
        [
            "app",
            "modelo",
            "work",
            "verify",
            "--modelo",
            "349",
            "--year",
            "2026",
            "--period",
            "1T",
        ],
    )
    assert verified.exit_code == 0, verified.output

    output_path = tmp_path / "modelo-349.txt"
    exported = _invoke(
        [
            "app",
            "modelo",
            "export",
            "--modelo",
            "349",
            "--year",
            "2026",
            "--period",
            "1T",
            "--output",
            str(output_path),
        ],
    )
    assert exported.exit_code == 0, exported.output

    operator_records = [
        record for record in _exported_records(output_path, expected_records=5) if record.startswith("2349")
    ]
    assert len(operator_records) == 4
    rows = {(record[77:92].strip(), record[132]): record for record in operator_records}

    issued = rows[("123456789", "E")]
    assert issued[75:77] == "DE"
    assert issued[92:132].strip() == "Kunde GmbH"
    assert issued[133:146] == "0000000100000"

    service = rows[("12345678901", "S")]
    assert service[75:77] == "FR"
    assert service[92:132].strip() == "Service SARL"
    assert service[133:146] == "0000000870000"

    received = rows[("222222222", "A")]
    assert received[75:77] == "DE"
    assert received[92:132].strip() == "Supplier GmbH"
    assert received[133:146] == "0000001600000"

    received_service = rows[("12345678901", "I")]
    assert received_service[75:77] == "IT"
    assert received_service[92:132].strip() == "Servizi SRL"
    assert received_service[133:146] == "0000000300000"


def test_emilio_catalogue_service_invoice_feeds_m349() -> None:
    with open_test_profile_session("11111111-1111-4111-8111-111111111111"):
        register_minimal_profile(profile_id="11111111-1111-4111-8111-111111111111")
        created_invoice = _invoke(
            [
                "app",
                "ledger",
                "invoice",
                "add",
                "--kind",
                "issued",
                "--counterparty-nif",
                "DE123456789",
                "--counterparty-name",
                "DE Kunde GmbH",
                "--invoice-number",
                "OUT-2024-Q1-DE-S",
                "--invoice-date",
                "2024-01-18",
                "--taxable-base",
                "4000.00",
                "--iva-rate",
                "0",
                "--country-code",
                "DE",
                "--operation-type",
                "S",
            ],
        )
        assert created_invoice.exit_code == 0, created_invoice.output
        assert "operation_type\tS" in created_invoice.output

        repository = InvoiceCatalogueRepository()
        stored = next(invoice for invoice in repository.load().values() if invoice.invoice_number == "OUT-2024-Q1-DE-S")
        assert stored.bucket_id is not None
        resolution = InvoiceCatalogueSourceResolver(invoice_repository=repository).resolve(
            CalculationSourceContext(
                bucket_id=stored.bucket_id,
                modelo="349",
                filing_year=2024,
                period=Period.from_year_and_code(2024, "1T"),
                revision=_modelo_349_revision(),
            ),
        )

    assert resolution.binding_values["iva-349-declarante-numero-operadores"] == (Decimal("1"))
    assert resolution.binding_values["iva-349-declarante-importe-operaciones"] == Decimal("4000.00")
    assert len(resolution.detail_rows) == 1
    row_obj: Any = resolution.detail_rows[0]
    assert row_obj.codigo_pais == "DE"
    assert row_obj.nif_comunitario == "DE123456789"
    assert row_obj.razon_social == "DE Kunde GmbH"
    assert row_obj.clave_operacion == "S"
    assert row_obj.importe == Decimal("4000.00")
