"""CLI validation tests for evidence-driven LLM ledger splitting.

Successful provider execution requires a live external provider and is not
simulated here. These cases pin pre-provider CLI refusals only.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....tests.cli_envelope import unwrap_cli_result
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("00000000-0000-4000-8000-000000000000"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id="00000000-0000-4000-8000-000000000000")
        )
        yield


def _import_one_transaction(tmp_path: Path) -> str:
    """Import one CSV row (gross 121.00 outgoing) and return its transaction id."""
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor Mixto SL,mixed invoice,-121.00,EUR,split-001\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    result = invoke_cached_cli(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = unwrap_cli_result(listed)["rows"]
    assert rows, listed.output
    return rows[0]["transaction_id"]


def _rows() -> list[dict[str, Any]]:
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return unwrap_cli_result(listed)["rows"]


def test_llm_split_apply_without_yes_is_refused(
    tmp_path: Path,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = invoke_cached_cli(["app", "ledger", "split", tx, "--llm", "claude", "--apply"])
    assert result.exit_code != 0
    # Nothing was persisted: the single parent row is intact.
    assert len(_rows()) == 1


def test_llm_split_rejects_manual_child_flags(
    tmp_path: Path,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = invoke_cached_cli(
        [
            "app",
            "ledger",
            "split",
            tx,
            "--llm",
            "claude",
            "--child-amount",
            "60.00",
            "--child-description",
            "manual",
        ],
    )
    assert result.exit_code != 0
    assert len(_rows()) == 1
