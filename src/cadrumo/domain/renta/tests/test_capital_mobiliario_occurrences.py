"""Tests for the capital-mobiliario occurrence arithmetic."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from ..capital_mobiliario_occurrences import (
    AttestedNoWithholding,
    CapitalMobiliarioOccurrence,
    PayerComputed,
    PayerEvidence,
    PayerOutcome,
    PayerRecordEvidence,
    PayerRefusal,
    PayerRefusalKind,
    compute_capital_mobiliario_occurrences,
)
from ..errors import RentaValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# RIRPF art. 90.1 and LIRPF art. 101.4: the official rate on capital-mobiliario
# income. Production code receives it from the registry; the test supplies it.
OFFICIAL_RATE = Decimal("0.19")
D = Decimal
# The official design's detail records for interest (0027) and dividends (0029).
INTEREST_RECORD = "RegistroB11"
DIVIDEND_RECORD = "RegistroB13"


@dataclass(frozen=True)
class _Record:
    importe_integro: Decimal
    retencion: Decimal


def _occ(
    ref: str,
    net: str,
    *,
    record: str = INTEREST_RECORD,
    payer: str = "PAYER-A",
    share: str = "1",
    expenses: str = "0",
) -> CapitalMobiliarioOccurrence:
    return CapitalMobiliarioOccurrence(ref, record, payer, D(share), D(net), D(expenses))


def _record(integro: str, retencion: str) -> PayerRecordEvidence:
    return PayerRecordEvidence(_Record(D(integro), D(retencion)))


def _run(
    occurrences: list[CapitalMobiliarioOccurrence], evidence: dict[str, PayerEvidence]
) -> tuple[PayerOutcome, ...]:
    return compute_capital_mobiliario_occurrences(occurrences, evidence, OFFICIAL_RATE)


def _computed(outcome: PayerOutcome) -> PayerComputed:
    assert isinstance(outcome, PayerComputed)
    return outcome


def _refused(outcome: PayerOutcome) -> PayerRefusal:
    assert isinstance(outcome, PayerRefusal)
    return outcome


def test_manual_deposit_interest_single_occurrence() -> None:
    # Manual Renta 2025, part 1, p. 329: deposit interest 400, retention 19% = 76.
    # Cash credited is 400 - 76 = 324.
    (outcome,) = _run([_occ("dep", "324")], {"PAYER-A": _record("400", "76")})
    (occ,) = _computed(outcome).occurrences
    assert (occ.gross, occ.withholding, occ.expenses) == (D("400.00"), D("76.00"), D("0.00"))


def test_manual_account_interest_single_occurrence() -> None:
    # Manual Renta 2025, part 1, p. 362: bank TZ account interest 37, retention 7.03.
    (outcome,) = _run([_occ("cc", "29.97")], {"PAYER-A": _record("37", "7.03")})
    (occ,) = _computed(outcome).occurrences
    assert (occ.gross, occ.withholding) == (D("37.00"), D("7.03"))


def test_manual_dividends_with_custody_expense() -> None:
    # Manual Renta 2025, part 1, p. 361-362: dividends 1,502, retention 285.38,
    # custody and administration expense 90 (p. 363).
    (outcome,) = _run(
        [_occ("val", "1216.62", record=DIVIDEND_RECORD, expenses="90")],
        {"PAYER-A": _record("1502", "285.38")},
    )
    (occ,) = _computed(outcome).occurrences
    assert (occ.detail_record, occ.gross, occ.withholding, occ.expenses) == (
        DIVIDEND_RECORD,
        D("1502.00"),
        D("285.38"),
        D("90.00"),
    )


def test_holding_share_half() -> None:
    # Joint account of 200 net cash; the taxpayer holds half: 100 net, plus 19 retained = 119.
    (outcome,) = _run([_occ("joint", "200", share="0.5")], {"PAYER-A": _record("119", "19")})
    (occ,) = _computed(outcome).occurrences
    assert (occ.gross, occ.withholding) == (D("119.00"), D("19.00"))


def test_multi_occurrence_rebuilds_withholding_from_rate() -> None:
    # Two accounts: gross 100 and 200 at 19% leave net cash 81 and 162.
    # Payer record: integro 300, retencion 57.
    outcome = _run([_occ("a1", "81"), _occ("a2", "162")], {"PAYER-A": _record("300", "57")})
    first, second = _computed(outcome[0]).occurrences
    assert (first.gross, first.withholding) == (D("100.00"), D("19.00"))
    assert (second.gross, second.withholding) == (D("200.00"), D("38.00"))


def test_multi_occurrence_interest_and_dividend_with_rounding() -> None:
    # Manual figures: gross 37 (withholding 7.03) and 1,502 (285.38) at one bank.
    # Net cash 29.97 and 1216.62; record 1539 / 292.41.
    outcome = _run(
        [_occ("cc", "29.97"), _occ("val", "1216.62", record=DIVIDEND_RECORD)],
        {"PAYER-A": _record("1539", "292.41")},
    )
    first, second = _computed(outcome[0]).occurrences
    assert (first.gross, first.withholding) == (D("37.00"), D("7.03"))
    assert (second.gross, second.withholding) == (D("1502.00"), D("285.38"))


def test_multi_occurrence_withholding_sum_mismatch() -> None:
    # Cash agrees with a 300 gross, but the record states 50 withheld instead of 57.
    outcome = _run([_occ("a1", "81"), _occ("a2", "162")], {"PAYER-A": _record("293", "50")})
    refusal = _refused(outcome[0])
    assert refusal.kind is PayerRefusalKind.WITHHOLDING_SUM_MISMATCH
    assert (refusal.computed, refusal.recorded) == (D("57.00"), D("50"))


def test_payer_check_mismatch_states_both_figures() -> None:
    # 324 net + 76 retained = 400, but the certificate says 450.
    outcome = _run([_occ("dep", "324")], {"PAYER-A": _record("450", "76")})
    refusal = _refused(outcome[0])
    assert refusal.kind is PayerRefusalKind.PAYER_CHECK_MISMATCH
    assert (refusal.computed, refusal.recorded) == (D("400.00"), D("450"))
    assert refusal.position_refs == ("dep",)


def test_payer_check_tolerates_one_cent() -> None:
    (outcome,) = _run([_occ("dep", "324")], {"PAYER-A": _record("400.01", "76")})
    assert isinstance(outcome, PayerComputed)


def test_payer_check_refuses_two_cents() -> None:
    (outcome,) = _run([_occ("dep", "324")], {"PAYER-A": _record("400.02", "76")})
    assert _refused(outcome).kind is PayerRefusalKind.PAYER_CHECK_MISMATCH


def test_missing_payer_evidence_is_refused() -> None:
    (outcome,) = _run([_occ("dep", "324")], {})
    refusal = _refused(outcome)
    assert refusal.kind is PayerRefusalKind.PAYER_EVIDENCE_MISSING
    assert refusal.payer_key == "PAYER-A"


def test_attested_absence_has_zero_withholding_and_gross_equals_share_of_cash() -> None:
    outcome = _run(
        [_occ("a1", "10.50", share="0.5"), _occ("a2", "20")],
        {"PAYER-A": AttestedNoWithholding()},
    )
    first, second = _computed(outcome[0]).occurrences
    assert (first.gross, first.withholding) == (D("5.25"), D("0.00"))
    assert (second.gross, second.withholding) == (D("20.00"), D("0.00"))


def test_payers_are_independent_and_ordered_by_first_occurrence() -> None:
    outcome = _run(
        [_occ("a", "324", payer="P1"), _occ("b", "10", payer="P2")],
        {"P1": _record("400", "76")},
    )
    assert [o.payer_key for o in outcome] == ["P1", "P2"]
    assert isinstance(outcome[0], PayerComputed)
    assert _refused(outcome[1]).kind is PayerRefusalKind.PAYER_EVIDENCE_MISSING


@pytest.mark.parametrize("share", ["0", "-0.1", "1.01"])
def test_holding_share_outside_range_is_refused(share: str) -> None:
    with pytest.raises(RentaValidationError):
        _occ("x", "10", share=share)


def test_negative_expenses_are_refused() -> None:
    with pytest.raises(RentaValidationError):
        _occ("x", "10", expenses="-1")


@pytest.mark.parametrize("rate", ["0", "1", "-0.19"])
def test_rate_outside_open_unit_interval_is_refused(rate: str) -> None:
    with pytest.raises(RentaValidationError):
        compute_capital_mobiliario_occurrences([_occ("x", "10")], {}, D(rate))


def test_repeated_position_and_detail_record_is_refused() -> None:
    with pytest.raises(RentaValidationError):
        _run([_occ("x", "10"), _occ("x", "5")], {})
