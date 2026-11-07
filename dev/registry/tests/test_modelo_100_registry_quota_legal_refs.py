"""Modelo 100 quota and extraction-profile legal-reference registry tests."""

from __future__ import annotations

from functools import lru_cache

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import single_exercise_editions

from .authored_edition_support import newest_authored_edition
from .modelo_100_registry_support import (
    ANUALIDADES_ALIMENTOS_TOTAL_CASILLA,
    AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
    BASE_LIQUIDABLE_ART_50_REF,
    BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA,
    BROAD_DEDUCTION_ART_68_REF,
    FRACTIONAL_PAYMENT_ARTICLE_REF,
    GENERAL_BASE_CUOTA_CASILLAS,
    GENERAL_SCALE_ART_63_REF,
    M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE,
    MODELO_100_2025_FORM_ORDER_REF,
    PERSONAL_FAMILY_MINIMUM_ART_56_REF,
    SAVINGS_BASE_ART_49_REF,
    SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025,
    STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
    STATE_DEDUCTION_ART_67_REF,
    STATE_INTEGRAL_QUOTA_ART_62_REF,
    governing_redaction,
    modelo_100_revision,
)
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = committed_supported_filing_years()
# The newest Modelo 100 edition the registry authors; edition-specific declarations below are asserted against it.
_REVIEWED_EDITION = newest_authored_edition("100")
# The floor edition numbers its cuota chain differently; every later authored edition
# carries the 0500-0546 run checked below, and the horizon only projects the newest one.
_CONTIGUOUS_CUOTA_CHAIN_YEARS = tuple(year for year in _SUPPORT.years if _SUPPORT.floor < year < _SUPPORT.horizon)

_LIVE_M100_YEARS = single_exercise_editions("100")
# The two oldest editions carry the anualidades total as a manual scalar; the per-child block and its sum
# formula exist in every later one.
_ANUALIDADES_MANUAL_INPUT_YEARS = _LIVE_M100_YEARS[:2]
_ANUALIDADES_FORMULA_YEARS = _LIVE_M100_YEARS[2:]

#: Each edition's applicability window cites the redaction of an article actually in force at its devengo
#: (the catalogue records an amended article as one row per redaction), resolved from the catalogue's own
#: effective windows rather than named per year.
_AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF = "ley-35-2006:art-75"
_AUTONOMIC_SAVINGS_SCALE_ART_76_REF = "ley-35-2006:art-76"


def _art_75_ref(filing_year: int) -> str:
    return governing_redaction(_AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF, modelo_100_revision(filing_year))


def _art_76_ref(filing_year: int) -> str:
    return governing_redaction(_AUTONOMIC_SAVINGS_SCALE_ART_76_REF, modelo_100_revision(filing_year))


def _art_63_ref(filing_year: int) -> str:
    return governing_redaction(GENERAL_SCALE_ART_63_REF, modelo_100_revision(filing_year))


@lru_cache
def _revision_for(filing_year: int):
    return modelo_100_revision(filing_year)


def test_modelo_100_general_liquidable_and_cuota_chain_exclude_unrelated_articles() -> None:
    for filing_year in _LIVE_M100_YEARS:
        revision = _revision_for(filing_year)
        general_scale_art_63_ref = _art_63_ref(filing_year)
        checked_casilla_ids = {BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA, *GENERAL_BASE_CUOTA_CASILLAS}
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in checked_casilla_ids}

        assert set(casillas_by_id) == checked_casilla_ids
        base_casilla = casillas_by_id[BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA]
        assert BASE_LIQUIDABLE_ART_50_REF in base_casilla.legal_refs
        assert PERSONAL_FAMILY_MINIMUM_ART_56_REF not in base_casilla.legal_refs
        assert SAVINGS_BASE_ART_49_REF not in base_casilla.legal_refs
        assert FRACTIONAL_PAYMENT_ARTICLE_REF not in base_casilla.legal_refs

        formula_by_target = {
            formula.target_casilla_id: formula
            for formula in revision.formulas
            if formula.target_casilla_id in checked_casilla_ids
        }
        base_formula = formula_by_target.get(BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA)
        if base_formula is not None:
            assert BASE_LIQUIDABLE_ART_50_REF in base_formula.legal_refs
            assert general_scale_art_63_ref in base_formula.legal_refs
            assert PERSONAL_FAMILY_MINIMUM_ART_56_REF not in base_formula.legal_refs
            assert SAVINGS_BASE_ART_49_REF not in base_formula.legal_refs
            assert FRACTIONAL_PAYMENT_ARTICLE_REF not in base_formula.legal_refs

        for casilla_id in GENERAL_BASE_CUOTA_CASILLAS:
            casilla = casillas_by_id[casilla_id]
            formula = formula_by_target[casilla_id]
            assert general_scale_art_63_ref in casilla.legal_refs, (filing_year, casilla.id)
            assert SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, (filing_year, casilla.id)
            assert FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, (filing_year, casilla.id)
            assert SAVINGS_BASE_ART_49_REF not in formula.legal_refs, (filing_year, formula.id)
            assert FRACTIONAL_PAYMENT_ARTICLE_REF not in formula.legal_refs, (filing_year, formula.id)


def test_modelo_100_scale_result_casillas_use_scale_articles_not_fractional_payment_article() -> None:
    revision = _revision_for(_REVIEWED_EDITION)
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025
    }
    formula_by_target = {
        formula.target_casilla_id: formula
        for formula in revision.formulas
        if formula.target_casilla_id in SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025
    }

    assert set(casillas_by_id) == set(SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025)
    assert set(formula_by_target) == set(SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025)
    for casilla_id, expected_ref in SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025.items():
        casilla = casillas_by_id[casilla_id]
        formula = formula_by_target[casilla_id]
        assert expected_ref in casilla.legal_refs, casilla.id
        assert expected_ref in formula.legal_refs, formula.id
        assert SAVINGS_BASE_ART_49_REF not in casilla.legal_refs, casilla.id
        assert FRACTIONAL_PAYMENT_ARTICLE_REF not in casilla.legal_refs, casilla.id
        assert FRACTIONAL_PAYMENT_ARTICLE_REF not in formula.legal_refs, formula.id


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
            STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
            _art_75_ref(filing_year),
        }
        revision = _revision_for(filing_year)
        formula_id = "renta-anualidades-alimentos-hijos-suma"
        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

        assert formula_id in formulas_by_id
        formula = formulas_by_id[formula_id]
        assert formula.target_casilla_id == ANUALIDADES_ALIMENTOS_TOTAL_CASILLA
        assert set(formula.legal_refs) == expected_refs
        assert BASE_LIQUIDABLE_ART_50_REF not in formula.legal_refs
        assert expected_refs <= set(casillas_by_id[ANUALIDADES_ALIMENTOS_TOTAL_CASILLA].legal_refs)
        required_text = {text for citation in formula.source_citations for text in citation.required_text}
        assert "anualidades por alimentos a favor de los hijos" in required_text
        assert "resto de la base liquidable general" in required_text


def test_modelo_100_anualidades_casilla_is_manual_input_before_the_per_child_block() -> None:
    """The editions before the per-child block carry 0527 as a manual scalar input with no sum formula."""
    for filing_year in _ANUALIDADES_MANUAL_INPUT_YEARS:
        expected_refs = {
            STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
            _art_75_ref(filing_year),
        }
        revision = _revision_for(filing_year)
        formula_id = "renta-anualidades-alimentos-hijos-suma"
        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}

        assert formula_id not in formulas_by_id, (
            f"{filing_year}: casilla 0527 must not be computed from a per-child sum formula; "
            "the per-child anualidades block only exists in the AEAT form from 2022 onward."
        )
        anualidades_casilla = casillas_by_id[ANUALIDADES_ALIMENTOS_TOTAL_CASILLA]
        assert getattr(anualidades_casilla, "input_kind", None) != "computed", (
            f"{filing_year}: casilla 0527 must be a manual input, not computed."
        )
        assert expected_refs <= set(anualidades_casilla.legal_refs)


@pytest.mark.parametrize("filing_year", _CONTIGUOUS_CUOTA_CHAIN_YEARS)
def test_modelo_100_cuota_chain_casillas_do_not_cite_fractional_payment_article(filing_year: int) -> None:
    revision = _revision_for(filing_year)
    checked = [casilla for casilla in revision.casillas if casilla.id.isdigit() and "0500" <= casilla.id <= "0546"]

    assert {casilla.id for casilla in checked} == {f"{number:04d}" for number in range(500, 547)}
    offenders = {
        casilla.id: casilla.legal_refs for casilla in checked if FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
    }
    assert not offenders


# LIRPF art. 75 (anualidades por alimentos, autonomic separate escala) is
# a legitimate legal_ref on the autonomic escala/cuota formulas ONLY for the
# revisions where the separate-escala régimen is modelled. It stays absent on
# the tipo-medio and cuota-íntegra formulas, which do not carry the régimen.
_SEPARATE_ESCALA_MODELLED_YEARS = frozenset(_LIVE_M100_YEARS)


def _autonomic_separate_escala_formula_ids(filing_year: int) -> frozenset[str]:
    return frozenset(
        {
            "renta-cuota-escala-autonomica-sobre-base-liquidable-general",
            "renta-cuota-escala-autonomica-sobre-minimo-personal-familiar",
            "renta-cuota-base-liquidable-general-autonomica",
        },
    )


def test_modelo_100_autonomic_quota_formula_refs_match_lirpf_articles() -> None:
    for filing_year in _LIVE_M100_YEARS:
        revision = _revision_for(filing_year)
        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        form_order_refs = {MODELO_100_2025_FORM_ORDER_REF} if filing_year == _REVIEWED_EDITION else set()
        separate_escala_ids = _autonomic_separate_escala_formula_ids(filing_year)
        regime_modelled = filing_year in _SEPARATE_ESCALA_MODELLED_YEARS
        art_75_ref = _art_75_ref(filing_year)
        art_76_ref = _art_76_ref(filing_year)
        regime_refs = {art_75_ref} if regime_modelled else set()
        expected_refs_by_formula = {
            "renta-tipo-medio-gravamen-autonomico-base-liquidable-general": {
                AUTONOMIC_GENERAL_SCALE_ART_74_REF,
            },
            "renta-tipo-medio-gravamen-autonomico-base-liquidable-ahorro": {
                art_76_ref,
            },
            "renta-minimo-personal-base-liquidable-ahorro-autonomica": {
                PERSONAL_FAMILY_MINIMUM_ART_56_REF,
                art_76_ref,
                *form_order_refs,
            },
            "renta-cuota-escala-autonomica-sobre-base-liquidable-general": {
                AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                AUTONOMIC_GENERAL_SCALE_ART_74_REF,
                *regime_refs,
                *form_order_refs,
            },
            "renta-cuota-escala-autonomica-sobre-minimo-personal-familiar": {
                AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                AUTONOMIC_GENERAL_SCALE_ART_74_REF,
                *regime_refs,
                *form_order_refs,
            },
            "renta-cuota-base-liquidable-general-autonomica": {
                AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                AUTONOMIC_GENERAL_SCALE_ART_74_REF,
                *regime_refs,
                *form_order_refs,
            },
            "renta-cuota-integra-autonomica": {
                AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
                AUTONOMIC_GENERAL_SCALE_ART_74_REF,
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
            assert STATE_INTEGRAL_QUOTA_ART_62_REF not in legal_refs, formula_id
            assert STATE_DEDUCTION_ART_67_REF not in legal_refs, formula_id
            # art-75 is permitted only on the separate-escala formulas in modelled years.
            if not (regime_modelled and formula_id in separate_escala_ids):
                assert art_75_ref not in legal_refs, formula_id

        assert not offenders, filing_year


def test_modelo_100_extraction_profile_legal_refs_match_target_casillas() -> None:
    profiled_editions = 0
    for filing_year in _LIVE_M100_YEARS:
        revision = _revision_for(filing_year)
        casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
        profiles_by_surface = {
            profile.surface: profile
            for profile in revision.extraction_profiles
            if profile.surface in M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE
        }
        if not profiles_by_surface:
            continue
        profiled_editions += 1

        assert set(profiles_by_surface) == set(M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE), filing_year
        for surface, profile in profiles_by_surface.items():
            expected_refs = frozenset(
                governing_redaction(reference_id, revision)
                for reference_id in M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE[surface]
            )
            target_refs = frozenset(
                legal_ref
                for target in profile.target_casillas
                for legal_ref in casillas_by_id[target.casilla_id].legal_refs
            )

            assert target_refs == expected_refs, (filing_year, surface)
            assert set(profile.legal_refs) == expected_refs, (filing_year, surface)
            assert BROAD_DEDUCTION_ART_68_REF not in profile.legal_refs

    assert profiled_editions
    assert _REVIEWED_EDITION in _LIVE_M100_YEARS
    assert _revision_for(_REVIEWED_EDITION).extraction_profiles
