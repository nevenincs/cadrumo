"""Truth-table tests for :func:`aeat.deadlines.applies_to`.

Each parametrised case asserts the documented BOE / Manual práctico
rule for one autónomo modelo against one profile-flag combination.
"""

from __future__ import annotations

import pytest

from aeat.deadlines import (
    AutonomoProfile,
    IVARegime,
    ScheduleComputationError,
    applies_to,
    explain,
)

pytestmark = pytest.mark.unit


def _make_profile(
    *,
    iva_regime: IVARegime = IVARegime.GENERAL,
    has_employees: bool = False,
    pays_professionals_with_retencion: bool = False,
    professional_income_withholding_ge_70pct: bool = False,
    pays_rent_with_retencion: bool = False,
    does_intracomunitario: bool = False,
    third_party_transactions_above_347_threshold: bool = False,
    bienes_extranjero_above_threshold: bool = False,
) -> AutonomoProfile:
    return AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=iva_regime,
        has_employees=has_employees,
        pays_professionals_with_retencion=pays_professionals_with_retencion,
        professional_income_withholding_ge_70pct=professional_income_withholding_ge_70pct,
        pays_rent_with_retencion=pays_rent_with_retencion,
        does_intracomunitario=does_intracomunitario,
        third_party_transactions_above_347_threshold=third_party_transactions_above_347_threshold,
        bienes_extranjero_above_threshold=bienes_extranjero_above_threshold,
    )


def test_modelo_130_applies_by_default() -> None:
    assert applies_to(_make_profile(), "130") is True


def test_modelo_130_professional_withholding_exception() -> None:
    assert (
        applies_to(
            _make_profile(professional_income_withholding_ge_70pct=True),
            "130",
        )
        is False
    )


@pytest.mark.parametrize(
    ("regime", "expected"),
    [
        (IVARegime.GENERAL, True),
        (IVARegime.SIMPLIFICADO, True),
        (IVARegime.RECARGO_EQUIVALENCIA, False),
        (IVARegime.EXENTO, False),
    ],
)
def test_modelo_303(regime: IVARegime, expected: bool) -> None:
    assert applies_to(_make_profile(iva_regime=regime), "303") is expected


@pytest.mark.parametrize(
    ("regime", "expected"),
    [
        (IVARegime.GENERAL, True),
        (IVARegime.SIMPLIFICADO, True),
        (IVARegime.RECARGO_EQUIVALENCIA, False),
        (IVARegime.EXENTO, False),
    ],
)
def test_modelo_390_mirrors_303(regime: IVARegime, expected: bool) -> None:
    assert applies_to(_make_profile(iva_regime=regime), "390") is expected


def test_modelo_100_universal() -> None:
    assert applies_to(_make_profile(), "100") is True


@pytest.mark.parametrize(
    ("has_employees", "pays_professionals", "expected"),
    [
        (False, False, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
def test_modelo_111(has_employees: bool, pays_professionals: bool, expected: bool) -> None:
    assert (
        applies_to(
            _make_profile(
                has_employees=has_employees,
                pays_professionals_with_retencion=pays_professionals,
            ),
            "111",
        )
        is expected
    )


@pytest.mark.parametrize(
    ("has_employees", "pays_professionals", "expected"),
    [
        (False, False, False),
        (True, False, True),
        (False, True, True),
    ],
)
def test_modelo_190_mirrors_111(has_employees: bool, pays_professionals: bool, expected: bool) -> None:
    assert (
        applies_to(
            _make_profile(
                has_employees=has_employees,
                pays_professionals_with_retencion=pays_professionals,
            ),
            "190",
        )
        is expected
    )


@pytest.mark.parametrize("pays_rent", [True, False])
def test_modelo_115(pays_rent: bool) -> None:
    assert applies_to(_make_profile(pays_rent_with_retencion=pays_rent), "115") is pays_rent


@pytest.mark.parametrize("pays_rent", [True, False])
def test_modelo_180_mirrors_115(pays_rent: bool) -> None:
    assert applies_to(_make_profile(pays_rent_with_retencion=pays_rent), "180") is pays_rent


@pytest.mark.parametrize("intra_eu", [True, False])
def test_modelo_349(intra_eu: bool) -> None:
    assert applies_to(_make_profile(does_intracomunitario=intra_eu), "349") is intra_eu


@pytest.mark.parametrize("above", [True, False])
def test_modelo_347(above: bool) -> None:
    assert (
        applies_to(
            _make_profile(third_party_transactions_above_347_threshold=above),
            "347",
        )
        is above
    )


@pytest.mark.parametrize("above", [True, False])
def test_modelo_720(above: bool) -> None:
    assert applies_to(_make_profile(bienes_extranjero_above_threshold=above), "720") is above


def test_unknown_modelo_raises() -> None:
    with pytest.raises(ScheduleComputationError):
        applies_to(_make_profile(), "999")


def test_explain_unknown_modelo_raises() -> None:
    with pytest.raises(ScheduleComputationError):
        explain(_make_profile(), "999")


def test_explain_returns_decision() -> None:
    text_yes = explain(_make_profile(pays_professionals_with_retencion=True), "111")
    text_no = explain(_make_profile(), "111")
    assert "aplica" in text_yes
    assert "no aplica" in text_no
