"""CLI validation tests for evidence-driven LLM ledger splitting.

Successful provider execution requires a live external provider and is not
simulated here. These cases pin pre-provider CLI refusals only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ....tests.cli_envelope import unwrap_cli_result
from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import llm_profile_isolated_backend
from ._ledger_llm_support import _import_one_transaction as _shared_import_one_transaction

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["llm_profile_isolated_backend"]


def _import_one_transaction(tmp_path: Path) -> str:
    """Import one CSV row (gross 121.00 outgoing) and return its transaction id."""
    return _shared_import_one_transaction(
        tmp_path,
        payee="Proveedor Mixto SL",
        reference="mixed invoice",
        amount="-121.00",
        marker="split-001",
    )


def _rows() -> list[dict[str, Any]]:
    listed = invoke_cached_cli(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return unwrap_cli_result(listed)["rows"]


def test_llm_split_apply_without_yes_is_refused(
    tmp_path: Path,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = invoke_cached_cli(["app", "ledger", "split", tx, "--llm", "--apply"])
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
            "--child-amount",
            "60.00",
            "--child-description",
            "manual",
        ],
    )
    assert result.exit_code != 0
    assert len(_rows()) == 1
