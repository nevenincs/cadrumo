"""IVA compensation records identify their subject through the tax-id authority.

``IvaCompensationPeriodState`` and ``IvaCompensationCarryForwardLot`` name the
filing subject, and those values reach carry-forward projection, wallet balance
and live history consumers as if they identified that subject. A bounded plain
string cannot enforce the AEAT checksum, so ``taxpayer_nif='bad'`` was
persistable and returned intact; both fields are now
:data:`~cadrumo.core.identity.SubjectTaxId`, the same authority every other
subject-identifying field uses.

Anti-tautology: the checksum-invalid case (``12345678A``) is one letter away
from the valid one (``12345678Z``), so a guard that merely checked shape or
length would accept it and fail this test. The whitespace case asserts the
NORMALISED value, so a validator that accepted the input without canonicalising
it also fails.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import IvaCompensationStateProvenance, Period
from ..carry_forward import (
    IvaCompensationCarryForwardLot,
    IvaCompensationExpiryReviewState,
    IvaCompensationPeriodState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VALID_NIF = "12345678Z"
#: Same eight digits as ``_VALID_NIF`` with the wrong control letter, so only a
#: real checksum — not a shape or length check — can tell them apart.
_CHECKSUM_INVALID_NIF = "12345678A"
_PRESENTED_AT = datetime(2025, 4, 20, tzinfo=UTC)


def _period_state(taxpayer_nif: str) -> IvaCompensationPeriodState:
    return IvaCompensationPeriodState(
        taxpayer_nif=taxpayer_nif,
        provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        expediente_id="202530300000001Z",
        status="presented",
        presented_at=_PRESENTED_AT,
        generated_amount=Decimal("100.00"),
        available_end_amount=Decimal("100.00"),
        source_observation_key="303:2025:1T",
    )


def _lot(taxpayer_nif: str) -> IvaCompensationCarryForwardLot:
    return IvaCompensationCarryForwardLot(
        taxpayer_nif=taxpayer_nif,
        source_filing_year=2025,
        source_period=Period.from_year_and_code(2025, "1T"),
        generated_amount=Decimal("100.00"),
        applied_amount=Decimal("40.00"),
        remaining_amount=Decimal("60.00"),
        age_years=0,
        expiry_review_state=IvaCompensationExpiryReviewState.ACTIVE,
        source_observation_key="303:2025:1T",
    )


@pytest.mark.parametrize("malformed", ["bad", _CHECKSUM_INVALID_NIF])
def test_period_state_refuses_a_malformed_taxpayer_identity(malformed: str) -> None:
    with pytest.raises(ValidationError):
        _period_state(malformed)


@pytest.mark.parametrize("malformed", ["bad", _CHECKSUM_INVALID_NIF])
def test_carry_forward_lot_refuses_a_malformed_taxpayer_identity(malformed: str) -> None:
    with pytest.raises(ValidationError):
        _lot(malformed)


def test_period_state_normalises_a_valid_whitespace_padded_identity() -> None:
    assert _period_state(f"  {_VALID_NIF}  ").taxpayer_nif == _VALID_NIF


def test_carry_forward_lot_normalises_a_valid_whitespace_padded_identity() -> None:
    assert _lot(f"  {_VALID_NIF}  ").taxpayer_nif == _VALID_NIF


def test_period_state_accepts_a_valid_identity_unchanged() -> None:
    assert _period_state(_VALID_NIF).taxpayer_nif == _VALID_NIF


def test_period_state_allows_an_explicitly_undeclared_subject() -> None:
    """None is the declared 'subject not carried' case, distinct from malformed.

    The annual-partition reconstruction rebuilds period states from casilla
    observations, which record no taxpayer. Those states are scaffold for the
    FIFO partition and are never persisted, so they declare no subject rather
    than fabricating a label. This must stay distinguishable from the
    malformed cases above, which are still refused.
    """
    state = IvaCompensationPeriodState(
        taxpayer_nif=None,
        provenance=IvaCompensationStateProvenance.CASILLA_RECONSTRUCTION,
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        presented_at=_PRESENTED_AT,
        generated_amount=Decimal("100.00"),
        available_end_amount=Decimal("100.00"),
        source_observation_key="303:2025:1T",
    )

    assert state.taxpayer_nif is None
