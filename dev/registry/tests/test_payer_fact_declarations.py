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

from cadrumo.core.modelo import Modelo
from cadrumo.domain.calculations.registry.applicability import (
    derive_modelo_applicability,
    hydrate_applicability_rule,
    iter_modelo_applicability_rules,
)
from cadrumo.domain.calculations.registry.applicability_models import ApplicabilityVerdict
from cadrumo.domain.calculations.registry.applicability_payer_facts import (
    PayerFactDeclaration,
    PayerFactLedgerSource,
    PayerFactProjection,
    payer_fact_declaration,
    resolve_payer_fact,
    resolve_payer_fact_catalogue,
)
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as CompiledAuthority
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
from cadrumo.domain.calculations.registry.schema_revision_members import (
    ApplicabilityExclusionDefinition,
    ApplicabilityRuleDefinition,
)
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    supported_authored_exercises,
)
from cadrumo.domain.contribuyente.entity_type import require_entity_type
from cadrumo.domain.deadlines.models import ModeloEnrollment, ModeloIVAProfile, TaxpayerProfile
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.compiler.validate_applicability_section import validate_applicability_section

from .referential_integrity_support import REFERENCE_LEGAL_ID

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = filing_year_envelope().horizon
_TODAY = date(_YEAR, 6, 30)
_M136_EXERCISE_DATES = tuple(date(year, 6, 30) for year in supported_authored_exercises("136"))
_PAYER_FACT_ID = "modelo-payer-applicability-facts"
_M136_FACT = "premio_loteria_gravamen_especial_sin_retencion"
_SII_FACT = "iva_books_kept_through_sii"


@dataclass(frozen=True, slots=True)
class _Case:
    modelo: str
    field: str
    yes_extras: tuple[tuple[str, frozenset[str]], ...] = ()
    answers_the_sii_exclusion: bool = False
    """Whether a yes also needs the facts Modelo 347's SII exclusion reads answered.

    Those are the five IVA enrolments of a declared block and the
    large-company condition; every one is three-state, so an unanswered one
    leaves the exclusion undetermined and the modelo incomplete.
    """


_THREE_STATE_CASES = (
    _Case("347", "third_party_transactions_above_347_threshold", answers_the_sii_exclusion=True),
    _Case("720", "bienes_extranjero_above_threshold"),
    _Case("721", "monedas_virtuales_extranjero_above_threshold"),
    _Case(
        "136",
        "premio_loteria_gravamen_especial_sin_retencion",
        (("premio_loteria_gravamen_especial_trimestres", frozenset({f"{_YEAR}-1T"})),),
    ),
)


def _natural_person(**facts: object) -> TaxpayerProfile:
    return TaxpayerProfile.model_validate(
        {
            "tax_id": "X0001500M",
            "entity_type": require_entity_type("natural_person"),
            "irpf_income_categories": frozenset({require_irpf_income_category("actividad_economica")}),
            "iva_regime": require_iva_regime("GENERAL"),
            **facts,
        },
    )


def _iva_block(**facts: bool) -> ModeloIVAProfile:
    """An IVA block that answers every enrolment question, as a no unless overridden.

    Each enrolment is three-state, so omitting one states nothing about it and
    leaves every fact derived over the block unanswered rather than no.
    """
    return ModeloIVAProfile.model_validate(
        {
            "tax_territory": "common_regime",
            "regime_composition": "general",
            "roi_enrolled": False,
            "oss_enrolled": False,
            "group_member_enrolled": False,
            "group_dominant_entity_enrolled": False,
            "intracommunity_operations_exceed_50000_eur": False,
            "sii_enrolled": False,
            "redeme_enrolled": False,
            "cash_accounting_regime_enrolled": False,
            "voluntary_sii_enrolled": False,
            "hydrocarbon_deposit_advance_payment_deduction_entitled": False,
            **facts,
        },
    )


_NOT_A_LARGE_COMPANY = ModeloEnrollment(large_company=False)
"""The volumen de operaciones condition answered as a no.

The SII fact is derived over it as well as over the IVA block, so a stated no
on every enrolment still leaves the fact unanswered until this is stated too.
"""


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
    sii_answers = {"iva": _iva_block(), "enrollment": _NOT_A_LARGE_COMPANY} if case.answers_the_sii_exclusion else {}
    profile = _natural_person(**{case.field: True, **dict(case.yes_extras), **sii_answers})

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
            "tax_id": "B00015016",
            "entity_type": require_entity_type("legal_entity"),
            "iva_regime": require_iva_regime("GENERAL"),
            "premio_loteria_gravamen_especial_sin_retencion": True,
            "premio_loteria_gravamen_especial_trimestres": frozenset({f"{_YEAR}-1T"}),
        },
    )

    assert derive_modelo_applicability(profile, "136", today=_TODAY).verdict is ApplicabilityVerdict.NOT_APPLICABLE


@pytest.mark.usefixtures("governed_fact_scope")
def test_modelo_136_undeclared_is_incomplete_across_its_revisions() -> None:
    for today in _M136_EXERCISE_DATES:
        result = derive_modelo_applicability(_natural_person(), "136", today=today)
        assert result.verdict is ApplicabilityVerdict.INCOMPLETE, today
        assert "orden-hap-70-2013:art-6" in result.legal_refs, today


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize(
    ("answer", "declaration", "verdict"),
    (
        (None, PayerFactDeclaration.UNDECLARED, ApplicabilityVerdict.INCOMPLETE),
        (False, PayerFactDeclaration.DECLARED_NO, ApplicabilityVerdict.NOT_APPLICABLE),
        (True, PayerFactDeclaration.DECLARED_YES, ApplicabilityVerdict.APPLICABLE),
    ),
)
def test_the_capital_income_fact_reads_three_states_from_its_optional_profile_field(
    answer: bool | None,
    declaration: PayerFactDeclaration,
    verdict: ApplicabilityVerdict,
) -> None:
    """The registry declares no ``three_state`` key; it derives the reading from ``bool | None``.

    While the profile field was a plain ``bool`` defaulting to ``False`` this
    fact was two-state, so the taxpayer's own no could not be told apart from
    an unanswered question and Modelo 193 stayed INCOMPLETE either way.
    """
    fact = resolve_payer_fact("pays_capital_income_with_retencion", effective_date=_TODAY)
    assert isinstance(fact, PayerFactProjection)
    assert fact.three_state is True

    profile = _natural_person(pays_capital_income_with_retencion=answer)

    assert payer_fact_declaration(profile, fact) is declaration
    assert derive_modelo_applicability(profile, "193", today=_TODAY).verdict is verdict


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("effective_date", _M136_EXERCISE_DATES)
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
            "iva.sii_enrolled|iva.tax_territory",
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
    block_without_the_cadence_condition = _natural_person(iva=_iva_block())
    all_no = _natural_person(iva=_iva_block(), enrollment=_NOT_A_LARGE_COMPANY)
    voluntary = _natural_person(iva=_iva_block(voluntary_sii_enrolled=True))
    large_company_without_block = _natural_person(enrollment=ModeloEnrollment(large_company=True))

    assert payer_fact_declaration(without_block, fact) is PayerFactDeclaration.UNDECLARED
    # The condition is one of the fact's keys, so a complete block is not a complete answer.
    assert payer_fact_declaration(block_without_the_cadence_condition, fact) is PayerFactDeclaration.UNDECLARED
    assert payer_fact_declaration(all_no, fact) is PayerFactDeclaration.DECLARED_NO
    assert payer_fact_declaration(voluntary, fact) is PayerFactDeclaration.DECLARED_YES
    assert payer_fact_declaration(large_company_without_block, fact) is PayerFactDeclaration.DECLARED_YES


_THRESHOLD_FACT = "exceeds_third_party_threshold"
_M347_RECORD_COUNT = "modelo-347-declarante-numero-personas-entidades"


@pytest.mark.usefixtures("governed_fact_scope")
def test_the_threshold_fact_is_answered_from_the_modelo_347_declared_record_count() -> None:
    fact = resolve_payer_fact(_THRESHOLD_FACT, effective_date=_TODAY)

    assert isinstance(fact, PayerFactProjection)
    assert fact.ledger_source == PayerFactLedgerSource(
        modelo=Modelo("347"),
        period="0A",
        record_count_binding=_M347_RECORD_COUNT,
    )


def _m347_ledger_source_failures() -> list[str]:
    """Run the applicability section validator over every compiled 347 revision; keep the ledger findings."""
    authority = compiled_bundled_authority()
    failures: list[str] = []
    for revision_id, revision in authority.modelo("347").revisions.items():
        failures.extend(
            validate_applicability_section(prefix=f"347 {revision_id}", modelo="347", revision=revision, legal_refs={}),
        )
    return [failure for failure in failures if "ledger source" in failure]


def test_the_declared_ledger_source_validates_against_the_modelo_347_revisions() -> None:
    with validating_governed_facts(compiled_bundled_authority()):
        assert _m347_ledger_source_failures() == []


@pytest.mark.parametrize(
    ("key", "value", "message"),
    (
        pytest.param("ledger_record_count_binding", "modelo-347-no-such-binding", "unknown binding", id="unknown"),
        pytest.param(
            "ledger_record_count_binding",
            "modelo-347-declarante-importe-total-anual-operaciones",
            "not a distinct count",
            id="amount-not-count",
        ),
        pytest.param("ledger_modelo", "349", "not the rule's own modelo", id="foreign-modelo"),
    ),
)
def test_a_ledger_source_naming_a_binding_the_revision_cannot_count_fails_validation(
    key: str,
    value: str,
    message: str,
) -> None:
    with validating_governed_facts(_OverriddenPayerFacts(f"payer_fact.{_THRESHOLD_FACT}.{key}", value)):
        failures = _m347_ledger_source_failures()

    assert failures
    assert all(message in failure for failure in failures)


@pytest.mark.parametrize(
    ("key", "value", "message"),
    (
        pytest.param("ledger_period", "13T", "not a filing period", id="period"),
        pytest.param("ledger_modelo", "not-a-modelo", "invalid modelo", id="modelo"),
    ),
)
def test_a_malformed_ledger_source_is_refused_at_hydration(key: str, value: str, message: str) -> None:
    with (
        validating_governed_facts(_OverriddenPayerFacts(f"payer_fact.{_THRESHOLD_FACT}.{key}", value)),
        pytest.raises(RegistryValidationError, match=message),
    ):
        resolve_payer_fact_catalogue(effective_date=_TODAY)


_TWO_STATE_PROFILE_KEY = "enrollment.public_administration_budget_gt_6000000"
"""A plain boolean in a required profile section, so its ``False`` is two-state.

Every fact the bundled catalogue authors is three-state, which is why the
refusal below has to serve a fact of its own: the shape the guard exists for is
a projection whose field cannot hold an unanswered answer, not a named fact.
"""


def _declared_no_exclusion_rule(payer_fact: str) -> ApplicabilityRuleDefinition:
    return ApplicabilityRuleDefinition(
        id="m999-seed",
        applicable_entity_types=("natural_person",),
        applicable_reason="applies",
        not_applicable_reason="does not apply",
        exclusions=(
            ApplicabilityExclusionDefinition(
                id="m999-excluded",
                payer_fact=payer_fact,
                payer_fact_declared=False,
                reason="excluded",
                legal_refs=(REFERENCE_LEGAL_ID,),
            ),
        ),
        legal_refs=(REFERENCE_LEGAL_ID,),
    )


def test_an_exclusion_reading_the_declared_no_of_a_two_state_fact_is_refused_at_hydration() -> None:
    """A field that cannot hold an unanswered answer gives the exclusion nothing to read.

    Its ``False`` is both the taxpayer's no and a question nobody asked, so an
    exclusion keyed on the no would fire for every silent profile.
    """
    override = _OverriddenPayerFacts(
        f"payer_fact.{_M136_FACT}.profile_key",
        _TWO_STATE_PROFILE_KEY,
    )

    with (
        validating_governed_facts(override),
        pytest.raises(RegistryValidationError, match="cannot tell a declared no"),
    ):
        hydrate_applicability_rule(Modelo("136"), _declared_no_exclusion_rule(_M136_FACT))


def test_the_same_exclusion_over_the_authored_three_state_fact_hydrates() -> None:
    """The refusal above is the field's shape, not the exclusion's own declaration."""
    with validating_governed_facts(compiled_bundled_authority()):
        rule = hydrate_applicability_rule(Modelo("136"), _declared_no_exclusion_rule(_M136_FACT))

    assert [exclusion.id for exclusion in rule.exclusions] == ["m999-excluded"]


_SUPPORTED_YEARS = filing_year_envelope().years


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize("modelo", ("216", "296"))
def test_resident_withholding_alone_does_not_open_the_irnr_modelos(
    registry_authority: CompiledAuthority, modelo: str, year: int
) -> None:
    """An employer or payer of professional fees withholds IRPF (Modelo 111), not IRNR.

    TRLIRNR art. 31 binds the payer of income subject to IRNR, so 216 and 296 turn on
    paying non-residents, which only the taxpayer can state.
    """
    profile = _natural_person(has_employees=True, pays_professionals_with_retencion=True)

    result = derive_modelo_applicability(profile, modelo, today=date(int(year), 6, 30), authority=registry_authority)

    assert result.verdict is ApplicabilityVerdict.INCOMPLETE
    assert "trlirnr-rdleg-5-2004:art-31" in result.legal_refs


@pytest.mark.usefixtures("governed_fact_scope")
@pytest.mark.parametrize("year", _SUPPORTED_YEARS)
@pytest.mark.parametrize(
    ("modelo", "field"),
    (
        ("216", "pays_non_resident_income_with_retencion"),
        ("296", "pays_non_resident_income_with_retencion"),
        ("714", "patrimonio_declaration_threshold_met"),
    ),
)
def test_the_new_payer_facts_decide_their_modelos_in_every_supported_year(
    registry_authority: CompiledAuthority, modelo: str, field: str, year: int
) -> None:
    """Unanswered is undetermined, a no excludes and a yes obliges, in every supported year.

    Read through the authority compiled from the authored registry, so the proof does
    not wait on a publish.
    """
    today = date(int(year), 6, 30)

    def verdict(**facts: object) -> ApplicabilityVerdict:
        return derive_modelo_applicability(
            _natural_person(**facts), modelo, today=today, authority=registry_authority
        ).verdict

    assert verdict() is ApplicabilityVerdict.INCOMPLETE
    assert verdict(**{field: False}) is ApplicabilityVerdict.NOT_APPLICABLE
    assert verdict(**{field: True}) is ApplicabilityVerdict.APPLICABLE
