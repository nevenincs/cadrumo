"""Modelo 100 deduction legal-reference registry tests."""

from __future__ import annotations

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.runtime_graph import expression_casilla_refs
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    single_exercise_editions,
    supported_authored_exercises,
)

from .modelo_100_registry_support import (
    AUTONOMIC_DEDUCTION_ART_77_REF,
    BASE_IMPONIBLE_AHORRO_CASILLA,
    BROAD_DEDUCTION_ART_68_REF,
    BUSINESS_INVESTMENT_ART_68_2_REF,
    CAPITAL_MOBILIARIO_AHORRO_CASILLA,
    CEUTA_MELILLA_DEDUCTION_ART_68_4_REF,
    CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF,
    DEDUCTION_LIMITS_ART_69_REF,
    DONATION_DEDUCTION_ART_68_3_REF,
    DONATION_DEDUCTION_CASILLAS,
    ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF,
    HOME_INVESTMENT_DEDUCTION_DT_18_REF,
    NEW_COMPANY_INVESTMENT_ART_68_1_REF,
    RENTAL_HOUSING_DEDUCTION_DT_15_REF,
    SAVINGS_BASE_ART_49_REF,
    STATE_DEDUCTION_ART_67_REF,
    loaded_registry,
    modelo_100_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AUTHORED_EXERCISES = single_exercise_editions("100")
_SALDO_POSITIVO_CASILLA = validated_casilla_id("0429", surface="test_modelo_100_registry.casilla")
#: The vehicle incentive's disposición adicional enters the catalogue on the date its amending law takes effect.
_DA_59_FIRST_EXERCISE = loaded_registry()[1].legal["ley-35-2006:da-59"].effective_from.year


@pytest.mark.parametrize("filing_year", supported_authored_exercises("100"))
def test_disposal_excess_cites_the_law_in_force_for_the_filing_year(filing_year: int) -> None:
    """Legacy DA 30 survives; the vehicle incentive's DA 59 begins in 2024."""
    revision = modelo_100_revision(filing_year)
    excess_bindings = {
        binding.id: binding
        for binding in revision.bindings
        if binding.id
        in {
            "renta-activity-asset-disposal-excess-direct-0179",
            "renta-activity-asset-disposal-excess-objective-1478",
        }
    }
    assert len(excess_bindings) == 2
    for binding in excess_bindings.values():
        assert "ley-35-2006:da-30" in binding.legal_refs
        assert ("ley-35-2006:da-59" in binding.legal_refs) == (filing_year >= _DA_59_FIRST_EXERCISE)


def test_modelo_100_savings_base_includes_current_capital_mobiliario() -> None:
    """The year's savings capital-mobiliario income (0041) reaches 0460 once, through its positive balance 0429.

    The official savings-base element sums the balance boxes, not 0041 itself, so a direct 0041 term
    would count the same income twice.
    """
    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
        by_target = {formula.target_casilla_id: formula for formula in revision.formulas}
        savings_base = by_target[BASE_IMPONIBLE_AHORRO_CASILLA]
        positive_balance = by_target[_SALDO_POSITIVO_CASILLA]

        assert SAVINGS_BASE_ART_49_REF in savings_base.legal_refs, filing_year
        assert _SALDO_POSITIVO_CASILLA in expression_casilla_refs(savings_base.expression)
        assert CAPITAL_MOBILIARIO_AHORRO_CASILLA not in expression_casilla_refs(savings_base.expression), filing_year
        assert SAVINGS_BASE_ART_49_REF in positive_balance.legal_refs, filing_year
        positive_balance_refs = set(expression_casilla_refs(positive_balance.expression))
        assert positive_balance_refs == {CAPITAL_MOBILIARIO_AHORRO_CASILLA}, filing_year


def test_modelo_100_donation_deduction_surface_cites_art_68_3() -> None:
    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
        casillas_by_id = {
            casilla.id: casilla for casilla in revision.casillas if casilla.id in DONATION_DEDUCTION_CASILLAS
        }

        assert set(casillas_by_id) == DONATION_DEDUCTION_CASILLAS, filing_year
        for casilla in casillas_by_id.values():
            assert DONATION_DEDUCTION_ART_68_3_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert BROAD_DEDUCTION_ART_68_REF not in casilla.legal_refs, (filing_year, casilla.id)

        formula_by_id = {
            formula.id: formula
            for formula in revision.formulas
            if formula.id
            in {
                "renta-deduccion-donativos-estatal-50-porciento",
                "renta-deduccion-donativos-autonomica-50-porciento",
            }
        }

        assert set(formula_by_id) == {
            "renta-deduccion-donativos-estatal-50-porciento",
            "renta-deduccion-donativos-autonomica-50-porciento",
        }, filing_year
        estatal = formula_by_id["renta-deduccion-donativos-estatal-50-porciento"]
        autonomica = formula_by_id["renta-deduccion-donativos-autonomica-50-porciento"]
        assert DONATION_DEDUCTION_ART_68_3_REF in estatal.legal_refs
        assert STATE_DEDUCTION_ART_67_REF in estatal.legal_refs
        assert BROAD_DEDUCTION_ART_68_REF not in estatal.legal_refs
        assert DONATION_DEDUCTION_ART_68_3_REF in autonomica.legal_refs
        assert AUTONOMIC_DEDUCTION_ART_77_REF in autonomica.legal_refs
        assert BROAD_DEDUCTION_ART_68_REF not in autonomica.legal_refs


def test_modelo_100_ceuta_melilla_deduction_cites_art_68_4() -> None:
    role_refs = {
        "irpf_deduccion_ceuta_melilla_estatal": STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_ceuta_melilla_autonomica": AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_ceuta_melilla_estatal": "estatal",
        "irpf_deduccion_ceuta_melilla_autonomica": "autonomica",
    }

    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
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
        assert CEUTA_MELILLA_DEDUCTION_ART_68_4_REF in anexo_casilla.legal_refs

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            suffix = formula_suffixes[role]
            formula_id = f"renta-deduccion-ceuta-melilla-{suffix}-50-porciento"
            casilla = casillas_by_role[role]
            formula = formulas_by_id[formula_id]

            assert CEUTA_MELILLA_DEDUCTION_ART_68_4_REF in casilla.legal_refs
            assert CEUTA_MELILLA_DEDUCTION_ART_68_4_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_cultural_interest_deduction_cites_art_68_5() -> None:
    role_refs = {
        "irpf_deduccion_interes_cultural_estatal": STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_interes_cultural_autonomica": AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_interes_cultural_estatal": "estatal",
        "irpf_deduccion_interes_cultural_autonomica": "autonomica",
    }

    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
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
        assert CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in anexo_casilla.legal_refs
        assert DEDUCTION_LIMITS_ART_69_REF in anexo_casilla.legal_refs

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            suffix = formula_suffixes[role]
            formula_id = f"renta-deduccion-cultural-{suffix}-50-porciento"
            casilla = casillas_by_role[role]
            formula = formulas_by_id[formula_id]

            assert CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in casilla.legal_refs
            assert CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_new_company_investment_deduction_cites_art_68_1() -> None:
    anexo_section = ("resultados", "anexo_a_res", "deduccion_empresas_nueva_creacion_res")

    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
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
            if NEW_COMPANY_INVESTMENT_ART_68_1_REF not in casilla.legal_refs
            or BROAD_DEDUCTION_ART_68_REF in casilla.legal_refs
            or AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs
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

    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
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
            if BUSINESS_INVESTMENT_ART_68_2_REF not in casilla.legal_refs or "ley-35-2006:art-68" in casilla.legal_refs
        }
        assert not offenders, filing_year

        formula = next(
            formula
            for formula in revision.formulas
            if formula.id == "renta-deduccion-incentivos-inversion-empresarial-total"
        )
        assert BUSINESS_INVESTMENT_ART_68_2_REF in formula.legal_refs
        assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_home_investment_deduction_cites_dt_18() -> None:
    role_refs = {
        "irpf_deduccion_vivienda_habitual_estatal": STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_vivienda_habitual_autonomica": AUTONOMIC_DEDUCTION_ART_77_REF,
    }

    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
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
            assert HOME_INVESTMENT_DEDUCTION_DT_18_REF in casilla.legal_refs, (filing_year, casilla.id)
            assert BROAD_DEDUCTION_ART_68_REF not in casilla.legal_refs, (filing_year, casilla.id)

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            casilla = casillas_by_role[role]
            formula_id = casilla.formula
            assert formula_id is not None, casilla.id
            formula = formulas_by_id[formula_id]
            required_text = {text for citation in formula.source_citations for text in citation.required_text}

            assert formula.target_casilla_id == casilla.id
            assert HOME_INVESTMENT_DEDUCTION_DT_18_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert BROAD_DEDUCTION_ART_68_REF not in formula.legal_refs
            assert "Deducción por inversión en vivienda habitual" in required_text
            assert "actividades económicas" not in required_text


def test_modelo_100_energy_efficiency_deduction_formula_cites_da_50() -> None:
    for filing_year in _AUTHORED_EXERCISES[1:]:
        revision = modelo_100_revision(filing_year)
        casilla = next(
            casilla
            for casilla in revision.casillas
            if casilla.semantic_role == "irpf_deduccion_eficiencia_energetica_viviendas"
        )
        formula = next(
            formula
            for formula in revision.formulas
            if formula.id == "renta-deduccion-eficiencia-energetica-vivienda-suma"
        )

        assert ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF in casilla.legal_refs
        assert ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF in formula.legal_refs
        assert STATE_DEDUCTION_ART_67_REF in formula.legal_refs
        assert "ley-35-2006:art-68" not in formula.legal_refs


def test_modelo_100_rental_housing_transitional_deduction_cites_dt_15() -> None:
    role_refs = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": "estatal",
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": "autonomica",
    }

    for filing_year in _AUTHORED_EXERCISES:
        revision = modelo_100_revision(filing_year)
        casillas_by_role = {
            casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
        }
        assert set(casillas_by_role) == set(role_refs), filing_year

        formulas_by_id = {formula.id: formula for formula in revision.formulas}
        for role, quota_ref in role_refs.items():
            suffix = formula_suffixes[role]
            formula_id = f"renta-deduccion-alquiler-vivienda-{suffix}-50-porciento"
            casilla = casillas_by_role[role]
            formula = formulas_by_id[formula_id]

            assert RENTAL_HOUSING_DEDUCTION_DT_15_REF in casilla.legal_refs
            assert RENTAL_HOUSING_DEDUCTION_DT_15_REF in formula.legal_refs
            assert quota_ref in formula.legal_refs
            assert "ley-35-2006:art-68" not in formula.legal_refs
