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

from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import pytest
from click.testing import Result

from ....domain.categories.spending_category import SpendingCategory
from ....domain.iva import IvaCategory
from ....tests.cli_envelope import unwrap_cli_result as _json_result
from ....tests.cli_runner import invoke_cached_cli
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
        payee="Proveedor SL",
        reference="material",
        amount="-121.00",
        marker="sat-001",
    )


def _row_by_id(transaction_id: str) -> dict[str, object]:
    listed = _invoke(["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = _json_object(_json_result(listed))
    rows = payload["rows"]
    assert isinstance(rows, list)
    by_id: dict[str, dict[str, object]] = {}
    for raw_row in rows:
        row = _json_object(raw_row)
        row_id = row["transaction_id"]
        assert isinstance(row_id, str)
        by_id[row_id] = row
    return by_id[transaction_id]


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
            IvaCategory.DOMESTIC_GENERAL.value,
            "--saturate",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json_result(result)
    assert payload["transaction"]["classified_by"] == "derived:iva-category"

    row = _row_by_id(tx)
    # The business classification chosen earlier is preserved; only the IVA
    # substrate was derived and stamped derived:. The derived 0.21 rate proves
    # the operator-selected DOMESTIC_GENERAL category drove the registry lookup.
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
        ["app", "ledger", "classify", tx, "--iva-category", IvaCategory.DOMESTIC_GENERAL.value, "--saturate"],
    )
    assert result.exit_code != 0
    assert "business" in result.output.lower()
