"""CLI validation tests for LLM-assisted ledger classification.

Successful provider execution requires a live external provider and is not
simulated here. These cases exercise deterministic CLI validation and real PATH
discovery without replacing the configured provider.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....tests import temporary_env
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .envelope_helpers import unwrap_cli_result as _json_result

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


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
    return rows[0]["transaction_id"]


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
        ["app", "ledger", "classify", tx, "--llm", "claude", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


def test_llm_invalid_provider_lists_choices(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _invoke(["app", "ledger", "classify", tx, "--llm", "not-a-provider"])
    assert result.exit_code != 0
    # Typer renders the Choice([...]) accepted-value set on a bad enum value.
    assert "claude" in result.output and "antigravity" in result.output and "codex" in result.output


def test_providers_lists_availability(tmp_path: Path) -> None:
    result = _invoke(["--format", "json", "app", "ledger", "providers"])
    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    names = {p["provider"] for p in payload["providers"]}
    assert names == {"claude", "antigravity", "codex"}
    for p in payload["providers"]:
        assert isinstance(p["available"], bool)


def test_llm_unavailable_provider_refuses_from_real_path_lookup(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()

    with temporary_env(PATH=str(empty_path)):
        result = _invoke(["app", "ledger", "classify", tx, "--llm", "antigravity"])

    assert result.exit_code != 0
    assert "antigravity" in result.output
    assert "PATH" in result.output
    assert _row_by_id(tx)["business_classification"] == "NOT_YET_PROCESSED"


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
        ["app", "ledger", "classify", tx, "--llm", "claude", *extra_flags, "--nif", "12345678Z"],
    )

    assert result.exit_code != 0, result.output
    # The refusal names the offending flag rather than swallowing it.
    assert "--nif" in result.output
    # No silent-ignore: the row was not classified as a side effect of the
    # rejected invocation.
    assert _row_by_id(tx)["business_classification"] == "NOT_YET_PROCESSED"
