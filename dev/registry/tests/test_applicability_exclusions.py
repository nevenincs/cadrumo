"""Applicability exclusions: the shared mechanism and the Modelo 347 declarations.

The mechanism half builds isolated fragments and proves the hydration boundary
refuses what an exclusion cannot read. The Modelo 347 half resolves the rule
from the compiled authored registry and checks verdicts for real profiles
against RGAT arts. 31 and 32 (RD 1065/2007) and RIVA art. 62.6.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    ModeloApplicability,
    ModeloApplicabilityRule,
    derive_modelo_applicability,
    hydrate_applicability_rule,
    resolve_applicability_rule_from_authority,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.irpf_income_categories import require_irpf_income_category
from cadrumo.domain.calculations.registry.iva_regime_vocabulary import require_iva_regime
from cadrumo.domain.calculations.registry.queries import RegistryQueryService
from cadrumo.domain.calculations.registry.schema_revision_members import (
    ApplicabilityExclusionDefinition,
    ApplicabilityRuleDefinition,
)
from cadrumo.domain.calculations.registry.third_party_declaration_roles import require_third_party_declaration_role
from cadrumo.domain.contribuyente.entity_type import require_entity_type, require_legal_entity_form
from cadrumo.domain.deadlines.models import ModeloEnrollment, ModeloIVAProfile, TaxpayerProfile
from dev.registry.compiler.authority import compiled_bundled_authority

from ..compiler.validate_applicability_section import validate_applicability_section
from ._referential_integrity_support import REFERENCE_LEGAL_ID, minimal_legal_ref, minimal_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_TODAY = date(2026, 10, 3)
_ART_31 = "rd-1065-2007:art-31"
_ART_32 = "rd-1065-2007:art-32"
_RIVA_62 = "rd-1624-1992:art-62"


def _fragment(*exclusions: ApplicabilityExclusionDefinition) -> ApplicabilityRuleDefinition:
    return ApplicabilityRuleDefinition(
        id="m999-seed",
        applicable_entity_types=("natural_person", "legal_entity"),
        required_payer_fact="exceeds_third_party_threshold",
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        exclusions=exclusions,
        legal_refs=(REFERENCE_LEGAL_ID,),
    )


def _exclusion(**fields: object) -> ApplicabilityExclusionDefinition:
    return ApplicabilityExclusionDefinition.model_validate(
        {"id": "m999-excluded", "reason": "excluded", "legal_refs": (REFERENCE_LEGAL_ID,), **fields},
    )


def _iva(**facts: bool) -> ModeloIVAProfile:
    return ModeloIVAProfile.model_validate(
        {
            "tax_territory": "common_regime",
            "regime_composition": "general",
            "redeme_enrolled": False,
            "cash_accounting_regime_enrolled": False,
            "voluntary_sii_enrolled": False,
            "hydrocarbon_deposit_advance_payment_deduction_entitled": False,
            **facts,
        },
    )


def _sociedad(**facts: object) -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "B12345674",
            "entity_type": require_entity_type("legal_entity"),
            "legal_entity_form": require_legal_entity_form("sl"),
            "iva_regime": require_iva_regime("GENERAL"),
            **facts,
        },
    )


def _persona(categories: tuple[str, ...], iva_regime: str, **facts: object) -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X1234567L",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset(require_irpf_income_category(token) for token in categories),
            "iva_regime": require_iva_regime(iva_regime),
            **facts,
        },
    )


def _m347(profile: TaxpayerProfile) -> ModeloApplicability:
    return derive_modelo_applicability(profile, "347", today=_TODAY, authority=compiled_bundled_authority())


def _m347_rule() -> ModeloApplicabilityRule:
    return resolve_applicability_rule_from_authority(compiled_bundled_authority(), Modelo("347"))


def _m347_exclusion_reason(exclusion_id: str) -> str:
    return next(exclusion.reason for exclusion in _m347_rule().exclusions if exclusion.id == exclusion_id)


# ---------------------------------------------------------------------
# The shared mechanism
# ---------------------------------------------------------------------


def test_an_exclusion_naming_an_undeclared_payer_fact_is_refused() -> None:
    fragment = _fragment(_exclusion(payer_fact="not_a_declared_payer_fact"))

    with pytest.raises(RegistryValidationError, match="not_a_declared_payer_fact"):
        hydrate_applicability_rule(Modelo("347"), fragment)


@pytest.mark.parametrize("payer_fact", ("pays_capital_income_with_retencion", "pays_withheld_income"))
def test_an_exclusion_reading_a_two_state_fact_is_refused(payer_fact: str) -> None:
    fragment = _fragment(_exclusion(payer_fact=payer_fact))

    with pytest.raises(RegistryValidationError, match="cannot tell a declared no"):
        hydrate_applicability_rule(Modelo("347"), fragment)


def test_an_exclusion_naming_an_unknown_role_selection_is_refused() -> None:
    fragment = _fragment(_exclusion(declaration_role_selection="Z"))

    with pytest.raises(RegistryValidationError, match="'Z'"):
        hydrate_applicability_rule(Modelo("347"), fragment)


def test_an_exclusion_naming_an_unknown_axis_token_is_refused() -> None:
    fragment = _fragment(_exclusion(iva_regimes=("NOT_A_REGIME",)))

    with pytest.raises(RegistryValidationError, match="NOT_A_REGIME"):
        hydrate_applicability_rule(Modelo("347"), fragment)


@pytest.mark.parametrize(
    ("fields", "message"),
    (
        pytest.param({}, "at least one condition", id="no-condition"),
        pytest.param({"entity_types": ("legal_entity",), "payer_fact_declared": False}, "without naming", id="answer"),
        pytest.param({"iva_regimes": ("GENERAL", "GENERAL")}, "unique", id="duplicate-token"),
        pytest.param({"entity_types": ("legal_entity",), "unknown_condition": True}, "unknown_condition", id="extra"),
    ),
)
def test_a_malformed_exclusion_declaration_is_refused(fields: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _exclusion(**fields)


def test_exclusion_ids_are_unique_within_a_rule() -> None:
    with pytest.raises(ValueError, match="exclusion ids must be unique"):
        _fragment(_exclusion(entity_types=("legal_entity",)), _exclusion(iva_regimes=("GENERAL",)))


def test_the_section_validator_reports_an_exclusion_legal_ref_that_does_not_resolve() -> None:
    exclusion = _exclusion(entity_types=("legal_entity",), legal_refs=("ley-does-not-exist:art-9",))
    revision = minimal_revision().model_copy(update={"applicability": (_fragment(exclusion),)})

    failures = validate_applicability_section(
        prefix="modelo 347 revision 2025",
        modelo="347",
        revision=revision,
        legal_refs={REFERENCE_LEGAL_ID: minimal_legal_ref()},
    )

    assert any("exclusion m999-excluded" in failure and "ley-does-not-exist:art-9" in failure for failure in failures)


def test_a_holding_exclusion_overrides_a_declared_yes_and_an_unanswered_one_never_reads_applicable() -> None:
    rule = hydrate_applicability_rule(
        Modelo("347"),
        _fragment(_exclusion(payer_fact="bienes_extranjero_above_threshold")),
    )
    base = {"third_party_transactions_above_347_threshold": True}

    excluded = rule.evaluate(_sociedad(**base, bienes_extranjero_above_threshold=True))
    undetermined = rule.evaluate(_sociedad(**base))
    declared_no = rule.evaluate(_sociedad(**base, bienes_extranjero_above_threshold=False))
    ruled_out = rule.evaluate(_sociedad(third_party_transactions_above_347_threshold=False))

    assert (excluded.verdict, excluded.reason) == (ApplicabilityVerdict.NOT_APPLICABLE, "excluded")
    assert undetermined.verdict is ApplicabilityVerdict.INCOMPLETE
    assert declared_no.verdict is ApplicabilityVerdict.APPLICABLE
    # An unanswered exclusion does not mask the payer fact's own definitive no.
    assert (ruled_out.verdict, ruled_out.reason) == (ApplicabilityVerdict.NOT_APPLICABLE, "does not apply")


def test_an_exclusion_on_an_unanswered_income_category_set_is_undetermined() -> None:
    rule = hydrate_applicability_rule(
        Modelo("347"),
        _fragment(_exclusion(entity_types=("natural_person",), lacking_income_categories=("actividad_economica",))),
    )

    undeclared = rule.evaluate(_persona((), "GENERAL", third_party_transactions_above_347_threshold=True))
    legal_entity = rule.evaluate(_sociedad(third_party_transactions_above_347_threshold=True))

    assert undeclared.verdict is ApplicabilityVerdict.INCOMPLETE
    assert legal_entity.verdict is ApplicabilityVerdict.APPLICABLE


# ---------------------------------------------------------------------
# Modelo 347: RGAT art. 32.e and RIVA art. 62.6 (SII)
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("iva_facts", "large_company"),
    (
        pytest.param({"sii_enrolled": True}, False, id="mandatory-sii"),
        pytest.param({"voluntary_sii_enrolled": True}, False, id="voluntary-sii"),
        pytest.param({"redeme_enrolled": True}, False, id="redeme"),
        pytest.param({"group_member_enrolled": True}, False, id="iva-group"),
        pytest.param({}, True, id="large-company"),
    ),
)
def test_a_sii_filer_is_not_obliged_to_file_modelo_347(iva_facts: dict[str, bool], large_company: bool) -> None:
    profile = _sociedad(
        third_party_transactions_above_347_threshold=True,
        iva=_iva(**iva_facts),
        enrollment=ModeloEnrollment(large_company=large_company),
    )

    result = _m347(profile)

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.reason == _m347_exclusion_reason("m347-sii")
    assert {_ART_32, _RIVA_62} <= set(result.legal_refs)


def test_an_unanswered_sii_status_keeps_modelo_347_incomplete() -> None:
    result = _m347(_sociedad(third_party_transactions_above_347_threshold=True))

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "Suministro Inmediato de Información" in result.reason
    assert _ART_32 in result.legal_refs


def test_an_unanswered_sii_status_does_not_mask_a_declared_below_threshold() -> None:
    result = _m347(_sociedad(third_party_transactions_above_347_threshold=False))

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.reason == _m347_rule().not_applicable_reason


# ---------------------------------------------------------------------
# Modelo 347: RGAT art. 31.1 activity requirement
# ---------------------------------------------------------------------


def test_a_general_regime_autonomo_above_the_threshold_files_modelo_347() -> None:
    profile = _persona(
        ("actividad_economica",), "GENERAL", third_party_transactions_above_347_threshold=True, iva=_iva()
    )

    assert _m347(profile).verdict is ApplicabilityVerdict.APPLICABLE


def test_a_salaried_person_without_activity_is_not_obliged_to_file_modelo_347() -> None:
    result = _m347(_persona(("trabajo",), "NO_APLICA", third_party_transactions_above_347_threshold=True))

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.reason == _m347_exclusion_reason("m347-sin-actividad")
    assert result.legal_refs == (_ART_31,)


def test_a_landlord_with_an_iva_subject_lease_stays_in_scope() -> None:
    profile = _persona(
        ("capital_inmobiliario",), "GENERAL", third_party_transactions_above_347_threshold=True, iva=_iva()
    )

    assert _m347(profile).verdict is ApplicabilityVerdict.APPLICABLE


# ---------------------------------------------------------------------
# Modelo 347: RGAT art. 32.c floor for collectors on behalf of third parties
# ---------------------------------------------------------------------


def _collector(*, above_threshold: bool) -> TaxpayerProfile:
    return _sociedad(
        declaration_roles=frozenset({require_third_party_declaration_role("third_party_fee_collector")}),
        third_party_transactions_above_347_threshold=above_threshold,
        iva=_iva(),
    )


def test_a_collector_answering_no_to_the_general_threshold_stays_incomplete() -> None:
    result = _m347(_collector(above_threshold=False))

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "300,51" in result.reason
    assert _ART_32 in result.legal_refs


def test_a_collector_above_the_threshold_files_modelo_347() -> None:
    assert _m347(_collector(above_threshold=True)).verdict is ApplicabilityVerdict.APPLICABLE


def test_a_filer_without_the_collector_role_answering_no_is_not_obliged() -> None:
    result = _m347(_sociedad(third_party_transactions_above_347_threshold=False, iva=_iva()))

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.reason == _m347_rule().not_applicable_reason


def test_every_modelo_347_edition_carries_the_same_exclusions() -> None:
    exclusion_ids = {
        revision.id: tuple(exclusion.id for rule in revision.applicability for exclusion in rule.exclusions)
        for _modelo_id, revision in RegistryQueryService(compiled_bundled_authority()).iter_modelo_revisions(
            modelo_codes=("347",),
        )
    }

    assert len(exclusion_ids) >= 2
    assert set(exclusion_ids.values()) == {("m347-sii", "m347-sin-actividad", "m347-cobro-por-cuenta-de-terceros")}
