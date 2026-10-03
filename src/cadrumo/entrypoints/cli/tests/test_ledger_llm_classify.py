"""CLI validation tests for LLM-assisted ledger classification.

Successful provider execution requires a live external provider and is not
simulated here. These cases exercise deterministic CLI validation and real PATH
discovery without replacing the configured provider.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ._ledger_llm_support import _import_one_transaction as _shared_import_one_transaction
from ._ledger_llm_support import ledger_llm_profile
from .ledger_ux_support import _invoke_exact_profile
from .runtime_profile_cli_fixture import NativeCliProfileFixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["ledger_llm_profile"]


def _invoke(ledger_llm_profile: NativeCliProfileFixture, args: Sequence[str]) -> Result:
    return _invoke_exact_profile(ledger_llm_profile, args)


def _import_one_transaction(ledger_llm_profile: NativeCliProfileFixture, tmp_path: Path) -> str:
    return _shared_import_one_transaction(
        tmp_path,
        invoke_cli=partial(_invoke, ledger_llm_profile),
        payee="Restaurante Sol",
        reference="client lunch",
        amount="-45.00",
        marker="llm-001",
    )


def _row_by_id(ledger_llm_profile: NativeCliProfileFixture, transaction_id: str) -> dict[str, Any]:
    listed = _invoke(ledger_llm_profile, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = _json_result(listed)["rows"]
    return {r["transaction_id"]: r for r in rows}[transaction_id]


@pytest.mark.windows_only
def test_llm_rejects_combination_with_manual_classification(
    ledger_llm_profile: NativeCliProfileFixture,
    tmp_path: Path,
) -> None:
    tx = _import_one_transaction(ledger_llm_profile, tmp_path)
    result = _invoke(
        ledger_llm_profile,
        ["app", "ledger", "classify", tx, "--llm", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# unknown option: --nif is refused, never silently ignored (audit m18)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("extra_flags", [[], ["--saturate"]])
@pytest.mark.windows_only
def test_llm_classify_rejects_unknown_nif_option(
    ledger_llm_profile: NativeCliProfileFixture,
    tmp_path: Path,
    extra_flags: list[str],
) -> None:
    """``--nif`` is not a classify flag: it must be refused, never silently dropped.

    Audit finding m18 observed ``--nif`` appearing to be *silently ignored* on the
    LLM-assisted classify surface (the real identity flag is ``--tax-id`` on
    ``config profile create``, never on ``ledger classify``). The silent-accept
    appearance only arose when no profile was active and the cold-start write guard
    refused first, masking option parsing. With an active profile present (this
    case's native fixture), the unknown option must be rejected with a non-zero
    exit, the offending flag named, and *nothing* classified — never accepted as a
    no-op scoping flag. This regression fails the moment a no-op ``--nif`` (or
    ``ignore_unknown_options``) is added to the surface.
    """
    tx = _import_one_transaction(ledger_llm_profile, tmp_path)

    result = _invoke(
        ledger_llm_profile,
        ["app", "ledger", "classify", tx, "--llm", *extra_flags, "--nif", "12345678Z"],
    )

    assert result.exit_code != 0, result.output
    # The refusal names the offending flag rather than swallowing it.
    assert "--nif" in result.output
    # No silent-ignore: the row was not classified as a side effect of the
    # rejected invocation.
    assert _row_by_id(ledger_llm_profile, tx)["business_classification"] == "NOT_YET_PROCESSED"
