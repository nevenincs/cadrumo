"""A declared bien de inversión and every Modelo 303 quarter of the years around it.

The operator journey is the supported one: the purchase invoice is registered,
the purchase is added to the ledger with ``--deduction-kind domestic_investment``
and ``--investment-asset-id``, and the good is declared in the bienes-inversión
register against that ledger row. Each quarter is then calculated through
``aeat app modelo work calculate``.

The register pairs each good with exactly one acquisition row of its
acquisition year, and a quarterly return reads only its own quarter's rows. So
the good bought in the second quarter must still be provable from the first,
third and fourth, and a good bought in an earlier year must not reach into a
later year's quarters at all: LIVA art. 107 regularises it in the four years
FOLLOWING acquisition, through casilla [43] of each year's last period, which
reads the register and never the earlier year's ledger row.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from click.testing import Result

from ....adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from ....adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from ....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from ....core.bucket_pointer import resolve_active_bucket_id
from ....core.period import Period
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ....tests.cli_envelope import require_error_document, unwrap_schema_envelope
from ._m303_ordinary_cli_support import admit_ordinary_m303_secure_evidence, joint_return_options
from ._modelo_work_ux_support import operator_profile_facts
from .modelo_profile_seed import ProfileSeeder, invoke_seeded_profile_cli, seed_profile

__all__ = ["_isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_YEAR = 2025
_QUARTERS = ("1T", "2T", "3T", "4T")
_SALE_DAYS = ("02-14", "05-14", "08-14", "11-14")

# One sale a quarter, and one bien de inversión whose cuota stays below the
# quarter's devengada so no quarter carries a compensation forward.
_SALE_BASE = Decimal("10000.00")
_SALE_CUOTA = Decimal("2100.00")
#: Above the LIVA art. 108 escaso-valor threshold of 3.005,06 EUR.
_INVESTMENT_BASE = Decimal("4000.00")
_INVESTMENT_CUOTA = Decimal("840.00")
_ASSET_ID = "BI-TORNO-CNC"

_COMPENSATION_DECIDED_AT = datetime(2025, 1, 2, 10, tzinfo=UTC)


def _invoke(args: list[str]) -> Result:
    return invoke_seeded_profile_cli(["--format", "json", *args])


def _seed_operator(request: pytest.FixtureRequest, *, activity_start_date: str) -> str:
    facts = {
        fact.path: (str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value))
        for fact in MODELO_READY_PROFILE_FACTS
    }
    facts.update(operator_profile_facts(activity_start_date=activity_start_date))
    cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))(label="operator", facts=facts)
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _seed_nil_compensation(bucket_id: str) -> None:
    """Record the nil prior-period compensation every quarter asks before it calculates."""
    with open_test_profile_session(bucket_id):
        repository = IvaWalletDecisionRepository()
        for quarter in _QUARTERS:
            repository.save_decision(
                IvaCompensationReconciliationDecision(
                    taxpayer_nif="12345678Z",
                    target_year=_YEAR,
                    target_period=Period.from_year_and_code(_YEAR, quarter),
                    target_registry_snapshot_ref=published_snapshot(
                        "303", filing_year=_YEAR, period=quarter
                    ).snapshot_ref,
                    source_registry_snapshot_refs=(),
                    selected_authority="aeat_wallet",
                    selected_amount=Decimal("0.00"),
                    wallet_amount=Decimal("0.00"),
                    local_recurrence_amount=None,
                    override_amount=None,
                    divergence="match",
                    blocked=False,
                    stale_wallet=False,
                    reason_identity="first_period_zero_aeat_wallet" if quarter == "1T" else "aeat_wallet_validated",
                    wallet_captured_at=_COMPENSATION_DECIDED_AT,
                    decided_at=_COMPENSATION_DECIDED_AT,
                )
            )


def _added_transaction_id(result: Result) -> str:
    assert result.exit_code == 0, result.output
    transaction = unwrap_schema_envelope(result.output)["transaction"]
    assert isinstance(transaction, dict)
    transaction_id = transaction["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _add_quarterly_sales() -> None:
    for day in _SALE_DAYS:
        _added_transaction_id(
            _invoke(
                [
                    "app",
                    "ledger",
                    "add",
                    "--date",
                    f"{_YEAR}-{day}",
                    "--amount",
                    str(_SALE_BASE + _SALE_CUOTA),
                    "--direction",
                    "INCOMING",
                    "--description",
                    f"Factura cliente {_YEAR}-{day}",
                    "--classification",
                    "BUSINESS",
                    "--taxable-base",
                    str(_SALE_BASE),
                    "--iva-rate",
                    "0.21",
                    "--iva-amount",
                    str(_SALE_CUOTA),
                    "--iva-category",
                    "domestic_general",
                ]
            )
        )


def _minimal_pdf(text: str) -> bytes:
    """Return one syntactically minimal, synthetic PDF carrying ``text``."""
    body = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii", errors="replace")
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" + body + b"\n%%EOF\n"


def _add_investment_purchase(tmp_path: Path, *, day: str) -> str:
    document = tmp_path / "torno.pdf"
    document.write_bytes(_minimal_pdf(f"Factura torno base {_INVESTMENT_BASE} IVA {_INVESTMENT_CUOTA}"))
    registered = _invoke(
        [
            "app",
            "ledger",
            "evidence",
            "add",
            str(document),
            "--supplier",
            "Proveedor de prueba SL",
            "--invoice-number",
            f"REC-{day}-TORNO",
            "--invoice-date",
            day,
            "--taxable-base",
            str(_INVESTMENT_BASE),
            "--iva-rate",
            "0.21",
            "--iva-amount",
            str(_INVESTMENT_CUOTA),
        ]
    )
    assert registered.exit_code == 0, registered.output
    evidence_id = unwrap_schema_envelope(registered.output)["evidence_id"]
    assert isinstance(evidence_id, str)
    return _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                day,
                "--amount",
                str(_INVESTMENT_BASE + _INVESTMENT_CUOTA),
                "--direction",
                "OUTGOING",
                "--description",
                "Torno CNC",
                "--classification",
                "BUSINESS",
                "--category-id",
                "hardware_amortizable",
                "--taxable-base",
                str(_INVESTMENT_BASE),
                "--iva-rate",
                "0.21",
                "--iva-amount",
                str(_INVESTMENT_CUOTA),
                "--iva-category",
                "domestic_general",
                "--deduction-kind",
                "domestic_investment",
                "--investment-asset-id",
                _ASSET_ID,
                "--purchase-invoice-evidence-id",
                evidence_id,
            ]
        )
    )


def _declare(*, acquisition_year: int, acquisition_ledger_id: str) -> None:
    declared = _invoke(
        [
            "app",
            "ledger",
            "bienes-inversion",
            "declare",
            _ASSET_ID,
            "--description",
            "Torno CNC",
            "--acquisition-year",
            str(acquisition_year),
            "--acquisition-ledger-id",
            acquisition_ledger_id,
            "--cuota-soportada",
            str(_INVESTMENT_CUOTA),
            "--prorrata-inicial",
            "100",
            "--kind",
            "mueble",
        ]
    )
    assert declared.exit_code == 0, declared.output


def _calculate(quarter: str) -> Result:
    created = _invoke(
        ["app", "modelo", "work", "create", "--modelo", "303", "--year", str(_YEAR), "--period", quarter],
    )
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    answers = (
        admit_ordinary_m303_secure_evidence(period="4T").calculate_options()
        if quarter == "4T"
        else joint_return_options()
    )
    return _invoke(["app", "modelo", "work", "calculate", work_unit_id, *answers])


def _casilla_values(result: Result) -> dict[str, Decimal]:
    assert result.exit_code == 0, result.output
    values = unwrap_schema_envelope(result.output)["casilla_values"]
    assert isinstance(values, dict)
    return {str(key): Decimal(str(value)) for key, value in values.items()}


def test_every_quarter_of_the_acquisition_year_calculates(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """A good bought in 2T leaves 1T, 3T and 4T calculating, and only 2T declares it."""
    bucket_id = _seed_operator(request, activity_start_date=f"{_YEAR}-01-01")
    _seed_nil_compensation(bucket_id)
    _add_quarterly_sales()
    _declare(
        acquisition_year=_YEAR,
        acquisition_ledger_id=_add_investment_purchase(tmp_path, day=f"{_YEAR}-05-20"),
    )

    values = {quarter: _casilla_values(_calculate(quarter)) for quarter in _QUARTERS}

    for quarter, quarter_values in values.items():
        # Every quarter devengó its own sale: 10.000 of base, 2.100 of cuota.
        assert quarter_values["07"] == _SALE_BASE, quarter
        assert quarter_values["iva.repercutido.general"] == _SALE_CUOTA, quarter
        # The acquisition year regularises nothing under LIVA art. 107.Uno.
        assert quarter_values["43"] == Decimal("0"), quarter
    # Bienes de inversión interiores [30]/[31]: the torno, in its own quarter only.
    assert values["2T"]["30"] == _INVESTMENT_BASE
    assert values["2T"]["31"] == _INVESTMENT_CUOTA
    for quarter in ("1T", "3T", "4T"):
        assert values[quarter]["30"] == Decimal("0"), quarter
        assert values[quarter]["31"] == Decimal("0"), quarter
    # 2T: 2.100 devengada less the 840 deducible; every other quarter keeps its 2.100.
    assert values["2T"]["iva.resultado-regimen-general"] == _SALE_CUOTA - _INVESTMENT_CUOTA
    for quarter in ("1T", "3T", "4T"):
        assert values[quarter]["iva.resultado-regimen-general"] == _SALE_CUOTA, quarter


def test_a_record_naming_no_ledger_row_refuses_the_quarters_of_its_year(
    request: pytest.FixtureRequest,
) -> None:
    """The register cannot claim a good the ledger never bought, in any quarter of the year."""
    bucket_id = _seed_operator(request, activity_start_date=f"{_YEAR}-01-01")
    _seed_nil_compensation(bucket_id)
    _add_quarterly_sales()
    _declare(
        acquisition_year=_YEAR,
        acquisition_ledger_id=hashlib.sha256(b"no ledger row carries this id").hexdigest(),
    )

    for quarter in ("1T", "3T"):
        refused = _calculate(quarter)

        assert refused.exit_code == 2, refused.output
        error = require_error_document(refused.output)["error"]
        assert isinstance(error, dict)
        assert error["code"] == "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION", quarter
        assert error["message"] == "A capital-goods IVA regularisation record failed validation.", quarter
        assert error["context"]["investment_asset_ids"] == _ASSET_ID, quarter


def test_a_good_acquired_in_an_earlier_year_leaves_every_later_quarter_calculating(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """A 2024 good is inside its art. 107 window in 2025 and still breaks none of its quarters.

    Its reciprocity belongs to 2024. In 2025 the register feeds only the 4T
    regularización, and with the initial 100 % prorrata unchanged the proposed
    casilla [43] is zero.
    """
    bucket_id = _seed_operator(request, activity_start_date=f"{_YEAR - 1}-01-01")
    _seed_nil_compensation(bucket_id)
    _declare(
        acquisition_year=_YEAR - 1,
        acquisition_ledger_id=_add_investment_purchase(tmp_path, day=f"{_YEAR - 1}-05-20"),
    )
    _add_quarterly_sales()

    values = {quarter: _casilla_values(_calculate(quarter)) for quarter in _QUARTERS}

    for quarter, quarter_values in values.items():
        assert quarter_values["07"] == _SALE_BASE, quarter
        assert quarter_values["31"] == Decimal("0"), quarter
        assert quarter_values["iva.resultado-regimen-general"] == _SALE_CUOTA, quarter
    assert values["4T"]["43"] == Decimal("0")
