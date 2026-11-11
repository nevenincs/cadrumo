"""CLI surface tests for aeat app modelo iva-wallet balance."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.iva_wallet_balance import query_iva_wallet_balance
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.entrypoints.cli.tests.native_profile_cli_support import invoke_native_cli, reauthenticate_native_profile
from cadrumo.tests.cli_envelope import require_schema_envelope
from cadrumo_runtime.host.tests.native_commands.runtime_profile_cli_fixture import (
    NativeCliProfileFixture,
    native_cli_profile_scope,
)

from .iva_wallet_inspector_support import NIF, state

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

#: The compensation credit of a quarter can be applied for four years (LIVA art. 99.Tres).
_EXPIRY_WINDOW = 4
_OLDEST_ACTIVE_AGE = 4
_NEWER_ACTIVE_AGE = 3
_EXPIRED_AGE = 6
#: The oldest supported exercise is the expired lot, so the as-of year sits an expired lot's age after it.
_AS_OF = filing_year_envelope().floor + _EXPIRED_AGE


@pytest.fixture()
def _runtime_profile(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="f699b704-4c17-4682-ab50-7a2051ce4c52"):
        yield


def test_balance_totals_remaining_after_fifo_applications(
    _runtime_profile: None,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Q1 +1200 and Q2 -300 four years back, then Q1 -500 three years back, leave 400 active as of the horizon."""
    repo = IvaCompensationHistoryRepository()
    repo.save_period(state(filing_year=_AS_OF - _OLDEST_ACTIVE_AGE, period="1T", generated=Decimal("1200.00")))
    repo.save_period(state(filing_year=_AS_OF - _OLDEST_ACTIVE_AGE, period="2T", applied=Decimal("300.00")))
    repo.save_period(state(filing_year=_AS_OF - _NEWER_ACTIVE_AGE, period="1T", applied=Decimal("500.00")))

    report = query_iva_wallet_balance(
        as_of_year=_AS_OF,
        repository=IvaCompensationHistoryRepository(),
        operation=authority_operation,
    )

    assert report.total_balance == Decimal("400.00")
    assert report.active_balance == Decimal("400.00")
    assert report.expired_balance == Decimal("0")
    assert report.lot_count == 1
    # the lot's source year plus the four-year window is the as-of year; expiry_review_state=EXPIRY_REVIEW_DUE at age 4
    assert report.next_expiry_year == _AS_OF
    assert report.as_of_year == _AS_OF
    assert report.unallocated_applied_amount == Decimal("0.00")


def test_balance_splits_active_and_expired_lots(
    _runtime_profile: None,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Two remaining lots: the older is expired, the newer is still usable at the as-of year."""
    repo = IvaCompensationHistoryRepository()
    repo.save_period(state(filing_year=_AS_OF - _EXPIRED_AGE, period="4T", generated=Decimal("100.00")))
    repo.save_period(state(filing_year=_AS_OF - _NEWER_ACTIVE_AGE, period="2T", generated=Decimal("200.00")))

    report = query_iva_wallet_balance(
        as_of_year=_AS_OF,
        repository=IvaCompensationHistoryRepository(),
        operation=authority_operation,
    )

    # the older lot is EXPIRED_REVIEW_REQUIRED (age=6), excluded from next_expiry_year
    # the newer lot is ACTIVE (age=3), next_expiry_year = its source year + 4
    assert report.next_expiry_year == _AS_OF - _NEWER_ACTIVE_AGE + _EXPIRY_WINDOW
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
    repo.save_period(state(filing_year=_AS_OF - _EXPIRED_AGE, period="4T", generated=Decimal("100.00")))

    report = query_iva_wallet_balance(
        as_of_year=_AS_OF,
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
        as_of_year=_AS_OF,
        repository=IvaCompensationHistoryRepository(),
        operation=authority_operation,
    )

    assert report.total_balance == Decimal("0")
    assert report.active_balance == Decimal("0")
    assert report.expired_balance == Decimal("0")
    assert report.lot_count == 0
    assert report.next_expiry_year is None
    assert report.unallocated_applied_amount == Decimal("0")


def _register_profile_with_expiring_and_active_lots(
    profile: NativeCliProfileFixture, label: str, authority_operation: PinnedAuthorityOperation
) -> None:
    """Register a profile whose wallet holds an expired lot of 100.00 and an active lot of 200.00."""
    profile.register(label=label, facts={"identity.tax_id": NIF})
    reauthenticate_native_profile(profile, authority_operation=authority_operation)
    repo = IvaCompensationHistoryRepository()
    repo.save_period(state(filing_year=_AS_OF - _EXPIRED_AGE, period="4T", generated=Decimal("100.00")))
    repo.save_period(state(filing_year=_AS_OF - _NEWER_ACTIVE_AGE, period="2T", generated=Decimal("200.00")))


def test_cli_balance_verb_emits_expected_keys(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The CLI JSON surface emits gross, active, and expired balances."""
    with native_cli_profile_scope(tmp_path) as profile:
        _register_profile_with_expiring_and_active_lots(profile, "wallet-balance-json", authority_operation)

        result = invoke_native_cli(
            profile,
            "app",
            "modelo",
            "iva-wallet",
            "balance",
            "--as-of-year",
            str(_AS_OF),
        )

    assert result.exit_code == 0, result.output
    payload = require_schema_envelope(result.output)
    assert payload["total_balance"] == "300.00"
    assert payload["active_balance"] == "200.00"
    assert payload["expired_balance"] == "100.00"
    assert payload["lot_count"] == 2
    assert payload["next_expiry_year"] == _AS_OF - _NEWER_ACTIVE_AGE + _EXPIRY_WINDOW
    assert payload["as_of_year"] == _AS_OF


def test_cli_balance_verb_text_output_lines(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Text-mode output includes tab-separated active and expired metric lines."""
    with native_cli_profile_scope(tmp_path) as profile:
        _register_profile_with_expiring_and_active_lots(profile, "wallet-balance-text", authority_operation)

        result = invoke_native_cli(
            profile,
            "app",
            "modelo",
            "iva-wallet",
            "balance",
            "--as-of-year",
            str(_AS_OF),
            output_format=None,
        )

    assert result.exit_code == 0, result.output
    assert "operation\tmodelo.iva-wallet.balance" in result.output
    assert "total_balance\t300.00" in result.output
    assert "active_balance\t200.00" in result.output
    assert "expired_balance\t100.00" in result.output
    assert f"next_expiry_year\t{_AS_OF - _NEWER_ACTIVE_AGE + _EXPIRY_WINDOW}" in result.output
