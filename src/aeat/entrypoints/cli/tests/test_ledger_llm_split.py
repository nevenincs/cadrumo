"""Real-behavior CLI tests for evidence-driven LLM ledger splitting.

Exercises ``aeat app ledger split --llm`` end to end against the real CLI, real
application use cases, and real SQLite persistence in an isolated storage root.
No test doubles or monkeypatch: determinism comes from **dependency injection** —
a tiny concrete :class:`LLMSplitProposer` registered through the production
:func:`register_classifier` registry (``resolve_split_proposer`` narrows it on
the runtime-checkable protocol), so the CLI/app/persistence stack runs end to
end offline.

Coverage for the Stage-3b split contract:

* suggest (``--llm`` without ``--apply``) returns the proposed children with
  system-derived amounts and persists nothing;
* apply (``--llm --apply --yes``) drives the single-writer split plus per-child
  classification with ``classified_by = llm:<model>`` and registry-derived IVA;
* ``--apply`` without ``--yes`` is refused;
* ``--llm`` combined with the manual ``--child-amount`` flags is refused.
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


class _DeterministicSplitProposer:
    """Concrete in-process :class:`LLMSplitProposer` returning a fixed proposal.

    Implements the protocol (``decided_by`` + ``propose_split``) without any
    subprocess or network I/O so the CLI/app/persistence stack runs end to end
    offline. Registered under a real provider name via
    :func:`register_classifier` so ``resolve_split_proposer`` returns it.
    """

    def __init__(self, *, model: str = "test-split-1") -> None:
        self._model = model

    @property
    def decided_by(self) -> str:
        return f"llm:claude:{self._model}"

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        """Mirror the production classifier surface; unused by the split path."""
        return LLMClassificationResponse(
            classification=BusinessClassification.BUSINESS,
            confidence=Decimal("0.9"),
            reason="business supplier invoice",
            category=SpendingCategory.MATERIAL_OFICINA,
        )

    def propose_split(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMSplitResponse:
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


@pytest.fixture
def _deterministic_claude_split() -> Iterator[_DeterministicSplitProposer]:
    """Register a deterministic split proposer under the ``claude`` provider."""
    fixture = _DeterministicSplitProposer()
    register_classifier("claude", lambda **_kwargs: fixture)
    try:
        yield fixture
    finally:
        from ....domain.transactions._llm import build_claude_classifier

        register_classifier("claude", build_claude_classifier)


def _import_one_transaction(tmp_path: Path) -> str:
    """Import one CSV row (gross 121.00 outgoing) and return its transaction id."""
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor Mixto SL,mixed invoice,-121.00,EUR,split-001\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    assert rows, listed.output
    return rows[0]["transaction_id"]


def _rows() -> list[dict[str, Any]]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return json.loads(listed.output)["result"]["rows"]


def test_llm_split_suggest_returns_children_and_persists_nothing(
    tmp_path: Path,
    _deterministic_claude_split: _DeterministicSplitProposer,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "split", tx, "--llm", "claude"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["llm"] is True
    assert payload["persisted"] is False
    children = payload["proposed_children"]
    assert [child["amount"] for child in children] == ["72.60", "48.40"]
    assert all(child["iva_rate"] == "0.21" for child in children)
    assert payload["provenance"] == "llm:claude:test-split-1"

    # Nothing persisted: the single parent row is still present and unsplit.
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["transaction_id"] == tx


def test_llm_split_apply_persists_split_and_classified_children(
    tmp_path: Path,
    _deterministic_claude_split: _DeterministicSplitProposer,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "split", tx, "--llm", "claude", "--apply", "--yes"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["llm"] is True
    assert payload["persisted"] is True
    assert payload["classified_child_count"] == 2
    child_ids = payload["child_transaction_ids"]
    assert len(child_ids) == 2

    rows = {row["transaction_id"]: row for row in _rows()}
    # The two children are persisted, BUSINESS, llm-classified, registry-rated.
    persisted_sum = Decimal("0")
    for child_id in child_ids:
        row = rows[child_id]
        assert row["business_classification"] == "BUSINESS"
        assert row["classified_by"] == "llm:claude:test-split-1"
        assert row["iva_rate"] == "0.21"
        persisted_sum += Decimal(row["amount"])
    assert persisted_sum == Decimal("121.00")


def test_llm_split_apply_without_yes_is_refused(
    tmp_path: Path,
    _deterministic_claude_split: _DeterministicSplitProposer,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(app, ["app", "ledger", "split", tx, "--llm", "claude", "--apply"])
    assert result.exit_code != 0
    # Nothing was persisted: the single parent row is intact.
    assert len(_rows()) == 1


def test_llm_split_rejects_manual_child_flags(
    tmp_path: Path,
    _deterministic_claude_split: _DeterministicSplitProposer,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "split",
            tx,
            "--llm",
            "claude",
            "--child-amount",
            "60.00",
            "--child-description",
            "manual",
        ],
    )
    assert result.exit_code != 0
    assert len(_rows()) == 1
