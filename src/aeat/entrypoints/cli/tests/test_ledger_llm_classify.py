"""Real-behavior CLI tests for LLM-assisted ledger classification.

Exercises ``aeat app ledger classify --llm`` end to end against the real CLI,
real application use cases, and real SQLite persistence in an isolated storage
root. No test doubles or monkeypatch: determinism comes from
**dependency injection** — a tiny concrete :class:`LLMClassifier` registered
through the production :func:`register_classifier` registry (the same offline
pattern the LLM adapter's deterministic provider establishes), and a real
``PATH`` manipulation for the unavailable-provider refusal.

Coverage for the LLM-ledger-classification contract:

* suggest (``--llm`` without ``--apply``) returns the classifier's decision
  and persists nothing;
* apply (``--llm --apply``) persists with ``classified_by = llm:<model>``;
* a subsequent manual ``classify --classification`` override wins and flips
  provenance back to manual;
* reject (no ``--apply``) leaves the row unchanged;
* an unavailable provider yields an instructive refusal with a non-zero exit.
"""

from __future__ import annotations

import json
import os
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
from ....domain.transactions import (
    BusinessClassification,
    LLMClassificationResponse,
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


class _DeterministicClassifier:
    """Concrete in-process :class:`LLMClassifier` returning a fixed response.

    Implements the protocol (``decided_by`` + ``classify``) without any
    subprocess or network I/O so the CLI/app/persistence stack runs end to end
    offline. Registered under a real provider name via
    :func:`register_classifier` so ``resolve_classifier`` returns it.
    """

    def __init__(
        self,
        *,
        model: str = "test-fixed-1",
        classification: BusinessClassification = BusinessClassification.BUSINESS,
        category: SpendingCategory | None = SpendingCategory.MANUTENCION_DIETAS_NACIONAL,
        confidence: Decimal = Decimal("0.91"),
        reason: str = "restaurante meal with a named client suggests a business meal",
    ) -> None:
        self._model = model
        self._classification = classification
        self._category = category
        self._confidence = confidence
        self._reason = reason

    @property
    def decided_by(self) -> str:
        return f"llm:claude:{self._model}"

    def classify(self, transaction: Transaction) -> LLMClassificationResponse:
        return LLMClassificationResponse(
            classification=self._classification,
            confidence=self._confidence,
            reason=self._reason,
            category=self._category,
        )


@pytest.fixture
def _deterministic_claude() -> Iterator[_DeterministicClassifier]:
    """Register a deterministic classifier under the ``claude`` provider.

    The CLI resolves the production ``claude`` builder; overriding the registry
    entry injects a fixed, offline decision while keeping the real
    ``resolve_classifier`` -> ``classify`` path intact.
    """
    fixture = _DeterministicClassifier()
    register_classifier("claude", lambda **_kwargs: fixture)
    try:
        yield fixture
    finally:
        # Restore the production subprocess builder so peer tests are unaffected.
        from ....domain.transactions._llm import build_claude_classifier

        register_classifier("claude", build_claude_classifier)


def _import_one_transaction(tmp_path: Path) -> str:
    """Import one CSV row and return its transaction id."""
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Restaurante Sol,client lunch,-45.00,EUR,llm-001\n"
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


def _row_by_id(transaction_id: str) -> dict[str, Any]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    return {r["transaction_id"]: r for r in rows}[transaction_id]


# ---------------------------------------------------------------------------
# suggest: returns the decision, persists nothing
# ---------------------------------------------------------------------------


def test_llm_suggest_returns_decision_and_persists_nothing(
    tmp_path: Path, _deterministic_claude: _DeterministicClassifier
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "classify", "--id", tx, "--llm", "claude"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["llm"] is True
    assert payload["persisted"] is False
    assert payload["classification"] == "BUSINESS"
    assert payload["category"] == SpendingCategory.MANUTENCION_DIETAS_NACIONAL.value
    assert payload["confidence"].startswith("0.91")
    assert payload["reason"]
    assert payload["provenance"] == "llm:claude:test-fixed-1"

    # Nothing persisted: the row is still unclassified.
    assert _row_by_id(tx)["business_classification"] == "NOT_YET_PROCESSED"


def test_llm_reject_no_apply_leaves_row_unchanged(
    tmp_path: Path, _deterministic_claude: _DeterministicClassifier
) -> None:
    tx = _import_one_transaction(tmp_path)
    before = _row_by_id(tx)

    suggest = _RUNNER.invoke(app, ["app", "ledger", "classify", "--id", tx, "--llm", "claude"])
    assert suggest.exit_code == 0, suggest.output

    after = _row_by_id(tx)
    assert after["business_classification"] == before["business_classification"] == "NOT_YET_PROCESSED"
    assert after["classified_by"] == before["classified_by"]


# ---------------------------------------------------------------------------
# apply: persists with llm: provenance
# ---------------------------------------------------------------------------


def test_llm_apply_persists_with_llm_provenance(
    tmp_path: Path, _deterministic_claude: _DeterministicClassifier
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", "--id", tx, "--llm", "claude", "--apply"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["llm"] is True
    assert payload["persisted"] is True
    assert payload["transaction"]["classified_by"] == "llm:claude:test-fixed-1"

    row = _row_by_id(tx)
    assert row["business_classification"] == "BUSINESS"
    assert row["classified_by"] == "llm:claude:test-fixed-1"
    assert row["category_id"] == SpendingCategory.MANUTENCION_DIETAS_NACIONAL.value
    # The MVP must not set any regulated tax value from the LLM.
    assert row["taxable_base"] is None
    assert row["iva_rate"] is None
    assert row["iva_amount"] is None
    assert row["irpf_category"] is None


def test_llm_apply_then_manual_override_wins(tmp_path: Path, _deterministic_claude: _DeterministicClassifier) -> None:
    tx = _import_one_transaction(tmp_path)

    applied = _RUNNER.invoke(app, ["app", "ledger", "classify", "--id", tx, "--llm", "claude", "--apply"])
    assert applied.exit_code == 0, applied.output
    assert _row_by_id(tx)["classified_by"] == "llm:claude:test-fixed-1"

    # Manual classification is always the explicit override and flips provenance.
    override = _RUNNER.invoke(app, ["app", "ledger", "classify", "--id", tx, "--classification", "PERSONAL"])
    assert override.exit_code == 0, override.output

    row = _row_by_id(tx)
    assert row["business_classification"] == "PERSONAL"
    assert row["classified_by"] == "manual"


# ---------------------------------------------------------------------------
# unavailable provider: instructive refusal + non-zero exit
# ---------------------------------------------------------------------------


def test_llm_unavailable_provider_refuses_instructively(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)

    # Real PATH manipulation: an empty PATH makes every provider CLI
    # unresolvable, so the availability probe fails for real (no patch/mock).
    empty_dir = tmp_path / "empty-path"
    empty_dir.mkdir()
    previous_path = os.environ.get("PATH", "")
    os.environ["PATH"] = str(empty_dir)
    try:
        result = _RUNNER.invoke(app, ["app", "ledger", "classify", "--id", tx, "--llm", "antigravity"])
    finally:
        os.environ["PATH"] = previous_path

    assert result.exit_code != 0
    assert "antigravity" in result.output
    # Instructive: names PATH and the discovery command.
    assert "PATH" in result.output


# ---------------------------------------------------------------------------
# mutual exclusivity + provider availability listing
# ---------------------------------------------------------------------------


def test_llm_rejects_combination_with_manual_classification(
    tmp_path: Path, _deterministic_claude: _DeterministicClassifier
) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", "--id", tx, "--llm", "claude", "--classification", "BUSINESS"],
    )
    assert result.exit_code != 0


def test_llm_invalid_provider_lists_choices(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(app, ["app", "ledger", "classify", "--id", tx, "--llm", "not-a-provider"])
    assert result.exit_code != 0
    # Typer renders the Choice([...]) accepted-value set on a bad enum value.
    assert "claude" in result.output and "antigravity" in result.output and "codex" in result.output


def test_providers_lists_availability(tmp_path: Path) -> None:
    result = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "providers"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    names = {p["provider"] for p in payload["providers"]}
    assert names == {"claude", "antigravity", "codex"}
    for p in payload["providers"]:
        assert isinstance(p["available"], bool)
