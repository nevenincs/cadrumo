"""Modelo 349 export rows from catalogue invoices through the real CLI."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _create_profile() -> None:
    result = _invoke(
        [
            "config",
            "profile",
            "create",
            "m349-catalogue",
            "--quiet",
            "--tax-id",
            "12345678Z",
            "--entity-type",
            "natural_person",
            "--name",
            "Ana",
            "--surnames",
            "Catalogo",
            "--irpf-income-categories",
            "actividad_economica",
            "--activity",
            "consultoria intracomunitaria",
        ],
    )
    assert result.exit_code == 0, result.output


def _create_catalogue_invoice(
    *,
    kind: str,
    counterparty_nif: str,
    counterparty_name: str,
    invoice_number: str,
    taxable_base: str,
    operation_type: str,
) -> None:
    result = _invoke(
        [
            "app",
            "ledger",
            "invoice",
            "catalogue",
            "create",
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
            "DE",
            "--operation-type",
            operation_type,
        ],
    )
    assert result.exit_code == 0, result.output


def _exported_records(path: Path) -> list[str]:
    payload = path.read_bytes()
    assert len(payload) == 1500
    text = payload.decode("latin-1")
    return [text[index : index + 500] for index in range(0, len(text), 500)]


def test_m349_catalogue_invoices_persist_and_export_operador_rows(tmp_path: Path) -> None:
    _create_profile()
    _create_catalogue_invoice(
        kind="issued",
        counterparty_nif="DE123456789",
        counterparty_name="Kunde GmbH",
        invoice_number="EU-2026-001",
        taxable_base="1000.00",
        operation_type="E",
    )
    _create_catalogue_invoice(
        kind="received",
        counterparty_nif="DE222222222",
        counterparty_name="Supplier GmbH",
        invoice_number="EU-2026-002",
        taxable_base="750.00",
        operation_type="A",
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
    assert "casilla\tdecl.numero-operadores\t2" in calculated.output
    assert "casilla\tdecl.importe-operaciones\t1750.00" in calculated.output
    assert len([line for line in calculated.output.splitlines() if line.startswith("detail_row\t")]) == 2

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

    operator_records = [record for record in _exported_records(output_path) if record.startswith("2349")]
    assert len(operator_records) == 2
    rows = {(record[77:92].strip(), record[132]): record for record in operator_records}

    issued = rows[("123456789", "E")]
    assert issued[75:77] == "DE"
    assert issued[92:132].strip() == "Kunde GmbH"
    assert issued[133:146] == "0000000100000"

    received = rows[("222222222", "A")]
    assert received[75:77] == "DE"
    assert received[92:132].strip() == "Supplier GmbH"
    assert received[133:146] == "0000000075000"
