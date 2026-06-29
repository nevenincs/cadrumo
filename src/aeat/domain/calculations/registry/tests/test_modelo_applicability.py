"""Registry-owned tests for modelo applicability rule grounding."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from ....deadlines import (
    EntityType,
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
    TaxpayerProfile,
)
from .. import ValidatedRegistryAuthority
from ..applicability import (
    ApplicabilityVerdict,
    derive_modelo_applicability,
    iter_modelo_applicability_rules,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_seed_modelo_applicability_rules_are_registry_owned() -> None:
    """The seed rules are exposed by the registry package."""

    assert derive_modelo_applicability.__module__ == ("aeat.domain.calculations.registry._applicability")
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

    authority = ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())
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
    objetiva_autonomo = direct_autonomo.model_copy(update={"irpf_estimation_regime": IrpfEstimationRegime.OBJETIVA})
    sociedad_limitada = TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )

    assert derive_modelo_applicability(direct_autonomo, "130").verdict is (ApplicabilityVerdict.APPLICABLE)
    assert derive_modelo_applicability(direct_autonomo, "131").verdict is (ApplicabilityVerdict.NOT_APPLICABLE)
    assert derive_modelo_applicability(objetiva_autonomo, "131").verdict is (ApplicabilityVerdict.APPLICABLE)
    assert derive_modelo_applicability(sociedad_limitada, "202").verdict is (ApplicabilityVerdict.APPLICABLE)
    assert derive_modelo_applicability(sociedad_limitada, "100").verdict is (ApplicabilityVerdict.NOT_APPLICABLE)


def test_actividad_economica_without_declared_regime_defaults_to_directa_m130() -> None:
    """An actividad-económica autónomo with no declared estimation regime owes M130.

    Operator repro: a profile created with
    ``--irpf-income-categories actividad_economica`` but no
    ``--irpf-estimation-regime`` leaves ``irpf_estimation_regime`` ``None``.
    Estimación directa is the default IRPF method (LIRPF art. 16; RIRPF
    art. 32 makes módulos opt-in), so the undeclared regime resolves to
    directa: Modelo 130 is APPLICABLE and Modelo 131 is NOT_APPLICABLE.
    The two stay mutually exclusive — the profile is never told it owes
    both, and the actividad-económica filer is never silently dropped
    from the M130 family.
    """

    autonomo_no_regime = TaxpayerProfile(
        tax_id="A4567890B",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        iva_regime=IVARegime.GENERAL,
    )
    # The undeclared regime defaults to directa (the LIRPF default method).
    assert autonomo_no_regime.irpf_estimation_regime is None
    assert autonomo_no_regime.fiscal_residency is None
    assert derive_modelo_applicability(autonomo_no_regime, "130").verdict is ApplicabilityVerdict.APPLICABLE
    assert derive_modelo_applicability(autonomo_no_regime, "131").verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_non_resident_irnr_natural_person_does_not_owe_modelo_130() -> None:
    """Declared IRNR non-residency positively excludes the resident-IRPF M130."""

    non_resident_autonomo = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence="FR",
    )

    result = derive_modelo_applicability(non_resident_autonomo, "130")

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.applicable is False
    assert "NON_RESIDENT_IRNR" in result.reason
    assert "trlirnr-rdleg-5-2004:art-2" in result.legal_refs


def test_non_resident_irnr_natural_person_does_not_owe_modelo_100() -> None:
    """Declared IRNR non-residency positively excludes the resident-IRPF M100."""

    non_resident_autonomo = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence="FR",
    )

    result = derive_modelo_applicability(non_resident_autonomo, "100")

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.applicable is False
    assert "NON_RESIDENT_IRNR" in result.reason
    assert "trlirnr-rdleg-5-2004:art-2" in result.legal_refs


def test_non_resident_irnr_legal_entity_without_pe_does_not_owe_modelo_200() -> None:
    """Declared IRNR non-residency must not be treated as resident-company M200."""

    resident_company = TaxpayerProfile(
        tax_id="B66012345",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )
    non_resident_company = TaxpayerProfile(
        tax_id="B66012345",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        fiscal_residency=FiscalResidency.NON_RESIDENT_IRNR,
        country_of_fiscal_residence="DE",
    )

    assert derive_modelo_applicability(resident_company, "200").verdict is ApplicabilityVerdict.APPLICABLE

    result = derive_modelo_applicability(non_resident_company, "200")

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.applicable is False
    assert "NON_RESIDENT_IRNR" in result.reason
    assert "establecimiento permanente" in result.reason
    assert "trlirnr-rdleg-5-2004:art-2" in result.legal_refs
    assert "trlirnr-rdleg-5-2004:art-24" in result.legal_refs


def test_objective_estimation_regime_routes_to_m131() -> None:
    """An autónomo who explicitly elects módulos owes M131, not M130."""

    autonomo_modulos = TaxpayerProfile(
        tax_id="A4567890B",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        iva_regime=IVARegime.GENERAL,
        irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
    )
    assert autonomo_modulos.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA
    assert derive_modelo_applicability(autonomo_modulos, "131").verdict is ApplicabilityVerdict.APPLICABLE
    assert derive_modelo_applicability(autonomo_modulos, "130").verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_pure_landlord_without_actividad_economica_owes_no_m130() -> None:
    """A non-owing profile (pure landlord, no actividad económica) gets no M130.

    The directa default must not over-include: the regime fallback only
    fires after the income-category gate confirms actividad económica. A
    natural person whose only income is ``capital_inmobiliario`` declares
    no actividad económica, so Modelo 130 stays NOT_APPLICABLE — the fix
    does not spuriously add M130 for a taxpayer who does not owe it.
    """

    landlord = TaxpayerProfile(
        tax_id="A4567890B",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.CAPITAL_INMOBILIARIO}),
        iva_regime=IVARegime.GENERAL,
    )
    assert derive_modelo_applicability(landlord, "130").verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert derive_modelo_applicability(landlord, "131").verdict is ApplicabilityVerdict.NOT_APPLICABLE


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


def test_modelo_721_uses_crypto_abroad_threshold_not_modelo_720_bienes_fact() -> None:
    """M721 cannot inherit M720's bienes-en-el-extranjero threshold fact.

    The two obligations have separate subject matter. A taxpayer can
    have no Modelo 720 bienes/derechos above threshold while still
    holding Modelo 721 virtual currencies abroad above threshold.
    """

    base_profile = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=False,
    )

    assert derive_modelo_applicability(base_profile, "720").verdict is ApplicabilityVerdict.INCOMPLETE
    base_721 = derive_modelo_applicability(base_profile, "721")
    assert base_721.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "monedas virtuales" in base_721.reason
    assert "alquileres sujetos a retención" not in base_721.reason
    assert "ley-58-2003:da-18" in base_721.legal_refs
    assert "orden-hfp-886-2023:art-2" in base_721.legal_refs

    crypto_profile = base_profile.model_copy(update={"monedas_virtuales_extranjero_above_threshold": True})

    assert derive_modelo_applicability(crypto_profile, "720").verdict is ApplicabilityVerdict.INCOMPLETE
    assert derive_modelo_applicability(crypto_profile, "721").verdict is ApplicabilityVerdict.APPLICABLE


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
