"""Ledger classify, review, and history UX regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from .ledger_ux_support import _imported_transaction_id, _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]


def test_add_with_business_pct_on_a_business_row_surfaces_the_real_cause(
    tmp_path: Path,
) -> None:
    """The illegal --business-pct/--classification pair names the field.

    A non-MIXED classification forbids --business-pct. The refusal must
    name that exact rule rather than the misleading "run config repair".
    """
    result = _invoke(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Office chair",
            "--classification",
            "BUSINESS",
            "--business-pct",
            "1.0",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
        ],
    )
    assert result.exit_code != 0
    assert "business_pct" in result.output
    assert "MIXED" in result.output
    assert "config repair" not in result.output


def test_add_business_row_without_business_pct_succeeds(tmp_path: Path) -> None:
    """The same row minus --business-pct is legal and still works."""
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "Office chair",
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
            "--iva-rate",
            "0.21",
            "--iva-amount",
            "21.00",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["business_classification"] == "BUSINESS"


def test_review_by_short_id_prefix_resolves_the_transaction(
    tmp_path: Path,
) -> None:
    """`review <prefix>` resolves the prefix instead of refusing."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(["--format", "json", "app", "ledger", "view", txn[:8]])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    # `view` emits the uniform single-transaction shape, whose subject key is
    # `transaction_id`; the bare `id` this replaced was the row shape of the
    # list surface these calls used to go through.
    assert payload["transaction_id"] == txn
    assert "config repair" not in result.output


def test_review_by_full_id_still_resolves_the_transaction(
    tmp_path: Path,
) -> None:
    """`review <full>` keeps working after the prefix-resolution fix."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(["--format", "json", "app", "ledger", "view", txn])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["transaction_id"] == txn


def test_classify_with_negative_taxable_base_names_the_real_cause(
    tmp_path: Path,
) -> None:
    """A negative `--taxable-base` on classify surfaces the validator cause.

    The opaque "command input failed validation. Run config repair"
    refusal is replaced with the specific reason; `config repair`
    cannot fix a bad CLI argument and must not be suggested.
    """
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        ["app", "ledger", "classify", txn, "--classification", "BUSINESS", "--taxable-base", "-397.11"],
    )
    assert result.exit_code != 0
    assert "taxable_base" in result.output
    assert "config repair" not in result.output


def test_classify_with_valid_taxable_base_still_succeeds(tmp_path: Path) -> None:
    """A non-negative `--taxable-base` classifies the row normally."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--taxable-base",
            "100.00",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["result"]["transaction"]["taxable_base"] == "100"


def test_classify_accepts_business_pct_for_a_mixed_row(tmp_path: Path) -> None:
    """`classify --classification MIXED --business-pct` works in one step."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "MIXED",
            "--business-pct",
            "0.5",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["business_classification"] == "MIXED"
    assert transaction["business_pct"] == "0.5"


def test_classify_mixed_without_business_pct_names_the_flag(tmp_path: Path) -> None:
    """`classify --classification MIXED` without the share names `--business-pct`."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        ["app", "ledger", "classify", txn, "--classification", "MIXED"],
    )
    assert result.exit_code != 0
    assert "--business-pct" in result.output
    assert "config repair" not in result.output


def test_classify_business_pct_on_non_mixed_row_is_refused(tmp_path: Path) -> None:
    """`--business-pct` with a non-MIXED classification is refused, not dropped."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        ["app", "ledger", "classify", txn, "--classification", "BUSINESS", "--business-pct", "0.5"],
    )
    assert result.exit_code != 0
    assert "--business-pct" in result.output
    assert "MIXED" in result.output


def test_classify_refuses_m210_evidence_flags_on_auto_split(tmp_path: Path) -> None:
    """M210 evidence cannot be silently ignored by the automatic split route."""
    transaction_id = _imported_transaction_id(tmp_path)
    result = _invoke(
        [
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--auto-split",
            "--m210-tipo-renta-code",
            "01",
        ],
    )

    assert result.exit_code != 0
    assert "explicit operator decision" in result.output


def test_classify_reason_persists_to_transaction_notes(tmp_path: Path) -> None:
    """`classify --reason` records WHY into the transaction notes."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            txn,
            "--classification",
            "BUSINESS",
            "--reason",
            "Recurring SaaS subscription used solely for the business.",
        ],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["notes"] == "Recurring SaaS subscription used solely for the business."


def test_classify_empty_reason_is_refused_instructively(tmp_path: Path) -> None:
    """An explicitly empty `--reason` is refused, naming the flag and the fix."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        ["app", "ledger", "classify", txn, "--classification", "BUSINESS", "--reason", "   "],
    )
    assert result.exit_code != 0
    assert "--reason" in result.output
    assert "config repair" not in result.output


def test_classify_without_reason_leaves_notes_unchanged(tmp_path: Path) -> None:
    """Omitting `--reason` keeps the no-rationale path working (notes stay empty)."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(
        ["--format", "json", "app", "ledger", "classify", txn, "--classification", "BUSINESS"],
    )
    assert result.exit_code == 0, result.output
    transaction = json.loads(result.output)["result"]["transaction"]
    assert transaction["business_classification"] == "BUSINESS"
    assert transaction["notes"] == ""


def test_history_accepts_the_id_positionally_like_view(tmp_path: Path) -> None:
    """`ledger history <id>` takes the id positionally, matching `ledger view`."""
    txn = _imported_transaction_id(tmp_path)
    result = _invoke(["--format", "json", "app", "ledger", "history", txn])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction_id"] == txn
    assert payload["event_count"] >= 1
