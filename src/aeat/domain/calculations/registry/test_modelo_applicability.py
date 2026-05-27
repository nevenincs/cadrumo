"""Registry-owned tests for modelo applicability rule grounding."""

from __future__ import annotations

from datetime import date

import pytest

from aeat.core.resources import bundled_path
from aeat.domain.calculations.registry import ValidatedRegistryAuthority
from aeat.domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    derive_modelo_applicability,
    iter_modelo_applicability_rules,
)
from aeat.domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
    TaxpayerProfile,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_seed_modelo_applicability_rules_are_registry_owned() -> None:
    """The W03.S11 seed rules are exposed by the registry package."""

    assert derive_modelo_applicability.__module__ == (
        "aeat.domain.calculations.registry._applicability"
    )
    rules = iter_modelo_applicability_rules()
    assert {rule.modelo for rule in rules} == {
        "100",
        "111",
        "115",
        "130",
        "131",
        "180",
        "184",
        "190",
        "200",
        "202",
        "303",
        "347",
        "349",
        "390",
        "720",
        "721",
    }


def test_seed_modelo_applicability_legal_refs_resolve_in_registry() -> None:
    """Every seed applicability rule carries real scoped legal refs."""

    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"), source_root=bundled_path()
    )
    registered_legal_ids = set(authority.catalogues.legal)
    assert registered_legal_ids

    for rule in iter_modelo_applicability_rules():
        assert rule.legal_refs, rule.modelo
        unresolved = sorted(ref for ref in rule.legal_refs if ref not in registered_legal_ids)
        assert not unresolved, f"{rule.modelo} unresolved legal_refs: {unresolved}"
        for ref in rule.legal_refs:
            assert ":" in ref, f"{rule.modelo} legal_ref is not scoped: {ref!r}"


def test_registry_rules_derive_per_entity_and_per_regime_verdicts() -> None:
    """Real profiles exercise entity and IRPF-regime applicability gates."""

    direct_autonomo = TaxpayerProfile(
        tax_id="A4567890B",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_SIMPLIFICADA,
        iva_regime=IVARegime.GENERAL,
    )
    objetiva_autonomo = direct_autonomo.model_copy(
        update={"irpf_estimation_regime": IrpfEstimationRegime.OBJETIVA}
    )
    sociedad_limitada = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )

    assert derive_modelo_applicability(direct_autonomo, "130").verdict is (
        ApplicabilityVerdict.APPLICABLE
    )
    assert derive_modelo_applicability(direct_autonomo, "131").verdict is (
        ApplicabilityVerdict.NOT_APPLICABLE
    )
    assert derive_modelo_applicability(objetiva_autonomo, "131").verdict is (
        ApplicabilityVerdict.APPLICABLE
    )
    assert derive_modelo_applicability(sociedad_limitada, "202").verdict is (
        ApplicabilityVerdict.APPLICABLE
    )
    assert derive_modelo_applicability(sociedad_limitada, "100").verdict is (
        ApplicabilityVerdict.NOT_APPLICABLE
    )


def test_impatriado_art93_exempts_modelo_720_even_with_bienes_declared() -> None:
    """LIRPF Art. 93 impatriado profile: M720 must be NOT_APPLICABLE.

    An impatriado under the Beckham regime is taxed as a non-resident
    (IRNR) and does not owe the bienes-en-el-extranjero obligation
    reserved for IRPF residents. The exemption fires even when
    ``bienes_extranjero_above_threshold`` is ``True`` so the rule-table
    payer-fact gate is never reached.
    """

    beckham_profile = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
        irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
        special_regime_start_date=date(2023, 1, 1),
        # bienes declared above threshold — exemption must still fire
        bienes_extranjero_above_threshold=True,
    )
    # Pass today within the 6-year window (2023-2028) so the exemption fires.
    result = derive_modelo_applicability(beckham_profile, "720", today=date(2026, 5, 27))
    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    # Reason must cite the Art. 93 special regime
    assert "Art. 93" in result.reason or "impatriado" in result.reason.lower()
    # Legal refs must include the LIRPF Art. 93 authority
    assert any("ley-35-2006" in ref for ref in result.legal_refs)


def test_general_regime_profile_with_bienes_declared_modelo_720_applicable() -> None:
    """A non-impatriado natural person with bienes above threshold is APPLICABLE for M720.

    This is the counter-proof: removing the special regime restores the
    standard payer-fact logic and the profile gets APPLICABLE.
    """

    general_profile = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
        irpf_special_regime=None,
        bienes_extranjero_above_threshold=True,
    )
    result = derive_modelo_applicability(general_profile, "720")
    assert result.verdict is ApplicabilityVerdict.APPLICABLE


def test_impatriado_exemption_does_not_affect_other_modelos() -> None:
    """The impatriado pre-check is scoped strictly to M720.

    An impatriado with trabajo income is still APPLICABLE for M100;
    the Art. 93 exemption must not bleed into unrelated modelos.
    """

    beckham_profile = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
        irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
        special_regime_start_date=date(2023, 1, 1),
    )
    # Modelo 100 applies regardless of the special regime: the impatriado
    # files Modelo 151, but Modelo 100 applicability is not gated here.
    assert (
        derive_modelo_applicability(beckham_profile, "100", today=date(2026, 5, 27)).verdict
        is ApplicabilityVerdict.APPLICABLE
    )
