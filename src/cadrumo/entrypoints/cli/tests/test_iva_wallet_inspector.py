"""CLI surface tests for aeat app modelo iva-wallet balance."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.calculations.iva_wallet_balance import query_iva_wallet_balance
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.cli_envelope import require_schema_envelope
from ._iva_wallet_inspector_support import _NIF, _state
from .native_profile_cli_support import invoke_native_cli, reauthenticate_native_profile
from .runtime_profile_cli_fixture import native_cli_profile_scope

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]


@pytest.fixture()
def _runtime_profile(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f699b704-4c17-4682-ab50-7a2051ce4c52"):
        yield


def test_balance_totals_remaining_after_fifo_applications(
    _runtime_profile: None,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Q1 2024 +1200, Q2 2024 -300, Q1 2025 -500 leaves 400 active at as_of_year=2028."""
    repo = IvaCompensationHistoryRepository()
    repo.save_period(_state(filing_year=2024, period="1T", generated=Decimal("1200.00")))
    repo.save_period(_state(filing_year=2024, period="2T", applied=Decimal("300.00")))
    repo.save_period(_state(filing_year=2025, period="1T", applied=Decimal("500.00")))

    report = query_iva_wallet_balance(
        as_of_year=2028,
        repository=IvaCompensationHistoryRepository(),
        operation=authority_operation,
    )

    assert report.total_balance == Decimal("400.00")
    assert report.active_balance == Decimal("400.00")
    assert report.expired_balance == Decimal("0")
    assert report.lot_count == 1
    # source_filing_year=2024 + 4 = 2028; expiry_review_state=EXPIRY_REVIEW_DUE at age 4
    assert report.next_expiry_year == 2028
    assert report.as_of_year == 2028
    assert report.unallocated_applied_amount == Decimal("0.00")


def test_balance_splits_active_and_expired_lots(
    _runtime_profile: None,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Two remaining lots: 2022 is expired, 2025 is still usable at as_of_year=2028."""
    repo = IvaCompensationHistoryRepository()
    repo.save_period(_state(filing_year=2022, period="4T", generated=Decimal("100.00")))
    repo.save_period(_state(filing_year=2025, period="2T", generated=Decimal("200.00")))

    report = query_iva_wallet_balance(
        as_of_year=2028,
        repository=IvaCompensationHistoryRepository(),
        operation=authority_operation,
    )

    # 2022 lot is EXPIRED_REVIEW_REQUIRED (age=6), excluded from next_expiry_year
    # 2025 lot is ACTIVE (age=3), next_expiry_year = 2025 + 4 = 2029
    assert report.next_expiry_year == 2029
    assert report.total_balance == Decimal("300.00")
    assert report.active_balance == Decimal("200.00")
    assert report.expired_balance == Decimal("100.00")
    assert report.lot_count == 2


def test_next_expiry_year_none_when_no_active_lots_with_balance(
    _runtime_profile: None,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """All remaining balance is in expired lots: next_expiry_year is None."""
    repo = IvaCompensationHistoryRepository()
    repo.save_period(_state(filing_year=2022, period="4T", generated=Decimal("100.00")))

    report = query_iva_wallet_balance(
        as_of_year=2028,
        repository=IvaCompensationHistoryRepository(),
        operation=authority_operation,
    )

    # age=6, EXPIRED_REVIEW_REQUIRED — not ACTIVE
    assert report.next_expiry_year is None
    assert report.total_balance == Decimal("100.00")
    assert report.active_balance == Decimal("0")
    assert report.expired_balance == Decimal("100.00")


def test_empty_history_returns_zero_balance(
    _runtime_profile: None,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    report = query_iva_wallet_balance(
        as_of_year=2026,
        repository=IvaCompensationHistoryRepository(),
        operation=authority_operation,
    )

    assert report.total_balance == Decimal("0")
    assert report.active_balance == Decimal("0")
    assert report.expired_balance == Decimal("0")
    assert report.lot_count == 0
    assert report.next_expiry_year is None
    assert report.unallocated_applied_amount == Decimal("0")


def test_cli_balance_verb_emits_expected_keys(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The CLI JSON surface emits gross, active, and expired balances."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="wallet-balance-json", facts={"identity.tax_id": _NIF})
        reauthenticate_native_profile(profile, authority_operation=authority_operation)
        repo = IvaCompensationHistoryRepository()
        repo.save_period(_state(filing_year=2022, period="4T", generated=Decimal("100.00")))
        repo.save_period(_state(filing_year=2025, period="2T", generated=Decimal("200.00")))

        result = invoke_native_cli(
            profile,
            "app",
            "modelo",
            "iva-wallet",
            "balance",
            "--as-of-year",
            "2028",
        )

    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    assert payload["total_balance"] == "300.00"
    assert payload["active_balance"] == "200.00"
    assert payload["expired_balance"] == "100.00"
    assert payload["lot_count"] == 2
    assert payload["next_expiry_year"] == 2029
    assert payload["as_of_year"] == 2028


def test_cli_balance_verb_text_output_lines(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Text-mode output includes tab-separated active and expired metric lines."""
    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label="wallet-balance-text", facts={"identity.tax_id": _NIF})
        reauthenticate_native_profile(profile, authority_operation=authority_operation)
        repo = IvaCompensationHistoryRepository()
        repo.save_period(_state(filing_year=2022, period="4T", generated=Decimal("100.00")))
        repo.save_period(_state(filing_year=2025, period="2T", generated=Decimal("200.00")))

        result = invoke_native_cli(
            profile,
            "app",
            "modelo",
            "iva-wallet",
            "balance",
            "--as-of-year",
            "2028",
            output_format=None,
        )

    assert result.exit_code == 0, result.output
    assert "operation\tmodelo.iva-wallet.balance" in result.output
    assert "total_balance\t300.00" in result.output
    assert "active_balance\t200.00" in result.output
    assert "expired_balance\t100.00" in result.output
    assert "next_expiry_year\t2029" in result.output
