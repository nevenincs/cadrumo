"""Real CLI journey for the three purchase kinds a 2025 1T Modelo 303 could not carry.

Every row here is authored through the live ``aeat app ledger`` parser and the
quarter is calculated through ``aeat app modelo work calculate``, so the
assertions are about what an operator can actually file.

* A monthly RETA quota is a Social Security contribution: LIVA art. 7 places it
  outside the taxable event, and LIRPF art. 30 deducts it. It bore no cuota, so
  it declares a base and nothing else.
* An insurance premium is exempt under LIVA art. 20.Uno.16, so it likewise bore
  no cuota to deduct.
* A bien de inversión above the LIVA art. 108 threshold deducts its cuota against
  a reciprocal bienes-inversión register record, which the row names through
  ``--investment-asset-id``.

The casilla arithmetic is stated in the assertions rather than read from the
implementation, and the two zero-cuota rows are asserted to reach no Modelo 303
box: the form has none for an exempt or non-subject acquisition, so their bases
belong on the annual resumen and on the IRPF expense side, not here.
"""

from __future__ import annotations

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
from ....tests.cli_envelope import (
    require_error_document,
    unwrap_envelope_notices,
    unwrap_schema_envelope,
)
from ._m303_ordinary_cli_support import joint_return_options
from ._modelo_work_ux_support import operator_profile_facts
from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["_isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_PERIOD = Period.from_year_and_code(2025, "1T")
_WALLET_DECIDED_AT = datetime(2025, 4, 1, 10, tzinfo=UTC)
_OPERATION_DATE = "2025-02-15"

# One taxable sale, one ordinary taxable purchase, one bien de inversión, and the
# two rows that bore no cuota. Every gross reconstitutes base plus cuota, which
# the ledger enforces.
_SALE_BASE = Decimal("1000.00")
_SALE_CUOTA = Decimal("210.00")
_PURCHASE_BASE = Decimal("200.00")
_PURCHASE_CUOTA = Decimal("42.00")
#: Above the LIVA art. 108 escaso-valor threshold of 3.005,06 EUR.
_INVESTMENT_BASE = Decimal("4000.00")
_INVESTMENT_CUOTA = Decimal("840.00")
_RETA_QUOTA = Decimal("314.40")
_PREMIUM = Decimal("240.00")

_INVESTMENT_ASSET_ID = "BI-2025-ORDENADOR"


def _profile_facts() -> dict[str, str]:
    facts = {
        fact.path: (str(fact.value).lower() if isinstance(fact.value, bool) else str(fact.value))
        for fact in MODELO_READY_PROFILE_FACTS
    }
    facts.update(operator_profile_facts(activity_start_date="2025-01-01"))
    return facts


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(["--format", "json", *args])


def _added_transaction_id(result: Result) -> str:
    assert result.exit_code == 0, result.output
    payload = unwrap_schema_envelope(result.output)
    transaction = payload["transaction"]
    assert isinstance(transaction, dict)
    transaction_id = transaction["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _seed_zero_compensation_wallet_decision(bucket_id: str) -> None:
    """Record the first-period nil compensation decision 303 asks before calculating."""
    snapshot_ref = published_snapshot("303", filing_year=2025, period="1T").snapshot_ref
    with open_test_profile_session(bucket_id):
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=2025,
                target_period=_PERIOD,
                target_registry_snapshot_ref=snapshot_ref,
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
                wallet_captured_at=_WALLET_DECIDED_AT,
                decided_at=_WALLET_DECIDED_AT,
            )
        )


def _minimal_pdf(text: str) -> bytes:
    """Return one syntactically minimal PDF carrying ``text``.

    ``evidence add`` accepts only the document extensions a real purchase invoice
    arrives in, so the fixture is a document rather than a text file. It stays
    synthetic: the bytes name no real supplier, taxpayer or amount outside this
    module's own constants.
    """
    body = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii", errors="replace")
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n" + body + b"\n%%EOF\n"


def _register_purchase_invoice_evidence(tmp_path: Path, *, label: str, base: Decimal, cuota: Decimal) -> str:
    """Register one purchase invoice document and return its evidence id.

    The deduction's evidence pointer is derived from the registered record rather
    than typed, so an input-IVA deduction can only be declared on a row that
    links one.
    """
    document = tmp_path / f"{label}.pdf"
    document.write_bytes(_minimal_pdf(f"Factura {label} base {base} IVA {cuota}"))
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
            f"REC-2025-{label}",
            "--invoice-date",
            _OPERATION_DATE,
            "--taxable-base",
            str(base),
            "--iva-rate",
            "0.21",
            "--iva-amount",
            str(cuota),
        ]
    )
    assert registered.exit_code == 0, registered.output
    payload = unwrap_schema_envelope(registered.output)
    evidence_id = payload["evidence_id"]
    assert isinstance(evidence_id, str)
    return evidence_id


def _add_sale() -> str:
    return _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                _OPERATION_DATE,
                "--amount",
                str(_SALE_BASE + _SALE_CUOTA),
                "--direction",
                "INCOMING",
                "--description",
                "Factura cliente 2025-1T",
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
            ],
        )
    )


def _add_taxable_purchase(tmp_path: Path, *, extra_options: tuple[str, ...] = ()) -> str:
    evidence_id = _register_purchase_invoice_evidence(
        tmp_path, label="corriente", base=_PURCHASE_BASE, cuota=_PURCHASE_CUOTA
    )
    return _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                _OPERATION_DATE,
                "--amount",
                str(_PURCHASE_BASE + _PURCHASE_CUOTA),
                "--direction",
                "OUTGOING",
                "--description",
                "Material de oficina",
                "--classification",
                "BUSINESS",
                "--category-id",
                "material_oficina",
                "--taxable-base",
                str(_PURCHASE_BASE),
                "--iva-rate",
                "0.21",
                "--iva-amount",
                str(_PURCHASE_CUOTA),
                "--iva-category",
                "domestic_general",
                "--deduction-kind",
                "domestic_current",
                "--purchase-invoice-evidence-id",
                evidence_id,
                *extra_options,
            ],
        )
    )


def _add_investment_purchase(tmp_path: Path) -> str:
    evidence_id = _register_purchase_invoice_evidence(
        tmp_path, label="inversion", base=_INVESTMENT_BASE, cuota=_INVESTMENT_CUOTA
    )
    return _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                _OPERATION_DATE,
                "--amount",
                str(_INVESTMENT_BASE + _INVESTMENT_CUOTA),
                "--direction",
                "OUTGOING",
                "--description",
                "Ordenador de sobremesa",
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
                _INVESTMENT_ASSET_ID,
                "--purchase-invoice-evidence-id",
                evidence_id,
            ],
        )
    )


def _declare_bien_inversion(acquisition_ledger_id: str) -> None:
    declared = _invoke(
        [
            "app",
            "ledger",
            "bienes-inversion",
            "declare",
            _INVESTMENT_ASSET_ID,
            "--description",
            "Ordenador de sobremesa",
            "--acquisition-year",
            "2025",
            "--acquisition-ledger-id",
            acquisition_ledger_id,
            "--cuota-soportada",
            str(_INVESTMENT_CUOTA),
            "--prorrata-inicial",
            "100",
            "--kind",
            "mueble",
        ],
    )
    assert declared.exit_code == 0, declared.output


def _add_reta_quota() -> str:
    return _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                _OPERATION_DATE,
                "--amount",
                str(_RETA_QUOTA),
                "--direction",
                "OUTGOING",
                "--description",
                "Cuota RETA febrero 2025",
                "--classification",
                "BUSINESS",
                "--category-id",
                "cuotas_autonomos_ss",
                "--taxable-base",
                str(_RETA_QUOTA),
                "--iva-rate",
                "0",
                "--iva-amount",
                "0",
                "--iva-category",
                "operacion_no_sujeta",
            ],
        )
    )


def _add_exempt_premium() -> str:
    return _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                _OPERATION_DATE,
                "--amount",
                str(_PREMIUM),
                "--direction",
                "OUTGOING",
                "--description",
                "Prima seguro responsabilidad civil",
                "--classification",
                "BUSINESS",
                "--category-id",
                "seguros_responsabilidad_civil",
                "--taxable-base",
                str(_PREMIUM),
                "--iva-rate",
                "0",
                "--iva-amount",
                "0",
                "--iva-category",
                "domestic_exempt",
            ],
        )
    )


def _calculate_1t() -> Result:
    created = _invoke(
        ["app", "modelo", "work", "create", "--modelo", "303", "--year", "2025", "--period", "1T"],
    )
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return _invoke(["app", "modelo", "work", "calculate", work_unit_id, *joint_return_options()])


def _casilla_values(result: Result) -> dict[str, str]:
    payload = unwrap_schema_envelope(result.output)
    values = payload["casilla_values"]
    assert isinstance(values, dict)
    return {key: str(value) for key, value in values.items()}


def test_the_quarter_files_with_every_purchase_kind_in_it(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """All five rows reach one 2025 1T calculation, and the casillas match hand arithmetic."""
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_zero_compensation_wallet_decision(bucket_id)

    _add_sale()
    _add_taxable_purchase(tmp_path)
    _declare_bien_inversion(_add_investment_purchase(tmp_path))
    _add_reta_quota()
    _add_exempt_premium()

    calculated = _calculate_1t()

    assert calculated.exit_code == 0, calculated.output
    values = _casilla_values(calculated)
    # Devengado: the single taxable sale, base and cuota.
    assert values["07"] == str(_SALE_BASE)
    assert values["iva.repercutido.general"] == str(_SALE_CUOTA)
    # Deducible operaciones interiores: the corriente purchase plus the bien de
    # inversión. 200.00 + 4000.00 = 4200.00 of base, 42.00 + 840.00 = 882.00 of
    # cuota. The two zero-cuota rows add nothing to either.
    assert values["28"] == str(_PURCHASE_BASE + _INVESTMENT_BASE)
    assert values["iva.soportado.interiores"] == str(_PURCHASE_CUOTA + _INVESTMENT_CUOTA)
    # Resultado régimen general: 210.00 devengada less 882.00 deducible.
    assert values["iva.resultado-regimen-general"] == str(
        _SALE_CUOTA - (_PURCHASE_CUOTA + _INVESTMENT_CUOTA),
    )
    # LIVA art. 107.Uno regularises a bien de inversión over the four years
    # FOLLOWING acquisition, so the acquisition year itself regularises nothing.
    assert values["43"] == "0.00"
    # No box on this form declares an exempt or non-subject acquisition, so
    # neither base may appear anywhere in the return.
    assert str(_RETA_QUOTA) not in values.values()
    assert str(_PREMIUM) not in values.values()
    # And their absence is reported rather than silent: a base that reached no box
    # is an advisory the operator sees on the calculation that omitted it.
    advisories = "\n".join(str(notice) for notice in unwrap_envelope_notices(calculated.output))
    assert "unrouted_declarable_quantity" in advisories, advisories
    assert "domestic_exempt" in advisories
    assert "operacion_no_sujeta" in advisories


def test_an_investment_asset_id_without_its_register_record_is_refused(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """The reciprocity half: the ledger row alone does not establish the asset.

    The write path that carries ``--investment-asset-id`` must not become a way to
    claim a bien de inversión the register does not hold, so the same row is added
    without declaring the record.
    """
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_zero_compensation_wallet_decision(bucket_id)

    _add_sale()
    _add_investment_purchase(tmp_path)

    refused = _calculate_1t()

    assert refused.exit_code == 2, refused.output
    error = require_error_document(refused.output)["error"]
    assert isinstance(error, dict)
    assert error["code"] == "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION"
    assert error["message"] == "investment observation has no reciprocal bienes-inversion record"


def test_a_reta_quota_without_its_iva_substrate_still_blocks_the_quarter(
    request: pytest.FixtureRequest,
) -> None:
    """The substrate is asked for, never inferred from the movement.

    A row with no base, tipo or cuota blocks readiness with the transaction id and
    the missing fact named. Deriving the three from the gross would put an
    undeclared base on a return, so the remedy stays the operator's declaration.
    """
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_zero_compensation_wallet_decision(bucket_id)

    bare = _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                _OPERATION_DATE,
                "--amount",
                str(_RETA_QUOTA),
                "--direction",
                "OUTGOING",
                "--description",
                "Cuota RETA febrero 2025",
                "--classification",
                "BUSINESS",
                "--category-id",
                "cuotas_autonomos_ss",
            ],
        )
    )

    refused = _calculate_1t()

    assert refused.exit_code == 1, refused.output
    error = require_error_document(refused.output)["error"]
    assert isinstance(error, dict)
    context = error["context"]
    assert isinstance(context, dict)
    assert context["reason"] == "missing_taxable_base"
    assert context["transaction_id"] == bare


def test_the_declared_substrate_unblocks_the_same_row(request: pytest.FixtureRequest) -> None:
    """The remedy the refusal above names actually works, on the same row.

    Paired with its refusal deliberately: the finding was not that the quota
    blocked the quarter but that nothing the operator could declare unblocked it.
    """
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_zero_compensation_wallet_decision(bucket_id)

    quota = _add_reta_quota()
    assert quota

    calculated = _calculate_1t()

    assert calculated.exit_code == 0, calculated.output
    values = _casilla_values(calculated)
    assert values["iva.resultado-regimen-general"] == "0.00"
    assert str(_RETA_QUOTA) not in values.values()


def test_a_deduction_claimed_on_the_exempt_premium_is_refused_by_the_cli(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """A premium that bore no cuota cannot claim one, and the refusal names the row."""
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_zero_compensation_wallet_decision(bucket_id)

    evidence_id = _register_purchase_invoice_evidence(tmp_path, label="prima", base=_PREMIUM, cuota=Decimal("0.00"))
    premium = _added_transaction_id(
        _invoke(
            [
                "app",
                "ledger",
                "add",
                "--date",
                _OPERATION_DATE,
                "--amount",
                str(_PREMIUM),
                "--direction",
                "OUTGOING",
                "--description",
                "Prima seguro responsabilidad civil",
                "--classification",
                "BUSINESS",
                "--category-id",
                "seguros_responsabilidad_civil",
                "--taxable-base",
                str(_PREMIUM),
                "--iva-rate",
                "0",
                "--iva-amount",
                "0",
                "--iva-category",
                "domestic_exempt",
                "--deduction-kind",
                "domestic_current",
                "--purchase-invoice-evidence-id",
                evidence_id,
            ],
        )
    )

    refused = _calculate_1t()

    assert refused.exit_code == 1, refused.output
    error = require_error_document(refused.output)["error"]
    assert isinstance(error, dict)
    context = error["context"]
    assert isinstance(context, dict)
    assert context["reason"] == "inadmissible_deduction_classification"
    assert context["transaction_id"] == premium


def test_an_asset_identity_on_an_ordinary_deduction_is_refused(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    """The other exclusion on the new write path: only an investment kind may name an asset.

    Fact 0085 makes the reciprocal identity required by the three investment
    kinds and forbidden on every other one, so a corriente purchase that names an
    asset is corrected rather than quietly carrying a link nothing reads.
    """
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    _seed_zero_compensation_wallet_decision(bucket_id)

    _add_sale()
    purchase = _add_taxable_purchase(
        tmp_path,
        extra_options=("--investment-asset-id", _INVESTMENT_ASSET_ID),
    )

    refused = _calculate_1t()

    assert refused.exit_code == 1, refused.output
    error = require_error_document(refused.output)["error"]
    assert isinstance(error, dict)
    context = error["context"]
    assert isinstance(context, dict)
    assert context["reason"] == "inadmissible_deduction_classification"
    assert context["transaction_id"] == purchase
    assert "investment_asset_id" in context["detail"]
