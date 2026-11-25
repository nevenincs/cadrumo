"""Whether a negative Modelo 303 result may be asked back, or only carried forward.

The rule is LIVA art. 115. Its Uno grants the refund of the balance standing at
31 December "en la autoliquidación correspondiente al último período de
liquidación de dicho año"; its Dos extends it to the end of every period only
for the taxpayers of art. 116, who opt into the monthly procedure whose
"período de liquidación [...] coincidirá con el mes natural" — the Registro de
devolución mensual of RIVA art. 30. The Manual práctico de IVA states the same
condition for the filer: "para poder solicitar la devolución del saldo
existente al término de cada periodo de liquidación, los sujetos pasivos
deberán estar inscritos en el registro de devolución mensual. En otro caso,
solo podrán solicitar la devolución del saldo que tengan a su favor al término
del último periodo de liquidación de cada año natural."

Which periods are the year's last is never asserted here as a list: it is read
from the registry's own declaration through the resolved scheme, and every
expectation below is stated from that declaration. The whole supported filing
envelope is enumerated from the registry, so no year silently stops being
covered.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.refund_eligibility import (
    RefundEligibilityPolicy,
    resolve_refund_eligibility_policy_for_period,
)
from ..refund_eligibility import (
    RedemeEnrolmentState,
    RefundEligibilityBasis,
    RefundEligibilityOutcome,
    redeme_enrolment_state,
    refund_eligibility_for_period,
    resolve_refund_eligibility,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_QUARTERS = ("1T", "2T", "3T", "4T")
_MONTHS = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")


def _supported_years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    """Every filing year the registry's one support envelope declares."""
    return tuple(sorted(operation.supported_filing_years().years))


def _scheme(year: int, code: str) -> RefundEligibilityPolicy:
    return resolve_refund_eligibility_policy_for_period(Period.from_year_and_code(year, code))


def _final_codes(scheme: RefundEligibilityPolicy, codes: tuple[str, ...]) -> frozenset[str]:
    """The codes of ``codes`` the registry itself declares final, so no list is held here."""
    return frozenset(code for code in codes if code in scheme.final_period_tokens)


def test_the_unstated_redeme_answer_is_not_a_no() -> None:
    """A profile that has not answered is not a profile that answered no."""
    assert redeme_enrolment_state(None) is RedemeEnrolmentState.UNSTATED
    assert redeme_enrolment_state(False) is RedemeEnrolmentState.NOT_ENROLLED
    assert redeme_enrolment_state(True) is RedemeEnrolmentState.ENROLLED


@pytest.mark.parametrize("codes", [_QUARTERS, _MONTHS], ids=["quarterly", "monthly"])
def test_a_non_final_period_carries_the_credit_forward_for_a_filer_outside_redeme(
    operation: PinnedAuthorityOperation, codes: tuple[str, ...]
) -> None:
    """LIVA art. 115.Uno: outside the year's last period a filer outside REDEME can only compensate."""
    for year in _supported_years(operation):
        scheme = _scheme(year, codes[0])
        final = _final_codes(scheme, codes)
        assert final, f"the registry declares no final {codes[0]!r}-cadence period, so this cadence is untested"
        for code in codes:
            if code in final:
                continue
            eligibility = resolve_refund_eligibility(
                period=Period.from_year_and_code(year, code),
                period_scheme=scheme,
                redeme=RedemeEnrolmentState.NOT_ENROLLED,
            )
            assert eligibility.outcome is RefundEligibilityOutcome.CARRY_FORWARD_ONLY, (year, code)
            assert eligibility.basis is RefundEligibilityBasis.NON_FINAL_PERIOD, (year, code)
            assert not eligibility.refund_allowed, (year, code)
            assert eligibility.legal_refs, (year, code)


@pytest.mark.parametrize("codes", [_QUARTERS, _MONTHS], ids=["quarterly", "monthly"])
def test_a_redeme_filer_may_ask_for_the_refund_in_every_period(
    operation: PinnedAuthorityOperation, codes: tuple[str, ...]
) -> None:
    """LIVA art. 115.Dos with art. 116: the monthly procedure opens the refund at the end of each period."""
    for year in _supported_years(operation):
        scheme = _scheme(year, codes[0])
        for code in codes:
            eligibility = resolve_refund_eligibility(
                period=Period.from_year_and_code(year, code),
                period_scheme=scheme,
                redeme=RedemeEnrolmentState.ENROLLED,
            )
            assert eligibility.outcome is RefundEligibilityOutcome.REFUND_ALLOWED, (year, code)
            assert eligibility.refund_allowed, (year, code)


@pytest.mark.parametrize("codes", [_QUARTERS, _MONTHS], ids=["quarterly", "monthly"])
def test_the_years_last_period_opens_the_refund_to_everyone(
    operation: PinnedAuthorityOperation, codes: tuple[str, ...]
) -> None:
    """The annual refund needs no inscription, so even an unstated one does not withhold it."""
    for year in _supported_years(operation):
        scheme = _scheme(year, codes[0])
        for code in _final_codes(scheme, codes):
            for redeme in RedemeEnrolmentState:
                eligibility = resolve_refund_eligibility(
                    period=Period.from_year_and_code(year, code), period_scheme=scheme, redeme=redeme
                )
                assert eligibility.outcome is RefundEligibilityOutcome.REFUND_ALLOWED, (year, code, redeme)
                assert eligibility.basis is RefundEligibilityBasis.FINAL_PERIOD, (year, code, redeme)


@pytest.mark.parametrize("codes", [_QUARTERS, _MONTHS], ids=["quarterly", "monthly"])
def test_an_unstated_inscription_outside_the_last_period_stays_undetermined(
    operation: PinnedAuthorityOperation, codes: tuple[str, ...]
) -> None:
    """Neither a refusal nor a refund: the missing fact is reported so it can be asked for."""
    for year in _supported_years(operation):
        scheme = _scheme(year, codes[0])
        final = _final_codes(scheme, codes)
        for code in codes:
            if code in final:
                continue
            eligibility = resolve_refund_eligibility(
                period=Period.from_year_and_code(year, code),
                period_scheme=scheme,
                redeme=RedemeEnrolmentState.UNSTATED,
            )
            assert eligibility.outcome is RefundEligibilityOutcome.UNDETERMINED_REDEME_UNSTATED, (year, code)
            assert eligibility.basis is RefundEligibilityBasis.REDEME, (year, code)
            assert not eligibility.refund_allowed, (year, code)


def test_a_monthly_filer_mid_year_and_in_december(operation: PinnedAuthorityOperation) -> None:
    """The cadence comes from the registry's period codes: month 05 is not final, month 12 is."""
    for year in _supported_years(operation):
        scheme = _scheme(year, "05")
        assert "05" not in scheme.final_period_tokens
        assert "12" in scheme.final_period_tokens

        mid_year = Period.from_year_and_code(year, "05")
        assert (
            resolve_refund_eligibility(
                period=mid_year, period_scheme=scheme, redeme=RedemeEnrolmentState.NOT_ENROLLED
            ).outcome
            is RefundEligibilityOutcome.CARRY_FORWARD_ONLY
        )
        assert (
            resolve_refund_eligibility(
                period=mid_year, period_scheme=scheme, redeme=RedemeEnrolmentState.ENROLLED
            ).outcome
            is RefundEligibilityOutcome.REFUND_ALLOWED
        )

        december = resolve_refund_eligibility(
            period=Period.from_year_and_code(year, "12"),
            period_scheme=_scheme(year, "12"),
            redeme=RedemeEnrolmentState.NOT_ENROLLED,
        )
        assert december.outcome is RefundEligibilityOutcome.REFUND_ALLOWED
        assert december.basis is RefundEligibilityBasis.FINAL_PERIOD


def test_each_earlier_supported_year_resolves_under_its_own_scheme(
    operation: PinnedAuthorityOperation,
) -> None:
    """A carry's source period is answered with that period's own scheme, not this year's."""
    years = _supported_years(operation)
    assert len(years) > 1, "the support envelope declares a single year, so no earlier year can be tested"
    for year in years:
        fourth_quarter = resolve_refund_eligibility(
            period=Period.from_year_and_code(year, "4T"),
            period_scheme=_scheme(year, "4T"),
            redeme=RedemeEnrolmentState.NOT_ENROLLED,
        )
        assert fourth_quarter.outcome is RefundEligibilityOutcome.REFUND_ALLOWED, year
        assert fourth_quarter.basis is RefundEligibilityBasis.FINAL_PERIOD, year


def test_the_convenience_entry_point_agrees_with_the_resolver(operation: PinnedAuthorityOperation) -> None:
    """Resolving the scheme inside must not change the answer a caller holding one gets."""
    for year in _supported_years(operation):
        for code in ("3T", "4T", "05", "12"):
            period = Period.from_year_and_code(year, code)
            for redeme in RedemeEnrolmentState:
                assert refund_eligibility_for_period(period=period, redeme=redeme) == resolve_refund_eligibility(
                    period=period, period_scheme=_scheme(year, code), redeme=redeme
                ), (year, code, redeme)


def test_the_legal_refs_come_from_the_registry_declaration(operation: PinnedAuthorityOperation) -> None:
    """No legal reference is held in code: each outcome cites what the registry declares."""
    year = _supported_years(operation)[-1]
    scheme = _scheme(year, "4T")
    declared = {ref for definition in scheme.definitions for ref in definition.legal_refs}
    assert declared, "the refund eligibility policy declares no legal reference to cite"

    for redeme in RedemeEnrolmentState:
        for code in ("3T", "4T"):
            eligibility = resolve_refund_eligibility(
                period=Period.from_year_and_code(year, code), period_scheme=scheme, redeme=redeme
            )
            assert set(eligibility.legal_refs) <= declared, (code, redeme)
