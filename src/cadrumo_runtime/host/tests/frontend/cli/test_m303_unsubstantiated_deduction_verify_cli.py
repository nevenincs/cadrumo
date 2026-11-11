"""Real CLI journey for a 2025 1T Modelo 303 whose deduction row is held back.

The IVA calculation holds back a received row whose input deduction carries no
evidence: the whole row, so an intra-EU acquisition loses its accrued cuota as
well as its deduction. ``work verify`` must then refuse the revision with a
worded blocking finding rather than fail internally, and export must refuse it.

Rows reach that state through the live ``aeat app ledger add`` parser:

* an intra-EU acquisition declared as ``intra_eu_current`` with no supplier
  invoice linked, and a domestic purchase declared as ``domestic_current`` with
  no purchase-invoice record linked, both of which the filer can repair by
  attaching the supplier's invoice, so they keep the general evidence finding;
* an import, a REAGP compensation and a rectification, whose documents no
  ledger write can record, so each is refused terminally under its own entry.

Attaching the supplier's invoice to the intra-EU acquisition lets the quarter
calculate its self-assessed cuota and deduct it in the same return
(LIVA art. 97.Uno.2.º).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.cli.tests.ordinary_m303_scenarios import joint_return_options
from cadrumo.tests.cli_envelope import require_error_document, unwrap_envelope_notices, unwrap_schema_envelope

from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile
from .test_m303_zero_cuota_and_investment_inputs_cli import (
    add_sale,
    added_transaction_id,
    profile_facts,
    register_purchase_invoice_evidence,
    seed_zero_compensation_wallet_decision,
)

__all__ = ["isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_YEAR = filing_year_envelope().horizon
_OPERATION_DATE = date(_YEAR, 2, 15).isoformat()
_BASE = Decimal("200.00")
_CUOTA = Decimal("42.00")
_EVIDENCE_CONDITION = "modelo.work.verify.iva_selected_scope_evidence.complete"
#: A missing supplier invoice is the filer's to attach.
_GENERAL_FINDING = "operator_decision"


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(["--format", "json", *args])


def _seed_quarter(request: pytest.FixtureRequest) -> None:
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    seed_zero_compensation_wallet_decision(bucket_id)
    add_sale()


def _add_intra_eu_acquisition(*evidence_options: str) -> str:
    """An acquisition from a French supplier, self-assessed under reverse charge.

    The movement is the base alone: the supplier invoices no Spanish IVA, the
    buyer accrues and deducts the cuota itself.
    """
    return added_transaction_id(
        _invoke(
            [
                "app", "ledger", "add",
                "--date", _OPERATION_DATE,
                "--amount", str(_BASE),
                "--direction", "OUTGOING",
                "--description", "Compra intracomunitaria",
                "--classification", "BUSINESS",
                "--category-id", "material_oficina",
                "--taxable-base", str(_BASE),
                "--iva-rate", "0.21",
                "--iva-amount", str(_CUOTA),
                "--iva-category", "intra_community_acquisition_reverse_charge",
                "--deduction-kind", "intra_eu_current",
                "--counterparty-country", "FR",
                *evidence_options,
            ],
        )
    )  # fmt: skip


def _add_purchase_without_invoice() -> str:
    """A domestic purchase claiming its deduction with no purchase invoice linked."""
    return added_transaction_id(
        _invoke(
            [
                "app", "ledger", "add",
                "--date", _OPERATION_DATE,
                "--amount", str(_BASE + _CUOTA),
                "--direction", "OUTGOING",
                "--description", "Material de oficina",
                "--classification", "BUSINESS",
                "--category-id", "material_oficina",
                "--taxable-base", str(_BASE),
                "--iva-rate", "0.21",
                "--iva-amount", str(_CUOTA),
                "--iva-category", "domestic_general",
                "--deduction-kind", "domestic_current",
            ],
        )
    )  # fmt: skip


def _calculate_1t() -> tuple[str, str]:
    created = _invoke(["app", "modelo", "work", "create", "--modelo", "303", "--year", str(_YEAR), "--period", "1T"])
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    calculated = _invoke(["app", "modelo", "work", "calculate", work_unit_id, *joint_return_options()])
    assert calculated.exit_code == 0, calculated.output
    calculation_revision_id = unwrap_schema_envelope(calculated.output)["calculation_revision_id"]
    assert isinstance(calculation_revision_id, str)
    return work_unit_id, calculation_revision_id


def _evidence_findings(output: str) -> dict[str, dict[str, str]]:
    """Return every held-back-row finding by exact subject, with its locale-neutral facts.

    The payload carries each finding's typed recovery verdict and the notice its
    facts, both in report order. Only findings failing the selected-scope
    evidence condition are kept, so an unrelated blocker cannot satisfy the test.
    """
    findings = unwrap_schema_envelope(output)["findings"]
    assert isinstance(findings, list)
    notices = [
        notice
        for notice in unwrap_envelope_notices(output)
        if str(notice["code"]).startswith("modelo.work.verify.finding.")
    ]
    selected: dict[str, dict[str, str]] = {}
    for finding, notice in zip(findings, notices, strict=True):
        action = finding["action"]
        if finding["severity"] != "blocking" or action is None:
            continue
        if action["failed_condition_id"] != _EVIDENCE_CONDITION:
            continue
        outcome = str(action["no_recovery_outcome"])
        context = STR_KEYED_MAPPING_ADAPTER.validate_python(notice["context"])
        facts = {key: str(value) for key, value in context.items()}
        facts["recovery_outcome"] = outcome
        subject = facts.get("transaction_ids", facts.get("source_ref_ids", "unidentified"))
        assert subject not in selected, output
        selected[subject] = facts
    return selected


def _assert_verify_refuses(calculation_revision_id: str) -> dict[str, dict[str, str]]:
    verified = _invoke(["app", "modelo", "work", "verify", calculation_revision_id])

    assert verified.exit_code == 1, verified.output
    assert "INTERNAL_CLI_UNEXPECTED_BOUNDARY" not in verified.output
    assert unwrap_schema_envelope(verified.output)["granted_verificado_completo"] is False
    return _evidence_findings(verified.output)


def _assert_export_refuses(work_unit_id: str, tmp_path: Path) -> None:
    artefact = tmp_path / "m303-2025-1t.txt"
    exported = _invoke(["app", "modelo", "export", work_unit_id, "--output", str(artefact)])

    assert exported.exit_code != 0, exported.output
    assert require_error_document(exported.output)["error"] is not None
    assert not artefact.exists()


def test_verify_refuses_an_intra_eu_acquisition_without_its_invoice_with_the_general_finding(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """The supplier's invoice is the filer's to attach, so the refusal is not terminal."""
    _seed_quarter(request)
    acquisition = _add_intra_eu_acquisition()
    work_unit_id, calculation_revision_id = _calculate_1t()

    findings = _assert_verify_refuses(calculation_revision_id)

    assert set(findings) == {f"transaction:{acquisition}"}, findings
    assert findings[f"transaction:{acquisition}"]["recovery_outcome"] == _GENERAL_FINDING
    _assert_export_refuses(work_unit_id, tmp_path)


def test_the_supplier_invoice_lets_the_intra_eu_acquisition_accrue_and_deduct_its_cuota(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """LIVA art. 97.Uno.2.º: the supplier's invoice justifies the deduction of the cuota the same return accrues."""
    _seed_quarter(request)
    evidence_id = register_purchase_invoice_evidence(tmp_path, label="intracomunitaria", base=_BASE, cuota=_CUOTA)
    _add_intra_eu_acquisition("--purchase-invoice-evidence-id", evidence_id)
    created = _invoke(["app", "modelo", "work", "create", "--modelo", "303", "--year", str(_YEAR), "--period", "1T"])
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    calculated = _invoke(["app", "modelo", "work", "calculate", work_unit_id, *joint_return_options()])
    assert calculated.exit_code == 0, calculated.output
    payload = unwrap_schema_envelope(calculated.output)
    calculation_revision_id = payload["calculation_revision_id"]
    assert isinstance(calculation_revision_id, str)
    values = payload["casilla_values"]
    assert isinstance(values, dict)
    # Devengado by the buyer [10]/[11] and deducted in the same return [36]/[37].
    assert Decimal(str(values["10"])) == _BASE
    assert Decimal(str(values["11"])) == _CUOTA
    assert Decimal(str(values["36"])) == _BASE
    assert Decimal(str(values["37"])) == _CUOTA
    verified = _invoke(["app", "modelo", "work", "verify", calculation_revision_id])
    assert "INTERNAL_CLI_UNEXPECTED_BOUNDARY" not in verified.output
    assert _evidence_findings(verified.output) == {}, verified.output


def test_verify_refuses_a_deduction_without_its_invoice_with_the_general_finding(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """A missing invoice is still the filer's to attach, so it keeps the general evidence finding."""
    _seed_quarter(request)
    purchase = _add_purchase_without_invoice()
    work_unit_id, calculation_revision_id = _calculate_1t()

    findings = _assert_verify_refuses(calculation_revision_id)

    assert set(findings) == {f"transaction:{purchase}"}, findings
    assert findings[f"transaction:{purchase}"]["recovery_outcome"] == _GENERAL_FINDING
    assert findings[f"transaction:{purchase}"]["source_ref_ids"] == f"transaction:{purchase}"
    _assert_export_refuses(work_unit_id, tmp_path)


def test_both_held_back_rows_are_named_by_the_general_finding(request: pytest.FixtureRequest) -> None:
    """Both rows lack the supplier's invoice, so one general finding names each of them."""
    _seed_quarter(request)
    acquisition = _add_intra_eu_acquisition()
    purchase = _add_purchase_without_invoice()
    _work_unit_id, calculation_revision_id = _calculate_1t()

    findings = _assert_verify_refuses(calculation_revision_id)

    assert len(findings) == 1, findings
    ((subject, facts),) = findings.items()
    assert facts["recovery_outcome"] == _GENERAL_FINDING
    assert set(subject.split("|")) == {f"transaction:{acquisition}", f"transaction:{purchase}"}


@pytest.mark.parametrize(
    ("category", "kind", "rate", "quota", "gross", "country", "authority"),
    [
        ("import_third_country", "import_current", "0.21", "42.00", "200.00", "US", "customs_declaration"),
        ("reagp_compensation", "reagp_compensation", "0", "24.00", "224.00", "ES", "reagp_receipt"),
        ("domestic_general", "rectification", "0.21", "42.00", "242.00", "ES", "rectification_evidence"),
    ],
)
def test_each_unrecordable_supporting_document_has_its_own_terminal_finding(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    category: str,
    kind: str,
    rate: str,
    quota: str,
    gross: str,
    country: str,
    authority: str,
) -> None:
    """Equal-looking entries remain two distinct blocked documents after real persistence."""
    _seed_quarter(request)
    transactions = tuple(
        added_transaction_id(
            _invoke(
                [
                    "app",
                    "ledger",
                    "add",
                    "--date",
                    _OPERATION_DATE,
                    "--amount",
                    gross,
                    "--direction",
                    "OUTGOING",
                    "--description",
                    f"Supporting entry {index}",
                    "--classification",
                    "BUSINESS",
                    "--category-id",
                    "material_oficina",
                    "--taxable-base",
                    "200.00",
                    "--iva-rate",
                    rate,
                    "--iva-amount",
                    quota,
                    "--iva-category",
                    category,
                    "--deduction-kind",
                    kind,
                    "--counterparty-country",
                    country,
                ]
            )
        )
        for index in (1, 2)
    )
    work_unit_id, revision_id = _calculate_1t()
    findings = _assert_verify_refuses(revision_id)
    assert set(findings) == set(transactions), findings
    for transaction in transactions:
        facts = findings[transaction]
        assert facts["recovery_outcome"] == "terminal"
        assert facts["transaction_count"] == "1"
        assert facts["transaction_ids"] == transaction
        assert facts["transaction_date"] == _OPERATION_DATE
        assert Decimal(facts["transaction_amount"]) == Decimal(gross)
        assert facts["transaction_currency"] == "EUR"
        assert facts["required_evidence_authority"] == authority
    _assert_export_refuses(work_unit_id, tmp_path)
