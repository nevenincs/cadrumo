"""An in-year machine purchase deducts its amortization charge, never its price.

The whole flow runs through the live command tree: the purchase is added with
``aeat app ledger add``, the asset is registered against that transaction with
``aeat app ledger actividad-asset create``, its 2025 charge is forecast and
claimed, and the Modelo 303, 130, and 100 figures are read from
``aeat app modelo work calculate``.

Every expected figure below is computed from the purchase and the governing
coefficient, not from a prior run:

- 1.000,00 base plus 21 % IVA soportado = 1.210,00 paid from the bank.
- Maquinaria carries a 12 % maximum linear coefficient (LIS art. 12.1.a), so the
  full-year charge on the 1.000,00 amortizable base (RIS art. 3.2) is 120,00.
- The machine enters service on 2025-04-05, so 2025 covers 271 of 365 service
  days: 120,00 x 271 / 365 = 89,0958... = 89,10 to the cent.
- Modelo 303 2T deducts the 210,00 input cuota on its 1.000,00 base.
- Modelo 130 2T deducts nothing yet: the 2025 charge is not covered until the
  year closes, and the 1.000,00 purchase is not an expense of the period.
- Modelo 130 4T and Modelo 100 deduct 89,10, once each.

The purchase carries the ``hardware_amortizable`` category the ledger preflight
requires of every deductible-expense row; the register owns the asset, so that
row's own depreciation route yields to the register instead of declaring the
purchase price at the amortization casilla.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....core.period import Period
from ....core.storage_taxonomy import StorageCategory
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import unwrap_schema_envelope
from ....tests.pdf_fixtures import text_pdf_bytes
from ....tests.storage_scope import storage_overrides
from ._m303_ordinary_cli_support import joint_return_options
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET_ID = "00000000-0000-4000-8000-000000000461"
_T0 = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
_ACQUIRED_ON = date(2025, 4, 5)
_ASSET_ID = "machine-2025"

_BASE = Decimal("1000.00")
_IVA = Decimal("210.00")
_PAID = Decimal("1210.00")

#: LIS art. 12.1.a table, "Maquinaria": 12 % maximum linear coefficient.
_MACHINERY_LINEAR_COEFFICIENT = Decimal("0.12")
#: 2025-04-05 through 2025-12-31 inclusive: 26 + 31 + 30 + 31 + 31 + 30 + 31 + 30 + 31.
_SERVICE_DAYS_2025 = Decimal("271")
_DAYS_IN_2025 = Decimal("365")
_CHARGE_2025 = (_BASE * _MACHINERY_LINEAR_COEFFICIENT * _SERVICE_DAYS_2025 / _DAYS_IN_2025).quantize(
    Decimal("0.01"),
    rounding=ROUND_HALF_UP,
)


#: The annual declaration's own answers: the declarant, the estimación-directa
#: modality, and the carried figures a first filing year has none of.
_M100_ANNUAL_ANSWERS = (
    "--casilla",
    "0001=declarante",
    "--casilla",
    "0165=declarante",
    "--casilla",
    "0166=A05",
    "--binding",
    "renta-modelo-100-estimacion-directa-es-normal=1",
    "--binding",
    "renta-certificado-trabajo-retenciones=0",
    "--binding",
    "renta-base-liquidable-negativa-general-anterior=0",
)

#: No earlier Modelo 130 was filed, so the carried prior-payment figure is zero.
_NO_PRIOR_PAGOS_FRACCIONADOS = ("--binding", "modelo-130-pagos-fraccionados-anteriores=0.00")


def _prepare_cli_directories(tmp_path: Path) -> None:
    for directory in storage_overrides(
        tmp_path,
        StorageCategory.SECRETS,
        StorageCategory.TOKENS,
        StorageCategory.RUNS,
        StorageCategory.DRAFTS,
        StorageCategory.FINANCIAL_TRANSACTIONS,
        StorageCategory.INVOICES,
    ).values():
        directory.mkdir(parents=True, exist_ok=True)


def _seed_ready_profile(root: Path) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Autonoma"),
                UserProfileFact(path="identity.surnames", value="Sintetica"),
                UserProfileFact(path="activities.description", value="taller mecanico sintetico"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(
                    path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                    value=False,
                ),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_taxpayer.sex", value="M"),
                UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                UserProfileFact(path="withholding.colegio_concertado", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
        root=root,
        label="register-owned acquisition",
    )


def _seed_zero_iva_compensation_decision(profile: TestRuntimeProfile) -> None:
    """Record the canonical zero prior-compensation decision the 2T Modelo 303 asks for.

    The machine purchase is the subject here, not the wallet reconciliation: the
    activity has no prior Modelo 303 compensation to carry, and the calculation
    refuses to guess that. Declaring it zero is the same answer the operator
    would give through the wallet workflow.
    """
    period = Period.from_year_and_code(2025, "2T")
    IvaWalletDecisionRepository(objects=profile.repository).save_decision(
        IvaCompensationReconciliationDecision(
            taxpayer_nif="12345678Z",
            target_year=2025,
            target_period=period,
            target_registry_snapshot_ref=published_snapshot("303", filing_year=2025, period="2T").snapshot_ref,
            source_registry_snapshot_refs=(),
            selected_authority="aeat_wallet",
            selected_amount=Decimal("0.00"),
            wallet_amount=Decimal("0.00"),
            local_recurrence_amount=None,
            override_amount=None,
            divergence="match",
            blocked=False,
            stale_wallet=False,
            reason_identity="first_period_zero_aeat_wallet",
            wallet_captured_at=_T0,
            decided_at=_T0,
        ),
    )


def _result(arguments: list[str]) -> dict[str, Any]:
    invoked = invoke_cached_cli(["--format", "json", *arguments])
    assert invoked.exit_code == 0, invoked.output
    payload = unwrap_schema_envelope(invoked.output)
    assert isinstance(payload, dict)
    return payload


def _add_supplier_invoice_evidence(tmp_path: Path, *, invoice_number: str = "MAQ-2025-0001") -> str:
    """Register the supplier invoice the input-IVA deduction rests on.

    LIVA art. 97 makes the invoice the deduction's justificante, and the ledger
    refuses a deduction classification with no immutable evidence behind it, so
    the document is registered before the payment references it.
    """
    document = tmp_path / f"factura-{invoice_number}.pdf"
    document.write_bytes(
        text_pdf_bytes(
            (
                "Maquinaria Sintetica SL",
                f"Factura {invoice_number}",
                "Base imponible 1.000,00",
                "IVA 21% 210,00",
                "Total 1.210,00",
            ),
        ),
    )
    payload = _result(
        [
            "app",
            "ledger",
            "evidence",
            "add",
            str(document),
            "--supplier",
            "Maquinaria Sintetica SL",
            "--invoice-number",
            invoice_number,
            "--invoice-date",
            _ACQUIRED_ON.isoformat(),
            "--taxable-base",
            str(_BASE),
            "--iva-rate",
            "0.21",
            "--iva-amount",
            str(_IVA),
        ],
    )
    evidence_id = payload.get("evidence_id")
    assert isinstance(evidence_id, str), payload
    return evidence_id


def _add_machine_purchase(
    evidence_id: str,
    *,
    category_id: str = "hardware_amortizable",
    description: str = "Compra de maquinaria",
) -> str:
    """Record the bank payment of the machine, with its deductible input IVA."""
    payload = _result(
        [
            "app",
            "ledger",
            "add",
            "--date",
            _ACQUIRED_ON.isoformat(),
            "--amount",
            str(_PAID),
            "--direction",
            "OUTGOING",
            "--description",
            description,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            str(_BASE),
            "--iva-rate",
            "0.21",
            "--iva-amount",
            str(_IVA),
            "--iva-category",
            "domestic_general",
            "--deduction-kind",
            "domestic_current",
            "--category-id",
            category_id,
            "--purchase-invoice-evidence-id",
            evidence_id,
        ],
    )
    transaction = payload.get("transaction")
    assert isinstance(transaction, dict), payload
    transaction_id = transaction.get("transaction_id")
    assert isinstance(transaction_id, str)
    return transaction_id


def _register_machine(transaction_id: str) -> None:
    revision = json.dumps(
        {
            "asset_id": _ASSET_ID,
            "revision_number": 1,
            "acquisition": {
                "observed_transaction_id": transaction_id,
                "invoice_evidence_id": "factura-maquinaria-2025",
                "evidence_fingerprint": "b" * 64,
            },
            "acquisition_shape": "primary_purchase",
            "asset_kind": "material",
            "basis": {
                "stage": "business_allocated",
                "basis_amount": str(_BASE),
                "prior_allocation_provenance": "compra afecta al 100% a la actividad",
            },
            "in_service_date": _ACQUIRED_ON.isoformat(),
            "opening_history": {"status": "known", "accumulated_amount": "0.00"},
            "acquired_condition": "new",
            "amortization": {
                "regime": "normal",
                "method": "linear",
                "authority_class_key": "maquinaria",
            },
        },
        separators=(",", ":"),
    )
    created = _result(["app", "ledger", "actividad-asset", "create", revision])
    revisions = created.get("revisions")
    assert isinstance(revisions, list)
    assert revisions[0]["asset_id"] == _ASSET_ID


def _claim_2025_charge() -> Decimal:
    forecast = _result(
        [
            "app",
            "ledger",
            "actividad-asset",
            "forecast",
            _ASSET_ID,
            "--covered-from",
            _ACQUIRED_ON.isoformat(),
            "--covered-until",
            "2026-01-01",
        ],
    )
    forecast_amount = Decimal(str(forecast["amount"]))
    claimed = _result(
        [
            "app",
            "ledger",
            "actividad-asset",
            "claim",
            json.dumps(forecast, separators=(",", ":")),
            "--creating-operation",
            "cli.register-owned-acquisition.claim",
        ],
    )
    claim = claimed.get("claim")
    assert isinstance(claim, dict)
    assert Decimal(str(claim["amount"])) == forecast_amount
    return forecast_amount


def _calculated_casillas(*, modelo: str, period: str, options: tuple[str, ...] = ()) -> dict[str, str]:
    created = _result(
        ["app", "modelo", "work", "create", "--modelo", modelo, "--year", "2025", "--period", period],
    )
    assert created
    calculated = _result(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            "--modelo",
            modelo,
            "--year",
            "2025",
            "--period",
            period,
            "--by",
            "Autonoma",
            *options,
        ],
    )
    values = calculated["casilla_values"]
    assert isinstance(values, dict)
    return {str(key): str(value) for key, value in values.items()}


def test_register_owned_acquisition_deducts_the_charge_and_keeps_its_input_iva(tmp_path: Path) -> None:
    """The supported route: ledger purchase plus register claim, with no collision."""
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="asset acquisition") as profile:
        _seed_ready_profile(profile.storage_root)
        _seed_zero_iva_compensation_decision(profile)
        transaction_id = _add_machine_purchase(_add_supplier_invoice_evidence(tmp_path))
        _register_machine(transaction_id)
        charge = _claim_2025_charge()

        iva_q2 = _calculated_casillas(modelo="303", period="2T", options=joint_return_options())
        renta_q2 = _calculated_casillas(modelo="130", period="2T", options=_NO_PRIOR_PAGOS_FRACCIONADOS)
        renta_q4 = _calculated_casillas(modelo="130", period="4T", options=_NO_PRIOR_PAGOS_FRACCIONADOS)
        annual = _calculated_casillas(modelo="100", period="0A", options=_M100_ANNUAL_ANSWERS)

    assert charge == _CHARGE_2025 == Decimal("89.10")

    # Modelo 303 still deducts the input cuota: the register owns the IRPF
    # treatment of the purchase, never its IVA.
    assert Decimal(iva_q2["28"]) == _BASE
    assert Decimal(iva_q2["iva.soportado.interiores"]) == _IVA

    # The 1.000,00 purchase is the amortizable base, so no quarter deducts it;
    # the second quarter's cumulative gasto is nothing at all.
    assert Decimal(renta_q2["02"]) == Decimal("0")
    assert Decimal(renta_q4["02"]) == charge
    assert Decimal(annual["0208"]) == charge
    assert Decimal(_BASE) not in {Decimal(value) for value in annual.values()}


def test_a_separate_depreciation_row_still_refuses_the_calculation(tmp_path: Path) -> None:
    """The collision the register exists to prevent is still a refusal, not a sum.

    The same store gains a second ledger row tagged with an amortization
    category. The register already charges 2025 and owns the amortization
    destinations exclusively, so declaring that row's amount as well would
    deduct the year's depreciation twice. Both the quarterly and the annual
    calculation refuse and name what to reclassify or reverse.
    """
    _prepare_cli_directories(tmp_path)
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="asset collision") as profile:
        _seed_ready_profile(profile.storage_root)
        transaction_id = _add_machine_purchase(_add_supplier_invoice_evidence(tmp_path))
        _register_machine(transaction_id)
        _claim_2025_charge()
        _add_machine_purchase(
            _add_supplier_invoice_evidence(tmp_path, invoice_number="MOB-2025-0002"),
            category_id="mobiliario_amortizable",
            description="Amortizacion de mobiliario declarada en el libro",
        )

        refused_quarter = invoke_cached_cli(
            [
                *("--format", "json", "app", "modelo", "work", "create"),
                *("--modelo", "130", "--year", "2025", "--period", "4T"),
            ],
        )
        assert refused_quarter.exit_code == 0, refused_quarter.output
        refused_quarter = invoke_cached_cli(
            [
                *("--format", "json", "app", "modelo", "work", "calculate"),
                *("--modelo", "130", "--year", "2025", "--period", "4T"),
                *("--by", "Autonoma"),
                *_NO_PRIOR_PAGOS_FRACCIONADOS,
            ],
        )

    assert refused_quarter.exit_code != 0, refused_quarter.output
    assert "competing transaction-ledger depreciation treatment" in refused_quarter.output
    assert _ASSET_ID in refused_quarter.output
    assert "mobiliario_amortizable" in refused_quarter.output
