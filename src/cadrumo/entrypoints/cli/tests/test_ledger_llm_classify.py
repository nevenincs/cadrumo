"""CLI validation tests for LLM-assisted ledger classification.

Successful provider execution requires a live external provider and is not
simulated here. These cases exercise deterministic CLI validation and real PATH
discovery without replacing the configured provider.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....tests.cli_runner import invoke_cached_cli
from ._isolated_profile_storage_fixtures import llm_profile_isolated_backend
from .envelope_helpers import unwrap_cli_result as _json_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["llm_profile_isolated_backend"]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _import_one_transaction(tmp_path: Path) -> str:
    """Import one CSV row and return its transaction id."""
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Restaurante Sol,client lunch,-45.00,EUR,llm-001\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    result = _invoke(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = _json_result(listed)["rows"]
    assert rows, listed.output
    raw_id = rows[0].get("transaction_id")
    assert isinstance(raw_id, str), listed.output
    return raw_id


def _row_by_id(transaction_id: str) -> dict[str, Any]:
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = _json_result(listed)["rows"]
    return {r["transaction_id"]: r for r in rows}[transaction_id]


def test_llm_rejects_combination_with_manual_classification(
    tmp_path: Path,
) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _invoke(
        ["app", "ledger", "classify", tx, "--llm", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# unknown option: --nif is refused, never silently ignored (audit m18)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra_flags", [[], ["--saturate"]])
def test_llm_classify_rejects_unknown_nif_option(
    tmp_path: Path,
    extra_flags: list[str],
) -> None:
    """``--nif`` is not a classify flag: it must be refused, never silently dropped.

    Audit finding m18 observed ``--nif`` appearing to be *silently ignored* on the
    LLM-assisted classify surface (the real identity flag is ``--tax-id`` on
    ``config profile create``, never on ``ledger classify``). The silent-accept
    appearance only arose when no profile was active and the cold-start write guard
    refused first, masking option parsing. With an active profile present (this
    module's autouse fixture), the unknown option must be rejected with a non-zero
    exit, the offending flag named, and *nothing* classified — never accepted as a
    no-op scoping flag. This regression fails the moment a no-op ``--nif`` (or
    ``ignore_unknown_options``) is added to the surface.
    """
    tx = _import_one_transaction(tmp_path)

    result = _invoke(
        ["app", "ledger", "classify", tx, "--llm", *extra_flags, "--nif", "12345678Z"],
    )

    assert result.exit_code != 0, result.output
    # The refusal names the offending flag rather than swallowing it.
    assert "--nif" in result.output
    # No silent-ignore: the row was not classified as a side effect of the
    # rejected invocation.
    assert _row_by_id(tx)["business_classification"] == "NOT_YET_PROCESSED"
