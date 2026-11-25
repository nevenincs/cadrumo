"""Native-profile coverage for operator-selected IVA derivation."""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.iva.schema import IvaCategory
from cadrumo.tests.cli_envelope import unwrap_cli_result

from ...native_commands.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from ...native_profile_facts import native_general_iva_facts
from .profile_cli_support import invoke_native_profile

_YEAR = filing_year_envelope().horizon

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = native_general_iva_facts()


def _view(profile: NativeCliProfileFixture, transaction_id: str) -> dict[str, Any]:
    result = invoke_native_profile(profile, "app", "ledger", "view", transaction_id)
    assert result.exit_code == 0, result.output
    return unwrap_cli_result(result)


def test_operator_iva_derivation_uses_exact_profile_worker_and_preserves_row_semantics(tmp_path: Path) -> None:
    """Validate local refusals, no-write denial, and a persisted exact-profile derivation."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-operator-iva", facts=_PROFILE_FACTS)

        added = invoke_native_profile(
            profile,
            "app",
            "ledger",
            "add",
            "--date",
            date(_YEAR, 4, 15).isoformat(),
            "--amount",
            "121.00",
            "--direction",
            "OUTGOING",
            "--description",
            "operator IVA worker fixture",
            "--idempotency-key",
            "native-ledger-operator-iva",
        )
        assert added.exit_code == 0, added.output
        transaction_id = unwrap_cli_result(added)["transaction_id"]
        assert isinstance(transaction_id, str) and len(transaction_id) == 64

        before = _view(profile, transaction_id)
        missing_category = invoke_native_profile(profile, "app", "ledger", "classify", transaction_id, "--saturate")
        assert missing_category.exit_code != 0
        assert "iva-category" in missing_category.output or "llm" in missing_category.output.lower()

        incompatible_flags = invoke_native_profile(
            profile,
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--saturate",
        )
        assert incompatible_flags.exit_code != 0
        assert "--classification" in incompatible_flags.output

        not_business = invoke_native_profile(
            profile,
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--iva-category",
            IvaCategory("domestic_general").value,
            "--saturate",
        )
        assert not_business.exit_code != 0
        assert "business" in not_business.output.lower()
        after_refusal = _view(profile, transaction_id)
        assert after_refusal["review_status"] == before["review_status"]
        assert after_refusal["transaction"] == before["transaction"]

        classified = invoke_native_profile(
            profile,
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--classification",
            "BUSINESS",
            "--category-id",
            SpendingCategory.from_registry("manutencion_dietas_nacional").value,
        )
        assert classified.exit_code == 0, classified.output

        derived = invoke_native_profile(
            profile,
            "app",
            "ledger",
            "classify",
            transaction_id,
            "--iva-category",
            IvaCategory("domestic_general").value,
            "--saturate",
        )
        assert derived.exit_code == 0, derived.output
        derived_payload = unwrap_cli_result(derived)
        derived_transaction = derived_payload["transaction"]
        assert isinstance(derived_transaction, dict)
        assert derived_transaction["classified_by"] == "derived:iva-category"

        readback = _view(profile, transaction_id)
        row = readback["transaction"]
        assert isinstance(row, dict)
        assert row["business_classification"] == "BUSINESS"
        assert row["classified_by"] == "derived:iva-category"
        assert row["iva_category"] == IvaCategory("domestic_general").value
        assert Decimal(str(row["taxable_base"])) == Decimal("100.00")
        assert Decimal(str(row["iva_rate"])) == Decimal("0.21")
        assert Decimal(str(row["iva_amount"])) == Decimal("21.00")
