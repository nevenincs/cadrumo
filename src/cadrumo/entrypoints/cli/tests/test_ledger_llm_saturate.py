"""Native-profile coverage for operator-selected IVA derivation."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....domain.categories.spending_category import SpendingCategory
from ....domain.iva.schema import IvaCategory
from ....tests.cli_envelope import unwrap_cli_result
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Native",
    "identity.surnames": "Operator IVA",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(profile: NativeCliProfileFixture, *command: str) -> Result:
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        (
            "--language",
            "en",
            "--format",
            "json",
            "--profile",
            profile.label,
            "--profile-secrets-stdin",
            *command,
        ),
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


def _view(profile: NativeCliProfileFixture, transaction_id: str) -> dict[str, Any]:
    result = _invoke(profile, "app", "ledger", "view", transaction_id)
    assert result.exit_code == 0, result.output
    return unwrap_cli_result(result)


def test_operator_iva_derivation_uses_exact_profile_worker_and_preserves_row_semantics(tmp_path: Path) -> None:
    """Validate local refusals, no-write denial, and a persisted exact-profile derivation."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="native-ledger-operator-iva", facts=_PROFILE_FACTS)

        added = _invoke(
            profile,
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
            "operator IVA worker fixture",
            "--idempotency-key",
            "native-ledger-operator-iva",
        )
        assert added.exit_code == 0, added.output
        transaction_id = unwrap_cli_result(added)["transaction_id"]
        assert isinstance(transaction_id, str) and len(transaction_id) == 64

        before = _view(profile, transaction_id)
        missing_category = _invoke(profile, "app", "ledger", "classify", transaction_id, "--saturate")
        assert missing_category.exit_code != 0
        assert "iva-category" in missing_category.output or "llm" in missing_category.output.lower()

        incompatible_flags = _invoke(
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

        not_business = _invoke(
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

        classified = _invoke(
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

        derived = _invoke(
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
