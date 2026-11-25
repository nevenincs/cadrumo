"""A payer fact only the taxpayer's stated records answer, declared by the registry and read by the 232 rule.

The Modelo 232 rule requires the fact that applies Orden HFP/816/2017 art. 2 to the
operations the taxpayer states. The profile holds no field for it, so a verdict
comes from a derivation over the stated records or stays incomplete. A complete
stated set that meets no ground answers no, where a ledger's silence never does.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.core.i18n.render import tr
from cadrumo.core.modelo import Modelo
from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.contribuyente.renta_codes import FiscalResidency
from cadrumo.domain.deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile

from ..applicability import derive_modelo_applicability, iter_modelo_applicability_rules
from ..applicability_models import (
    ApplicabilityProvenance,
    ApplicabilityVerdict,
    LedgerPayerFactDerivation,
    ModeloApplicability,
)
from ..applicability_payer_facts import (
    PayerFactDeclaration,
    PayerFactProjection,
    PayerFactRecordsKind,
    _catalogue,
    payer_fact_declaration,
    payer_fact_profile_keys,
    resolve_payer_fact_catalogue,
)
from ..authority import PinnedAuthorityOperation
from ..errors import RegistryValidationError
from .authored_editions import filing_year_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_PAYER_FACT = "meets_modelo_232_related_party_grounds"
_MODELO = "232"
_YEARS = tuple(filing_year_envelope().years)
_PREFIX = f"payer_fact.{_PAYER_FACT}."


def _company() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
    )


def _fact(operation: PinnedAuthorityOperation, year: int) -> PayerFactProjection:
    catalogue = resolve_payer_fact_catalogue(effective_date=date(year, 12, 31))
    return next(item for item in catalogue if item.token == _PAYER_FACT)


def _verdict(
    operation: PinnedAuthorityOperation, year: int, derivation: LedgerPayerFactDerivation | None
) -> ModeloApplicability:
    facts = {} if derivation is None else {_PAYER_FACT: derivation}
    return derive_modelo_applicability(
        _company(), _MODELO, reference_date=date(year, 12, 31), operation=operation, ledger_payer_facts=facts
    )


def test_the_catalogue_declares_the_fact_as_stated_records_with_no_profile_field(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _YEARS:
        fact = _fact(operation, year)
        assert fact.records_source is not None, year
        assert fact.records_source.kind is PayerFactRecordsKind.MODELO_232_RELATED_PARTY, year
        assert fact.records_source.modelo == Modelo(_MODELO), year
        assert fact.records_source.period == "0A", year
        assert fact.ledger_source is None, year
        assert fact.profile_keys == (), year
        assert payer_fact_profile_keys(fact) == (), year
        assert payer_fact_declaration(_company(), fact) is PayerFactDeclaration.UNDECLARED, year


def test_the_232_rule_requires_that_fact_for_every_year(operation: PinnedAuthorityOperation) -> None:
    rule = next(item for item in iter_modelo_applicability_rules(operation=operation) if item.modelo == _MODELO)
    assert isinstance(rule.required_payer_fact, PayerFactProjection)
    assert rule.required_payer_fact.token == _PAYER_FACT
    assert rule.exclusions == ()


def test_an_undecided_derivation_leaves_a_company_incomplete_and_names_the_fact(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _YEARS:
        fact = _fact(operation, year)
        label = fact.label
        for derivation in (None, LedgerPayerFactDerivation.UNKNOWN):
            verdict = _verdict(operation, year, derivation)
            assert verdict.verdict is ApplicabilityVerdict.INCOMPLETE, (year, derivation)
            assert fact.undetermined_reason is not None, year
            assert verdict.reason == fact.undetermined_reason, (year, derivation)
            assert "la mitad de tu cifra de negocios" in verdict.reason, (year, derivation)
            assert "paraísos fiscales" in verdict.reason, (year, derivation)
            assert label not in verdict.reason, (year, derivation)


def test_a_derived_yes_is_applicable_and_a_derived_no_is_not_applicable_from_the_stated_records(
    operation: PinnedAuthorityOperation,
) -> None:
    for year in _YEARS:
        owed = _verdict(operation, year, LedgerPayerFactDerivation.DERIVED_YES)
        not_owed = _verdict(operation, year, LedgerPayerFactDerivation.DERIVED_NO)
        assert owed.verdict is ApplicabilityVerdict.APPLICABLE, year
        assert owed.provenance is ApplicabilityProvenance.LEDGER_DERIVED, year
        assert owed.evidence_disagreement is None, year
        assert "Modelo 232" in owed.reason, year
        assert not_owed.verdict is ApplicabilityVerdict.NOT_APPLICABLE, year
        assert not_owed.provenance is ApplicabilityProvenance.LEDGER_DERIVED, year


def test_a_derived_no_carries_the_records_basis_and_the_derivation_notes_only_when_derived(
    operation: PinnedAuthorityOperation,
) -> None:
    note = "Synthetic detail behind the derivation."
    for year in _YEARS:
        label = _fact(operation, year).label
        reference = date(year, 12, 31)
        facts = {_PAYER_FACT: LedgerPayerFactDerivation.DERIVED_NO}
        not_owed = derive_modelo_applicability(
            _company(),
            _MODELO,
            reference_date=reference,
            operation=operation,
            ledger_payer_facts=facts,
            records_derivation_notes={_PAYER_FACT: note},
        )
        owed = derive_modelo_applicability(
            _company(),
            _MODELO,
            reference_date=reference,
            operation=operation,
            ledger_payer_facts={_PAYER_FACT: LedgerPayerFactDerivation.DERIVED_YES},
            records_derivation_notes={_PAYER_FACT: note},
        )
        unknown = derive_modelo_applicability(
            _company(),
            _MODELO,
            reference_date=reference,
            operation=operation,
            ledger_payer_facts={_PAYER_FACT: LedgerPayerFactDerivation.UNKNOWN},
            records_derivation_notes={_PAYER_FACT: note},
        )
        assert not_owed.verdict is ApplicabilityVerdict.NOT_APPLICABLE, year
        assert tr("filing.applicability.records_derived_basis_not_met", fact=label) in not_owed.reason, year
        assert tr("filing.applicability.records_derived_basis", fact=label) not in not_owed.reason, year
        assert not_owed.reason.endswith(note), year
        assert owed.reason.endswith(note), year
        assert tr("filing.applicability.records_derived_basis", fact=label) in owed.reason, year
        assert note not in unknown.reason, year


_RECORDS = {
    f"{_PREFIX}records_kind": "modelo-232-related-party",
    f"{_PREFIX}records_modelo": "232",
    f"{_PREFIX}records_period": "0A",
}
_BASE = {
    "payer_fact.order": _PAYER_FACT,
    f"{_PREFIX}value": _PAYER_FACT,
    f"{_PREFIX}label": "label",
    f"{_PREFIX}legal_refs": "orden-hfp-816-2017:art-2",
}


def test_the_grammar_accepts_a_complete_records_source_alone(operation: PinnedAuthorityOperation) -> None:
    (fact,) = _catalogue({**_BASE, **_RECORDS})
    assert fact.records_source is not None
    assert fact.profile_keys == ()


@pytest.mark.parametrize(
    "extra",
    [
        {f"{_PREFIX}profile_key": "has_employees"},
        {f"{_PREFIX}any_of_profile_keys": "has_employees|does_intracomunitario"},
        {f"{_PREFIX}period_set_key": "premio_loteria_gravamen_especial_trimestres", f"{_PREFIX}period_set_label": "x"},
        {
            f"{_PREFIX}ledger_modelo": "347",
            f"{_PREFIX}ledger_period": "0A",
            f"{_PREFIX}ledger_record_count_binding": "modelo-347-declarante-numero-personas-entidades",
        },
    ],
    ids=["profile-key", "any-of-keys", "period-set", "ledger-source"],
)
def test_the_grammar_refuses_a_records_source_beside_another_answer(
    operation: PinnedAuthorityOperation, extra: dict[str, str]
) -> None:
    with pytest.raises(RegistryValidationError):
        _catalogue({**_BASE, **_RECORDS, **extra})


@pytest.mark.parametrize(
    ("override", "missing"),
    [
        ({f"{_PREFIX}records_kind": "unknown-store"}, None),
        ({f"{_PREFIX}records_modelo": "not-a-modelo"}, None),
        ({f"{_PREFIX}records_period": "not-a-period"}, None),
        ({}, "records_period"),
        ({}, "records_kind"),
    ],
    ids=["kind", "modelo", "period", "missing-period", "missing-kind"],
)
def test_the_grammar_refuses_an_unknown_or_incomplete_records_source(
    operation: PinnedAuthorityOperation, override: dict[str, str], missing: str | None
) -> None:
    records = {key: value for key, value in _RECORDS.items() if missing is None or not key.endswith(missing)}
    with pytest.raises(RegistryValidationError):
        _catalogue({**_BASE, **records, **override})
