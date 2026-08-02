"""Modelo 100 quota and extraction-profile legal-reference registry tests."""

from __future__ import annotations

from functools import lru_cache

import pytest

from ._modelo_100_legal_refs_support import (
    _ANUALIDADES_ALIMENTOS_TOTAL_CASILLA,
    _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
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

_LIVE_M100_YEARS = tuple(range(2020, 2026))
_ANUALIDADES_FORMULA_YEARS = tuple(range(2022, 2026))
_ANUALIDADES_MANUAL_INPUT_YEARS = (2020, 2021)
_EXTRACTION_PROFILE_YEARS = tuple(range(2021, 2024))

#: Each pre-2024/2025 filing year's applicability window predates arts. 75/76's
#: current catalogue redactions (effective_from 2025-04-03 / 2024-12-22), so it
#: cites the version-scoped redaction actually in force for that filing year
#: instead of the bare current id.
_AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF_BY_YEAR = {
    2020: "ley-35-2006:art-75-2015",
    2021: "ley-35-2006:art-75-2015",
    2022: "ley-35-2006:art-75-2015",
    2023: "ley-35-2006:art-75-2015",
    2024: "ley-35-2006:art-75",
    2025: "ley-35-2006:art-75",
}
_AUTONOMIC_SAVINGS_SCALE_ART_76_REF_BY_YEAR = {
    2020: "ley-35-2006:art-76-2015",
    2021: "ley-35-2006:art-76-2021",
    2022: "ley-35-2006:art-76-2021",
    2023: "ley-35-2006:art-76-2023",
    2024: "ley-35-2006:art-76",
    2025: "ley-35-2006:art-76",
}


@lru_cache
def _revision_for(filing_year: int):
    return _modelo_100_snapshot(filing_year).revision


def test_modelo_100_general_liquidable_and_cuota_chain_exclude_unrelated_articles() -> None:
    for filing_year in _LIVE_M100_YEARS:
        revision = _revision_for(filing_year)
        checked_casilla_ids = {_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA, *_GENERAL_BASE_CUOTA_CASILLAS}
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in checked_casilla_ids}

        assert set(casillas_by_id) == checked_casilla_ids
        base_casilla = casillas_by_id[_BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA]
        assert _BASE_LIQUIDABLE_ART_50_REF in base_casilla.legal_refs
        assert _PERSONAL_FAMILY_MINIMUM_ART_56_REF not in base_casilla.legal_refs
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
            assert _GENERAL_SCALE_ART_63_REF in base_formula.legal_refs
            assert _PERSONAL_FAMILY_MINIMUM_ART_56_REF not in base_formula.legal_refs
            assert _SAVINGS_BASE_ART_49_REF not in base_formula.legal_refs
            assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in base_formula.legal_refs

        for casilla_id in _GENERAL_BASE_CUOTA_CASILLAS:
            casilla = casillas_by_id[casilla_id]
            formula = formula_by_target[casilla_id]
            assert _GENERAL_SCALE_ART_63_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert _SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, (filing_year, casilla.id)
            assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, (filing_year, casilla.id)
            assert _SAVINGS_BASE_ART_49_REF not in formula.legal_refs, (filing_year, formula.id)
            assert _FRACTIONAL_PAYMENT_ARTICLE_REF not in formula.legal_refs, (filing_year, formula.id)


def test_modelo_100_2025_scale_result_casillas_use_scale_articles_not_fractional_payment_article() -> None:
    revision = _revision_for(2025)
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


# Casilla 0527 (anualidades por alimentos) is a direct manual input in 2020 and
# 2021 (the bundled AEAT XSD declares IMPALIM `maxOccurs="1"`, a plain scalar
# with no per-child structure) and a computed sum over the per-child "Hijo/Hija
# N: Importe de las anualidades por alimentos satisfechas" block from 2022
# onward. Casillas 1741/1744/1749/1754/1759 are unrelated Anexo C
# aportaciones/contribuciones a sistemas de previsión social fields in 2021
# and must not be summed into 0527 for that year.


def test_modelo_100_anualidades_formula_uses_child_support_articles() -> None:
    for filing_year in _ANUALIDADES_FORMULA_YEARS:
        expected_refs = {
            _STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
            _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF_BY_YEAR[filing_year],
        }
        revision = _revision_for(filing_year)
        formula_id = f"renta-{filing_year}-anualidades-alimentos-hijos-suma"
        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

        assert formula_id in formulas_by_id
        formula = formulas_by_id[formula_id]
        assert formula.target_casilla_id == _ANUALIDADES_ALIMENTOS_TOTAL_CASILLA
        assert set(formula.legal_refs) == expected_refs
        assert _BASE_LIQUIDABLE_ART_50_REF not in formula.legal_refs
        assert expected_refs <= set(casillas_by_id[_ANUALIDADES_ALIMENTOS_TOTAL_CASILLA].legal_refs)
        required_text = {text for citation in formula.source_citations for text in citation.required_text}
        assert "anualidades por alimentos a favor de los hijos" in required_text
        assert "resto de la base liquidable general" in required_text


def test_modelo_100_anualidades_casilla_is_manual_input_pre_2022() -> None:
    """2020/2021 carry 0527 as a manual scalar input with no sum formula."""
    for filing_year in _ANUALIDADES_MANUAL_INPUT_YEARS:
        expected_refs = {
            _STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
            _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF_BY_YEAR[filing_year],
        }
        revision = _revision_for(filing_year)
        formula_id = f"renta-{filing_year}-anualidades-alimentos-hijos-suma"
        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

        assert formula_id not in formulas_by_id, (
            f"{filing_year}: casilla 0527 must not be computed from a per-child sum formula; "
            "the per-child anualidades block only exists in the AEAT form from 2022 onward."
        )
        anualidades_casilla = casillas_by_id[_ANUALIDADES_ALIMENTOS_TOTAL_CASILLA]
        assert getattr(anualidades_casilla, "input_kind", None) != "computed", (
            f"{filing_year}: casilla 0527 must be a manual input, not computed."
        )
        assert expected_refs <= set(anualidades_casilla.legal_refs)


def test_modelo_100_2025_cuota_chain_casillas_do_not_cite_fractional_payment_article() -> None:
    revision = _revision_for(2025)
    checked = [casilla for casilla in revision.casillas if casilla.id.isdigit() and "0500" <= casilla.id <= "0546"]

    assert {casilla.id for casilla in checked} == {f"{number:04d}" for number in range(500, 547)}
    offenders = {
        casilla.id: casilla.legal_refs for casilla in checked if _FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
    }
    assert not offenders


# LIRPF art. 75 (anualidades por alimentos, autonomic separate escala) is
# a legitimate legal_ref on the autonomic escala/cuota formulas ONLY for the
# revisions where the separate-escala régimen is modelled. It stays absent on
# the tipo-medio and cuota-íntegra formulas, which do not carry the régimen.
_SEPARATE_ESCALA_MODELLED_YEARS = frozenset({2020, 2021, 2022, 2023, 2024, 2025})


def _autonomic_separate_escala_formula_ids(filing_year: int) -> frozenset[str]:
    return frozenset(
        {
            f"renta-{filing_year}-cuota-escala-autonomica-sobre-base-liquidable-general",
            f"renta-{filing_year}-cuota-escala-autonomica-sobre-minimo-personal-familiar",
            f"renta-{filing_year}-cuota-base-liquidable-general-autonomica",
        },
    )


def test_modelo_100_autonomic_quota_formula_refs_match_lirpf_articles() -> None:
    for filing_year in _LIVE_M100_YEARS:
        revision = _revision_for(filing_year)
        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        form_order_refs = {_MODELO_100_2025_FORM_ORDER_REF} if filing_year == 2025 else set()
        separate_escala_ids = _autonomic_separate_escala_formula_ids(filing_year)
        regime_modelled = filing_year in _SEPARATE_ESCALA_MODELLED_YEARS
        art_75_ref = _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF_BY_YEAR[filing_year]
        art_76_ref = _AUTONOMIC_SAVINGS_SCALE_ART_76_REF_BY_YEAR[filing_year]
        regime_refs = {art_75_ref} if regime_modelled else set()
        expected_refs_by_formula = {
            f"renta-{filing_year}-tipo-medio-gravamen-autonomico-base-liquidable-general": {
                _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            },
            f"renta-{filing_year}-tipo-medio-gravamen-autonomico-base-liquidable-ahorro": {
                art_76_ref,
            },
            f"renta-{filing_year}-minimo-personal-base-liquidable-ahorro-autonomica": {
                _PERSONAL_FAMILY_MINIMUM_ART_56_REF,
                art_76_ref,
                *form_order_refs,
            },
            f"renta-{filing_year}-cuota-escala-autonomica-sobre-base-liquidable-general": {
                _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
                *regime_refs,
                *form_order_refs,
            },
            f"renta-{filing_year}-cuota-escala-autonomica-sobre-minimo-personal-familiar": {
                _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
                *regime_refs,
                *form_order_refs,
            },
            f"renta-{filing_year}-cuota-base-liquidable-general-autonomica": {
                _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
                *regime_refs,
                *form_order_refs,
            },
            f"renta-{filing_year}-cuota-integra-autonomica": {
                _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
                art_76_ref,
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
            # art-75 is permitted only on the separate-escala formulas in modelled years.
            if not (regime_modelled and formula_id in separate_escala_ids):
                assert art_75_ref not in legal_refs, formula_id

        assert not offenders, filing_year


def test_modelo_100_extraction_profile_legal_refs_match_target_casillas() -> None:
    for filing_year in _EXTRACTION_PROFILE_YEARS:
        revision = _revision_for(filing_year)
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

            assert target_refs == expected_refs, (filing_year, surface)
            assert set(profile.legal_refs) == expected_refs, (filing_year, surface)
            assert _BROAD_DEDUCTION_ART_68_REF not in profile.legal_refs
