"""CLI validation tests for evidence-driven LLM ledger splitting.

Successful provider execution requires a live external provider and is not
simulated here. These cases pin pre-provider CLI refusals only.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

import pytest

from ....tests.cli_envelope import unwrap_cli_result
from ._ledger_llm_support import _import_one_transaction as _shared_import_one_transaction
from ._ledger_llm_support import ledger_llm_profile
from .ledger_ux_support import _invoke_exact_profile
from .runtime_profile_cli_fixture import NativeCliProfileFixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["ledger_llm_profile"]


def _import_one_transaction(ledger_llm_profile: NativeCliProfileFixture, tmp_path: Path) -> str:
    """Import one CSV row (gross 121.00 outgoing) and return its transaction id."""
    return _shared_import_one_transaction(
        tmp_path,
        invoke_cli=partial(_invoke_exact_profile, ledger_llm_profile),
        payee="Proveedor Mixto SL",
        reference="mixed invoice",
        amount="-121.00",
        marker="split-001",
    )


def _rows(ledger_llm_profile: NativeCliProfileFixture) -> list[dict[str, Any]]:
    listed = _invoke_exact_profile(ledger_llm_profile, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return unwrap_cli_result(listed)["rows"]


@pytest.mark.windows_only
def test_llm_split_apply_without_yes_is_refused(
    ledger_llm_profile: NativeCliProfileFixture,
    tmp_path: Path,
) -> None:
    tx = _import_one_transaction(ledger_llm_profile, tmp_path)

    result = _invoke_exact_profile(ledger_llm_profile, ["app", "ledger", "split", tx, "--llm", "--apply"])
    assert result.exit_code != 0
    # Nothing was persisted: the single parent row is intact.
    assert (
        len(
            _rows(
                ledger_llm_profile,
            )
        )
        == 1
    )


@pytest.mark.windows_only
def test_llm_split_rejects_manual_child_flags(
    ledger_llm_profile: NativeCliProfileFixture,
    tmp_path: Path,
) -> None:
    tx = _import_one_transaction(ledger_llm_profile, tmp_path)

    result = _invoke_exact_profile(
        ledger_llm_profile,
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
    assert (
        len(
            _rows(
                ledger_llm_profile,
            )
        )
        == 1
    )
