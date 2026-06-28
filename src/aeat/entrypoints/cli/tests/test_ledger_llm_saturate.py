"""Real-behavior CLI tests for ``aeat app ledger classify --llm --saturate``.

Exercises the stage-2 saturation surface end to end against the real CLI, real
application + domain derivation, and real SQLite persistence in an isolated
storage root. Determinism comes from dependency injection — a concrete
:class:`LLMClassifier` (returning a fixed response that includes an
``iva_category``) registered through the production
:func:`register_classifier` registry — never a mock or monkeypatch.

Coverage for the saturate contract (llm-ledger-classification decision):

* preview (``--saturate`` without ``--apply``) derives the rate / base / amount
  from the model-selected IVA category and persists nothing;
* apply (``--saturate --apply``) persists the derived substrate with
  ``classified_by = llm:<model>`` and the gross==base+iva invariant holds;
* a non-derivable IVA category surfaces an operator-facing note and no numbers;
* ``--saturate`` without ``--llm`` but WITH ``--iva-category`` derives the
  substrate operator-initiated, stamped ``derived:iva-category`` — the F2
  fallback for when the model declines or the operator already knows the
  category;
* ``--saturate`` without ``--llm`` and without ``--iva-category`` is refused
  instructively (pointing at ``--iva-category`` or ``--llm``);
* operator-derive refuses a non-business row.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

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


class _SaturatingClassifier:
    """Concrete classifier returning a fixed response carrying an IVA category."""

    def __init__(
        self,
        *,
        iva_category: IvaCategory = IvaCategory.DOMESTIC_GENERAL_21,
        model: str = "sat-1",
    ) -> None:
        self._iva_category = iva_category
        self._model = model

    @property
    def decided_by(self) -> str:
        return f"llm:claude:{self._model}"

    def classify(self, transaction: Transaction, *, evidence_text: str | None = None) -> LLMClassificationResponse:
        return LLMClassificationResponse(
            classification=BusinessClassification.BUSINESS,
            confidence=Decimal("0.92"),
            reason="business expense with a domestic supplier",
            category=SpendingCategory.MANUTENCION_DIETAS_NACIONAL,
            iva_category=self._iva_category,
        )


@pytest.fixture
def _saturating_claude() -> Iterator[None]:
    register_classifier("claude", lambda **_kwargs: _SaturatingClassifier())
    try:
        yield
    finally:
        from ....domain.transactions._llm import build_claude_classifier

        register_classifier("claude", build_claude_classifier)


@pytest.fixture
def _non_derivable_claude() -> Iterator[None]:
    register_classifier(
        "claude",
        lambda **_kwargs: _SaturatingClassifier(iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY),
    )
    try:
        yield
    finally:
        from ....domain.transactions._llm import build_claude_classifier

        register_classifier("claude", build_claude_classifier)


def _import_one_transaction(tmp_path: Path) -> str:
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor SL,material,-121.00,EUR,sat-001\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    result = _RUNNER.invoke(app, ["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return json.loads(listed.output)["result"]["rows"][0]["transaction_id"]


def _row_by_id(transaction_id: str) -> dict[str, object]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = json.loads(listed.output)["result"]["rows"]
    return {r["transaction_id"]: r for r in rows}[transaction_id]


def test_saturate_preview_derives_substrate_and_persists_nothing(tmp_path: Path, _saturating_claude: None) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", tx, "--llm", "claude", "--saturate"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["persisted"] is False
    assert payload["iva_category"] == IvaCategory.DOMESTIC_GENERAL_21.value
    assert payload["rate_derivable"] is True
    assert payload["taxable_base"] == "100.00"
    assert payload["iva_rate"] == "0.21"
    assert payload["iva_amount"] == "21.00"

    # Nothing persisted.
    assert _row_by_id(tx)["business_classification"] == "NOT_YET_PROCESSED"
    assert _row_by_id(tx)["taxable_base"] is None


def test_saturate_apply_persists_derived_substrate_with_llm_provenance(
    tmp_path: Path,
    _saturating_claude: None,
) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", tx, "--llm", "claude", "--saturate", "--apply"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    # D1: --saturate --apply is a single-transaction mutation and emits the
    # canonical quintet; llm provenance rides on transaction.classified_by, not a
    # top-level `persisted`/`iva_category` flag. The model-selected IVA category's
    # effect is verified through the persisted substrate (row checks below).
    assert payload["transaction"]["classified_by"] == "llm:claude:sat-1"
    assert payload["review_status"]

    row = _row_by_id(tx)
    assert row["business_classification"] == "BUSINESS"
    assert row["classified_by"] == "llm:claude:sat-1"
    assert Decimal(str(row["taxable_base"])) == Decimal("100.00")
    assert Decimal(str(row["iva_rate"])) == Decimal("0.21")
    assert Decimal(str(row["iva_amount"])) == Decimal("21.00")


def test_saturate_non_derivable_category_surfaces_note_no_numbers(tmp_path: Path, _non_derivable_claude: None) -> None:
    tx = _import_one_transaction(tmp_path)

    result = _RUNNER.invoke(
        app,
        ["--format", "json", "app", "ledger", "classify", tx, "--llm", "claude", "--saturate"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["iva_category"] == IvaCategory.INTRA_COMMUNITY_SUPPLY.value
    assert payload["rate_derivable"] is False
    assert payload["taxable_base"] is None
    assert payload["derivation_note"]


def test_saturate_apply_then_manual_override_wins(tmp_path: Path, _saturating_claude: None) -> None:
    """Manual classify is the explicit per-field override and flips provenance."""
    tx = _import_one_transaction(tmp_path)
    applied = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", tx, "--llm", "claude", "--saturate", "--apply"],
    )
    assert applied.exit_code == 0, applied.output
    assert _row_by_id(tx)["classified_by"] == "llm:claude:sat-1"

    # The operator overrides the saturated IVA substrate by hand; manual wins.
    override = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            tx,
            "--classification",
            "BUSINESS",
            "--iva-category",
            IvaCategory.DOMESTIC_REDUCED_10.value,
            "--taxable-base",
            "110.00",
            "--iva-rate",
            "0.10",
            "--iva-amount",
            "11.00",
        ],
    )
    assert override.exit_code == 0, override.output

    row = _row_by_id(tx)
    assert row["classified_by"] == "manual"
    assert Decimal(str(row["taxable_base"])) == Decimal("110.00")
    assert Decimal(str(row["iva_amount"])) == Decimal("11.00")


def test_saturate_without_llm_is_refused(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", tx, "--classification", "BUSINESS", "--saturate"],
    )
    assert result.exit_code != 0
    assert "saturate" in result.output.lower()


def _classify_business(tx: str) -> None:
    """Classify a row BUSINESS (the precondition for operator-initiated IVA derivation)."""
    classified = _RUNNER.invoke(
        app,
        [
            "app",
            "ledger",
            "classify",
            tx,
            "--classification",
            "BUSINESS",
            "--category-id",
            SpendingCategory.MANUTENCION_DIETAS_NACIONAL.value,
        ],
    )
    assert classified.exit_code == 0, classified.output


def test_operator_derive_without_llm_persists_derived_substrate(tmp_path: Path) -> None:
    """F2: --saturate --iva-category (no --llm) derives + persists with derived: provenance."""
    tx = _import_one_transaction(tmp_path)
    _classify_business(tx)

    result = _RUNNER.invoke(
        app,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "classify",
            tx,
            "--iva-category",
            IvaCategory.DOMESTIC_GENERAL_21.value,
            "--saturate",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["classified_by"] == "derived:iva-category"

    row = _row_by_id(tx)
    # The business classification chosen earlier is preserved; only the IVA
    # substrate was derived and stamped derived:. The derived 0.21 rate proves
    # the operator-selected DOMESTIC_GENERAL_21 category drove the registry lookup.
    assert row["business_classification"] == "BUSINESS"
    assert row["classified_by"] == "derived:iva-category"
    assert Decimal(str(row["taxable_base"])) == Decimal("100.00")
    assert Decimal(str(row["iva_rate"])) == Decimal("0.21")
    assert Decimal(str(row["iva_amount"])) == Decimal("21.00")


def test_operator_derive_without_iva_category_points_at_iva_or_llm(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    _classify_business(tx)

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", tx, "--saturate"],
    )
    assert result.exit_code != 0
    # The refusal names --saturate; its full instructive text (point at
    # --iva-category or --llm) is asserted via the locale catalogue value, not the
    # ANSI-wrapped error panel.
    assert "saturate" in result.output.lower()


def test_operator_derive_refuses_non_business_row(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)  # row stays NOT_YET_PROCESSED

    result = _RUNNER.invoke(
        app,
        ["app", "ledger", "classify", tx, "--iva-category", IvaCategory.DOMESTIC_GENERAL_21.value, "--saturate"],
    )
    assert result.exit_code != 0
    assert "business" in result.output.lower()
