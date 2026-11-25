"""No reason the activity-asset register raises refuses checking, exporting or recording a declaration.

The reasons are read from the modules that raise them, so a new one is held to
this without being listed here. Real rows then run through both Renta resolvers,
because a row the register reports can also reach the form through the ledger's
own issues, which no scan of the register's modules sees.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.transactions.models import Transaction
from ...actividad_asset.history import ActivityAssetHistory
from ...modelo.calculation_notes import BLOCKING_REASONS, GATE_REFUSED_REASONS
from ..source_mesh import CalculationSourceResolution
from .ledger_source_mesh_support import (
    machine_acquisition_transaction,
    reasons,
    register_asset,
    resolve_m100,
    resolve_m130,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_AGGREGATION = Path(__file__).resolve().parents[1]
_RAISING_MODULES = (
    *sorted(_AGGREGATION.glob("*actividad_asset*.py")),
    *sorted(_AGGREGATION.glob("*activity_asset*.py")),
)


def _raised_reasons(path: Path) -> frozenset[str]:
    return frozenset(
        node.value.value
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.keyword)
        and node.arg == "reason"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def test_no_reason_asset_data_raises_is_one_the_application_refuses_filing_on() -> None:
    raised = frozenset().union(*(_raised_reasons(path) for path in _RAISING_MODULES))

    assert "ledger_amortization_row_unregistered" in raised
    assert "activity_asset_foral_territory" in raised
    assert "activity_asset_residence_unresolved" in raised
    assert raised & GATE_REFUSED_REASONS == frozenset()
    assert raised & BLOCKING_REASONS == frozenset()


def test_the_scan_sees_a_reason_named_at_its_raising_call(tmp_path: Path) -> None:
    module = tmp_path / "module.py"
    module.write_text('note(reason="unresolved_binding", source_kind=kind)\nnote(reason=variable)\n', encoding="utf-8")

    assert _raised_reasons(module) == {"unresolved_binding"}


def _without_base(category: str) -> Transaction:
    row = machine_acquisition_transaction(category, provider_id=f"no-base-{category}")
    return row.model_copy(update={"taxable_base": None})


def _in_dollars(category: str) -> Transaction:
    row = machine_acquisition_transaction(category, provider_id=f"dollars-{category}")
    return row.model_copy(update={"currency": "USD", "value_in_eur": None})


def _ordinary(category: str) -> Transaction:
    return machine_acquisition_transaction(category, provider_id=f"ordinary-{category}")


def _both_returns(history: ActivityAssetHistory, row: Transaction) -> tuple[CalculationSourceResolution, ...]:
    return (resolve_m100(history, rows=(row,)), resolve_m130(history, "2T", rows=(row,)))


@pytest.mark.parametrize("make_row", [_without_base, _in_dollars, _ordinary], ids=["no_base", "dollars", "ordinary"])
@pytest.mark.parametrize("category", ["mobiliario_amortizable", "hardware_amortizable"])
def test_an_unregistered_amortization_row_is_reported_once_and_refuses_nothing(make_row, category: str) -> None:
    row = make_row(category)

    for resolution in _both_returns(ActivityAssetHistory(), row):
        raised = reasons(resolution)
        assert raised.count("ledger_amortization_row_unregistered") == 1, raised
        assert "source_domain_not_ready" not in raised, raised
        assert "source_issue" not in raised, raised
        assert set(raised) & BLOCKING_REASONS == set(), raised


@pytest.mark.parametrize("make_row", [_without_base, _in_dollars], ids=["no_base", "dollars"])
def test_a_row_the_register_owns_refuses_nothing_whatever_the_ledger_says(make_row) -> None:
    row = make_row("mobiliario_amortizable")
    asset = register_asset("machine", transaction_id=row.transaction_id, basis=Decimal("1000.00"))

    for resolution in _both_returns(ActivityAssetHistory(revisions=(asset,)), row):
        assert set(reasons(resolution)) & BLOCKING_REASONS == set(), reasons(resolution)


def test_an_ordinary_expense_with_no_base_is_still_the_ledgers_to_refuse() -> None:
    """What the register does not answer for keeps its refusal, so the fix removes nothing else."""
    row = machine_acquisition_transaction("asesoria_fiscal", provider_id="no-base-ordinary")

    assert "source_domain_not_ready" in reasons(
        resolve_m130(ActivityAssetHistory(), "2T", rows=(row.model_copy(update={"taxable_base": None}),))
    )
