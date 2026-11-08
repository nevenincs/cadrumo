"""Whether a recipient's income bears retención resolves, with its provisions, in every supported year.

Hand-derived oracle. An IRPF recipient's work income, activity income, urban rent
and movable capital income bear retención (LIRPF arts. 99 and 101, RIRPF arts. 75
and 76). An IS recipient's income bears it only where RIS art. 60.1 lists it
(letters a, e and f: capital income, urban rent and collective investment
transmissions), arising at exigibility or earlier payment (art. 65); a
professional fee and work income are not in that list.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry.tests.published_authority import published_supported_filing_years
from ..received_invoice_withholding import withholding_subjectness
from ..withholding_recognition import WithholdingIncomeKind, WithholdingRecipientTaxRegime

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_IRPF_PROVISIONS = ("ley-35-2006:art-99", "ley-35-2006:art-101", "rd-439-2007:art-75", "rd-439-2007:art-76")
_RIS_SUBJECT = ("rd-634-2015:art-60", "rd-634-2015:art-65")
_RIS_NOT_SUBJECT = ("rd-634-2015:art-60",)

_IRPF = WithholdingRecipientTaxRegime.IRPF
_IS = WithholdingRecipientTaxRegime.IS
_KIND = WithholdingIncomeKind

_ORACLE = (
    (_IRPF, _KIND.WORK, True, _IRPF_PROVISIONS),
    (_IRPF, _KIND.PROFESSIONAL, True, _IRPF_PROVISIONS),
    (_IRPF, _KIND.URBAN_RENT, True, _IRPF_PROVISIONS),
    (_IRPF, _KIND.ORDINARY_MOVABLE_CAPITAL, True, _IRPF_PROVISIONS),
    (_IRPF, _KIND.INVESTMENT_FUND, True, _IRPF_PROVISIONS),
    (_IS, _KIND.URBAN_RENT, True, _RIS_SUBJECT),
    (_IS, _KIND.ORDINARY_MOVABLE_CAPITAL, True, _RIS_SUBJECT),
    (_IS, _KIND.INVESTMENT_FUND, True, _RIS_SUBJECT),
    (_IS, _KIND.PROFESSIONAL, False, _RIS_NOT_SUBJECT),
    (_IS, _KIND.WORK, False, _RIS_NOT_SUBJECT),
)


def _envelope_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    return tuple(sorted(support.years))


@pytest.mark.parametrize("year", _envelope_years())
def test_every_row_resolves_with_its_provisions_in_each_supported_year(year: int) -> None:
    for on in (date(year, 1, 1), date(year, 12, 31)):
        resolved = [(regime, kind, *withholding_subjectness(regime, kind, on=on)) for regime, kind, _, _ in _ORACLE]

        assert resolved == list(_ORACLE), f"{on}"


def test_a_regime_the_fact_does_not_declare_settles_nothing() -> None:
    year = _envelope_years()[-1]

    assert withholding_subjectness(
        WithholdingRecipientTaxRegime.IRNR, WithholdingIncomeKind.PROFESSIONAL, on=date(year, 6, 30)
    ) == (None, ())
