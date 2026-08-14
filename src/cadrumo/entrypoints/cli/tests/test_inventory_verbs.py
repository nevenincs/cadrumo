"""CLI surface tests for `aeat app ledger inventory {list, create, movement add, valuation preview}`."""

from __future__ import annotations

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ._strict_cli_fixture_support import inventory_isolated_backend

__all__ = ["inventory_isolated_backend"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_inventory_list_starts_empty() -> None:
    result = invoke_cached_cli(["app", "ledger", "inventory", "list"])
    assert result.exit_code == 0, result.output
    assert "count\t0" in result.output


def test_inventory_create_persists() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "100.00",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "actividad_id\tact-1" in result.output
    assert "valuation_method\tfifo" in result.output
    assert "opening_stock\t100.00" in result.output

    list_result = invoke_cached_cli(["app", "ledger", "inventory", "list"])
    assert list_result.exit_code == 0, list_result.output
    assert "act-1\t2026\tfifo" in list_result.output


def test_inventory_create_refuses_duplicate() -> None:
    invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "0",
        ],
    )
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "0",
        ],
    )
    assert result.exit_code != 0


def test_inventory_movement_add_records_against_existing_ledger() -> None:
    invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "create",
            "act-1",
            "--year",
            "2026",
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "0",
        ],
    )
    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "inventory",
            "movement",
            "add",
            "--actividad-id",
            "act-1",
            "--year",
            "2026",
            "--movement-id",
            "mov-1",
            "--date",
            "2026-03-15",
            "--kind",
            "purchase",
            "--quantity",
            "10",
            "--unit-cost",
            "5.50",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "movements\t1" in result.output
