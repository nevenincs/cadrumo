"""Declared, refused and unanswered payer facts through the compiled registry.

Every dated payer fact whose profile field can hold an unanswered state reads
three ways: a declared yes is APPLICABLE, a declared no is NOT_APPLICABLE with
the rule's own reason, and an unanswered question is INCOMPLETE. The Modelo 136
fact also needs its quarter set before a yes counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from cadrumo.domain.calculations.registry.applicability import (
    ApplicabilityVerdict,
    derive_modelo_applicability,
    iter_modelo_applicability_rules,
)
from cadrumo.domain.calculations.registry.applicability_payer_facts import (
    PayerFactDeclaration,
    PayerFactProjection,
    payer_fact_declaration,
    resolve_payer_fact,
    resolve_payer_fact_catalogue,
)
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactEntry
from cadrumo.domain.calculations.registry.facts.resolution import (
    GovernedFactQuery,
    MappingFactQuery,
    ResolvedGovernedFact,
    ResolvedMappingFact,
)
from cadrumo.domain.calculations.registry.governed_fact_scope import validating_governed_facts
from cadrumo.domain.calculations.registry.irpf_income_categories import require_irpf_income_category
from cadrumo.domain.calculations.registry.iva_regime_vocabulary import require_iva_regime
from cadrumo.domain.calculations.registry.schema_references import TemporalSupportEnvelope
from cadrumo.domain.contribuyente.entity_type import require_entity_type
from cadrumo.domain.deadlines.models import ModeloEnrollment, ModeloIVAProfile, TaxpayerProfile
from dev.registry.compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TODAY = date(2025, 6, 30)
_PAYER_FACT_ID = "modelo-payer-applicability-facts"
_M136_FACT = "premio_loteria_gravamen_especial_sin_retencion"
_SII_FACT = "iva_books_kept_through_sii"


@dataclass(frozen=True, slots=True)
class _Case:
    modelo: str
    field: str
    yes_extras: tuple[tuple[str, frozenset[str]], ...] = ()
    declares_iva_block: bool = False
    """Whether a yes also needs a declared IVA block, as Modelo 347's SII exclusion reads it."""


_THREE_STATE_CASES = (
    _Case("347", "third_party_transactions_above_347_threshold", declares_iva_block=True),
    _Case("720", "bienes_extranjero_above_threshold"),
    _Case("721", "monedas_virtuales_extranjero_above_threshold"),
    _Case(
        "136",
        "premio_loteria_gravamen_especial_sin_retencion",
        (("premio_loteria_gravamen_especial_trimestres", frozenset({"2025-1T"})),),
    ),
)


def _natural_person(**facts: object) -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X1234567L",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": require_iva_regime("GENERAL"),
            **facts,
        },
    )


def _iva_block(**facts: bool) -> ModeloIVAProfile:
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


def _rule_not_applicable_reason(modelo: str) -> str:
    return next(rule.not_applicable_reason for rule in iter_modelo_applicability_rules() if rule.modelo == modelo)


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("case", _THREE_STATE_CASES, ids=lambda case: case.modelo)
def test_unanswered_payer_fact_is_incomplete(case: _Case) -> None:
    result = derive_modelo_applicability(_natural_person(), case.modelo, today=_TODAY)

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "Hecho requerido para este modelo" in result.reason


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("case", _THREE_STATE_CASES, ids=lambda case: case.modelo)
def test_declared_no_is_not_applicable_with_the_rule_reason(case: _Case) -> None:
    result = derive_modelo_applicability(_natural_person(**{case.field: False}), case.modelo, today=_TODAY)

    assert result.verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert result.reason == _rule_not_applicable_reason(case.modelo)


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("case", _THREE_STATE_CASES, ids=lambda case: case.modelo)
def test_declared_yes_is_applicable(case: _Case) -> None:
    iva_block = {"iva": _iva_block()} if case.declares_iva_block else {}
    profile = _natural_person(**{case.field: True, **dict(case.yes_extras), **iva_block})

    assert derive_modelo_applicability(profile, case.modelo, today=_TODAY).verdict is ApplicabilityVerdict.APPLICABLE


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("quarters", (None, frozenset()), ids=("absent", "empty"))
def test_modelo_136_yes_without_quarters_is_incomplete_and_names_the_quarters(
    quarters: frozenset[str] | None,
) -> None:
    profile = _natural_person(
        premio_loteria_gravamen_especial_sin_retencion=True,
        premio_loteria_gravamen_especial_trimestres=quarters,
    )

    result = derive_modelo_applicability(profile, "136", today=_TODAY)

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "Periodos sin declarar: trimestres naturales en que se cobraron esos premios." in result.reason


@pytest.mark.usefixtures("governed_fact_scope")
def test_modelo_136_is_not_applicable_to_a_legal_entity_whatever_the_fact_says() -> None:
    profile = TaxpayerProfile.model_validate(
        {
            "tax_id": "B12345674",
            "entity_type": require_entity_type("legal_entity"),
            "iva_regime": require_iva_regime("GENERAL"),
            "premio_loteria_gravamen_especial_sin_retencion": True,
            "premio_loteria_gravamen_especial_trimestres": frozenset({"2025-1T"}),
        },
    )

    assert derive_modelo_applicability(profile, "136", today=_TODAY).verdict is ApplicabilityVerdict.NOT_APPLICABLE


@pytest.mark.usefixtures("governed_fact_scope")
def test_modelo_136_undeclared_is_incomplete_across_its_revisions() -> None:
    for today in (date(2022, 6, 30), date(2026, 6, 30)):
        result = derive_modelo_applicability(_natural_person(), "136", today=today)
        assert result.verdict is ApplicabilityVerdict.INCOMPLETE, today
        assert "orden-hap-70-2013:art-6" in result.legal_refs, today


@pytest.mark.usefixtures("governed_fact_scope")
def test_a_plain_boolean_payer_fact_keeps_its_two_state_reading() -> None:
    fact = resolve_payer_fact("pays_capital_income_with_retencion", effective_date=_TODAY)
    assert isinstance(fact, PayerFactProjection)
    assert fact.three_state is False

    unanswered = _natural_person(pays_capital_income_with_retencion=False)

    assert payer_fact_declaration(unanswered, fact) is PayerFactDeclaration.UNDECLARED
    assert derive_modelo_applicability(unanswered, "193", today=_TODAY).verdict is ApplicabilityVerdict.INCOMPLETE


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("effective_date", (date(2022, 6, 30), date(2025, 6, 30)))
def test_modelo_136_fact_is_dated_three_state_with_a_quarter_companion(effective_date: date) -> None:
    fact = resolve_payer_fact(_M136_FACT, effective_date=effective_date)

    assert isinstance(fact, PayerFactProjection)
    assert fact.three_state is True
    assert fact.period_companion is not None
    assert fact.period_companion.profile_key == "premio_loteria_gravamen_especial_trimestres"
    assert "orden-hap-70-2013:art-6" in fact.legal_refs


class _OverriddenPayerFacts:
    """Serve the compiled governed facts with one payer-fact entry replaced."""

    def __init__(self, key: str, value: str) -> None:
        self._authority = compiled_bundled_authority()
        self._key = key
        self._value = value

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        resolved = self._authority.resolve_governed_fact(query)
        if not (isinstance(query, MappingFactQuery) and query.fact_id == _PAYER_FACT_ID):
            return resolved
        assert isinstance(resolved, ResolvedMappingFact)
        entries = tuple(
            MappingFactEntry(key=entry.key, value=self._value) if entry.key == self._key else entry
            for entry in resolved.payload.entries
        )
        assert entries != resolved.payload.entries, self._key
        return resolved.model_copy(update={"payload": resolved.payload.model_copy(update={"entries": entries})})

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self._authority.supported_filing_years()


@pytest.mark.parametrize(
    ("key", "value", "message"),
    (
        pytest.param(
            f"payer_fact.{_M136_FACT}.period_set_key",
            "premio_loteria_trimestres_desconocidos",
            "does not declare",
            id="unknown-period-set",
        ),
        pytest.param(
            f"payer_fact.{_M136_FACT}.period_set_key",
            "premio_loteria_gravamen_especial_sin_retencion",
            "optional token-set",
            id="period-set-not-a-token-set",
        ),
        pytest.param(
            f"payer_fact.{_M136_FACT}.profile_key",
            "premio_loteria_gravamen_especial_trimestres",
            "must be a boolean profile field",
            id="yes-no-key-not-boolean",
        ),
        pytest.param(
            f"payer_fact.{_SII_FACT}.any_of_profile_keys",
            "iva.sii_enrolled|iva.not_a_profile_field",
            "does not declare",
            id="derived-unknown-key",
        ),
        pytest.param(
            f"payer_fact.{_SII_FACT}.any_of_profile_keys",
            "iva.sii_enrolled|tax_id.value",
            "not a profile section",
            id="derived-key-crosses-a-scalar",
        ),
        pytest.param(
            f"payer_fact.{_SII_FACT}.any_of_profile_keys",
            "iva.sii_enrolled|iva.refund_account",
            "must be a boolean profile field",
            id="derived-key-not-boolean",
        ),
        pytest.param(
            f"payer_fact.{_SII_FACT}.any_of_profile_keys",
            "iva.sii_enrolled",
            "fewer than two",
            id="derived-from-one-key",
        ),
    ),
)
def test_a_payer_fact_naming_an_unusable_profile_field_fails_validation(key: str, value: str, message: str) -> None:
    with (
        validating_governed_facts(_OverriddenPayerFacts(key, value)),
        pytest.raises(RegistryValidationError, match=message),
    ):
        resolve_payer_fact_catalogue(effective_date=_TODAY)


def test_the_unmodified_catalogue_resolves_through_the_same_override_seam() -> None:
    label_key = f"payer_fact.{_M136_FACT}.label"
    label = "obtuvo un premio de loterías o apuestas sujeto al gravamen especial sin retención ni ingreso a cuenta"
    with validating_governed_facts(_OverriddenPayerFacts(label_key, label + ".")):
        catalogue = resolve_payer_fact_catalogue(effective_date=_TODAY)

    assert {fact.token for fact in catalogue} >= {
        "exceeds_third_party_threshold",
        "bienes_extranjero_above_threshold",
        "monedas_virtuales_extranjero_above_threshold",
        _M136_FACT,
        "pays_capital_income_with_retencion",
    }


@pytest.mark.usefixtures("governed_fact_scope")
def test_the_sii_fact_is_a_three_state_derived_fact_over_the_iva_block() -> None:
    fact = resolve_payer_fact(_SII_FACT, effective_date=_TODAY)

    assert isinstance(fact, PayerFactProjection)
    assert fact.three_state is True
    assert {"iva.sii_enrolled", "iva.voluntary_sii_enrolled", "iva.redeme_enrolled"} <= set(fact.profile_keys)
    assert {"rd-1065-2007:art-32", "rd-1624-1992:art-62"} <= set(fact.legal_refs)


@pytest.mark.usefixtures("governed_fact_scope")
def test_the_sii_fact_reads_any_yes_unanswered_without_the_block_and_no_only_when_all_say_no() -> None:
    fact = resolve_payer_fact(_SII_FACT, effective_date=_TODAY)

    without_block = _natural_person()
    all_no = _natural_person(iva=_iva_block())
    voluntary = _natural_person(iva=_iva_block(voluntary_sii_enrolled=True))
    large_company_without_block = _natural_person(enrollment=ModeloEnrollment(large_company=True))

    assert payer_fact_declaration(without_block, fact) is PayerFactDeclaration.UNDECLARED
    assert payer_fact_declaration(all_no, fact) is PayerFactDeclaration.DECLARED_NO
    assert payer_fact_declaration(voluntary, fact) is PayerFactDeclaration.DECLARED_YES
    assert payer_fact_declaration(large_company_without_block, fact) is PayerFactDeclaration.DECLARED_YES
