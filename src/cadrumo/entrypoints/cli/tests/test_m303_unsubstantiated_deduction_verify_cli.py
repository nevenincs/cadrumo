"""Real CLI journey for a 2025 1T Modelo 303 whose deduction row is held back.

The IVA calculation holds back a received row whose input deduction carries no
evidence: the whole row, so an intra-EU acquisition loses its accrued cuota as
well as its deduction. ``work verify`` must then refuse the revision with a
worded blocking finding rather than fail internally, and export must refuse it.

Two rows reach that state through the live ``aeat app ledger add`` parser:

* an intra-EU acquisition declared as ``intra_eu_current``, whose deduction is
  established only by the intra-EU self-assessment, a document no ledger write
  can record, so the refusal tells the filer to file the period another way;
* a domestic purchase declared as ``domestic_current`` with no purchase-invoice
  record linked, which the filer can still repair, so it keeps the general
  evidence finding.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.type_adapters import STR_KEYED_MAPPING_ADAPTER
from ....tests.cli_envelope import require_error_document, unwrap_envelope_notices, unwrap_schema_envelope
from ._m303_ordinary_cli_support import joint_return_options
from .modelo_profile_seed import ProfileSeeder, invoke_seeded_profile_cli, seed_profile
from .test_m303_zero_cuota_and_investment_inputs_cli import (
    _add_sale,
    _added_transaction_id,
    _profile_facts,
    _seed_zero_compensation_wallet_decision,
)

__all__ = ["_isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_OPERATION_DATE = "2025-02-15"
_BASE = Decimal("200.00")
_CUOTA = Decimal("42.00")
_EVIDENCE_CONDITION = "modelo.work.verify.iva_selected_scope_evidence.complete"
#: Nothing inside the product records an intra-EU self-assessment, so that
#: refusal is terminal; a missing invoice is the filer's to attach.
_INTRA_EU_FINDING = "terminal"
_GENERAL_FINDING = "operator_decision"


def _invoke(args: list[str]) -> Result:
    return invoke_seeded_profile_cli(["--format", "json", *args])


def _seed_quarter(request: pytest.FixtureRequest) -> None:
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_zero_compensation_wallet_decision(bucket_id)
    _add_sale()


def _add_intra_eu_acquisition() -> str:
    """An acquisition from a French supplier, self-assessed under reverse charge.

    The movement is the base alone: the supplier invoices no Spanish IVA, the
    buyer accrues and deducts the cuota itself.
    """
    return _added_transaction_id(
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
            ],
        )
    )  # fmt: skip


def _add_purchase_without_invoice() -> str:
    """A domestic purchase claiming its deduction with no purchase invoice linked."""
    return _added_transaction_id(
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
    created = _invoke(["app", "modelo", "work", "create", "--modelo", "303", "--year", "2025", "--period", "1T"])
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


def test_verify_refuses_an_intra_eu_acquisition_with_a_worded_refusal(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """The self-assessment cannot be recorded, so the refusal names that and sends the filer elsewhere."""
    _seed_quarter(request)
    acquisition = _add_intra_eu_acquisition()
    work_unit_id, calculation_revision_id = _calculate_1t()

    findings = _assert_verify_refuses(calculation_revision_id)

    assert set(findings) == {acquisition}, findings
    assert findings[acquisition]["recovery_outcome"] == _INTRA_EU_FINDING
    assert findings[acquisition]["transaction_count"] == "1"
    assert findings[acquisition]["transaction_ids"] == acquisition
    _assert_export_refuses(work_unit_id, tmp_path)


def test_the_intra_eu_refusal_renders_in_every_supported_locale(request: pytest.FixtureRequest) -> None:
    """Each locale tells the filer the document cannot be recorded and to file another way."""
    _seed_quarter(request)
    _add_intra_eu_acquisition()
    _work_unit_id, calculation_revision_id = _calculate_1t()

    rendered: dict[str, str] = {}
    for language in ("en", "es", "ca", "hu"):
        verified = invoke_seeded_profile_cli(
            ["--language", language, "app", "modelo", "work", "verify", calculation_revision_id],
        )
        assert verified.exit_code == 1, verified.output
        rendered[language] = verified.output

    assert "self-assessment document for an intra-EU purchase" in rendered["en"]
    assert "File this declaration another way." in rendered["en"]
    assert "adquisición intracomunitaria" in rendered["es"]
    assert "Presenta esta declaración por otra vía." in rendered["es"]
    assert "adquisició intracomunitària" in rendered["ca"]
    assert "per una altra via." in rendered["ca"]
    assert "közösségen belüli beszerzés önadózási bizonylata" in rendered["hu"]
    assert "Nyújtsd be ezt a bevallást más módon." in rendered["hu"]


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


def test_both_held_back_rows_are_refused_each_under_its_own_finding(request: pytest.FixtureRequest) -> None:
    """The intra-EU row is lifted out of the general finding, not reported twice."""
    _seed_quarter(request)
    acquisition = _add_intra_eu_acquisition()
    purchase = _add_purchase_without_invoice()
    _work_unit_id, calculation_revision_id = _calculate_1t()

    findings = _assert_verify_refuses(calculation_revision_id)

    assert set(findings) == {acquisition, f"transaction:{purchase}"}, findings
    assert findings[acquisition]["recovery_outcome"] == _INTRA_EU_FINDING
    assert findings[acquisition]["transaction_ids"] == acquisition
    assert findings[f"transaction:{purchase}"]["recovery_outcome"] == _GENERAL_FINDING
    assert findings[f"transaction:{purchase}"]["source_ref_ids"] == f"transaction:{purchase}"


@pytest.mark.parametrize(
    ("category", "kind", "rate", "quota", "gross", "country", "authority"),
    [
        (
            "intra_community_acquisition_reverse_charge",
            "intra_eu_current",
            "0.21",
            "42.00",
            "200.00",
            "FR",
            "intra_eu_self_assessment",
        ),
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
        _added_transaction_id(
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
