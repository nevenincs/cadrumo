"""Modelo 100 deduction legal-reference registry tests."""

from __future__ import annotations

import pytest

from .....core import validated_casilla_id
from ..runtime_graph import expression_casilla_refs
from ._modelo_100_registry_support import (
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _BASE_IMPONIBLE_AHORRO_CASILLA,
    _BROAD_DEDUCTION_ART_68_REF,
    _BUSINESS_INVESTMENT_ART_68_2_REF,
    _CAPITAL_MOBILIARIO_AHORRO_CASILLA,
    _CEUTA_MELILLA_DEDUCTION_ART_68_4_REF,
    _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF,
    _DEDUCTION_LIMITS_ART_69_REF,
    _DONATION_DEDUCTION_ART_68_3_REF,
    _DONATION_DEDUCTION_CASILLAS,
    _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF,
    _HOME_INVESTMENT_DEDUCTION_DT_18_REF,
    _NEW_COMPANY_INVESTMENT_ART_68_1_REF,
    _RENTAL_HOUSING_DEDUCTION_DT_15_REF,
    _SAVINGS_BASE_ART_49_REF,
    _STATE_DEDUCTION_ART_67_REF,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_100_savings_base_includes_current_capital_mobiliario() -> None:
    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        formula = next(
            formula for formula in revision.formulas if formula.target_casilla_id == _BASE_IMPONIBLE_AHORRO_CASILLA
        )

        assert _SAVINGS_BASE_ART_49_REF in formula.legal_refs, filing_year
        assert _CAPITAL_MOBILIARIO_AHORRO_CASILLA in expression_casilla_refs(formula.expression), filing_year


def test_modelo_100_donation_deduction_surface_cites_art_68_3() -> None:
    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        casillas_by_id = {
            casilla.id: casilla for casilla in revision.casillas if casilla.id in _DONATION_DEDUCTION_CASILLAS
        }

        assert set(casillas_by_id) == _DONATION_DEDUCTION_CASILLAS, filing_year
        for casilla in casillas_by_id.values():
            assert _DONATION_DEDUCTION_ART_68_3_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert _BROAD_DEDUCTION_ART_68_REF not in casilla.legal_refs, (filing_year, casilla.id)

        formula_by_id = {
            formula.id: formula
            for formula in revision.formulas
            if formula.id
            in {
                f"renta-{filing_year}-deduccion-donativos-estatal-50-porciento",
                f"renta-{filing_year}-deduccion-donativos-autonomica-50-porciento",
            }
        }

        assert set(formula_by_id) == {
            f"renta-{filing_year}-deduccion-donativos-estatal-50-porciento",
            f"renta-{filing_year}-deduccion-donativos-autonomica-50-porciento",
        }, filing_year
        estatal = formula_by_id[f"renta-{filing_year}-deduccion-donativos-estatal-50-porciento"]
        autonomica = formula_by_id[f"renta-{filing_year}-deduccion-donativos-autonomica-50-porciento"]
        assert _DONATION_DEDUCTION_ART_68_3_REF in estatal.legal_refs
        assert _STATE_DEDUCTION_ART_67_REF in estatal.legal_refs
        assert _BROAD_DEDUCTION_ART_68_REF not in estatal.legal_refs
        assert _DONATION_DEDUCTION_ART_68_3_REF in autonomica.legal_refs
        assert _AUTONOMIC_DEDUCTION_ART_77_REF in autonomica.legal_refs
        assert _BROAD_DEDUCTION_ART_68_REF not in autonomica.legal_refs


def test_modelo_100_ceuta_melilla_deduction_cites_art_68_4() -> None:
    role_refs = {
        "irpf_deduccion_ceuta_melilla_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_ceuta_melilla_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_ceuta_melilla_estatal": "estatal",
        "irpf_deduccion_ceuta_melilla_autonomica": "autonomica",
    }

    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        casillas_by_role = {
            casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
        }
        assert set(casillas_by_role) == set(role_refs), filing_year

        anexo_casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.semantic_role == "irpf_anexo_a_ceuta_melilla_deduccion_importe"
        )
        assert anexo_casilla.id == validated_casilla_id("0727", surface="test_modelo_100_registry.casilla"), filing_year
        assert _CEUTA_MELILLA_DEDUCTION_ART_68_4_REF in anexo_casilla.legal_refs

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            suffix = formula_suffixes[role]
            formula_id = f"renta-{filing_year}-deduccion-ceuta-melilla-{suffix}-50-porciento"
            casilla = casillas_by_role[role]
            formula = formulas_by_id[formula_id]

            assert _CEUTA_MELILLA_DEDUCTION_ART_68_4_REF in casilla.legal_refs
            assert _CEUTA_MELILLA_DEDUCTION_ART_68_4_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_cultural_interest_deduction_cites_art_68_5() -> None:
    role_refs = {
        "irpf_deduccion_interes_cultural_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_interes_cultural_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_interes_cultural_estatal": "estatal",
        "irpf_deduccion_interes_cultural_autonomica": "autonomica",
    }

    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        casillas_by_role = {
            casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
        }
        assert set(casillas_by_role) == set(role_refs), filing_year

        anexo_casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.semantic_role == "irpf_anexo_a_interes_cultural_deduccion_importe"
        )
        assert anexo_casilla.id == validated_casilla_id("0726", surface="test_modelo_100_registry.casilla"), filing_year
        assert _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in anexo_casilla.legal_refs
        assert _DEDUCTION_LIMITS_ART_69_REF in anexo_casilla.legal_refs

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            suffix = formula_suffixes[role]
            formula_id = f"renta-{filing_year}-deduccion-cultural-{suffix}-50-porciento"
            casilla = casillas_by_role[role]
            formula = formulas_by_id[formula_id]

            assert _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in casilla.legal_refs
            assert _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_new_company_investment_deduction_cites_art_68_1() -> None:
    anexo_section = ("resultados", "anexo_a_res", "deduccion_empresas_nueva_creacion_res")

    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        state_casilla = next(
            casilla for casilla in revision.casillas if casilla.semantic_role == "irpf_deduccion_empresa_nueva_creacion"
        )
        detail_casillas = [casilla for casilla in revision.casillas if tuple(casilla.section[:3]) == anexo_section]
        entity_nif_casillas = [
            casilla
            for casilla in revision.casillas
            if casilla.semantic_role == "irpf_deduccion_nueva_empresa_entidad_nif"
        ]

        assert state_casilla.id == validated_casilla_id("0549", surface="test_modelo_100_registry.casilla"), filing_year
        assert {casilla.id for casilla in detail_casillas} == frozenset(
            validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
            for _v in ("0711", "0712", "0713", "0714")
        )
        assert {casilla.id for casilla in entity_nif_casillas} == frozenset(
            validated_casilla_id(_v, surface="test_modelo_100_registry.casilla")
            for _v in ("0711", "0713", "1131", "1133")
        )

        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in [state_casilla, *detail_casillas, *entity_nif_casillas]
            if _NEW_COMPANY_INVESTMENT_ART_68_1_REF not in casilla.legal_refs
            or _BROAD_DEDUCTION_ART_68_REF in casilla.legal_refs
            or _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs
        }
        assert not offenders, filing_year


def test_modelo_100_business_investment_deductions_cite_art_68_2() -> None:
    section = ("resultados", "anexo_a_res", "deducciones_inversion_empresarial_res")
    rollup_roles = {
        "irpf_deduccion_incentivos_inversion_empresarial_estatal": validated_casilla_id(
            "0554", surface="test_modelo_100_registry.casilla"
        ),
        "irpf_deduccion_incentivos_inversion_empresarial_autonomica": validated_casilla_id(
            "0555", surface="test_modelo_100_registry.casilla"
        ),
        "irpf_deducciones_incentivos_inversion_total": validated_casilla_id(
            "0845", surface="test_modelo_100_registry.casilla"
        ),
    }

    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        rollup_casillas = {
            casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in rollup_roles
        }
        checked = [
            *rollup_casillas.values(),
            *(casilla for casilla in revision.casillas if tuple(casilla.section[:3]) == section),
        ]

        assert {role: casilla.id for role, casilla in rollup_casillas.items()} == rollup_roles, filing_year
        assert checked, filing_year
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if _BUSINESS_INVESTMENT_ART_68_2_REF not in casilla.legal_refs or "ley-35-2006:art-68" in casilla.legal_refs
        }
        assert not offenders, filing_year

        formula = next(
            formula
            for formula in revision.formulas
            if formula.id == f"renta-{filing_year}-deduccion-incentivos-inversion-empresarial-total"
        )
        assert _BUSINESS_INVESTMENT_ART_68_2_REF in formula.legal_refs
        assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_home_investment_deduction_cites_dt_18() -> None:
    role_refs = {
        "irpf_deduccion_vivienda_habitual_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_vivienda_habitual_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }

    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        casillas_by_role = {
            casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
        }
        detail_casillas = [
            casilla
            for casilla in revision.casillas
            if tuple(casilla.section[:3]) == ("resultados", "anexo_a_res", "deduccion_vivienda_habitual_res")
        ]

        assert set(casillas_by_role) == set(role_refs), filing_year
        assert detail_casillas, filing_year
        for casilla in [*casillas_by_role.values(), *detail_casillas]:
            assert _HOME_INVESTMENT_DEDUCTION_DT_18_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert _BROAD_DEDUCTION_ART_68_REF not in casilla.legal_refs, (filing_year, casilla.id)

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            casilla = casillas_by_role[role]
            formula_id = casilla.formula
            assert formula_id is not None, casilla.id
            formula = formulas_by_id[formula_id]
            required_text = {text for citation in formula.source_citations for text in citation.required_text}

            assert formula.target_casilla_id == casilla.id
            assert _HOME_INVESTMENT_DEDUCTION_DT_18_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert _BROAD_DEDUCTION_ART_68_REF not in formula.legal_refs
            assert "Deducción por inversión en vivienda habitual" in required_text
            assert "actividades económicas" not in required_text


def test_modelo_100_energy_efficiency_deduction_formula_cites_da_50() -> None:
    for filing_year in range(2021, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.semantic_role == "irpf_deduccion_eficiencia_energetica_viviendas"
        )
        formula = next(
            formula
            for formula in revision.formulas
            if formula.id == f"renta-{filing_year}-deduccion-eficiencia-energetica-vivienda-suma"
        )

        assert _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF in casilla.legal_refs
        assert _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF in formula.legal_refs
        assert _STATE_DEDUCTION_ART_67_REF in formula.legal_refs
        assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_rental_housing_transitional_deduction_cites_dt_15() -> None:
    role_refs = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": "estatal",
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": "autonomica",
    }

    for filing_year in range(2020, 2026):
        revision = _modelo_100_snapshot(filing_year).revision
        casillas_by_role = {
            casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
        }
        assert set(casillas_by_role) == set(role_refs), filing_year

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            suffix = formula_suffixes[role]
            formula_id = f"renta-{filing_year}-deduccion-alquiler-vivienda-{suffix}-50-porciento"
            casilla = casillas_by_role[role]
            formula = formulas_by_id[formula_id]

            assert _RENTAL_HOUSING_DEDUCTION_DT_15_REF in casilla.legal_refs
            assert _RENTAL_HOUSING_DEDUCTION_DT_15_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert "ley-35-2006:art-68" not in formula.legal_refs
