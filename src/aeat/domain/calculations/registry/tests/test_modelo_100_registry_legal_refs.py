"""Modelo 100 legal-reference registry tests."""

from __future__ import annotations

import pytest

from .. import calculation_closure_legal_refs
from .test_modelo_100_registry import (
    _ANDALUCIA_EJERCICIO_FISICO_ROLE,
    _ANEXO_C_BASE_NEGATIVE_GENERAL_BINDING_ID,
    _ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID,
    _ANEXO_C_BASE_NEGATIVE_GENERAL_REFS,
    _ANUALIDADES_ALIMENTOS_TOTAL_CASILLA,
    _ARTISTIC_ACTIVITY_REDUCTION_2025_CASILLA_REFS,
    _ATTRIBUTION_REGIME_2025_MODE_FLAG_CASILLA_REFS,
    _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF,
    _AUTONOMIC_DEDUCTION_2025_SECTION_COUNTS,
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _AUTONOMIC_GENERAL_SCALE_ART_74_REF,
    _AUTONOMIC_INTEGRAL_QUOTA_ART_73_REF,
    _AUTONOMIC_SAVINGS_SCALE_ART_76_REF,
    _BASE_IMPONIBLE_AHORRO_CASILLA,
    _BASE_LIQUIDABLE_ART_50_REF,
    _BASE_LIQUIDABLE_GENERAL_GRAVAMEN_CASILLA,
    _BROAD_DEDUCTION_ART_68_REF,
    _BROAD_INCOME_CHAPTER_SPAN_REFS,
    _BUSINESS_INVESTMENT_ART_68_2_REF,
    _C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE,
    _CANARIAS_DONACION_DESCENDIENTES_ROLE,
    _CAPITAL_GAINS_2025_SECTION_COUNTS,
    _CAPITAL_GAINS_SECTION_REFS,
    _CAPITAL_MOBILIARIO_AHORRO_CASILLA,
    _CASILLA_0575,
    _CASILLA_0580,
    _CASILLA_0581,
    _CASILLA_0921,
    _CASILLA_1091,
    _CEUTA_MELILLA_DEDUCTION_ART_68_4_REF,
    _CULTURAL_INTEREST_DEDUCTION_ART_68_5_REF,
    _DA45_CLAUSULA_SUELO_REF,
    _DEDUCTION_LIMITS_ART_69_REF,
    _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE,
    _DEDUCTION_LOSS_INTEREST_STATE_SECOND_ROLE,
    _DONATION_DEDUCTION_ART_68_3_REF,
    _DONATION_DEDUCTION_CASILLAS,
    _ECONOMIC_ACTIVITY_SECTION_REFS,
    _ENERGY_EFFICIENCY_DEDUCTION_DA_50_REF,
    _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
    _FRACTIONAL_PAYMENT_AMOUNT_ARTICLE_REF,
    _FRACTIONAL_PAYMENT_ARTICLE_REF,
    _GENERAL_BASE_ART_48_REF,
    _GENERAL_BASE_CUOTA_CASILLAS,
    _GENERAL_SCALE_ART_63_REF,
    _HOME_INVESTMENT_DEDUCTION_DT_18_REF,
    _INCENTIVO_ART_33_REGULARIZATION_CASILLAS,
    _INMUEBLE_2025_CONTINUITY_REFS,
    _LGT_INTEREST_ART_26_REF,
    _LIRPF_CAPITAL_GAINS_ART_33_REF,
    _M100_EXTRACTION_PROFILE_TARGET_LEGAL_REFS_BY_SURFACE,
    _MODELO_100_2025_FORM_ORDER_REF,
    _NEW_COMPANY_INVESTMENT_ART_68_1_REF,
    _NO_FRACTIONAL_PAYMENT_2025_APPLICATION_LINK_IDS,
    _NO_FRACTIONAL_PAYMENT_2025_BINDING_IDS,
    _NO_FRACTIONAL_PAYMENT_2025_CONSTRUCT_IDS,
    _NO_FRACTIONAL_PAYMENT_2025_INPUT_SECTION_COUNTS,
    _NO_FRACTIONAL_PAYMENT_2025_SECTION_COUNTS,
    _NO_PAYMENTS_ON_ACCOUNT_2025_INPUT_SECTION_COUNTS,
    _OBJECTIVE_ESTIMATION_2025_SECTION_COUNTS,
    _PAYMENTS_ON_ACCOUNT_2025_CASILLA_SECTIONS,
    _PAYMENTS_ON_ACCOUNT_ARTICLE_REF,
    _PERSONAL_FAMILY_MINIMUM_ART_56_REF,
    _REGULARIZACION_DEDUCTION_LOSS_CASILLAS,
    _REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS,
    _REGULARIZACION_PREVIOUS_INTEREST_CASILLAS,
    _RENTAL_HOUSING_DEDUCTION_DT_15_REF,
    _RIRPF_DEDUCTION_LOSS_ART_59_REF,
    _SAVINGS_BASE_ART_49_REF,
    _SCALE_RESULT_EXPECTED_ART_BY_CASILLA_2025,
    _STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF,
    _STATE_DEDUCTION_ART_67_REF,
    _STATE_INTEGRAL_QUOTA_ART_62_REF,
    _casilla_id,
    _casilla_ids,
    _expression_casilla_refs,
    _loaded_registry,
    _modelo_100_snapshot,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_savings_base_includes_current_capital_mobiliario(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    formula = next(
        formula for formula in revision.formulas if formula.target_casilla_id == _BASE_IMPONIBLE_AHORRO_CASILLA
    )

    assert _SAVINGS_BASE_ART_49_REF in formula.legal_refs
    assert _CAPITAL_MOBILIARIO_AHORRO_CASILLA in _expression_casilla_refs(formula.expression)


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_donation_deduction_surface_cites_art_68_3(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _DONATION_DEDUCTION_CASILLAS
    }

    assert set(casillas_by_id) == _DONATION_DEDUCTION_CASILLAS
    for casilla in casillas_by_id.values():
        assert _DONATION_DEDUCTION_ART_68_3_REF in casilla.legal_refs, casilla.id
        assert _BROAD_DEDUCTION_ART_68_REF not in casilla.legal_refs, casilla.id

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
    }
    estatal = formula_by_id[f"renta-{filing_year}-deduccion-donativos-estatal-50-porciento"]
    autonomica = formula_by_id[f"renta-{filing_year}-deduccion-donativos-autonomica-50-porciento"]
    assert _DONATION_DEDUCTION_ART_68_3_REF in estatal.legal_refs
    assert _STATE_DEDUCTION_ART_67_REF in estatal.legal_refs
    assert _BROAD_DEDUCTION_ART_68_REF not in estatal.legal_refs
    assert _DONATION_DEDUCTION_ART_68_3_REF in autonomica.legal_refs
    assert _AUTONOMIC_DEDUCTION_ART_77_REF in autonomica.legal_refs
    assert _BROAD_DEDUCTION_ART_68_REF not in autonomica.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_ceuta_melilla_deduction_cites_art_68_4(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    role_refs = {
        "irpf_deduccion_ceuta_melilla_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_ceuta_melilla_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_ceuta_melilla_estatal": "estatal",
        "irpf_deduccion_ceuta_melilla_autonomica": "autonomica",
    }

    casillas_by_role = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
    }
    assert set(casillas_by_role) == set(role_refs)

    anexo_casilla = next(
        casilla
        for casilla in revision.casillas
        if casilla.semantic_role == "irpf_anexo_a_ceuta_melilla_deduccion_importe"
    )
    assert anexo_casilla.id == _casilla_id("0727")
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


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_cultural_interest_deduction_cites_art_68_5(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    role_refs = {
        "irpf_deduccion_interes_cultural_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_interes_cultural_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_interes_cultural_estatal": "estatal",
        "irpf_deduccion_interes_cultural_autonomica": "autonomica",
    }

    casillas_by_role = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
    }
    assert set(casillas_by_role) == set(role_refs)

    anexo_casilla = next(
        casilla
        for casilla in revision.casillas
        if casilla.semantic_role == "irpf_anexo_a_interes_cultural_deduccion_importe"
    )
    assert anexo_casilla.id == _casilla_id("0726")
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


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_new_company_investment_deduction_cites_art_68_1(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    anexo_section = ("resultados", "anexo_a_res", "deduccion_empresas_nueva_creacion_res")
    state_casilla = next(
        casilla for casilla in revision.casillas if casilla.semantic_role == "irpf_deduccion_empresa_nueva_creacion"
    )
    detail_casillas = [casilla for casilla in revision.casillas if tuple(casilla.section[:3]) == anexo_section]
    entity_nif_casillas = [
        casilla for casilla in revision.casillas if casilla.semantic_role == "irpf_deduccion_nueva_empresa_entidad_nif"
    ]

    assert state_casilla.id == _casilla_id("0549")
    assert {casilla.id for casilla in detail_casillas} == _casilla_ids("0711", "0712", "0713", "0714")
    assert {casilla.id for casilla in entity_nif_casillas} == _casilla_ids("0711", "0713", "1131", "1133")

    offenders = {
        casilla.id: casilla.legal_refs
        for casilla in [state_casilla, *detail_casillas, *entity_nif_casillas]
        if _NEW_COMPANY_INVESTMENT_ART_68_1_REF not in casilla.legal_refs
        or _BROAD_DEDUCTION_ART_68_REF in casilla.legal_refs
        or _AUTONOMIC_DEDUCTION_ART_77_REF in casilla.legal_refs
    }
    assert not offenders


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_business_investment_deductions_cite_art_68_2(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    section = ("resultados", "anexo_a_res", "deducciones_inversion_empresarial_res")
    rollup_roles = {
        "irpf_deduccion_incentivos_inversion_empresarial_estatal": _casilla_id("0554"),
        "irpf_deduccion_incentivos_inversion_empresarial_autonomica": _casilla_id("0555"),
        "irpf_deducciones_incentivos_inversion_total": _casilla_id("0845"),
    }
    rollup_casillas = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in rollup_roles
    }
    checked = [
        *rollup_casillas.values(),
        *(casilla for casilla in revision.casillas if tuple(casilla.section[:3]) == section),
    ]

    assert {role: casilla.id for role, casilla in rollup_casillas.items()} == rollup_roles
    assert checked
    offenders = {
        casilla.id: casilla.legal_refs
        for casilla in checked
        if _BUSINESS_INVESTMENT_ART_68_2_REF not in casilla.legal_refs or "ley-35-2006:art-68" in casilla.legal_refs
    }
    assert not offenders

    formula = next(
        formula
        for formula in revision.formulas
        if formula.id == f"renta-{filing_year}-deduccion-incentivos-inversion-empresarial-total"
    )
    assert _BUSINESS_INVESTMENT_ART_68_2_REF in formula.legal_refs
    assert "ley-35-2006:art-68" not in formula.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_home_investment_deduction_cites_dt_18(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    role_refs = {
        "irpf_deduccion_vivienda_habitual_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_vivienda_habitual_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    casillas_by_role = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
    }
    detail_casillas = [
        casilla
        for casilla in revision.casillas
        if tuple(casilla.section[:3]) == ("resultados", "anexo_a_res", "deduccion_vivienda_habitual_res")
    ]

    assert set(casillas_by_role) == set(role_refs)
    assert detail_casillas
    for casilla in [*casillas_by_role.values(), *detail_casillas]:
        assert _HOME_INVESTMENT_DEDUCTION_DT_18_REF in casilla.legal_refs, casilla.id
        assert _BROAD_DEDUCTION_ART_68_REF not in casilla.legal_refs, casilla.id

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


@pytest.mark.parametrize("filing_year", range(2021, 2026))
def test_modelo_100_energy_efficiency_deduction_formula_cites_da_50(filing_year: int) -> None:
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


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_rental_housing_transitional_deduction_cites_dt_15(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    role_refs = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": _STATE_DEDUCTION_ART_67_REF,
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": _AUTONOMIC_DEDUCTION_ART_77_REF,
    }
    formula_suffixes = {
        "irpf_deduccion_alquiler_vivienda_habitual_estatal": "estatal",
        "irpf_deduccion_alquiler_vivienda_habitual_autonomica": "autonomica",
    }

    casillas_by_role = {
        casilla.semantic_role: casilla for casilla in revision.casillas if casilla.semantic_role in role_refs
    }
    assert set(casillas_by_role) == set(role_refs)

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


@pytest.mark.parametrize(
    ("filing_year", "expected_section_tail", "expected_role", "expected_label_snippet"),
    (
        (
            2020,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2021,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2022,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2023,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2024,
            "canarias_res",
            _CANARIAS_DONACION_DESCENDIENTES_ROLE,
            "donaciones en metálico a descendientes",
        ),
        (
            2025,
            "andalucia_res",
            _ANDALUCIA_EJERCICIO_FISICO_ROLE,
            "ejercicio físico",
        ),
    ),
)
def test_modelo_100_casilla_0921_role_tracks_year_specific_official_meaning(
    filing_year: int,
    expected_section_tail: str,
    expected_role: str,
    expected_label_snippet: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_0921)

    assert casilla.number == "0921"
    assert casilla.section[-1] == expected_section_tail
    assert casilla.semantic_role == expected_role
    assert expected_label_snippet in casilla.label
    assert f"aeat-dr-100-{filing_year}-dictionary" in casilla.source_refs


@pytest.mark.parametrize(
    ("filing_year", "expected_section_tail", "expected_role", "expected_label_snippet"),
    (
        (
            2020,
            "c_valenciana_res",
            _C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE,
            "labores no remuneradas en el hogar",
        ),
        (
            2021,
            "c_valenciana_res",
            _C_VALENCIANA_LABORES_NO_REMUNERADAS_ROLE,
            "labores no remuneradas en el hogar",
        ),
        (
            2022,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
        (
            2023,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
        (
            2024,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
        (
            2025,
            "extremadura_res",
            _EXTREMADURA_VIVIENDA_ZONAS_RURALES_ROLE,
            "vivienda habitual en zonas rurales",
        ),
    ),
)
def test_modelo_100_casilla_1091_role_tracks_year_specific_official_meaning(
    filing_year: int,
    expected_section_tail: str,
    expected_role: str,
    expected_label_snippet: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_1091)

    assert casilla.number == "1091"
    assert casilla.section[-1] == expected_section_tail
    assert casilla.semantic_role == expected_role
    assert expected_label_snippet in casilla.label
    assert f"aeat-dr-100-{filing_year}-dictionary" in casilla.source_refs


@pytest.mark.parametrize(
    ("filing_year", "expected_role", "expected_label_snippet"),
    (
        (2020, _DEDUCTION_LOSS_INTEREST_STATE_SECOND_ROLE, "Parte estatal"),
        (2021, _DEDUCTION_LOSS_INTEREST_STATE_SECOND_ROLE, "Parte estatal"),
        (2022, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
        (2023, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
        (2024, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
        (2025, _DEDUCTION_LOSS_INTEREST_AUTONOMIC_SECOND_ROLE, "Parte autonómica"),
    ),
)
def test_modelo_100_casilla_0581_role_tracks_year_specific_state_autonomic_column(
    filing_year: int,
    expected_role: str,
    expected_label_snippet: str,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _CASILLA_0581)

    assert casilla.number == "0581"
    assert casilla.section[-1] == "gravamenes_res"
    assert casilla.semantic_role == expected_role
    assert expected_label_snippet in casilla.label
    assert f"aeat-dr-100-{filing_year}-dictionary" in casilla.source_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_da45_regularization_flags_cite_their_named_legal_basis(filing_year: int) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in {_CASILLA_0575, _CASILLA_0580}
    }

    assert set(casillas_by_id) == {_CASILLA_0575, _CASILLA_0580}
    for casilla_id, expected_role in (
        (_CASILLA_0575, "irpf_flag_regularizacion_da45_estatal"),
        (_CASILLA_0580, "irpf_flag_regularizacion_da45"),
    ):
        casilla = casillas_by_id[casilla_id]
        assert casilla.section[-1] == "gravamenes_res"
        assert casilla.semantic_role == expected_role
        assert "D.A. 45" in casilla.label
        assert _DA45_CLAUSULA_SUELO_REF in casilla.legal_refs


@pytest.mark.parametrize("filing_year", range(2022, 2026))
def test_modelo_100_art_33_incentive_loss_rows_cite_named_legal_basis(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _INCENTIVO_ART_33_REGULARIZATION_CASILLAS
    }

    assert set(casillas_by_id) == _INCENTIVO_ART_33_REGULARIZATION_CASILLAS
    for casilla in casillas_by_id.values():
        assert casilla.section[-1] == "gravamenes_res"
        assert "artículo 33.3" in casilla.label
        assert _LIRPF_CAPITAL_GAINS_ART_33_REF in casilla.legal_refs
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF not in casilla.legal_refs
        assert _LGT_INTEREST_ART_26_REF not in casilla.legal_refs


@pytest.mark.parametrize("filing_year", range(2022, 2026))
def test_modelo_100_previous_regularization_interest_rows_cite_lgt_interest_basis(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casillas_by_id = {
        casilla.id: casilla for casilla in revision.casillas if casilla.id in _REGULARIZACION_PREVIOUS_INTEREST_CASILLAS
    }

    assert set(casillas_by_id) == _REGULARIZACION_PREVIOUS_INTEREST_CASILLAS
    for casilla in casillas_by_id.values():
        assert casilla.section[-1] == "gravamenes_res"
        assert "Intereses de demora" in casilla.label
        assert "regularización anterior" in casilla.label
        assert _LGT_INTEREST_ART_26_REF in casilla.legal_refs
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF not in casilla.legal_refs


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_deduction_loss_regularization_rows_cite_exact_procedure(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    tracked_ids = _REGULARIZACION_DEDUCTION_LOSS_CASILLAS | _REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS
    casillas_by_id = {casilla.id: casilla for casilla in revision.casillas if casilla.id in tracked_ids}

    assert set(casillas_by_id) == tracked_ids
    for casilla_id in _REGULARIZACION_DEDUCTION_LOSS_CASILLAS:
        casilla = casillas_by_id[casilla_id]
        assert casilla.section[-1] == "gravamenes_res"
        assert "deducciones" in casilla.label.lower()
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF in casilla.legal_refs
        assert _LGT_INTEREST_ART_26_REF not in casilla.legal_refs

    for casilla_id in _REGULARIZACION_DEDUCTION_LOSS_INTEREST_CASILLAS:
        casilla = casillas_by_id[casilla_id]
        assert casilla.section[-1] == "gravamenes_res"
        assert "Intereses de demora" in casilla.label
        assert _RIRPF_DEDUCTION_LOSS_ART_59_REF in casilla.legal_refs
        assert _LGT_INTEREST_ART_26_REF in casilla.legal_refs


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


def test_modelo_100_2025_autonomic_deduction_sections_use_art77_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    expected_refs = {_AUTONOMIC_DEDUCTION_ART_77_REF, "orden-hac-277-2026:art-3"}
    for section, expected_count in _AUTONOMIC_DEDUCTION_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]
        art77_only_casillas = [
            casilla for casilla in checked if casilla.semantic_role != "irpf_deduccion_nueva_empresa_entidad_nif"
        ]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in art77_only_casillas
            if set(casilla.legal_refs) != expected_refs
        }
        assert not offenders


def test_modelo_100_2025_result_sections_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _NO_FRACTIONAL_PAYMENT_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if _FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
        }
        assert not offenders


def test_modelo_100_2025_input_sections_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _NO_FRACTIONAL_PAYMENT_2025_INPUT_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if _FRACTIONAL_PAYMENT_ARTICLE_REF in casilla.legal_refs
        }
        assert not offenders


def test_modelo_100_2025_input_sections_do_not_cite_payments_on_account_article() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _NO_PAYMENTS_ON_ACCOUNT_2025_INPUT_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if _PAYMENTS_ON_ACCOUNT_ARTICLE_REF in casilla.legal_refs
        }
        assert not offenders


def test_modelo_100_2025_payments_on_account_article_stays_on_payment_casillas_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    observed = {
        casilla.id: tuple(casilla.section[:2])
        for casilla in revision.casillas
        if _PAYMENTS_ON_ACCOUNT_ARTICLE_REF in casilla.legal_refs
    }

    assert observed == _PAYMENTS_ON_ACCOUNT_2025_CASILLA_SECTIONS


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_fractional_payment_casilla_carries_payment_obligation_and_amount_refs(
    filing_year: int,
) -> None:
    revision = _modelo_100_snapshot(filing_year).revision
    casilla = next(casilla for casilla in revision.casillas if casilla.id == _casilla_id("0604"))

    expected_refs = {
        _PAYMENTS_ON_ACCOUNT_ARTICLE_REF,
        _FRACTIONAL_PAYMENT_ARTICLE_REF,
        _FRACTIONAL_PAYMENT_AMOUNT_ARTICLE_REF,
    }
    assert expected_refs <= set(casilla.legal_refs)


def test_modelo_100_2025_gain_sections_use_capital_gains_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _CAPITAL_GAINS_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if set(casilla.legal_refs) != _CAPITAL_GAINS_SECTION_REFS
        }
        assert not offenders


def test_modelo_100_2025_attribution_mode_flags_use_attribution_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    offenders = {
        casilla_id: casillas[casilla_id].legal_refs
        for casilla_id, expected_refs in _ATTRIBUTION_REGIME_2025_MODE_FLAG_CASILLA_REFS.items()
        if set(casillas[casilla_id].legal_refs) != expected_refs
    }

    assert not offenders


def test_modelo_100_2025_casillas_do_not_retain_full_income_chapter_span() -> None:
    revision = _modelo_100_snapshot(2025).revision
    offenders = {
        casilla.id: casilla.legal_refs
        for casilla in revision.casillas
        if _BROAD_INCOME_CHAPTER_SPAN_REFS.issubset(casilla.legal_refs)
    }

    assert not offenders


def test_modelo_100_2025_inmueble_continuity_uses_inmueble_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    checked = [
        evolution
        for evolution in revision.casilla_continuidad_evolutions
        if str(evolution.continuidad_id) in _INMUEBLE_2025_CONTINUITY_REFS
    ]

    assert len(checked) == 10
    offenders = {
        evolution.id: evolution.legal_refs
        for evolution in checked
        if set(evolution.legal_refs) != _INMUEBLE_2025_CONTINUITY_REFS[str(evolution.continuidad_id)]
    }
    assert not offenders


def test_modelo_100_2025_anexo_c_base_negative_general_uses_member_refs_only() -> None:
    snapshot = _modelo_100_snapshot(2025)
    revision = snapshot.revision
    construct = snapshot.constructs[_ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    formulas = {formula.id: formula for formula in revision.formulas}
    bindings = {binding.id: binding for binding in revision.bindings}
    member_refs: set[str] = set()

    for casilla_id in construct.casilla_ids:
        member_refs.update(casillas[casilla_id].legal_refs)
    for formula_id in construct.formulas:
        member_refs.update(formulas[formula_id].legal_refs)
    for binding_id in construct.bindings:
        member_refs.update(bindings[binding_id].legal_refs)

    assert set(bindings[_ANEXO_C_BASE_NEGATIVE_GENERAL_BINDING_ID].legal_refs) == {
        _GENERAL_BASE_ART_48_REF,
        _MODELO_100_2025_FORM_ORDER_REF,
    }
    assert member_refs == _ANEXO_C_BASE_NEGATIVE_GENERAL_REFS
    assert set(construct.legal_refs) == _ANEXO_C_BASE_NEGATIVE_GENERAL_REFS


def test_modelo_100_2025_completeness_manifest_legal_refs_match_calculation_closure() -> None:
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    manifest = revision.completeness_manifest

    assert manifest is not None
    assert set(manifest.legal_refs) == calculation_closure_legal_refs(revision, modelo.id)


def test_modelo_100_2025_objective_estimation_sections_use_activity_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    for section, expected_count in _OBJECTIVE_ESTIMATION_2025_SECTION_COUNTS.items():
        checked = [casilla for casilla in revision.casillas if tuple(casilla.section[:2]) == section]

        assert len(checked) == expected_count
        offenders = {
            casilla.id: casilla.legal_refs
            for casilla in checked
            if set(casilla.legal_refs) != _ECONOMIC_ACTIVITY_SECTION_REFS
        }
        assert not offenders


def test_modelo_100_2025_artistic_activity_reductions_use_da60_refs_only() -> None:
    revision = _modelo_100_snapshot(2025).revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    offenders = {
        casilla_id: casillas[casilla_id].legal_refs
        for casilla_id, expected_refs in _ARTISTIC_ACTIVITY_REDUCTION_2025_CASILLA_REFS.items()
        if set(casillas[casilla_id].legal_refs) != expected_refs
    }

    assert not offenders


def test_modelo_100_2025_non_payment_metadata_do_not_cite_fractional_payment_article() -> None:
    revision = _modelo_100_snapshot(2025).revision

    bindings = {binding.id: binding for binding in revision.bindings}
    constructs = {construct.id: construct for construct in revision.constructs}
    application_links = {link.id: link for link in revision.application_links}

    binding_offenders = {
        binding_id: bindings[binding_id].legal_refs
        for binding_id in _NO_FRACTIONAL_PAYMENT_2025_BINDING_IDS
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in bindings[binding_id].legal_refs
    }
    construct_offenders = {
        construct_id: constructs[construct_id].legal_refs
        for construct_id in _NO_FRACTIONAL_PAYMENT_2025_CONSTRUCT_IDS
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in constructs[construct_id].legal_refs
    }
    application_link_offenders = {
        link_id: application_links[link_id].legal_refs
        for link_id in _NO_FRACTIONAL_PAYMENT_2025_APPLICATION_LINK_IDS
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in application_links[link_id].legal_refs
    }
    deadline_offenders = {
        deadline.id: deadline.legal_refs
        for deadline in revision.deadline_windows
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in deadline.legal_refs
    }
    continuity_offenders = {
        evolution.id: evolution.legal_refs
        for evolution in revision.casilla_continuidad_evolutions
        if _FRACTIONAL_PAYMENT_ARTICLE_REF in evolution.legal_refs
    }

    assert not binding_offenders
    assert not construct_offenders
    assert not application_link_offenders
    assert not deadline_offenders
    assert not continuity_offenders
