"""Offline-verifiable CLI contracts for LLM auto-splitting.

Successful provider execution requires a live external provider and is not
simulated here. These cases cover validation, typed notice construction, and
rejection-state projection through real application and persistence boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....application.ledger.llm_classification import reject_llm_suggestion
from ....core.json_contract import NoticeSeverity
from ....domain.categories import SpendingCategory
from ....domain.transactions import BusinessClassification
from ....llm.suggestions import LLMClassificationSuggestion
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_envelope import unwrap_envelope_notices
from ....tests.cli_runner import invoke_cached_cli
from .._ledger_llm_cli import split_recommendation_notice
from ._cli_json_support import _json_object
from ._isolated_profile_storage_fixtures import llm_profile_isolated_backend
from ._ledger_llm_support import _import_one_transaction as _shared_import_one_transaction

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["llm_profile_isolated_backend"]


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


def _import_one_transaction(tmp_path: Path) -> str:
    return _shared_import_one_transaction(
        tmp_path,
        payee="Proveedor Mixto SL",
        reference="mixed invoice",
        amount="-121.00",
        marker="auto-001",
    )


def _import_two_transactions(tmp_path: Path) -> tuple[str, str]:
    csv_path = tmp_path / "two-transactions.csv"
    csv_path.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor A,first invoice,-100.00,EUR,two-001\n"
        "2026-04-02,Proveedor B,second invoice,-200.00,EUR,two-002\n",
        encoding="utf-8",
    )
    imported = _invoke(["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = _json_object(_json_result(listed))["rows"]
    assert isinstance(rows, list)
    transaction_ids: list[str] = []
    for row in rows:
        transaction_id = _json_object(row)["transaction_id"]
        assert isinstance(transaction_id, str)
        transaction_ids.append(transaction_id)
    assert len(transaction_ids) == 2
    return transaction_ids[0], transaction_ids[1]


def test_auto_split_requires_read_evidence(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _invoke(["app", "ledger", "classify", tx, "--llm", "--auto-split"])
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
        ["app", "ledger", "classify", tx, "--llm", "--reject", "--apply", *extra_flags],
    )
    assert result.exit_code != 0
    assert "--reject" in result.output and "--apply" in result.output


def test_split_recommendation_notice_is_info_without_an_invented_action() -> None:
    transaction_id = "txn-contract"

    notice = split_recommendation_notice(transaction_id)

    assert notice.severity is NoticeSeverity.INFO
    assert notice.code == "ledger.classify.split_recommended"
    assert notice.action is None
    assert notice.context == {
        "transaction_id": transaction_id,
        "source": "evidence_read",
    }


def test_list_hide_llm_rejected_retains_unrelated_rows(tmp_path: Path) -> None:
    rejected_id, unrelated_id = _import_two_transactions(tmp_path)
    suggestion = LLMClassificationSuggestion(
        transaction_id=rejected_id,
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
        source_command="aeat app ledger classify --llm --reject",
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
