"""Modelo 100 quota and extraction-profile legal-reference registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_legal_refs_support import (
    _ANUALIDADES_ALIMENTOS_TOTAL_CASILLA,
    _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF,
    _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
    _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
    _BASE_LIQUIDABLE_ART_50_REF,
    _BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA,
    _BROAD_DEDUCTION_ART_68_REF,
    _FRACTIONAL_PAYMENT_ARTICLE_REF,
    _GENERAL_BASE_CUOTA_CASILLAS,
    _GENERAL_SCALE_ART_63_REF,
    _M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE,
    _MODELO_100_2025_FORM_ORDER_REF,
    _PERSONAL_FAMILY_MINIMUM_ART_56_REF,
    _SAVINGS_BASE_ART_49_REF,
    _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025,
    _STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
    _STATE_DEDUCTION_ART_67_REF,
    _STATE_INTEGRAL_QUOTA_ART_62_REF,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_general_liquidable_and_cuota_chain_exclude_unrelated_articles(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    checked_casilla_ids = {_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA, *_GENERAL_BASE_CUOTA_CASILLAS}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in checked_casilla_ids}

    assert set(casillas_by_id) == checked_casilla_ids
    base_casilla = casillas_by_id[_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA]
    assert _BASE_LIQUIDABLE_ART_50_REF in base_casilla.legal_refs
    assert _SAVINGS_BASE_ART_49_REF not in base_casilla.legal_refs
    assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in base_casilla.legal_refs

    formula_by_target = {
        formula.target_casilla_id: formula
        for formula in revision.formulas
        if formula.target_casilla_id in checked_casilla_ids
    }
    base_formula = formula_by_target.get(_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA)
    if base_formula is not None:
        assert _BASE_LIQUIDABLE_ART_50_REF in base_formula.legal_refs
        assert _SAVINGS_BASE_ART_49_REF not in base_formula.legal_refs
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in base_formula.legal_refs

    for casilla_id in _GENERAL_BASE_CUOTA_CASILLAS:
        casilla = casillas_by_id[casilla_id]
        formula = formula_by_target[casilla_id]
        assert _GENERAL_SCALE_ART_63_REF in casilla.legal_refs, casilla.id
        assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, casilla.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id
        assert _SAVINGS_BASE_ART_49_REF not in formula.legal_refs, formula.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in formula.legal_refs, formula.id


def test_modelo_100_2025_scale_result_casillas_use_scale_articles_not_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025
    }
    formula_by_target = {
        formula.target_casilla_id: formula
        for formula in revision.formulas
        if formula.target_casilla_id in _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025
    }

    assert set(casillas_by_id) == set(_SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025)
    assert set(formula_by_target) == set(_SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025)
    for casilla_id, expected_ref in _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025.items():
        casilla = casillas_by_id[casilla_id]
        formula = formula_by_target[casilla_id]
        assert expected_ref in casilla.legal_refs, casilla.id
        assert expected_ref in formula.legal_refs, formula.id
        assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, casilla.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id
        assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in formula.legal_refs, formula.id


@pytest.mark.parametrize("filing_year", range(2021, 2026))
def test_modelo_100_anualidades_formula_uses_child_support_articles(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    formula_id = f"renta-{filing_year}-anualidades-alimentos-hijos-suma"
    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    expected_refs = {
        _STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
        _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF,
    }

    assert formula_id in formulas_by_id
    formula = formulas_by_id[formula_id]
    assert formula.target_casilla_id == _ANUALIDADES_ALIMENTOS_TOTAL_CASILLA
    assert set(formula.legal_refs) == expected_refs
    assert _BASE_LIQUIDABLE_ART_50_REF not in formula.legal_refs
    assert expected_refs <= set(casillas_by_id[_ANUALIDADES_ALIMENTOS_TOTAL_CASILLA].legal_refs)
    required_text = {text for citation in formula.source_citations for text in citation.required_text}
    assert "anualidades por alimentos a favor de los hijos" in required_text
    assert "resto de la base liquidable general" in required_text


def test_modelo_100_2025_cuota_chain_casillas_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    checked = [casilla for casilla in revision.casillas if casilla.id.isdigit() and "0500" <= casilla.id <= "0546"]

    assert {casilla.id for casilla in checked} == {f"{number:04d}" for number in range(500, 547)}
    offenders = {
        casilla.id: casilla.legal_refs for casilla in checked if _FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
    }
    assert not offenders


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_autonomic_quota_formula_refs_match_lirpf_articles(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    form_order_refs = {_MODELO_100_2025_FORM_ORDER_REF} if filing_year == 2025 else set()
    expected_refs_by_formula = {
        f"renta-{filing_year}-tipo-medio-gravamen-autonomico-base-liquidable-general": {
            _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
        },
        f"renta-{filing_year}-tipo-medio-gravamen-autonomico-base-liquidable-ahorro": {
            _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
        },
        f"renta-{filing_year}-minimo-personal-base-liquidable-ahorro-autonomica": {
            _PERSONAL_FAMILY_MINIMUM_ART_56_REF,
            _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-escala-autonomica-sobre-base-liquidable-general": {
            _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
            _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-escala-autonomica-sobre-minimo-personal-familiar": {
            _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
            _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-base-liquidable-general-autonomica": {
            _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
            _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-integra-autonomica": {
            _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
            _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
            *form_order_refs,
        },
    }

    assert expected_refs_by_formula.keys() <= formulas_by_id.keys()
    offenders: dict[str, tuple[str, ...]] = {}
    for formula_id, expected_refs in expected_refs_by_formula.items():
        legal_refs = tuple(formulas_by_id[formula_id].legal_refs)
        if set(legal_refs) != expected_refs:
            offenders[formula_id] = legal_refs
        assert _STATE_INTEGRAL_QUOTA_ART_62_REF not in legal_refs, formula_id
        assert _STATE_DEDUCTION_ART_67_REF not in legal_refs, formula_id
        assert _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF not in legal_refs, formula_id

    assert not offenders


@pytest.mark.parametrize("filing_year", range(2021, 2024))
def test_modelo_100_extraction_profile_legal_refs_match_target_casillas(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
    profiles_by_surface = {
        profile.surface: profile
        for profile in revision.extraction_profiles
        if profile.surface in _M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE
    }

    assert set(profiles_by_surface) == set(_M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE)
    for surface, profile in profiles_by_surface.items():
        expected_refs = _M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE[surface]
        target_refs = frozenset(
            legal_ref
            for target in profile.target_casillas
            for legal_ref in casillas_by_id[target.casilla_id].legal_refs
        )

        assert target_refs == expected_refs
        assert set(profile.legal_refs) == expected_refs
        assert _BROAD_DEDUCTION_ART_68_REF not in profile.legal_refs
