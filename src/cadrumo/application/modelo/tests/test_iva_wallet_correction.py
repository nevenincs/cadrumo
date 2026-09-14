"""Application contract tests for IVA wallet amount validation."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from cadrumo.application.modelo.iva_wallet_seed import (
    ModeloIvaWalletSeedNegativeAmountError,
    correct_iva_compensation_period_for_bucket,
    record_iva_compensation_override_for_bucket,
    seed_iva_compensation_period_for_bucket,
)
from cadrumo.application.modelo.iva_wallet_seed_ports import ModeloIvaWalletSeedPorts
from cadrumo.core.period import Period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000303"
_SEED_FILING_PERIOD = Period.from_year_and_code(2024, "4T")


class _NeverReachedWalletPorts:
    """Inward fake proving invalid amounts fail before any capability access."""


def _ports() -> ModeloIvaWalletSeedPorts:
    return cast(ModeloIvaWalletSeedPorts, _NeverReachedWalletPorts())


def test_every_wallet_mutation_refuses_the_same_negative_amount_contract() -> None:
    """Seed, correction, and override reject a negative amount before any write."""
    amount = Decimal("-1.00")

    with pytest.raises(ModeloIvaWalletSeedNegativeAmountError) as seed_error:
        seed_iva_compensation_period_for_bucket(
            bucket_id=_BUCKET_ID,
            period=_SEED_FILING_PERIOD,
            amount=amount,
            ports=_ports(),
        )
    with pytest.raises(ModeloIvaWalletSeedNegativeAmountError) as correction_error:
        correct_iva_compensation_period_for_bucket(
            bucket_id=_BUCKET_ID,
            period=_SEED_FILING_PERIOD,
            amount=amount,
            reason="negative",
            ports=_ports(),
        )
    with pytest.raises(ModeloIvaWalletSeedNegativeAmountError) as override_error:
        record_iva_compensation_override_for_bucket(
            bucket_id=_BUCKET_ID,
            period=_SEED_FILING_PERIOD,
            amount=amount,
            reason="negative",
            evidence_locator="operator-test:negative",
            ports=_ports(),
        )

    expected_context = {"amount": "-1.00"}
    assert seed_error.value.context == expected_context
    assert correction_error.value.context == expected_context
    assert override_error.value.context == expected_context
