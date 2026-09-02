"""Modelo 100 quota-chain legal-reference checks against the bundled registry."""

from __future__ import annotations

import pytest

from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERSONAL_FAMILY_MINIMUM_ART_56_REF = "ley-35-2006:art-56"
_STATE_INTEGRAL_QUOTA_ART_62_REF = "ley-35-2006:art-62"
_GENERAL_SCALE_ART_63_REF = "ley-35-2006:art-63"
_STATE_LIQUID_QUOTA_ART_67_REF = "ley-35-2006:art-67"
_STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF = "ley-35-2006:art-64"
_AUTONOMIC_CHILD_SUPPORT_ANNUITIES_ART_75_REF = "ley-35-2006:art-75"
_MODELO_100_2025_FORM_ORDER_REF = "orden-hac-277-2026:art-3"

#: Each pre-2024 filing year's applicability window predates art.66's current
#: catalogue redaction (effective_from 2024-12-22, Ley 7/2024), so it cites the
#: version-scoped redaction actually in force for that filing year instead of
#: the bare current id.
_SAVINGS_STATE_SCALE_ART_66_REF_BY_YEAR = {
    2020: "ley-35-2006:art-66-2015",
    2021: "ley-35-2006:art-66-2021",
    2022: "ley-35-2006:art-66-2021",
    2023: "ley-35-2006:art-66-2023",
    2024: "ley-35-2006:art-66",
    2025: "ley-35-2006:art-66",
}

#: art-63's current redaction takes effect 2021-01-01 (Ley 11/2020's sixth
#: bracket above 300.000 euros); 2020's devengo (closes 2020-12-31) falls
#: entirely inside the pre-amendment art-63-2015 window (2015-01-01 to
#: 2020-12-31), so it cites the version-scoped redaction instead of the bare
#: current id.
_GENERAL_SCALE_ART_63_REF_BY_YEAR = {
    2020: "ley-35-2006:art-63-2015",
    2021: _GENERAL_SCALE_ART_63_REF,
    2022: _GENERAL_SCALE_ART_63_REF,
    2023: _GENERAL_SCALE_ART_63_REF,
    2024: _GENERAL_SCALE_ART_63_REF,
    2025: _GENERAL_SCALE_ART_63_REF,
}

# LIRPF art. 64 (anualidades por alimentos, estatal separate escala, #532) is a
# legitimate legal_ref on the state escala/cuota-base formulas ONLY for the
# revisions where the separate-escala régimen is modelled.
_SEPARATE_ESCALA_MODELLED_YEARS = frozenset({2020, 2021, 2022, 2023, 2024, 2025})


def _modelo_100_revisions():
    modelo, _catalogues = _committed_modelo("100")
    return modelo.revisions


@pytest.mark.parametrize("filing_year", range(2020, 2026))
def test_modelo_100_state_quota_formula_refs_match_lirpf_articles(filing_year: int) -> None:
    revision = _modelo_100_revisions()[str(filing_year)]
    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    form_order_refs = {_MODELO_100_2025_FORM_ORDER_REF} if filing_year == 2025 else set()
    regime_modelled = filing_year in _SEPARATE_ESCALA_MODELLED_YEARS
    regime_refs = {_STATE_CHILD_SUPPORT_ANNUITIES_ART_64_REF} if regime_modelled else set()
    _savings_state_scale_art_66_ref = _SAVINGS_STATE_SCALE_ART_66_REF_BY_YEAR[filing_year]
    general_scale_art_63_ref = _GENERAL_SCALE_ART_63_REF_BY_YEAR[filing_year]
    expected_refs_by_formula = {
        f"renta-{filing_year}-tipo-medio-gravamen-estatal-base-liquidable-general": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            general_scale_art_63_ref,
        },
        f"renta-{filing_year}-tipo-medio-gravamen-estatal-base-liquidable-ahorro": {
            _savings_state_scale_art_66_ref,
        },
        f"renta-{filing_year}-minimo-personal-base-liquidable-ahorro-estatal": {
            _PERSONAL_FAMILY_MINIMUM_ART_56_REF,
            _savings_state_scale_art_66_ref,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-escala-estatal-sobre-base-liquidable-general": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            general_scale_art_63_ref,
            *regime_refs,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-escala-estatal-sobre-minimo-personal-familiar": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            general_scale_art_63_ref,
            *regime_refs,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-base-liquidable-general-estatal": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            general_scale_art_63_ref,
            *regime_refs,
            *form_order_refs,
        },
        f"renta-{filing_year}-cuota-integra-estatal": {
            _STATE_INTEGRAL_QUOTA_ART_62_REF,
            general_scale_art_63_ref,
            _savings_state_scale_art_66_ref,
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
