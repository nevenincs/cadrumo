"""Real-behavior CLI tests for ``aeat app ledger classify --auto-split``.

Exercises the evidence-driven auto-split router end to end against the real CLI,
real application use cases, and real SQLite persistence in an isolated storage
root. No test doubles or monkeypatch: determinism comes from **dependency
injection** — a concrete classifier/split proposer registered through the
production :func:`register_classifier` registry.

The router uses one model call (the split proposer) to decide:

* a multi-child verdict drives the evidence-driven split (preview, or with
  ``--apply`` the base/IVA-separating split);
* a single-child "no split" verdict classifies the transaction in place from
  that lone child's selections;
* ``--auto-split`` without ``--read-evidence`` is refused.

It also covers the typed split-recommendation ``Notice`` that
``classify --read-evidence`` emits when the model flags the invoice as
multi-component.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    LLMClassificationResponse,
    LLMSplitChild,
    LLMSplitResponse,
    Transaction,
    register_classifier,
)
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
        yield


class _RouterModel:
    """Concrete classifier + split proposer with a configurable verdict.

    ``multi`` chooses a two-child split proposal (a genuine split) or a
    single-child no-split verdict; ``multiple_components`` is the multiplicity
    flag the classify path carries. Implements both protocol surfaces so the
    same fixture serves ``classify`` and ``propose_split`` offline.
    """

    def __init__(self, *, multi: bool, model: str = "router-1") -> None:
        self._multi = multi
        self._model = model

    @property
    def decided_by(self) -> str:
        return f"llm:claude:{self._model}"

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        return LLMClassificationResponse(
            classification=BusinessClassification.BUSINESS,
            confidence=Decimal("0.9"),
            reason="business supplier invoice",
            category=SpendingCategory.MATERIAL_OFICINA,
            iva_category=IvaCategory.DOMESTIC_GENERAL_21,
            multiple_components=self._multi,
        )

    def propose_split(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMSplitResponse:
        if self._multi:
            return LLMSplitResponse(
                children=(
                    LLMSplitChild(
                        proportion=Decimal("0.6"),
                        category=SpendingCategory.MATERIAL_OFICINA,
                        iva_category=IvaCategory.DOMESTIC_GENERAL_21,
                        evidence_citation="material de oficina",
                    ),
                    LLMSplitChild(
                        proportion=Decimal("0.4"),
                        category=SpendingCategory.SOFTWARE_SUSCRIPCION,
                        iva_category=IvaCategory.DOMESTIC_GENERAL_21,
                        evidence_citation="licencia software",
                    ),
                ),
                reason="invoice carries two distinct line items",
            )
        return LLMSplitResponse(
            children=(
                LLMSplitChild(
                    proportion=Decimal("1.0"),
                    category=SpendingCategory.MATERIAL_OFICINA,
                    iva_category=IvaCategory.DOMESTIC_GENERAL_21,
                    evidence_citation="material de oficina",
                ),
            ),
            reason="invoice is a single line at one rate",
        )


def _register(model: _RouterModel) -> None:
    register_classifier("claude", lambda **_kwargs: model)


@pytest.fixture(autouse=True)
def _restore_claude() -> Iterator[None]:
    try:
        yield
    finally:
        from ....domain.transactions._llm import build_claude_classifier

        register_classifier("claude", build_claude_classifier)


def _import_one_transaction(tmp_path: Path) -> str:
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor Mixto SL,mixed invoice,-121.00,EUR,auto-001\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return json.loads(listed.output)["result"]["rows"][0]["transaction_id"]


def _rows() -> list[dict[str, Any]]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return json.loads(listed.output)["result"]["rows"]


def test_auto_split_requires_read_evidence(tmp_path: Path) -> None:
    _register(_RouterModel(multi=True))
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(app, ["app", "ledger", "classify", tx, "--llm", "claude", "--auto-split"])
    assert result.exit_code != 0
    assert "--read-evidence" in result.output


def test_auto_split_multi_component_suggest_previews_split(tmp_path: Path) -> None:
    _register(_RouterModel(multi=True))
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", tx, "--llm", "claude", "--read-evidence", "--auto-split"],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "ledger.split"
    payload = envelope["result"]
    assert payload["persisted"] is False
    assert [child["amount"] for child in payload["proposed_children"]] == ["72.60", "48.40"]
    # Nothing persisted: one unsplit parent row.
    assert len(_rows()) == 1


def test_auto_split_multi_component_apply_persists_split(tmp_path: Path) -> None:
    _register(_RouterModel(multi=True))
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            tx,
            "--llm",
            "claude",
            "--read-evidence",
            "--auto-split",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["persisted"] is True
    child_ids = payload["child_transaction_ids"]
    assert len(child_ids) == 2
    rows = {row["transaction_id"]: row for row in _rows()}
    persisted_sum = Decimal("0")
    for child_id in child_ids:
        row = rows[child_id]
        assert row["business_classification"] == "BUSINESS"
        assert row["classified_by"] == "llm:claude:router-1"
        assert row["iva_rate"] == "0.21"
        persisted_sum += Decimal(row["amount"])
    assert persisted_sum == Decimal("121.00")


def test_auto_split_single_line_apply_classifies_in_place(tmp_path: Path) -> None:
    _register(_RouterModel(multi=False))
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            tx,
            "--llm",
            "claude",
            "--read-evidence",
            "--auto-split",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["command"] == "ledger.classify"
    # No split happened: still one row, classified in place.
    rows = _rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["transaction_id"] == tx
    assert row["business_classification"] == "BUSINESS"
    assert row["classified_by"] == "llm:claude:router-1"
    assert row["iva_rate"] == "0.21"


def test_classify_read_evidence_emits_split_recommendation_notice(tmp_path: Path) -> None:
    _register(_RouterModel(multi=True))
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", tx, "--llm", "claude", "--read-evidence"],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    notices = envelope["notices"]
    recommend = [n for n in notices if n["code"] == "ledger.classify.split_recommended"]
    assert recommend, envelope
    assert recommend[0]["severity"] == "info"
    assert "--auto-split" in recommend[0]["suggestion"]
    assert tx in recommend[0]["suggestion"]


def test_classify_read_evidence_single_line_emits_no_recommendation(tmp_path: Path) -> None:
    _register(_RouterModel(multi=False))
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", tx, "--llm", "claude", "--read-evidence"],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    codes = [n["code"] for n in envelope["notices"]]
    assert "ledger.classify.split_recommended" not in codes
