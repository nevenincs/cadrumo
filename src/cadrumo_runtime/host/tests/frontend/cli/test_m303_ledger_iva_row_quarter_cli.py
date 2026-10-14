"""Real CLI journey: book an IVA-bearing sale, then prepare that quarter's Modelo 303.

The operator adds one sale carrying its taxable base, IVA rate and cuota, and
then creates, calculates and verifies the quarter's Modelo 303, all through the
command line and the joined runtime.

The ledger holds the IVA rate as a fraction: 21 % is ``0.21``. A rate typed as
the percentage ``21`` is a unit mistake that would state a 2100 % rate, so the
add must refuse it with a message naming the accepted form, write nothing, and
never surface as an internal error. Typed as ``0.21`` the row is valid and the
quarter must calculate and verify with the sale in casillas 07 and 09.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from click.testing import Result

from cadrumo.adapters.persistence.profile.calculation_observations import IvaWalletDecisionRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import (
    isolated_cli_backend as _isolated_cli_backend,
)
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from cadrumo.tests.cli_envelope import unwrap_schema_envelope

from ._m303_ordinary_cli_support import joint_return_options
from .cli_runner import invoke_cached_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile
from .test_m303_zero_cuota_and_investment_inputs_cli import _profile_facts

__all__ = ["_isolated_cli_backend", "seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_YEAR = 2025
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_WALLET_DECIDED_AT = datetime(_YEAR, 4, 1, 10, tzinfo=UTC)
_BASE = Decimal("12000.00")
_CUOTA = Decimal("2520.00")


def _invoke(args: list[str]) -> Result:
    return invoke_cached_cli(["--format", "json", *args])


def _seed_operator() -> None:
    """A general-regime filer whose first quarter carries no compensation from before."""
    bucket_id = resolve_active_bucket_id()
    assert bucket_id is not None
    snapshot_ref = published_snapshot("303", filing_year=_YEAR, period="1T").snapshot_ref
    with open_test_profile_session(bucket_id):
        IvaWalletDecisionRepository().save_decision(
            IvaCompensationReconciliationDecision(
                taxpayer_nif="12345678Z",
                target_year=_YEAR,
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


def _add_sale(iva_rate: str) -> Result:
    return _invoke(
        [
            "app", "ledger", "add",
            "--date", f"{_YEAR}-02-15",
            "--amount", str(_BASE + _CUOTA),
            "--direction", "INCOMING",
            "--description", "Factura consultoria primer trimestre con IVA",
            "--counterparty", "Cliente SA",
            "--classification", "BUSINESS",
            "--taxable-base", str(_BASE),
            "--iva-rate", iva_rate,
            "--iva-amount", str(_CUOTA),
            "--irpf-category", "actividad_economica",
        ]
    )  # fmt: skip


def _ledger_row_count() -> int:
    listed = _invoke(["app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = unwrap_schema_envelope(listed.output)["rows"]
    assert isinstance(rows, list)
    return len(rows)


def test_an_iva_rate_typed_as_a_percentage_is_refused_and_writes_nothing(request: pytest.FixtureRequest) -> None:
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())

    added = _add_sale("21")

    assert added.exit_code != 0, added.output
    assert "INTERNAL_CLI_UNEXPECTED_BOUNDARY" not in added.output, added.output
    assert "Express 21% IVA as 0.21" in added.output, added.output
    assert _ledger_row_count() == 0


def test_an_iva_bearing_sale_reaches_a_calculated_and_verified_quarter(request: pytest.FixtureRequest) -> None:
    seeded_profile = cast(ProfileSeeder, request.getfixturevalue(seed_profile.__name__))
    seeded_profile(label="operator", facts=_profile_facts())
    _seed_operator()

    added = _add_sale("0.21")
    assert added.exit_code == 0, added.output

    created = _invoke(["app", "modelo", "work", "create", "--modelo", "303", "--year", str(_YEAR), "--period", "1T"])
    assert created.exit_code == 0, created.output
    work_unit_id = unwrap_schema_envelope(created.output)["work_unit_id"]
    assert isinstance(work_unit_id, str)

    calculated = _invoke(["app", "modelo", "work", "calculate", work_unit_id, *joint_return_options()])
    assert calculated.exit_code == 0, calculated.output
    calculation = unwrap_schema_envelope(calculated.output)
    values = calculation["casilla_values"]
    assert isinstance(values, dict)
    # The sale alone: base 12000.00 at 21 % is a cuota of 2520.00 devengada [27], nothing is
    # deducted, so the quarter's result [71] is that cuota.
    assert str(values["07"]) == str(_BASE)
    assert str(values["09"]) == str(_CUOTA)
    assert str(values["27"]) == str(_CUOTA)
    assert str(values["71"]) == str(_CUOTA)
    revision = calculation["calculation_revision_id"]
    assert isinstance(revision, str)

    verified = _invoke(["app", "modelo", "work", "verify", revision])
    assert verified.exit_code == 0, verified.output
    assert unwrap_schema_envelope(verified.output)["granted_verificado_completo"] is True
