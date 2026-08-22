"""Registry-owned tests for modelo applicability rule grounding."""

from __future__ import annotations

from datetime import date
from typing import TypedDict

import pytest
from pydantic import ValidationError

from .....core.resources import resources
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
from .. import (
    ApplicabilityVerdict,
    Modelo202Modality,
    Modelo202ModalityVerdict,
    ModeloApplicability,
    ModeloApplicabilityRule,
    derive_modelo_applicability,
    iter_modelo_applicability_rules,
)
from .._applicability import MODELO_APPLICABILITY_RULES
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _FactUpdateParams(TypedDict, total=False):
    pays_rent_with_retencion: bool
    does_intracomunitario: bool
    third_party_transactions_above_347_threshold: bool


_PERIODIC_IVA_MODELOS = ("303", "390")
_NON_PERIODIC_IVA_REGIMES = (IVARegime.EXENTO, IVARegime.RECARGO_EQUIVALENCIA)
_FACT_GATED_MODELO_CASES: tuple[tuple[str, _FactUpdateParams], ...] = (
    ("115", {"pays_rent_with_retencion": True}),
    ("180", {"pays_rent_with_retencion": True}),
    ("349", {"does_intracomunitario": True}),
    ("347", {"third_party_transactions_above_347_threshold": True}),
)
_NON_IMPATRIADO_SPECIAL_REGIMES = (None, IrpfSpecialRegime.GENERAL)


def test_seed_modelo_applicability_rules_are_registry_owned() -> None:
    """Every applicability rule authored in the registry is one the engine reads.

    This pinned a literal list of modelo ids, which had to be edited by hand on
    every enrolment and could not tell a missing entry from an intended one. It
    was hiding a real defect: nine modelos -- 136, 145, 151, 210, 216, 232, 296,
    360 and 714 -- carried applicability rules authored and loader-validated in
    their registry trees while absent from
    ``REGISTRY_RESOLVED_APPLICABILITY_MODELOS``, so ``has_applicability_rule``
    answered ``False`` for them and every profile got ``INCOMPLETE``. Authored
    regulatory data that nothing reads is the dormant-capacity failure, and a
    hand-maintained id list agreed with itself while it happened.

    The property instead: what the package exposes is exactly what the registry
    authors, plus the modelos still resolved from the literal table. A rule
    authored without enrolment now fails here, and so does an enrolment with no
    rule behind it.
    """

    assert derive_modelo_applicability.__module__ == ("cadrumo.domain.calculations.registry._applicability")

    modelos, _catalogues = _committed_registry_tree()
    authored = {
        modelo.id
        for modelo in modelos
        if any(revision.applicability for revision in modelo.revisions.values())
    }
    assert authored, "no modelo authors an applicability rule, so this assertion would be vacuous"

    still_literal = {str(modelo) for modelo in MODELO_APPLICABILITY_RULES}
    exposed = {rule.modelo for rule in iter_modelo_applicability_rules()}

    assert exposed == authored | still_literal, {
        "authored_but_not_exposed": sorted(authored - exposed),
        "exposed_but_not_authored_or_literal": sorted(exposed - (authored | still_literal)),
    }


def test_seed_modelo_applicability_legal_refs_resolve_in_registry() -> None:
    """Every seed applicability rule carries real scoped legal refs."""

    registered_legal_ids = set(resources().modelos.authority.catalogues.legal)
    assert registered_legal_ids

    for rule in iter_modelo_applicability_rules():
        assert rule.legal_refs, rule.modelo
        unresolved = sorted(ref for ref in rule.legal_refs if ref not in registered_legal_ids)
        assert not unresolved, f"{rule.modelo} unresolved legal_refs: {unresolved}"
        for ref in rule.legal_refs:
            assert ":" in ref, f"{rule.modelo} legal_ref is not scoped: {ref!r}"


def test_applicability_models_reject_blank_reasons_and_legal_refs() -> None:
    """Applicability explanations are grounded operator output, not free text."""
    with pytest.raises(ValidationError, match="reason"):
        ModeloApplicability(
            modelo="130",
            verdict=ApplicabilityVerdict.APPLICABLE,
            reason=" ",
            legal_refs=("ley-35-2006:art-99",),
        )
    with pytest.raises(ValidationError, match="legal_refs"):
        ModeloApplicability(
            modelo="130",
            verdict=ApplicabilityVerdict.APPLICABLE,
            reason="Modelo 130 aplica.",
            legal_refs=(" ",),
        )
    for field_name in ("applicable_reason", "not_applicable_reason"):
        payload = {
            "modelo": "130",
            "applicable_entity_types": frozenset({EntityType.NATURAL_PERSON}),
            "applicable_reason": "Modelo 130 aplica.",
            "not_applicable_reason": "Modelo 130 no aplica.",
            "legal_refs": ("ley-35-2006:art-99",),
        }
        payload[field_name] = " "
        with pytest.raises(ValidationError, match=field_name):
            ModeloApplicabilityRule.model_validate(payload)
    with pytest.raises(ValidationError, match="legal_refs"):
        ModeloApplicabilityRule(
            modelo="130",
            applicable_entity_types=frozenset({EntityType.NATURAL_PERSON}),
            applicable_reason="Modelo 130 aplica.",
            not_applicable_reason="Modelo 130 no aplica.",
            legal_refs=(" ",),
        )


def test_modelo_202_modality_verdict_rejects_blank_reason_and_legal_refs() -> None:
    """The M202 modality gate carries the same grounding contract."""
    with pytest.raises(ValidationError, match="reason"):
        Modelo202ModalityVerdict(
            modality=Modelo202Modality.ART_40_3_MANDATORY,
            reason=" ",
            legal_refs=("ley-27-2014:art-40",),
        )
    with pytest.raises(ValidationError, match="legal_refs"):
        Modelo202ModalityVerdict(
            modality=Modelo202Modality.ART_40_3_MANDATORY,
            reason="Modelo 202 modalidad obligatoria.",
            legal_refs=(" ",),
        )


def test_registry_rules_derive_per_entity_and_per_regime_verdicts() -> None:
    """Real profiles exercise entity and IRPF-regime applicability gates."""

    direct_autonomo = TaxpayerProfile(
        tax_id="A4567890A",
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


def _attribution_entity_profile(
    *,
    iva_regime: IVARegime = IVARegime.GENERAL,
    has_employees: bool = False,
    pays_professionals_with_retencion: bool = False,
    pays_rent_with_retencion: bool = False,
    does_intracomunitario: bool = False,
    third_party_transactions_above_347_threshold: bool = False,
) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="E12345674",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        iva_regime=iva_regime,
        has_employees=has_employees,
        pays_professionals_with_retencion=pays_professionals_with_retencion,
        pays_rent_with_retencion=pays_rent_with_retencion,
        does_intracomunitario=does_intracomunitario,
        third_party_transactions_above_347_threshold=third_party_transactions_above_347_threshold,
    )


def test_attribution_entity_with_general_iva_is_applicable_for_iva_modelos() -> None:
    """An attribution entity can be IVA-taxable even though income passes through."""

    for modelo in _PERIODIC_IVA_MODELOS:
        result = derive_modelo_applicability(_attribution_entity_profile(), modelo)

        assert result.verdict is ApplicabilityVerdict.APPLICABLE, modelo
        assert result.applicable is True, modelo


def test_attribution_entity_without_periodic_iva_regime_owes_no_m303_or_m390() -> None:
    """A non-periodic IVA regime must not make M303/M390 applicable."""

    for iva_regime in _NON_PERIODIC_IVA_REGIMES:
        profile = _attribution_entity_profile(iva_regime=iva_regime)

        for modelo in _PERIODIC_IVA_MODELOS:
            result = derive_modelo_applicability(profile, modelo)
            assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, (iva_regime, modelo)
            assert result.applicable is False, (iva_regime, modelo)


def test_attribution_entity_with_employees_is_applicable_for_modelo_111_and_190() -> None:
    """An attribution entity with withheld salary payments owes M111 and its summary."""

    profile = _attribution_entity_profile(has_employees=True)

    for modelo in ("111", "190"):
        result = derive_modelo_applicability(profile, modelo)
        assert result.verdict is ApplicabilityVerdict.APPLICABLE, modelo
        assert result.applicable is True, modelo


def test_attribution_entity_without_withheld_income_fact_is_incomplete_for_modelo_111() -> None:
    """Without an employee/professional payer fact, M111 is undecided, not applicable."""

    result = derive_modelo_applicability(_attribution_entity_profile(), "111")

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert result.applicable is False


def test_attribution_entity_with_required_fact_is_applicable_for_fact_gated_modelos() -> None:
    """Attribution entities can owe non-cuota payer/informative modelos."""

    for modelo, payer_fact_update in _FACT_GATED_MODELO_CASES:
        result = derive_modelo_applicability(_attribution_entity_profile(**payer_fact_update), modelo)

        assert result.verdict is ApplicabilityVerdict.APPLICABLE, modelo
        assert result.applicable is True, modelo


def test_attribution_entity_without_required_fact_is_incomplete_for_fact_gated_modelos() -> None:
    """Missing payer/trade facts stay undecided instead of entity-excluded."""

    for modelo, _payer_fact_update in _FACT_GATED_MODELO_CASES:
        result = derive_modelo_applicability(_attribution_entity_profile(), modelo)

        assert result.verdict is ApplicabilityVerdict.INCOMPLETE, modelo
        assert result.applicable is False, modelo


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
        tax_id="A4567890A",
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
        tax_id="A4567890A",
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
        tax_id="A4567890A",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.CAPITAL_INMOBILIARIO}),
        iva_regime=IVARegime.GENERAL,
    )
    assert derive_modelo_applicability(landlord, "130").verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert derive_modelo_applicability(landlord, "131").verdict is ApplicabilityVerdict.NOT_APPLICABLE


def _beckham_profile(
    *,
    start_date: date = date(2023, 1, 1),
    bienes_extranjero_above_threshold: bool = False,
) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
        irpf_special_regime=IrpfSpecialRegime.IMPATRIADO,
        special_regime_start_date=start_date,
        bienes_extranjero_above_threshold=bienes_extranjero_above_threshold,
    )


def test_impatriado_art93_exempts_modelo_720_even_with_bienes_declared() -> None:
    """LIRPF Art. 93 impatriado profile: M720 must be NOT_APPLICABLE.

    An impatriado under the Beckham regime is taxed as a non-resident
    (IRNR) and does not owe the bienes-en-el-extranjero obligation
    reserved for IRPF residents. The exemption fires even when
    ``bienes_extranjero_above_threshold`` is ``True`` so the rule-table
    payer-fact gate is never reached.
    """

    beckham_profile = _beckham_profile(bienes_extranjero_above_threshold=True)
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


def test_impatriado_in_window_routes_annual_irpf_to_modelo_151() -> None:
    """Within the Art. 93 window, M151 applies and M100 is suppressed."""

    beckham_profile = _beckham_profile()

    m100 = derive_modelo_applicability(beckham_profile, "100", today=date(2026, 5, 27))
    m151 = derive_modelo_applicability(beckham_profile, "151", today=date(2026, 5, 27))

    assert m100.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert m100.applicable is False
    assert "Art. 93" in m100.reason
    assert "Modelo 151" in m100.reason
    assert "ley-35-2006:art-93" in m100.legal_refs
    # The retired `orden-eha-2887-2008:modelo-151` stub resolved to no text and
    # was absent from the legal catalogue; the real, bundled form orders are
    # asserted instead, which is what makes the subset check below meaningful.
    assert "orden-hap-2783-2015:art-1" in m100.legal_refs
    assert "orden-hfp-1338-2023:art-1" in m100.legal_refs

    assert m151.verdict is ApplicabilityVerdict.APPLICABLE
    assert m151.applicable is True
    assert "Modelo 151" in m151.reason
    assert set(m151.legal_refs).issubset(resources().modelos.authority.catalogues.legal)


def test_impatriado_year_seven_restores_m100_m720_and_suppresses_m151() -> None:
    """After the six-year window, the profile returns to ordinary IRPF routing."""

    expired_profile = _beckham_profile(bienes_extranjero_above_threshold=True)
    year_seven = date(2029, 1, 1)

    assert (
        derive_modelo_applicability(expired_profile, "100", today=year_seven).verdict is ApplicabilityVerdict.APPLICABLE
    )
    assert (
        derive_modelo_applicability(expired_profile, "151", today=year_seven).verdict
        is ApplicabilityVerdict.NOT_APPLICABLE
    )
    assert (
        derive_modelo_applicability(expired_profile, "720", today=year_seven).verdict is ApplicabilityVerdict.APPLICABLE
    )


def test_non_impatriado_profile_does_not_route_to_modelo_151() -> None:
    """A general-regime natural person stays outside the M151 route."""

    for special_regime in _NON_IMPATRIADO_SPECIAL_REGIMES:
        general_profile = TaxpayerProfile(
            tax_id="X1234567L",
            entity_type=EntityType.NATURAL_PERSON,
            irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
            iva_regime=IVARegime.GENERAL,
            irpf_special_regime=special_regime,
        )

        result = derive_modelo_applicability(general_profile, "151", today=date(2026, 5, 27))

        assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE, special_regime
        assert result.applicable is False, special_regime
        assert "Art. 93" in result.reason
