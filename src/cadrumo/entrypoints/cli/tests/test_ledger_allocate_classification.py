"""Real-behavior test: ``ledger allocate`` derives classification from the business proportion.

A 100% allocation is BUSINESS, a 0% allocation is PERSONAL, and a
strictly-partial allocation is MIXED. The verb previously hard-coded
MIXED, silently mislabelling a fully-business expense (CLI testimonial
finding, persona Nuria).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.ledger.actions_manual import create_manual_transaction
from ....application.ledger.models import ManualLedgerTransactionCommand
from ....application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.enums import TransactionDirection
from ...ledger_action_composition import compose_ledger_action_ports
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
    "identity.name": "Tester",
    "identity.surnames": "Allocation",
    "activities.description": "freelance",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def _invoke(profile: NativeCliProfileFixture, args: Sequence[str]) -> Result:
    """Invoke the real CLI against this test's exact isolated profile."""
    assert profile.label is not None
    close_active_bucket_session()
    result = invoke_cached_cli(
        ["--language", "en", "--profile", profile.label, "--profile-secrets-stdin", *args],
        input=json.dumps({"profile_passphrase": profile.passphrase}),
    )
    assert profile.passphrase not in result.output
    return result


@pytest.fixture
def allocation_profile_and_transaction(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> Iterator[tuple[NativeCliProfileFixture, str]]:
    """Create one canonical ledger row in an isolated exact-profile runtime per case."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="allocation-classification", facts=_PROFILE_FACTS)
        assert profile.label is not None
        bucket_id = resolve_login_target(profile.label).bucket_id
        close_active_bucket_session()
        login = authenticate_profile_for_invocation(
            name=profile.label,
            passphrase_callback=lambda: profile.passphrase,
            profile_decode_context=authority_operation.profile_decode_context(),
        )
        assert login.bucket_id == bucket_id
        try:
            ports = compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation)
            created = create_manual_transaction(
                ManualLedgerTransactionCommand(
                    bucket_id=bucket_id,
                    booked_date=date(2026, 4, 15),
                    amount=Decimal("121.00"),
                    direction=TransactionDirection.OUTGOING,
                    description="Invoice 1",
                    counterparty="Client SL",
                    idempotency_key="allocation-classification-seed",
                ),
                ports=ports,
                occurred_at=datetime(2026, 4, 15, 12, tzinfo=UTC),
            )
            transaction_id = created.transaction.transaction_id
        finally:
            close_active_bucket_session()
        yield profile, transaction_id


def _allocate(profile: NativeCliProfileFixture, transaction_id: str, business_pct: str) -> dict[str, Any]:
    result = _invoke(
        profile,
        [
            "--format",
            "json",
            "app",
            "ledger",
            "allocate",
            transaction_id,
            "--business-pct",
            business_pct,
        ],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["result"]["transaction"]


def test_allocate_full_business_pct_yields_business(
    allocation_profile_and_transaction: tuple[NativeCliProfileFixture, str],
) -> None:
    profile, transaction_id = allocation_profile_and_transaction
    assert _allocate(profile, transaction_id, "1.0")["business_classification"] == "BUSINESS"


def test_allocate_partial_business_pct_yields_mixed(
    allocation_profile_and_transaction: tuple[NativeCliProfileFixture, str],
) -> None:
    profile, transaction_id = allocation_profile_and_transaction
    allocated = _allocate(profile, transaction_id, "0.5")
    assert allocated["business_classification"] == "MIXED"
    assert allocated["business_pct"] == "0.5"


def test_allocate_zero_business_pct_yields_personal(
    allocation_profile_and_transaction: tuple[NativeCliProfileFixture, str],
) -> None:
    profile, transaction_id = allocation_profile_and_transaction
    assert _allocate(profile, transaction_id, "0")["business_classification"] == "PERSONAL"


def _allocate_raw(profile: NativeCliProfileFixture, transaction_id: str, business_pct: str) -> Result:
    return _invoke(
        profile,
        [
            "app",
            "ledger",
            "allocate",
            transaction_id,
            "--business-pct",
            business_pct,
        ],
    )


def test_allocate_out_of_range_pct_shows_value_and_percent(
    allocation_profile_and_transaction: tuple[NativeCliProfileFixture, str],
) -> None:
    """An operator who types ``50`` (meaning 50 %) or ``1.5`` sees the offending value WITH its percent context, not a bare 'invalid'."""
    profile, transaction_id = allocation_profile_and_transaction
    result = _allocate_raw(profile, transaction_id, "1.5")
    assert result.exit_code != 0, result.output
    # The offending value and its percent translation both appear.
    assert "1.5" in result.output
    assert "150%" in result.output
    # And the convention is shown so the operator can self-correct.
    assert "0.5 for 50" in result.output


def test_allocate_whole_number_pct_shows_percent_context(
    allocation_profile_and_transaction: tuple[NativeCliProfileFixture, str],
) -> None:
    """``--business-pct 50`` is refused with the 5000% context and the 0..1 share convention."""
    profile, transaction_id = allocation_profile_and_transaction
    result = _allocate_raw(profile, transaction_id, "50")
    assert result.exit_code != 0, result.output
    assert "50" in result.output
    assert "5000%" in result.output
