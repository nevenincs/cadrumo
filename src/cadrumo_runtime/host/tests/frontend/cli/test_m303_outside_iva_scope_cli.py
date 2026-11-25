"""Real CLI journey: a received business cost outside IVA beside a taxable sale.

An autónomo's monthly RETA contribution is a business expense for IRPF and no
IVA operation at all: a Seguridad Social contribution is a public charge of a
tributary nature, not subject under LIVA art. 7.8.º. The operator records it as
``operacion_no_sujeta`` with a zero tipo and cuota. Modelo 303 declares a
non-subject base only for operations the taxpayer performs ([120], [123]), and
its deducible boxes carry operations that bore a cuota, so the contribution has
no box to reach. The quarter must calculate and verify, with every box exactly
what the sale alone produces.

A received row that IS an IVA operation keeps its obligation: a domestic
purchase or sale with no cuota on record is still refused before calculation.

The filing year is the year before the registry's horizon, read from the
published support envelope rather than written down.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from typing import cast

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend,
)
from cadrumo.application.user_profile.tests.persona_profile_facts import directa_normal_tax_id
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.errors.error_codes import ErrorCategory, get_error_exit_code
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_snapshot,
)
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from cadrumo.entrypoints.cli.tests.modelo_work_scenarios import operator_profile_facts
from cadrumo.entrypoints.cli.tests.ordinary_m303_scenarios import joint_return_options
from cadrumo.tests.cli_envelope import require_error_document, unwrap_envelope_notices, unwrap_schema_envelope

from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_SALE_BASE = Decimal("1000.00")
_SALE_CUOTA = Decimal("210.00")
_RETA_QUOTA = Decimal("294.00")
_PURCHASE_BASE = Decimal("200.00")


@cache
def _year() -> int:
    """The last complete filing year: one before the published horizon."""
    return PublishedGovernedFactSource().supported_filing_years().horizon - 1


def _period() -> Period:
    return Period.from_year_and_code(_year(), "1T")


def _operation_date() -> str:
    return f"{_year()}-02-15"


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(["--format", "json", *args])


def _seed_operator(request: pytest.FixtureRequest) -> None:
    """A general-regime filer active from 1 January, with no compensation carried into 1T."""
    facts = operator_profile_facts(activity_start_date=f"{_year()}-01-01")
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=facts)
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    decided_at = datetime(_year(), 4, 1, 10, tzinfo=UTC)
    snapshot_ref = published_snapshot("303", filing_year=_year(), period="1T").snapshot_ref
    with open_test_profile_session(bucket_id):
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif=directa_normal_tax_id(),
                target_year=_year(),
                target_period=_period(),
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
                wallet_captured_at=decided_at,
                decided_at=decided_at,
            )
        )


def _added_transaction_id(result: Result) -> str:
    assert result.exit_code == 0, result.output
    transaction = unwrap_schema_envelope(result.output)["transaction"]
    assert isinstance(transaction, dict)
    transaction_id = transaction["transaction_id"]
    assert isinstance(transaction_id, str)
    return transaction_id


def _add_sale() -> str:
    return _added_transaction_id(
        _invoke(
            [
                "app", "ledger", "add",
                "--date", _operation_date(),
                "--amount", str(_SALE_BASE + _SALE_CUOTA),
                "--direction", "INCOMING",
                "--description", "Factura reparacion primer trimestre",
                "--counterparty", "Cliente SA",
                "--classification", "BUSINESS",
                "--taxable-base", str(_SALE_BASE),
                "--iva-rate", "0.21",
                "--iva-amount", str(_SALE_CUOTA),
                "--iva-category", "domestic_general",
                "--irpf-category", "actividad_economica",
            ]
        )
    )  # fmt: skip


def _add_reta_quota() -> str:
    return _added_transaction_id(
        _invoke(
            [
                "app", "ledger", "add",
                "--date", _operation_date(),
                "--amount", str(_RETA_QUOTA),
                "--direction", "OUTGOING",
                "--description", "Cuota RETA trabajador autonomo",
                "--classification", "BUSINESS",
                "--category-id", "cuotas_autonomos_ss",
                "--taxable-base", str(_RETA_QUOTA),
                "--iva-rate", "0",
                "--iva-amount", "0",
                "--iva-category", "operacion_no_sujeta",
            ]
        )
    )  # fmt: skip


def _create_work_unit() -> str:
    created = _invoke(["app", "modelo", "work", "create", "--modelo", "303", "--year", str(_year()), "--period", "1T"])
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)
    return work_unit_id


def _calculate(work_unit_id: str) -> Result:
    return _invoke(["app", "modelo", "work", "calculate", work_unit_id, *joint_return_options()])


def test_a_reta_quota_outside_iva_leaves_the_quarter_calculated_and_verified(request: pytest.FixtureRequest) -> None:
    _seed_operator(request)
    _add_sale()
    _add_reta_quota()

    calculated = _calculate(_create_work_unit())

    assert calculated.exit_code == 0, calculated.output
    calculation = unwrap_schema_envelope(calculated.output)
    values = calculation["casilla_values"]
    assert isinstance(values, dict)
    # The sale alone: 1000.00 at 21 % devenga 210.00 [07]/[09], totalled in [27].
    # Nothing is deducible, so the result [71] is that cuota.
    assert str(values["07"]) == str(_SALE_BASE)
    assert str(values["09"]) == str(_SALE_CUOTA)
    assert str(values["27"]) == str(_SALE_CUOTA)
    assert str(values["71"]) == str(_SALE_CUOTA)
    # The contribution reaches no box: not the corrientes pair [28]/[29], and not
    # any other box of the return.
    assert str(values["28"]) == "0.00"
    assert str(values["29"]) == "0.00"
    assert str(_RETA_QUOTA) not in {str(value) for value in values.values()}
    # It has no base to declare, so no advisory reports one as missing.
    advisories = "\n".join(str(notice) for notice in unwrap_envelope_notices(calculated.output))
    assert "unrouted_declarable_quantity" not in advisories, advisories
    assert "structurally_unroutable_base_category" not in advisories, advisories

    revision = calculation["calculation_revision_id"]
    assert isinstance(revision, str)
    verified = _invoke(["app", "modelo", "work", "verify", revision])
    assert verified.exit_code == 0, verified.output
    assert unwrap_schema_envelope(verified.output)["granted_verificado_completo"] is True


@pytest.mark.parametrize(
    ("direction", "description", "category_option"),
    [
        ("OUTGOING", "Compra material sin cuota anotada", ("--category-id", "suministros_cliente_directos")),
        ("INCOMING", "Venta sin cuota anotada", ("--irpf-category", "actividad_economica")),
    ],
)
def test_an_iva_operation_without_its_cuota_is_still_refused(
    request: pytest.FixtureRequest,
    direction: str,
    description: str,
    category_option: tuple[str, str],
) -> None:
    """A domestic operation at the general tier owes its cuota fact; scope is not inferred from absence."""
    _seed_operator(request)
    incomplete = _added_transaction_id(
        _invoke(
            [
                "app", "ledger", "add",
                "--date", _operation_date(),
                "--amount", str(_PURCHASE_BASE),
                "--direction", direction,
                "--description", description,
                "--classification", "BUSINESS",
                *category_option,
                "--taxable-base", str(_PURCHASE_BASE),
                "--iva-category", "domestic_general",
            ]
        )
    )  # fmt: skip

    refused = _calculate(_create_work_unit())

    assert refused.exit_code == get_error_exit_code(ErrorCategory.REFUSED), refused.output
    error = require_error_document(refused.output)["error"]
    assert isinstance(error, dict)
    context = error["context"]
    assert isinstance(context, dict)
    assert context["reason"] == "missing_iva_amount"
    # The words name the movement by date, description and amount; its identity is the
    # refusal evidence the open-movement door is bound to, never the rendered context.
    assert "transaction_id" not in context
    (evidence,) = error["action"]["evidence"]
    assert evidence["values"]["transaction_id"] == incomplete
