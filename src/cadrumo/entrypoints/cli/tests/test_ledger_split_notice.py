"""Owning contract probes extracted from native integration scenarios."""

from __future__ import annotations

import pytest

from cadrumo.core.json_contract import NoticeSeverity
from cadrumo.entrypoints.cli._ledger_llm_cli import split_recommendation_notice

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


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
