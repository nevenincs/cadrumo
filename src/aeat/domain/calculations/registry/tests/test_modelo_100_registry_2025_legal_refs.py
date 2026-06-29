"""Modelo 100 2025 section and payment legal-reference registry tests."""

from __future__ import annotations

import pytest

from ._modelo_100_legal_refs_support import (
    _ANEXO_C_BASE_NEGATIVE_GENERAL_BINDING_ID,
    _ANEXO_C_BASE_NEGATIVE_GENERAL_CONSTRUCT_ID,
    _ANEXO_C_BASE_NEGATIVE_GENERAL_REFS,
    _ARTISTIC_ACTIVITY_REDUCTION_2025_CASILLA_REFS,
    _ATTRIBUTION_REGIME_2025_MODE_FLAG_CASILLA_REFS,
    _AUTONOMIC_DEDUCTION_2025_SECTION_COUNTS,
    _AUTONOMIC_DEDUCTION_ART_77_REF,
    _BROAD_INCOME_CHAPTER_SPAN_REFS,
    _CAPITAL_GAINS_2025_SECTION_COUNTS,
    _CAPITAL_GAINS_SECTION_REFS,
    _ECONOMIC_ACTIVITY_SECTION_REFS,
    _FRACTIONAL_PAYMENT_AMOUNT_ARTICLE_REF,
    _FRACTIONAL_PAYMENT_ARTICLE_REF,
    _GENERAL_BASE_ART_48_REF,
    _INMUEBLE_2025_CONTINUITY_REFS,
    _MODELO_100_2025_FORM_ORDER_REF,
    _NO_FRACTIONAL_PAYMENT_2025_APPLICATION_LINK_IDS,
    _NO_FRACTIONAL_PAYMENT_2025_BINDING_IDS,
    _NO_FRACTIONAL_PAYMENT_2025_CONSTRUCT_IDS,
    _NO_FRACTIONAL_PAYMENT_2025_INPUT_SECTION_COUNTS,
    _NO_FRACTIONAL_PAYMENT_2025_SECTION_COUNTS,
    _NO_PAYMENTS_ON_ACCOUNT_2025_INPUT_SECTION_COUNTS,
    _OBJECTIVE_ESTIMATION_2025_SECTION_COUNTS,
    _PAYMENTS_ON_ACCOUNT_2025_CASILLA_SECTIONS,
    _PAYMENTS_ON_ACCOUNT_ARTICLE_REF,
    _casilla_id,
    _loaded_registry,
    _modelo_100_snapshot,
    calculation_closure_legal_refs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
