"""Modelo 100 quota-chain legal-reference checks against the bundled registry."""

from __future__ import annotations

import pytest

from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERSONAL_FAMILY_MINIMUM_ART_56_REF = "ley-35-2006:art-56"
_STATE_INTEGRAL_QUOTA_ART_62_REF = "ley-35-2006:art-62"
_GENERAL_SCALE_ART_63_REF = "ley-35-2006:art-63"
_SAVINGS_STATE_SCALE_ART_66_REF = "ley-35-2006:art-66"
_STATE_LIQUID_QUOTA_ART_67_REF = "ley-35-2006:art-67"
_AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF = "ley-35-2006:art-75"
_MODELO_100_2025_FORM_ORDER_REF = "orden-hac-277-2026:art-3"


def _modelo_100_revisions():
    modelo, _catalogues = _committed_modelo("100")
    return modelo.revisions


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_state_quota_formula_refs_match_lirpf_articles(filing_year: int) -> None:
    revision = _modelo_100_revisions()[str(filing_year)]
    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    form_order_refs = {_MODELO_100_2025_FORM_ORDER_REF} if filing_year == 2025 else set()
    expected_refs_by_formula = {
        f"renta-{filing_year}-tipo-medio-gravamen-estatal-base-liquidable-general": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            _GENERAL_SCALE_ART_63_REF,
        },
        f"renta-{filing_year}-tipo-medio-gravamen-estatal-base-liquidable-ahorro": {
            _SAVINGS_STATE_SCALE_ART_66_REF,
        },
        f"renta-{filing_year}-minimo-personal-base-liquidable-ahorro-estatal": {
            _PERSONAL_FAMILY_MINIMUM_ART_56_REF,
            _SAVINGS_STATE_SCALE_ART_66_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-escala-estatal-sobre-base-liquidable-general": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            _GENERAL_SCALE_ART_63_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-escala-estatal-sobre-minimo-personal-familiar": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            _GENERAL_SCALE_ART_63_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-base-liquidable-general-estatal": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            _GENERAL_SCALE_ART_63_REF,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-integra-estatal": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            _GENERAL_SCALE_ART_63_REF,
            _SAVINGS_STATE_SCALE_ART_66_REF,
            *form_order_refs,
        },
    }

    assert expected_refs_by_formula.keys() <= formulas_by_id.keys()
    offenders: dict[str, tuple[str, ...]] = {}
    for formula_id, expected_refs in expected_refs_by_formula.items():
        legal_refs = tuple(formulas_by_id[formula_id].legal_refs)
        if set(legal_refs) != expected_refs:
            offenders[formula_id] = legal_refs
        assert _STATE_LIQUID_QUOTA_ART_67_REF not in legal_refs, formula_id
        assert _AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF not in legal_refs, formula_id

    assert not offenders
