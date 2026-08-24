"""The IVA block obliges one set of facts, and every authority reads it.

A profile declaring any Modelo IVA fact claims the whole block. Three
surfaces used to answer "what does a claimed block owe" independently: the
domain resolver refused without six facts, profile completeness knew of
none of them, and the wizard asked for them behind a narrower gate than the
one that claims the block. The operator met the divergence as a dead end --
``config profile status`` reported the profile ready and named
``app overview status`` as the next step, and that command refused for a
path no surface had asked for.
"""

from __future__ import annotations

import pytest

from ....domain.deadlines import (
    MODELO_IVA_BLOCK_CLAIMING_PATHS,
    MODELO_IVA_BLOCK_REQUIRED_PATHS,
    ProfileError,
    modelo_iva_profile_required_paths,
    profile_claims_modelo_iva_block,
    taxpayer_profile_from_mapping,
)
from ... import wizard as _wizard  # noqa: F401 - registers compiled profile keys
from .._completeness import conditional_profile_missing_required
from .._keys_validation import validate_profile_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_SATISFIED_IVA_BLOCK: dict[str, str] = {
    "iva.m303_regime_composition": "general",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


def test_declared_iva_regime_reports_the_whole_block_as_missing() -> None:
    """The reported symptom: a regime with no composition must not read as ready."""
    result = validate_profile_values(
        {
            "identity.tax_id": "12345678Z",
            "activities.description": "consultoria",
            "iva.regime": "GENERAL",
            "tax_residence.ccaa": "madrid",
        },
    )

    assert result.valid is False
    assert "iva.m303_regime_composition" in result.missing_required
    assert "tax_residence.jurisdiction_scope" in result.missing_required


def test_profile_with_no_iva_facts_is_never_asked_for_the_block() -> None:
    """A taxpayer with no IVA obligation declares none of the block-owned paths."""
    values = {
        "identity.tax_id": "12345678Z",
        "taxpayer_type.entity_type": "natural_person",
        "taxpayer_type.irpf_income_categories": "capital_inmobiliario",
        "tax_residence.ccaa": "madrid",
        "tax_residence.jurisdiction_scope": "common_regime",
    }

    assert profile_claims_modelo_iva_block(values) is False
    assert modelo_iva_profile_required_paths(values) == ()
    assert conditional_profile_missing_required(values) == ()
    assert validate_profile_values(values).valid is True


def test_any_single_iva_fact_claims_the_block_including_a_declined_enrolment() -> None:
    """Answering "no" is a declaration about IVA, so it claims the block too.

    This is the case that read as READY before: a fact written through
    ``config profile set`` claimed the block for the resolver while every
    readiness surface stayed silent.
    """
    values = {
        "identity.tax_id": "12345678Z",
        "taxpayer_type.entity_type": "natural_person",
        "taxpayer_type.irpf_income_categories": "capital_inmobiliario",
        "tax_residence.ccaa": "madrid",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.roi_enrolled": "false",
    }

    result = validate_profile_values(values)

    assert profile_claims_modelo_iva_block(values) is True
    assert result.valid is False
    assert "iva.m303_regime_composition" in result.missing_required


def test_every_block_owned_path_claims_the_block_on_its_own() -> None:
    """No path in the claim set may be declarable without obliging the rest."""
    for path in sorted(MODELO_IVA_BLOCK_CLAIMING_PATHS):
        assert profile_claims_modelo_iva_block({path: "false"}) is True, path


def test_a_satisfied_block_leaves_nothing_outstanding() -> None:
    values = {
        "identity.tax_id": "12345678Z",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }

    assert conditional_profile_missing_required(values) == ()


def test_completeness_demands_exactly_what_the_resolver_refuses_without() -> None:
    """The anti-divergence gate: derive the resolver's demands by running it.

    The published tuple is not compared against a restatement of itself. A
    claimed block is built through ``taxpayer_profile_from_mapping`` -- the
    public door every real caller passes through, canonical-token projection
    included -- and peeled one refusal at a time, so the set it ACTUALLY
    enforces is discovered rather than assumed. A fact added to the resolver
    without being published here reds this test.
    """
    satisfy = {
        "iva.m303_regime_composition": "general",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
    values: dict[str, str] = {"iva.regime": "GENERAL"}

    demanded: list[str] = []
    for _ in range(len(satisfy) + 1):
        try:
            profile = taxpayer_profile_from_mapping(dict(values), tax_id_default="12345678Z")
        except ProfileError as exc:
            named = [path for path in satisfy if path in str(exc)]
            assert len(named) == 1, f"refusal names no single known path: {exc}"
            path = named[0]
            assert path not in demanded, f"resolver re-refused {path}"
            demanded.append(path)
            values[path] = satisfy[path]
            continue
        assert profile.iva is not None, "a fully satisfied block must build an IVA profile"
        break
    else:  # pragma: no cover - the loop must terminate by resolving
        pytest.fail("resolver never resolved a fully satisfied IVA block")

    assert sorted(demanded) == sorted(MODELO_IVA_BLOCK_REQUIRED_PATHS)
    assert sorted(modelo_iva_profile_required_paths({"iva.regime": "GENERAL"})) == sorted(demanded)
