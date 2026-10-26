"""Regression test for annual withholding-summary applicability.

The annual withholding summary duty is grounded in RIRPF art. 108.

See Also:
    :func:`~domain.calculations.registry.applicability.iter_modelo_applicability_rules`
        Rule-table iterator checked for annual withholding refs.
"""

from __future__ import annotations

import importlib

import pytest

from cadrumo.core.aggregation import ThirdPartyDeclarationRole
from cadrumo.core.modelo import Modelo
from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)

from ..applicability import (
    ApplicabilityProvenance,
    ApplicabilityVerdict,
    LedgerPayerFactDerivation,
    ModeloApplicabilityRule,
    iter_modelo_applicability_rules,
)
from ..applicability_payer_facts import PayerFactDeclaration, PayerFactProjection, payer_fact_declaration
from ..authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def test_annual_withholding_summary_applicability_uses_art_108_not_art_109() -> None:
    """M180/M190 filing duty is RIRPF art. 108, not pago-fraccionado art. 109."""
    domain_mod = importlib.import_module("..applicability", package=__package__)
    core_mod = importlib.import_module(".....core.modelo", package=__package__)
    rules_by_modelo = {rule.modelo: rule for rule in domain_mod.iter_modelo_applicability_rules()}

    for modelo in (core_mod.Modelo("180"), core_mod.Modelo("190")):
        legal_refs = rules_by_modelo[modelo].legal_refs
        assert "rd-439-2007:art-108" in legal_refs
        assert "rd-439-2007:art-109" not in legal_refs


def _production_rule(operation: PinnedAuthorityOperation, modelo: str) -> ModeloApplicabilityRule:
    return next(rule for rule in iter_modelo_applicability_rules(operation=operation) if rule.modelo == Modelo(modelo))


def _m720_profile(declaration: bool | None) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        bienes_extranjero_above_threshold=declaration,
    )


def test_ledger_yes_overrides_a_declared_no_and_keeps_the_disagreement(
    operation: PinnedAuthorityOperation,
) -> None:
    rule = _production_rule(operation, "720")
    fact = rule.required_payer_fact
    assert isinstance(fact, PayerFactProjection)
    assert fact.period_companion is None

    result = rule.evaluate(
        _m720_profile(False),
        ledger_payer_facts={fact.token: LedgerPayerFactDerivation.DERIVED_YES},
    )

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.provenance is ApplicabilityProvenance.LEDGER_DERIVED
    assert result.evidence_disagreement is not None
    assert result.evidence_disagreement.profile_declaration is PayerFactDeclaration.DECLARED_NO
    assert result.evidence_disagreement.ledger_derivation is LedgerPayerFactDerivation.DERIVED_YES


def test_ledger_yes_answers_an_unanswered_fact_without_a_disagreement(
    operation: PinnedAuthorityOperation,
) -> None:
    rule = _production_rule(operation, "720")
    fact = rule.required_payer_fact
    assert isinstance(fact, PayerFactProjection)

    result = rule.evaluate(
        _m720_profile(None),
        ledger_payer_facts={fact.token: LedgerPayerFactDerivation.DERIVED_YES},
    )

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.provenance is ApplicabilityProvenance.LEDGER_DERIVED
    assert result.evidence_disagreement is None


def test_ledger_no_preserves_a_declared_yes_and_reports_the_disagreement(
    operation: PinnedAuthorityOperation,
) -> None:
    rule = _production_rule(operation, "720")
    fact = rule.required_payer_fact
    assert isinstance(fact, PayerFactProjection)

    result = rule.evaluate(
        _m720_profile(True),
        ledger_payer_facts={fact.token: LedgerPayerFactDerivation.DERIVED_NO},
    )

    assert result.verdict is ApplicabilityVerdict.APPLICABLE
    assert result.provenance is ApplicabilityProvenance.PROFILE_DECLARED
    assert result.evidence_disagreement is not None
    assert result.evidence_disagreement.profile_declaration is PayerFactDeclaration.DECLARED_YES
    assert result.evidence_disagreement.ledger_derivation is LedgerPayerFactDerivation.DERIVED_NO


def test_ledger_no_does_not_turn_an_unanswered_fact_into_not_applicable(
    operation: PinnedAuthorityOperation,
) -> None:
    rule = _production_rule(operation, "720")
    fact = rule.required_payer_fact
    assert isinstance(fact, PayerFactProjection)

    result = rule.evaluate(
        _m720_profile(None),
        ledger_payer_facts={fact.token: LedgerPayerFactDerivation.DERIVED_NO},
    )

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert result.provenance is ApplicabilityProvenance.PROFILE_DECLARED
    assert result.evidence_disagreement is None


def test_unknown_and_missing_ledger_derivations_leave_the_profile_decisive(
    operation: PinnedAuthorityOperation,
) -> None:
    rule = _production_rule(operation, "720")
    fact = rule.required_payer_fact
    assert isinstance(fact, PayerFactProjection)

    for derivation in (LedgerPayerFactDerivation.UNKNOWN, None):
        ledger = {} if derivation is None else {fact.token: derivation}
        declared_yes = rule.evaluate(_m720_profile(True), ledger_payer_facts=ledger)
        declared_no = rule.evaluate(_m720_profile(False), ledger_payer_facts=ledger)
        unanswered = rule.evaluate(_m720_profile(None), ledger_payer_facts=ledger)

        assert declared_yes.verdict is ApplicabilityVerdict.APPLICABLE
        assert declared_no.verdict is ApplicabilityVerdict.NOT_APPLICABLE
        assert unanswered.verdict is ApplicabilityVerdict.INCOMPLETE
        assert declared_yes.provenance is ApplicabilityProvenance.PROFILE_DECLARED
        assert declared_no.provenance is ApplicabilityProvenance.PROFILE_DECLARED
        assert unanswered.provenance is ApplicabilityProvenance.PROFILE_DECLARED
        assert declared_yes.evidence_disagreement is None
        assert declared_no.evidence_disagreement is None
        assert unanswered.evidence_disagreement is None


def test_period_companion_fact_does_not_accept_a_ledger_derivation(
    operation: PinnedAuthorityOperation,
) -> None:
    rule = _production_rule(operation, "136")
    fact = rule.required_payer_fact
    assert isinstance(fact, PayerFactProjection)
    assert fact.period_companion is not None

    profile = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.from_registry("natural_person"),
        iva_regime=IVARegime("EXENTO"),
        premio_loteria_gravamen_especial_sin_retencion=True,
    )
    result = rule.evaluate(
        profile,
        ledger_payer_facts={fact.token: LedgerPayerFactDerivation.DERIVED_YES},
    )

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert fact.period_companion.label in result.reason
    assert result.provenance is ApplicabilityProvenance.PROFILE_DECLARED
    assert result.evidence_disagreement is None


def _m347_profile(
    *,
    declaration: bool | None,
    tax_id: str,
    entity_type: EntityType,
    iva_regime: IVARegime,
    roles: frozenset[ThirdPartyDeclarationRole],
    iva: ModeloIVAProfile | None,
) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=tax_id,
        entity_type=entity_type,
        declaration_roles=roles,
        irpf_income_categories=frozenset(),
        iva_regime=iva_regime,
        third_party_transactions_above_347_threshold=declaration,
        iva=iva,
    )


def test_holding_legal_exclusion_wins_even_after_an_undetermined_exclusion(
    operation: PinnedAuthorityOperation,
) -> None:
    rule = _production_rule(operation, "347")
    legal_exclusion = next(exclusion for exclusion in rule.exclusions if exclusion.id == "m347-sii")
    collector_exclusion = next(
        exclusion for exclusion in rule.exclusions if exclusion.id == "m347-cobro-por-cuenta-de-terceros"
    )
    assert collector_exclusion.declaration_roles is not None
    iva = ModeloIVAProfile(
        tax_territory=M303TaxTerritory.from_registry("COMMON_REGIME"),
        regime_composition=M303RegimeComposition.from_registry("GENERAL"),
        sii_enrolled=True,
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
    )
    profile = _m347_profile(
        declaration=False,
        tax_id="B12345674",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        roles=collector_exclusion.declaration_roles,
        iva=iva,
    )
    # Put the declared-C collector exclusion first; the SII exclusion is the
    # holding legal NOT_APPLICABLE finding and must still decide.
    reordered_rule = rule.model_copy(update={"exclusions": tuple(reversed(rule.exclusions))})

    result = reordered_rule.evaluate(profile)

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.reason == legal_exclusion.reason
    assert result.legal_refs == legal_exclusion.legal_refs


def test_undetermined_exclusions_keep_their_authored_order(operation: PinnedAuthorityOperation) -> None:
    rule = _production_rule(operation, "347")
    sii_exclusion = next(exclusion for exclusion in rule.exclusions if exclusion.id == "m347-sii")
    activity_exclusion = next(exclusion for exclusion in rule.exclusions if exclusion.id == "m347-sin-actividad")
    profile = _m347_profile(
        declaration=True,
        tax_id="X1234567L",
        entity_type=EntityType.from_registry("natural_person"),
        iva_regime=IVARegime("NO_APLICA"),
        roles=frozenset(),
        iva=None,
    )
    fact = rule.required_payer_fact
    assert isinstance(fact, PayerFactProjection)
    assert payer_fact_declaration(profile, fact) is PayerFactDeclaration.DECLARED_YES
    reversed_rule = rule.model_copy(update={"exclusions": tuple(reversed(rule.exclusions))})
    sii_finding = sii_exclusion.evaluate(rule.modelo, profile)
    activity_finding = activity_exclusion.evaluate(rule.modelo, profile)
    assert sii_finding is not None
    assert activity_finding is not None

    original_order_result = rule.evaluate(profile)
    reversed_order_result = reversed_rule.evaluate(profile)

    assert original_order_result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert original_order_result.reason == sii_finding.applicability.reason
    assert original_order_result.legal_refs == sii_finding.applicability.legal_refs
    assert reversed_order_result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert reversed_order_result.reason == activity_finding.applicability.reason
    assert reversed_order_result.legal_refs == activity_finding.applicability.legal_refs
