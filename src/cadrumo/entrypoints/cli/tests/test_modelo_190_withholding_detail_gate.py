"""A Modelo 190 whose per-perceptor detail is empty must not be granted verificado completo.

Runs the live CLI parser end to end against the published registry: a filer
whose ledger holds four quarterly received professional invoices, each with 15%
retención practised, and whose per-perceptor withholding store is empty because
the withholding recognition path does not support that applicable year.

``work calculate`` still succeeds and materialises the percepciones count as an
explicit zero, because the bound casilla needs its fact and the pull surface
shares that resolver. ``work verify`` is where the zero stops: it exits 1 with a
blocking finding naming the modelo, the year, the source family and the remedy,
so the all-blank resumen anual cannot be filed locally (local filing requires a
granted verification).

The genuine nil filer keeps working: with every quarterly Modelo 111 window
attested as having satisfied no renta subject to retención, and nothing in the
ledger contradicting it, the same revision verifies and the disclosure survives
as an advisory.
"""

from __future__ import annotations

import json

import pytest

from ....adapters.persistence.profile.tests.profile_registration import register_cli_profile
from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from .cli_runner import invoke_cached_cli

__all__ = ["_isolated_cli_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_FILING_YEAR = "2022"
_ADVISER_NIF = "B12345674"
_ADVISER_NAME = "Asesoria Profesional SL"
_QUARTERLY_INVOICE_DATES = ("2022-03-20", "2022-06-20", "2022-09-20", "2022-12-20")
_ALL_QUARTERS_ATTESTED = "2022:1T,2022:2T,2022:3T,2022:4T"


def _create_profile() -> None:
    """Register the retenedor profile through the shared CLI registration door."""
    register_cli_profile(
        label="operator",
        facts={
            "identity.tax_id": "12345678Z",
            "taxpayer_type.entity_type": "natural_person",
            "identity.name": "Operator",
            "identity.surnames": "Retenedor",
            "activities.description": "design",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "censo.activity_start_date": "2020-01-01",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            "withholding.colegio_concertado": "false",
        },
        log_in=False,
    )


def _add_received_professional_invoice(*, number: str, invoice_date: str) -> str:
    """Mint one received professional invoice with 1000.00 base and 150.00 withheld."""
    created = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "invoice", "add",
            "--kind", "received",
            "--counterparty-name", _ADVISER_NAME,
            "--counterparty-nif", _ADVISER_NIF,
            "--invoice-number", number,
            "--invoice-date", invoice_date,
            "--country-code", "ES",
            "--taxable-base", "1000.00", "--iva-rate", "21",
            "--retention-rate", "0.15", "--retention-amount", "150.00",
            "--iva-category", "domestic_general",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    invoice_id = _payload(created.output)["invoice_id"]
    assert isinstance(invoice_id, str) and invoice_id, created.output
    return invoice_id


def _add_outgoing_professional_payment(*, description: str, paid_on: str) -> None:
    """Record one bank payment to a professional, carrying the IRPF withholding category."""
    added = invoke_cached_cli(
        [
            "--format", "json",
            "app", "ledger", "add",
            "--date", paid_on, "--value-date", paid_on,
            "--amount", "1000.00",
            "--direction", "OUTGOING",
            "--description", description,
            "--counterparty", _ADVISER_NAME,
            "--classification", "BUSINESS",
            "--irpf-category", "actividad_economica",
        ],
    )  # fmt: skip
    assert added.exit_code == 0, added.output


def _create_190_work_unit() -> str:
    created = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "190", "--year", _FILING_YEAR, "--period", "0A",
        ],
    )  # fmt: skip
    assert created.exit_code == 0, created.output
    payload = STR_KEYED_MAPPING_ADAPTER.validate_python(_payload(created.output))
    work_unit_id = payload["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _calculate(work_unit_id: str) -> str:
    calculated = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id],
    )
    assert calculated.exit_code == 0, calculated.output
    payload = _payload(calculated.output)
    values = STR_KEYED_MAPPING_ADAPTER.validate_python(payload["casilla_values"])
    assert values["decl.total-percepciones"] == "0", calculated.output
    assert values["decl.percepciones-total"] == "0.00", calculated.output
    assert values["decl.retenciones-total"] == "0.00", calculated.output
    assert any(
        "no per-perceptor-clave observations are persisted" in notice.get("context", {}).get("detail", "")
        for notice in unwrap_envelope_notices(calculated.output)
    ), calculated.output
    calculation_revision_id = payload["calculation_revision_id"]
    assert isinstance(calculation_revision_id, str)
    return calculation_revision_id


def _attest_every_quarter(periods: str = _ALL_QUARTERS_ATTESTED) -> None:
    attested = invoke_cached_cli(
        [
            "config", "profile", "edit", "operator", "--quiet",
            "--modelo-111-no-retenciones-periods", periods,
        ],
    )  # fmt: skip
    assert attested.exit_code == 0, attested.output


def _finding_facts(output: str, *, source_family: str = "withholding") -> dict[str, str]:
    """Return the notice context of the one withholding-detail finding.

    The verify payload renders each finding into localised prose; the
    locale-neutral facts ride the envelope notice channel, which is what a
    machine consumer routes on.
    """
    matching = [
        STR_KEYED_MAPPING_ADAPTER.validate_python(notice["context"])
        for notice in unwrap_envelope_notices(output)
        if notice["context"] is not None
        and STR_KEYED_MAPPING_ADAPTER.validate_python(notice["context"]).get("source_family") == source_family
    ]
    assert len(matching) == 1, output
    return {key: str(value) for key, value in matching[0].items()}


def test_verify_refuses_an_empty_190_contradicted_by_invoice_retenciones() -> None:
    """The four practised retenciones the store never received block the resumen anual."""
    _create_profile()
    for index, invoice_date in enumerate(_QUARTERLY_INVOICE_DATES, start=1):
        _add_received_professional_invoice(number=f"F-ASESOR-2022-{index:03d}", invoice_date=invoice_date)
    calculation_revision_id = _calculate(_create_190_work_unit())

    verified = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )

    assert verified.exit_code == 1, verified.output
    payload = _payload(verified.output)
    assert payload["granted_verificado_completo"] is False
    facts = _finding_facts(verified.output)
    assert facts["severity"] == "blocking"
    assert facts["modelo"] == "190"
    assert facts["filing_year"] == "2022"
    assert facts["source_family"] == "withholding"
    assert facts["source_modelo"] == "111"
    assert facts["contradicting_invoice_count"] == "4"
    assert facts["contradicting_ledger_row_count"] == "0"
    assert facts["legal_refs"] != ""


def test_verify_refuses_an_attested_nil_190_contradicted_by_a_ledger_payment() -> None:
    """A professional paid through the bank ledger alone still owes its perceptor record.

    The obligation follows from satisfying the renta, so the attestation covering
    every quarterly window does not survive a payment the ledger records.
    """
    _create_profile()
    _attest_every_quarter()
    _add_outgoing_professional_payment(description="Pago asesoria fiscal 3T", paid_on="2022-07-04")
    calculation_revision_id = _calculate(_create_190_work_unit())

    verified = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )

    assert verified.exit_code == 1, verified.output
    assert _payload(verified.output)["granted_verificado_completo"] is False
    facts = _finding_facts(verified.output)
    assert facts["severity"] == "blocking"
    assert facts["contradicting_invoice_count"] == "0"
    assert facts["contradicting_ledger_row_count"] == "1"
    assert facts["attested_periods"] == "1T|2T|3T|4T"


def test_verify_refuses_an_empty_190_that_nothing_attests() -> None:
    """An empty detail store with no ledger evidence and no attestation is still unproven."""
    _create_profile()
    calculation_revision_id = _calculate(_create_190_work_unit())

    verified = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )

    assert verified.exit_code == 1, verified.output
    facts = _finding_facts(verified.output)
    assert facts["severity"] == "blocking"
    assert facts["contradicting_invoice_count"] == "0"
    assert facts["unattested_periods"] == "1T|2T|3T|4T"
    assert facts["attestation_profile_path"] == "withholding.modelo_111_no_retenciones_periods"


def test_verify_grants_a_fully_attested_nil_190() -> None:
    """Every quarter attested and a clean ledger keeps the nil filer's path open."""
    _create_profile()
    _attest_every_quarter()
    calculation_revision_id = _calculate(_create_190_work_unit())

    verified = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )

    assert verified.exit_code == 0, verified.output
    payload = _payload(verified.output)
    assert payload["granted_verificado_completo"] is True
    facts = _finding_facts(verified.output)
    assert facts["severity"] == "warning"
    assert facts["attested_periods"] == "1T|2T|3T|4T"


def test_the_refusal_renders_in_every_supported_locale() -> None:
    """Transport facts stay stable while the operator-facing prose is translated."""
    _create_profile()
    _add_received_professional_invoice(number="F-ASESOR-2022-001", invoice_date=_QUARTERLY_INVOICE_DATES[0])
    calculation_revision_id = _calculate(_create_190_work_unit())

    rendered: dict[str, str] = {}
    for language in ("en", "es", "ca", "hu"):
        verified = invoke_cached_cli(
            ["--language", language, "app", "modelo", "work", "verify", calculation_revision_id],
        )
        assert verified.exit_code == 1, verified.output
        rendered[language] = verified.output

    assert len(set(rendered.values())) == 4
    assert "Enter them in this modelo's per-payee detail before you check it." in rendered["en"]
    assert "Regístralas en el detalle por perceptor de este modelo antes de comprobarlo." in rendered["es"]
    assert "Registra-les al detall per perceptor d'aquest model abans de comprovar-lo." in rendered["ca"]
    assert "Ellenőrzés előtt rögzítse őket a nyomtatvány kedvezményezettenkénti részletezésében." in rendered["hu"]


def test_a_partially_attested_year_is_still_refused() -> None:
    """Three attested quarters leave the fourth's percepciones unaccounted for."""
    _create_profile()
    _attest_every_quarter("2022:1T,2022:2T,2022:3T")
    calculation_revision_id = _calculate(_create_190_work_unit())

    verified = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )

    assert verified.exit_code == 1, verified.output
    facts = _finding_facts(verified.output)
    assert facts["severity"] == "blocking"
    assert facts["attested_periods"] == "1T|2T|3T"
    assert facts["unattested_periods"] == "4T"


def test_the_refused_revision_cannot_be_filed_locally() -> None:
    """The gate closes the filing path, not only the verify report."""
    _create_profile()
    _add_received_professional_invoice(number="F-ASESOR-2022-001", invoice_date=_QUARTERLY_INVOICE_DATES[0])
    calculation_revision_id = _calculate(_create_190_work_unit())
    refused = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "verify", calculation_revision_id],
    )
    assert refused.exit_code == 1, refused.output

    filed = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "file", calculation_revision_id,
            "--actor", "operator",
        ],
    )  # fmt: skip

    assert filed.exit_code != 0, filed.output
    assert json.loads(filed.output)["error"] is not None
