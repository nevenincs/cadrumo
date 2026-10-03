"""Offline-verifiable CLI contracts for LLM auto-splitting.

Successful provider execution requires a live external provider and is not
simulated here. These cases cover validation, typed notice construction, and
rejection-state projection through real application and persistence boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from functools import partial
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.ledger.llm_classification import reject_llm_suggestion
from ....application.ledger.llm_classification_ports import LLMClassificationSuggestion
from ....application.user_profile.login_session import login_profile, resolve_login_target
from ....core.json_contract import NoticeSeverity
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category import SpendingCategory
from ....domain.transactions.enums import BusinessClassification
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_envelope import unwrap_envelope_notices
from .._ledger_llm_cli import split_recommendation_notice
from ._cli_json_support import _json_object
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
        payee="Proveedor Mixto SL",
        reference="mixed invoice",
        amount="-121.00",
        marker="auto-001",
    )


def _import_two_transactions(ledger_llm_profile: NativeCliProfileFixture, tmp_path: Path) -> tuple[str, str]:
    csv_path = tmp_path / "two-transactions.csv"
    csv_path.write_text(
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor A,first invoice,-100.00,EUR,two-001\n"
        "2026-04-02,Proveedor B,second invoice,-200.00,EUR,two-002\n",
        encoding="utf-8",
    )
    imported = _invoke(ledger_llm_profile, ["app", "ledger", "import", "--file", str(csv_path), "--provider", "csv"])
    assert imported.exit_code == 0, imported.output
    listed = _invoke(ledger_llm_profile, ["--format", "json", "app", "ledger", "list"])
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


@pytest.mark.windows_only
def test_auto_split_requires_read_evidence(ledger_llm_profile: NativeCliProfileFixture, tmp_path: Path) -> None:
    tx = _import_one_transaction(ledger_llm_profile, tmp_path)
    result = _invoke(ledger_llm_profile, ["app", "ledger", "classify", tx, "--llm", "--auto-split"])
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
@pytest.mark.windows_only
def test_classify_reject_and_apply_are_mutually_exclusive(
    ledger_llm_profile: NativeCliProfileFixture, tmp_path: Path, extra_flags: list[str]
) -> None:
    tx = _import_one_transaction(ledger_llm_profile, tmp_path)
    result = _invoke(
        ledger_llm_profile,
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


@pytest.mark.windows_only
def test_list_hide_llm_rejected_retains_unrelated_rows(
    ledger_llm_profile: NativeCliProfileFixture, tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    rejected_id, unrelated_id = _import_two_transactions(ledger_llm_profile, tmp_path)
    suggestion = LLMClassificationSuggestion(
        transaction_id=rejected_id,
        provenance="llm:recorded-review-input",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.from_registry("material_oficina"),
        confidence=Decimal("0.9"),
        reason="recorded review input",
    )
    # Seed the actual rejection audit under the same registered encrypted profile.
    assert ledger_llm_profile.label is not None
    bucket_id = resolve_login_target(ledger_llm_profile.label).bucket_id
    close_active_bucket_session()
    try:
        login = login_profile(
            name=ledger_llm_profile.label,
            passphrase_callback=lambda: ledger_llm_profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        assert login.bucket_id == bucket_id
        rejection = reject_llm_suggestion(
            suggestion,
            bucket_id=bucket_id,
            reason="operator declined the recorded suggestion",
            actor="operator",
            source_command="aeat app ledger classify --llm --reject",
            transaction_repository=TransactionCatalogueRepository(bucket_id=bucket_id),
            bucket_event_repository=BucketEventHistoryRepository(),
        )
    finally:
        close_active_bucket_session()
    assert rejection.transaction_id == rejected_id

    filtered = _invoke(ledger_llm_profile, ["--format", "json", "app", "ledger", "list", "--hide-llm-rejected"])
    assert filtered.exit_code == 0, filtered.output
    shown = {row["transaction_id"] for row in _json_result(filtered)["rows"]}
    assert rejected_id not in shown
    assert unrelated_id in shown


@pytest.mark.windows_only
def test_view_shows_no_rejection_notice_when_none(ledger_llm_profile: NativeCliProfileFixture, tmp_path: Path) -> None:
    tx = _import_one_transaction(ledger_llm_profile, tmp_path)
    viewed = _invoke(ledger_llm_profile, ["--format", "json", "app", "ledger", "view", tx])
    assert viewed.exit_code == 0, viewed.output
    codes = [notice["code"] for notice in unwrap_envelope_notices(viewed.output)]
    assert "ledger.view.llm_suggestion_rejected" not in codes


@pytest.mark.windows_only
@pytest.mark.parametrize("extra_flags", [[], ["--read-evidence", "--auto-split"]])
def test_auto_split_and_classify_refuse_manual_override_before_provider(
    ledger_llm_profile: NativeCliProfileFixture, extra_flags: list[str]
) -> None:
    """Both public routes refuse the manual override before any provider work."""
    result = _invoke(
        ledger_llm_profile,
        ["app", "ledger", "classify", "a" * 64, "--llm", "--classification", "BUSINESS", *extra_flags],
    )
    assert result.exit_code != 0
    assert "--classification" in result.output


@pytest.mark.windows_only
def test_the_auto_split_flag_rule_is_answered_before_the_shared_ones(
    ledger_llm_profile: NativeCliProfileFixture,
) -> None:
    """Missing evidence is reported before the conflicting manual override."""
    result = _invoke(
        ledger_llm_profile,
        ["app", "ledger", "classify", "a" * 64, "--llm", "--auto-split", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0
    assert "--read-evidence" in result.output
