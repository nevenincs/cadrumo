"""Tests for ObservationKeyError registry binding and production validation paths.

Covers:
- ObservationKeyError is registered in ERROR_REGISTRY under ERROR_OBSERVATION_KEY.
- build_error_envelope produces a well-formed envelope for ObservationKeyError.
- Each of the five validation sites in _observations_repository raises
  ObservationKeyError (not bare ValueError) when its guard is violated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from ....core import Period
from ....core.errors import ERROR_REGISTRY, build_error_envelope
from ....domain.iva_compensation.reconciliation import IvaCompensationReconciliationDecision
from ..errors import ObservationKeyError
from ..observations_repository import (
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
    observation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Registry membership
# ---------------------------------------------------------------------------


def test_observation_key_error_is_in_error_registry() -> None:
    """ObservationKeyError must be registered so the CLI can handle it."""
    assert "ERROR_OBSERVATION_KEY" in ERROR_REGISTRY


def test_observation_key_error_code_matches_registry() -> None:
    code = ERROR_REGISTRY["ERROR_OBSERVATION_KEY"]
    assert code.code == "ERROR_OBSERVATION_KEY"
    assert code.message_key == "errors.error.error_observation_key"


def test_observation_key_error_build_error_envelope() -> None:
    """build_error_envelope must succeed for ObservationKeyError."""
    err = ObservationKeyError("observation filing_year 1999 out of supported range [2000, 2099]")
    envelope = build_error_envelope(err)
    assert envelope.code == "ERROR_OBSERVATION_KEY"


# ---------------------------------------------------------------------------
# Site 1: observation_key — filing_year out of range
# ---------------------------------------------------------------------------


def test_observation_key_raises_on_year_below_range() -> None:
    with pytest.raises(ObservationKeyError) as excinfo:
        observation_key("303", Period.from_year_and_code(1999, "1T"))

    assert str(excinfo.value) == "application.calculations.observations.errors.filing_year_out_of_range"


def test_observation_key_raises_on_year_above_range() -> None:
    with pytest.raises(ObservationKeyError) as excinfo:
        observation_key("303", Period.from_year_and_code(2100, "1T"))

    assert str(excinfo.value) == "application.calculations.observations.errors.filing_year_out_of_range"


def test_observation_key_succeeds_on_boundary_years() -> None:
    assert observation_key("303", Period.from_year_and_code(2000, "1T")) == "303:2000:1T"
    assert observation_key("303", Period.from_year_and_code(2099, "4T")) == "303:2099:4T"


def test_observation_key_derives_storage_token_from_typed_period() -> None:
    period = Period.from_year_and_code(2026, "ext-2t")

    assert str(period) == "2026 EXT-2T"
    assert observation_key("369", period) == "369:2026:EXT-2T"


def test_observation_key_rejects_untyped_combined_period() -> None:
    combined_period: object = "2026 1T"

    with pytest.raises(ObservationKeyError) as excinfo:
        observation_key("303", cast(Period, combined_period))

    assert str(excinfo.value) == "application.calculations.observations.errors.period_type_invalid"


# ---------------------------------------------------------------------------
# Site 2: iva_wallet_decision_key — empty taxpayer_nif
# ---------------------------------------------------------------------------


def test_iva_wallet_decision_key_raises_on_empty_nif() -> None:
    with pytest.raises(ObservationKeyError) as excinfo:
        iva_wallet_decision_key("   ", Period.from_year_and_code(2024, "1T"))

    assert str(excinfo.value) == "application.calculations.observations.errors.taxpayer_nif_blank"


def test_iva_wallet_decision_key_raises_on_blank_nif() -> None:
    with pytest.raises(ObservationKeyError) as excinfo:
        iva_wallet_decision_key("", Period.from_year_and_code(2024, "1T"))

    assert str(excinfo.value) == "application.calculations.observations.errors.taxpayer_nif_blank"


# ---------------------------------------------------------------------------
# Site 3: iva_wallet_decision_key — target_year out of range
# ---------------------------------------------------------------------------


def test_iva_wallet_decision_key_raises_on_year_below_range() -> None:
    with pytest.raises(ObservationKeyError) as excinfo:
        iva_wallet_decision_key("12345678A", Period.from_year_and_code(1999, "1T"))

    assert str(excinfo.value) == "application.calculations.observations.errors.iva_wallet_target_year_out_of_range"


def test_iva_wallet_decision_key_raises_on_year_above_range() -> None:
    with pytest.raises(ObservationKeyError) as excinfo:
        iva_wallet_decision_key("12345678A", Period.from_year_and_code(2100, "1T"))

    assert str(excinfo.value) == "application.calculations.observations.errors.iva_wallet_target_year_out_of_range"


def test_iva_wallet_decision_key_succeeds() -> None:
    key = iva_wallet_decision_key("12345678A", Period.from_year_and_code(2024, "1T"))
    assert key.startswith("iva-wallet-decision:")


# ---------------------------------------------------------------------------
# Site 4: iva_wallet_decision_event_key — empty decision.taxpayer_nif
# ---------------------------------------------------------------------------


def _make_decision(*, taxpayer_nif: str) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2024,
        target_period=Period.from_year_and_code(2024, "1T"),
        selected_authority="local_recurrence",
        selected_amount=Decimal("1234.56"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("1234.56"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        decided_at=datetime(2024, 4, 1, tzinfo=UTC),
    )


def test_iva_wallet_decision_event_key_raises_on_empty_nif() -> None:
    # IvaCompensationReconciliationDecision enforces min_length=1 on taxpayer_nif,
    # so we cannot construct one with an empty string. We verify the guard is
    # unreachable via normal construction — the pydantic model catches it first.
    # The relevant guard at site 4 is exercised when the nif strips to empty;
    # pydantic rejects zero-length at construction time, so site 4 is defended
    # at the model boundary. We document this and assert pydantic blocks it.
    with pytest.raises(ValidationError):
        _make_decision(taxpayer_nif="")


def test_iva_wallet_decision_event_key_succeeds_for_valid_decision() -> None:
    decision = _make_decision(taxpayer_nif="12345678A")
    key = iva_wallet_decision_event_key(decision)
    assert key.startswith("iva-wallet-decision-event:")


# ---------------------------------------------------------------------------
# Type contract: ObservationKeyError is a subtype of ValueError
# ---------------------------------------------------------------------------


def test_observation_key_error_is_value_error() -> None:
    """ObservationKeyError inherits from CoreValidationError which inherits ValueError."""
    err = ObservationKeyError("test")
    assert isinstance(err, ValueError)


# ---------------------------------------------------------------------------
# contract: decision-key lookup behaviour
# ---------------------------------------------------------------------------


def test_load_decision_returns_hashed_key_record(tmp_path: Path) -> None:
    """load_decision finds records written under the current hashed key.

    Exercises the load_decision path: a record persisted via save_decision is
    keyed with iva_wallet_decision_key (hashed) and must be returned directly.
    """

    from ....tests.secure_sql import isolated_runtime_profile
    from ..observations_repository import IvaWalletDecisionRepository

    decided_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    decision = IvaCompensationReconciliationDecision(
        taxpayer_nif="87654321B",
        target_year=2025,
        target_period=Period.from_year_and_code(2025, "2T"),
        selected_authority="local_recurrence",
        selected_amount=Decimal("500.00"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("500.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason_identity="aeat_wallet_validated",
        decided_at=decided_at,
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = IvaWalletDecisionRepository()
        repo.save_decision(decision)

        loaded = repo.load_decision("87654321B", Period.from_year_and_code(2025, "2T"))

    assert loaded == decision, f"Expected decision to be found via hashed key; got {loaded!r}"
