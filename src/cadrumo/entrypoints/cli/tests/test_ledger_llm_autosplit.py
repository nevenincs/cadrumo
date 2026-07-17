"""Offline-verifiable CLI contracts for LLM auto-splitting.

Successful provider execution requires a live external provider and is not
simulated here. These cases cover validation, typed notice construction, and
rejection-state projection through real application and persistence boundaries.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....application.ledger import LLMClassificationSuggestion, LLMProvider, reject_llm_suggestion
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....core.json_contract import NoticeSeverity
from ....domain.categories import SpendingCategory
from ....domain.transactions import BusinessClassification
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .._ledger_llm_cli import split_recommendation_notice

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
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor Mixto SL,mixed invoice,-121.00,EUR,auto-001\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    result = _invoke(["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return _json_result(listed)["rows"][0]["transaction_id"]


def _import_two_transactions(tmp_path: Path) -> tuple[str, str]:
    csv_path = tmp_path / "two-transactions.csv"
    csv_path.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor A,first invoice,-100.00,EUR,two-001\n"
        "2026-04-02,Proveedor B,second invoice,-200.00,EUR,two-002\n",
        encoding="utf-8",
    )
    imported = _invoke(["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    transaction_ids = tuple(row["transaction_id"] for row in _json_result(listed)["rows"])
    assert len(transaction_ids) == 2
    return transaction_ids[0], transaction_ids[1]


def test_auto_split_requires_read_evidence(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _invoke(["app", "ledger", "classify", tx, "--llm", "claude", "--auto-split"])
    assert result.exit_code != 0
    assert "--read-evidence" in result.output


@pytest.mark.parametrize(
    "extra_flags",
    [
        [],  # stage-1
        ["--saturate"],  # saturate route
        ["--read-evidence", "--auto-split"],  # auto-split route
    ],
)
def test_classify_reject_and_apply_are_mutually_exclusive(tmp_path: Path, extra_flags: list[str]) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _invoke(
        ["app", "ledger", "classify", tx, "--llm", "claude", "--reject", "--apply", *extra_flags],
    )
    assert result.exit_code != 0
    assert "--reject" in result.output and "--apply" in result.output


def test_split_recommendation_notice_is_info_with_exact_runnable_action() -> None:
    transaction_id = "txn-contract"

    notice = split_recommendation_notice(transaction_id, provider=LLMProvider.CLAUDE)

    assert notice.severity is NoticeSeverity.INFO
    assert notice.code == "ledger.classify.split_recommended"
    assert notice.suggestion == (
        f"aeat app ledger classify {transaction_id} --read-evidence --saturate --auto-split --apply --llm claude"
    )
    assert notice.context == {"transaction_id": transaction_id, "source": "evidence_read"}


def test_list_hide_llm_rejected_retains_unrelated_rows(tmp_path: Path) -> None:
    rejected_id, unrelated_id = _import_two_transactions(tmp_path)
    suggestion = LLMClassificationSuggestion(
        transaction_id=rejected_id,
        provider=None,
        provenance="llm:recorded-review-input",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.MATERIAL_OFICINA,
        confidence=Decimal("0.9"),
        reason="recorded review input",
    )
    rejection = reject_llm_suggestion(
        suggestion,
        bucket_id="00000000-0000-4000-8000-000000000000",
        reason="operator declined the recorded suggestion",
        actor="operator",
    )
    assert rejection.transaction_id == rejected_id

    filtered = _invoke(["--format", "json", "app", "ledger", "list", "--hide-llm-rejected"])
    assert filtered.exit_code == 0, filtered.output
    shown = {row["transaction_id"] for row in _json_result(filtered)["rows"]}
    assert rejected_id not in shown
    assert unrelated_id in shown


def test_view_shows_no_rejection_notice_when_none(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    viewed = _invoke(["--format", "json", "app", "ledger", "view", tx])
    assert viewed.exit_code == 0, viewed.output
    codes = [notice["code"] for notice in unwrap_envelope_notices(viewed.output)]
    assert "ledger.view.llm_suggestion_rejected" not in codes
