"""CLI surface tests for `aeat app ledger inventory {list, create, movement add, valuation preview}`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
        )
        yield


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
