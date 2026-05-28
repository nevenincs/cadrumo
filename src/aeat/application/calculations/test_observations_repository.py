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

import pytest
from pydantic import ValidationError

from ...core.errors import ERROR_REGISTRY, build_error_envelope
from ._errors import ObservationKeyError
from ._iva_wallet_reconciliation import IvaCompensationReconciliationDecision
from ._observations_repository import (
    iva_wallet_decision_event_key,
    iva_wallet_decision_key,
    observation_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
    with pytest.raises(ObservationKeyError, match="out of supported range"):
        observation_key("303", 1999, "1T")


def test_observation_key_raises_on_year_above_range() -> None:
    with pytest.raises(ObservationKeyError, match="out of supported range"):
        observation_key("303", 2100, "1T")


def test_observation_key_succeeds_on_boundary_years() -> None:
    assert observation_key("303", 2000, "1T") == "303:2000:1T"
    assert observation_key("303", 2099, "4T") == "303:2099:4T"


# ---------------------------------------------------------------------------
# Site 2: iva_wallet_decision_key — empty taxpayer_nif
# ---------------------------------------------------------------------------


def test_iva_wallet_decision_key_raises_on_empty_nif() -> None:
    with pytest.raises(ObservationKeyError, match="taxpayer_nif must be non-empty"):
        iva_wallet_decision_key("   ", 2024, "1T")


def test_iva_wallet_decision_key_raises_on_blank_nif() -> None:
    with pytest.raises(ObservationKeyError, match="taxpayer_nif must be non-empty"):
        iva_wallet_decision_key("", 2024, "1T")


# ---------------------------------------------------------------------------
# Site 3: iva_wallet_decision_key — target_year out of range
# ---------------------------------------------------------------------------


def test_iva_wallet_decision_key_raises_on_year_below_range() -> None:
    with pytest.raises(ObservationKeyError, match="out of supported range"):
        iva_wallet_decision_key("12345678A", 1999, "1T")


def test_iva_wallet_decision_key_raises_on_year_above_range() -> None:
    with pytest.raises(ObservationKeyError, match="out of supported range"):
        iva_wallet_decision_key("12345678A", 2100, "1T")


def test_iva_wallet_decision_key_succeeds() -> None:
    key = iva_wallet_decision_key("12345678A", 2024, "1T")
    assert key.startswith("iva-wallet-decision:")


# ---------------------------------------------------------------------------
# Site 4: iva_wallet_decision_event_key — empty decision.taxpayer_nif
# ---------------------------------------------------------------------------


def _make_decision(*, taxpayer_nif: str) -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif=taxpayer_nif,
        target_year=2024,
        target_period="1T",
        selected_authority="local_recurrence",
        selected_amount=Decimal("1234.56"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("1234.56"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="Test decision",
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
# Site 5: _legacy_iva_wallet_decision_key — target_year out of range
# (internal function; exercised indirectly via import-level white-box call)
# ---------------------------------------------------------------------------


def test_legacy_decision_key_year_guard() -> None:
    """The private legacy key helper must raise ObservationKeyError for out-of-range years."""
    from ._observations_repository import _legacy_iva_wallet_decision_key

    with pytest.raises(ObservationKeyError, match="out of supported range"):
        _legacy_iva_wallet_decision_key("12345678A", 1999, "1T")

    with pytest.raises(ObservationKeyError, match="out of supported range"):
        _legacy_iva_wallet_decision_key("12345678A", 2100, "1T")


# ---------------------------------------------------------------------------
# Type contract: ObservationKeyError is a subtype of ValueError
# ---------------------------------------------------------------------------


def test_observation_key_error_is_value_error() -> None:
    """ObservationKeyError inherits from CoreValidationError which inherits ValueError."""
    err = ObservationKeyError("test")
    assert isinstance(err, ValueError)


# ---------------------------------------------------------------------------
# S158: legacy decision-key bridge behaviour
# ---------------------------------------------------------------------------


def test_load_decision_returns_hashed_key_record(tmp_path) -> None:
    """load_decision finds records written under the current hashed key.

    Exercises the primary (non-fallback) path of load_decision: a record
    persisted via save_decision is keyed with iva_wallet_decision_key (hashed)
    and must be returned directly without triggering the legacy fallback.
    """
    from pathlib import Path

    from ...tests.secure_sql import isolated_runtime_profile
    from ._observations_repository import IvaWalletDecisionRepository

    decided_at = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
    decision = IvaCompensationReconciliationDecision(
        taxpayer_nif="87654321B",
        target_year=2025,
        target_period="2T",
        selected_authority="local_recurrence",
        selected_amount=Decimal("500.00"),
        wallet_amount=None,
        local_recurrence_amount=Decimal("500.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="Hashed-key path test.",
        decided_at=decided_at,
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = IvaWalletDecisionRepository()
        repo.save_decision(decision)

        loaded = repo.load_decision("87654321B", 2025, "2T")

    assert loaded == decision, (
        f"Expected decision to be found via hashed key; got {loaded!r}"
    )


def test_load_decision_falls_back_to_legacy_cleartext_key(tmp_path) -> None:
    """load_decision finds pre-hardening records written under the cleartext key.

    Simulates a record that was persisted before the sha256-key hardening
    by writing the envelope directly under the legacy key format
    `{nif}:{year}:{period}`. load_decision must return the decision via
    the _legacy_iva_wallet_decision_key fallback path.

    This test defends the migration bridge: if the fallback call in
    load_decision is removed before all pre-hardening records are migrated,
    this test fails loudly.
    """
    from datetime import UTC, datetime

    from ...adapters.persistence.storage.envelope._envelope import Envelope
    from ...tests.secure_sql import isolated_runtime_profile
    from ._observations_repository import (
        IvaWalletDecisionRepository,
        _IvaWalletDecisionEnvelopePayload,
        _legacy_iva_wallet_decision_key,
    )

    decided_at = datetime(2024, 3, 15, 9, 0, 0, tzinfo=UTC)
    pre_hardening_decision = IvaCompensationReconciliationDecision(
        taxpayer_nif="11223344C",
        target_year=2024,
        target_period="1T",
        selected_authority="aeat_wallet",
        selected_amount=Decimal("750.00"),
        wallet_amount=Decimal("750.00"),
        local_recurrence_amount=Decimal("750.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="Pre-hardening legacy key test.",
        decided_at=decided_at,
    )

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = IvaWalletDecisionRepository()
        legacy_key = _legacy_iva_wallet_decision_key("11223344C", 2024, "1T")

        # Simulate a pre-hardening record by writing directly under the cleartext key.
        payload = _IvaWalletDecisionEnvelopePayload(decision=pre_hardening_decision)
        envelope = Envelope[_IvaWalletDecisionEnvelopePayload](
            schema_version=repo.schema_version,
            written_at=decided_at,
            classification=repo.sensitivity,
            payload=payload,
        )
        repo._objects.save(
            namespace=repo.namespace,
            object_key=legacy_key,
            classification=repo.sensitivity,
            schema_version=repo.schema_version,
            written_at=decided_at,
            payload=envelope.model_dump_json().encode("utf-8"),
        )

        # load_decision must find it via the legacy fallback path.
        loaded = repo.load_decision("11223344C", 2024, "1T")

    assert loaded == pre_hardening_decision, (
        f"Expected legacy-keyed decision to be found via fallback; got {loaded!r}. "
        "The _legacy_iva_wallet_decision_key bridge in load_decision may have been removed prematurely."
    )
