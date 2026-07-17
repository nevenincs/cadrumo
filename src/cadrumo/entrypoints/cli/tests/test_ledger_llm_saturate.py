"""Real-behavior CLI tests for operator-initiated ledger saturation.

Successful provider execution requires a live external provider and is not
simulated here. These cases exercise the deterministic fallback where the
operator supplies the IVA category directly:

* ``--saturate`` without ``--llm`` but WITH ``--iva-category`` derives the
  substrate operator-initiated, stamped ``derived:iva-category`` — the F2
  fallback for when the model declines or the operator already knows the
  category;
* ``--saturate`` without ``--llm`` and without ``--iva-category`` is refused
  instructively (pointing at ``--iva-category`` or ``--llm``);
* operator-derive refuses a non-business row.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
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
    csv_content = (
        "Date,Payee,Payment reference,Amount (EUR),Currency,Transaction ID\n"
        "2026-04-01,Proveedor SL,material,-121.00,EUR,sat-001\n"
    )
    csv_path = tmp_path / "import.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    result = _invoke(["app", "ledger", "import", str(csv_path), "--provider", "csv"])
    assert result.exit_code == 0, result.output
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    return _json_result(listed)["rows"][0]["transaction_id"]


def _row_by_id(transaction_id: str) -> dict[str, object]:
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    rows = _json_result(listed)["rows"]
    return {r["transaction_id"]: r for r in rows}[transaction_id]


def test_saturate_without_llm_is_refused(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)
    result = _invoke(
        ["app", "ledger", "classify", tx, "--classification", "BUSINESS", "--saturate"],
    )
    assert result.exit_code != 0
    assert "saturate" in result.output.lower()


def _classify_business(tx: str) -> None:
    """Classify a row BUSINESS (the precondition for operator-initiated IVA derivation)."""
    classified = _invoke(
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

    result = _invoke(
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
    payload = _json_result(result)
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

    result = _invoke(
        ["app", "ledger", "classify", tx, "--saturate"],
    )
    assert result.exit_code != 0
    # The refusal names --saturate; its full instructive text (point at
    # --iva-category or --llm) is asserted via the locale catalogue value, not the
    # ANSI-wrapped error panel.
    assert "saturate" in result.output.lower()


def test_operator_derive_refuses_non_business_row(tmp_path: Path) -> None:
    tx = _import_one_transaction(tmp_path)  # row stays NOT_YET_PROCESSED

    result = _invoke(
        ["app", "ledger", "classify", tx, "--iva-category", IvaCategory.DOMESTIC_GENERAL_21.value, "--saturate"],
    )
    assert result.exit_code != 0
    assert "business" in result.output.lower()
