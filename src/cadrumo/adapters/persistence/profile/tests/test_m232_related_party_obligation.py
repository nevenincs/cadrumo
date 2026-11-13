"""Whether Modelo 232 is owed, derived from statements read back through the real encrypted store.

Each test states records through the guarded write path against the real pinned
authority, then derives the Orden HFP/816/2017 art. 2 outcome from what the store
returns, for every filing year in the registry's support envelope. Amounts are built
from the thresholds the registry serves. Identifiers, names and amounts are synthetic.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from .....application.aggregation.m232_registry_parameters import modelo_232_thresholds
from .....application.aggregation.m232_related_party_obligation import (
    derive_modelo_232_obligation,
    ledger_payer_fact_derivation,
)
from .....application.aggregation.m232_related_party_repository import (
    Modelo232PinnedWriteAuthority,
    Modelo232RelatedPartyRefusedError,
    Modelo232RelatedPartyWritePorts,
    state_m232_none,
    state_m232_operation,
    state_m232_turnover,
    withdraw_m232_none,
    withdraw_m232_turnover,
)
from .....application.invoices.source_resolver_ports import InvoiceSourceResolverPorts
from .....application.overview.applicability_evidence import (
    FilingYearApplicabilityEvidence,
    bind_filing_year_applicability_evidence,
    derive_ledger_payer_facts,
    loaded_invoice_source_ports,
)
from .....application.overview.calendar import build_overview_calendar
from .....application.overview.calendar_models import OverviewCalendarEntry, OverviewCalendarRange
from .....application.overview.explain import build_overview_explain
from .....application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from .....core.modelo import Modelo
from .....domain.calculations.registry.applicability import derive_modelo_applicability
from .....domain.calculations.registry.applicability_models import (
    ApplicabilityProvenance,
    ApplicabilityVerdict,
    LedgerPayerFactDerivation,
)
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.contribuyente.entity_type import EntityType
from .....domain.contribuyente.renta_codes import FiscalResidency
from .....domain.deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile
from .....domain.invoices.catalogue import InvoiceCatalogue
from .....domain.invoices.tests.catalogue_support import build_invoice_catalogue
from .....domain.modelos.m232_obligation import (
    Modelo232Ground,
    Modelo232GroundState,
    Modelo232Obligation,
    Modelo232ObligationFinding,
    Modelo232Thresholds,
)
from .....domain.modelos.m232_related_party import (
    Modelo232Direction,
    Modelo232Exclusion,
    Modelo232NoneStatement,
    Modelo232Operation,
    Modelo232OperationKind,
    Modelo232TurnoverSource,
    Modelo232TurnoverStatement,
)
from .....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...storage.runtime_repository import secure_object_repository_for_active_bucket
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..m232_related_party_records import Modelo232RelatedPartyStoreAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEARS = tuple(filing_year_envelope().years)
_MODELO = Modelo("232")
_PERIOD = "0A"
_CENT = Decimal("0.01")
_TAX_ID_ONE = "B99999991"
_TAX_ID_TWO = "B99999992"
_NAME = "Synthetic Related Holding"
_NOTE = "Synthetic note: the partners confirmed no group dealings."
_REFERENCE = "Synthetic ref: accounts filed with the registry, page 7."
_GENERAL_TYPE = "06"
_METHOD_ONE = "1A"
_METHOD_TWO = "1B"
_BUCKET_ID = "34734734-7347-4347-8347-347347347347"
_PAYER_FACT = "meets_modelo_232_related_party_grounds"


def _ports(operation: PinnedAuthorityOperation) -> Modelo232RelatedPartyWritePorts:
    return Modelo232RelatedPartyWritePorts(
        store=Modelo232RelatedPartyStoreAdapter(objects=secure_object_repository_for_active_bucket()),
        authority=Modelo232PinnedWriteAuthority(operation),
    )


def _store() -> Modelo232RelatedPartyStoreAdapter:
    return Modelo232RelatedPartyStoreAdapter(objects=secure_object_repository_for_active_bucket())


def _operation(ejercicio: int, **overrides: object) -> Modelo232Operation:
    fields: dict[str, object] = {
        "operation_id": uuid4().hex,
        "ejercicio": ejercicio,
        "operation_kind": Modelo232OperationKind.RELATED_PARTY,
        "counterparty_tax_id": _TAX_ID_ONE,
        "counterparty_name": _NAME,
        "counterparty_country": "DE",
        "tipo_vinculacion": "D",
        "tipo_operacion": _GENERAL_TYPE,
        "valuation_method": _METHOD_ONE,
        "direction": Modelo232Direction.PAGO,
        "amount_eur": Decimal("1.00"),
        "stated_at": datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC),
    }
    fields.update(overrides)
    return Modelo232Operation.model_validate(fields)


def _none(ejercicio: int) -> Modelo232NoneStatement:
    return Modelo232NoneStatement(
        statement_id=uuid4().hex,
        ejercicio=ejercicio,
        note=_NOTE,
        stated_at=datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC),
    )


def _turnover(ejercicio: int, amount: Decimal) -> Modelo232TurnoverStatement:
    return Modelo232TurnoverStatement(
        statement_id=uuid4().hex,
        ejercicio=ejercicio,
        turnover_eur=amount,
        source=Modelo232TurnoverSource.ANNUAL_ACCOUNTS,
        source_reference=_REFERENCE,
        stated_at=datetime(ejercicio, 4, 2, 9, 0, tzinfo=UTC),
    )


def _finding(operation: PinnedAuthorityOperation, ejercicio: int) -> Modelo232ObligationFinding:
    return derive_modelo_232_obligation(_store(), ejercicio, operation=operation, modelo=_MODELO, period=_PERIOD)


def _derived(operation: PinnedAuthorityOperation, ejercicio: int) -> LedgerPayerFactDerivation:
    return ledger_payer_fact_derivation(_store(), ejercicio, operation=operation, modelo=_MODELO, period=_PERIOD)


def _ground(finding: Modelo232ObligationFinding, ground: Modelo232Ground) -> Modelo232GroundState:
    return next(item.state for item in finding.grounds if item.ground is ground)


def _thresholds(operation: PinnedAuthorityOperation, ejercicio: int) -> Modelo232Thresholds:
    return modelo_232_thresholds(ejercicio, operation=operation, modelo=_MODELO, period=_PERIOD)


def _ample_turnover(operation: PinnedAuthorityOperation, ejercicio: int, total: Decimal) -> Decimal:
    return total / _thresholds(operation, ejercicio).turnover_share + Decimal(1)


def test_nothing_stated_derives_unknown_for_every_year(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        state_m232_turnover(_turnover(_YEARS[0], Decimal("1000.00")), ports=ports)
        derived = {year: _derived(operation, year) for year in _YEARS}
    assert set(derived.values()) == {LedgerPayerFactDerivation.UNKNOWN}


def test_a_none_statement_derives_no_and_withdrawing_it_derives_unknown(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        revisions = {}
        for year in _YEARS:
            revisions[year] = state_m232_none(_none(year), ports=ports)
        stated = {year: _derived(operation, year) for year in _YEARS}
        for year in _YEARS:
            withdraw_m232_none(
                year, at=datetime(year, 6, 1, tzinfo=UTC), ports=ports, expected_revision_id=revisions[year]
            )
        withdrawn = {year: _derived(operation, year) for year in _YEARS}
    assert set(stated.values()) == {LedgerPayerFactDerivation.DERIVED_NO}
    assert set(withdrawn.values()) == {LedgerPayerFactDerivation.UNKNOWN}


def test_operations_at_the_threshold_derive_no_and_one_cent_above_derive_yes(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    half = _YEARS[: len(_YEARS) // 2]
    rest = _YEARS[len(_YEARS) // 2 :]
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        for year in _YEARS:
            amount = _thresholds(operation, year).same_related_party_eur + (_CENT if year in rest else Decimal(0))
            state_m232_operation(_operation(year, amount_eur=amount), ports=ports)
            state_m232_turnover(_turnover(year, _ample_turnover(operation, year, amount)), ports=ports)
        findings = {year: _finding(operation, year) for year in _YEARS}
    for year in half:
        assert findings[year].obligation is Modelo232Obligation.NOT_OWED, year
    for year in rest:
        assert findings[year].obligation is Modelo232Obligation.OWED, year
        assert _ground(findings[year], Modelo232Ground.SAME_RELATED_PARTY) is Modelo232GroundState.MET, year


def test_income_and_payment_with_one_person_add_up_above_the_threshold(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        for year in _YEARS:
            half = _thresholds(operation, year).same_related_party_eur / 2 + _CENT
            state_m232_operation(_operation(year, amount_eur=half, direction=Modelo232Direction.INGRESO), ports=ports)
            state_m232_operation(_operation(year, amount_eur=half, direction=Modelo232Direction.PAGO), ports=ports)
            state_m232_turnover(_turnover(year, _ample_turnover(operation, year, half * 2)), ports=ports)
        findings = {year: _finding(operation, year) for year in _YEARS}
    for year in _YEARS:
        assert findings[year].obligation is Modelo232Obligation.OWED, year
        assert _ground(findings[year], Modelo232Ground.SAME_RELATED_PARTY) is Modelo232GroundState.MET, year


def test_the_same_amounts_with_two_people_stay_below_every_threshold(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        for year in _YEARS:
            half = _thresholds(operation, year).same_related_party_eur / 2 + _CENT
            state_m232_operation(_operation(year, amount_eur=half), ports=ports)
            state_m232_operation(_operation(year, amount_eur=half, counterparty_tax_id=_TAX_ID_TWO), ports=ports)
            state_m232_turnover(_turnover(year, _ample_turnover(operation, year, half * 2)), ports=ports)
        findings = {year: _finding(operation, year) for year in _YEARS}
    assert {finding.obligation for finding in findings.values()} == {Modelo232Obligation.NOT_OWED}


def test_specific_operations_of_one_type_add_up_across_counterparties(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        for year in _YEARS:
            share = _thresholds(operation, year).specific_operations_eur / 2 + _CENT
            state_m232_operation(_operation(year, amount_eur=share, specific_operation=True), ports=ports)
            state_m232_operation(
                _operation(year, amount_eur=share, specific_operation=True, counterparty_tax_id=_TAX_ID_TWO),
                ports=ports,
            )
            state_m232_turnover(_turnover(year, _ample_turnover(operation, year, share * 2)), ports=ports)
        findings = {year: _finding(operation, year) for year in _YEARS}
    for year in _YEARS:
        assert findings[year].obligation is Modelo232Obligation.OWED, year
        assert _ground(findings[year], Modelo232Ground.SPECIFIC_OPERATION_TYPE) is Modelo232GroundState.MET, year
        assert _ground(findings[year], Modelo232Ground.SAME_RELATED_PARTY) is Modelo232GroundState.NOT_MET, year


def test_an_intangibles_operation_stated_as_not_specific_is_refused_and_counts_as_specific_once_stated_so(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    year = filing_year_envelope().horizon
    thresholds = _thresholds(operation, year)
    (intangible_type,) = thresholds.always_specific_types
    amount = thresholds.specific_operations_eur + _CENT
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        with pytest.raises(Modelo232RelatedPartyRefusedError) as refused:
            state_m232_operation(
                _operation(year, tipo_operacion=intangible_type, amount_eur=amount, specific_operation=False),
                ports=ports,
            )
        stored_after_refusal = _store().load_operations(year)
        state_m232_operation(
            _operation(year, tipo_operacion=intangible_type, amount_eur=amount, specific_operation=True), ports=ports
        )
        state_m232_turnover(_turnover(year, _ample_turnover(operation, year, amount)), ports=ports)
        finding = _finding(operation, year)
    assert refused.value.reason == "specific_operation_required"
    assert stored_after_refusal == ()
    assert finding.obligation is Modelo232Obligation.OWED
    assert _ground(finding, Modelo232Ground.SPECIFIC_OPERATION_TYPE) is Modelo232GroundState.MET


def test_the_turnover_ground_is_unknown_without_a_turnover_and_follows_the_stated_one(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        small = {}
        for year in _YEARS:
            small[year] = _thresholds(operation, year).same_related_party_eur / 10
            state_m232_operation(_operation(year, amount_eur=small[year]), ports=ports)
        without = {year: (_derived(operation, year), _finding(operation, year)) for year in _YEARS}
        revisions = {}
        for year in _YEARS:
            revisions[year] = state_m232_turnover(_turnover(year, small[year] * 2 - _CENT), ports=ports)
        with_small_turnover = {year: _finding(operation, year) for year in _YEARS}
        for year in _YEARS:
            withdraw_m232_turnover(
                year, at=datetime(year, 6, 1, tzinfo=UTC), ports=ports, expected_revision_id=revisions[year]
            )
            state_m232_turnover(_turnover(year, small[year] * 2), ports=ports)
        with_large_turnover = {year: _finding(operation, year) for year in _YEARS}
    for year in _YEARS:
        derived, finding = without[year]
        assert derived is LedgerPayerFactDerivation.UNKNOWN, year
        assert _ground(finding, Modelo232Ground.TURNOVER_SHARE) is Modelo232GroundState.UNDECIDED, year
        assert with_small_turnover[year].obligation is Modelo232Obligation.OWED, year
        assert with_small_turnover[year].turnover_source is Modelo232TurnoverSource.ANNUAL_ACCOUNTS, year
        assert with_large_turnover[year].obligation is Modelo232Obligation.NOT_OWED, year


def test_an_excluded_operation_is_not_counted_but_shown(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        big = {}
        for year in _YEARS:
            big[year] = _thresholds(operation, year).same_related_party_eur * 2
            state_m232_operation(
                _operation(year, amount_eur=big[year], exclusion=Modelo232Exclusion.CONSOLIDATION_GROUP), ports=ports
            )
            state_m232_operation(_operation(year), ports=ports)
            state_m232_turnover(_turnover(year, _ample_turnover(operation, year, big[year])), ports=ports)
        findings = {year: _finding(operation, year) for year in _YEARS}
    for year in _YEARS:
        assert findings[year].obligation is Modelo232Obligation.NOT_OWED, year
        assert findings[year].counted_operations == 1, year
        assert findings[year].excluded_operations == 1, year
        assert findings[year].excluded_total_eur == big[year], year


@pytest.mark.parametrize(
    ("kind", "ground"),
    [
        (Modelo232OperationKind.TAX_HAVEN_OPERATION, Modelo232Ground.TAX_HAVEN),
        (Modelo232OperationKind.TAX_HAVEN_HOLDING, Modelo232Ground.TAX_HAVEN),
        (Modelo232OperationKind.INTANGIBLES_REDUCTION, Modelo232Ground.INTANGIBLES_REDUCTION),
    ],
)
def test_a_tax_haven_or_intangibles_reduction_record_derives_yes(
    tmp_path: Path, operation: PinnedAuthorityOperation, kind: Modelo232OperationKind, ground: Modelo232Ground
) -> None:
    related_person = kind is Modelo232OperationKind.INTANGIBLES_REDUCTION
    fields: dict[str, object] = {
        "operation_kind": kind,
        "amount_eur": _CENT,
        "counterparty_tax_id": _TAX_ID_ONE if related_person else None,
        "tipo_vinculacion": "A" if related_person else None,
        "tipo_operacion": None,
        "valuation_method": None,
        "direction": None,
    }
    if related_person:
        fields.update(parent_tax_id=_TAX_ID_TWO, parent_name=_NAME)
    if kind is Modelo232OperationKind.TAX_HAVEN_OPERATION:
        fields["description"] = "Synthetic description"
    if kind is Modelo232OperationKind.TAX_HAVEN_HOLDING:
        fields["participation_percent"] = Decimal("10.00")
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        for year in _YEARS:
            state_m232_operation(_operation(year, **fields), ports=ports)
        findings = {year: _finding(operation, year) for year in _YEARS}
        derived = {year: _derived(operation, year) for year in _YEARS}
    for year in _YEARS:
        assert findings[year].obligation is Modelo232Obligation.OWED, year
        assert _ground(findings[year], ground) is Modelo232GroundState.MET, year
        assert derived[year] is LedgerPayerFactDerivation.DERIVED_YES, year


def test_the_derivation_logs_nothing_and_names_no_counterparty(
    tmp_path: Path, operation: PinnedAuthorityOperation, caplog: pytest.LogCaptureFixture
) -> None:
    year = filing_year_envelope().horizon
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        amount = _thresholds(operation, year).same_related_party_eur + _CENT
        state_m232_operation(_operation(year, amount_eur=amount), ports=ports)
        state_m232_turnover(_turnover(year, _ample_turnover(operation, year, amount)), ports=ports)
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            finding = _finding(operation, year)
            _derived(operation, year)
    for private in (_TAX_ID_ONE, _NAME, _REFERENCE):
        assert private not in repr(finding)
    for private in (_TAX_ID_ONE, _NAME, _REFERENCE, str(amount)):
        assert private not in caplog.text
    assert not any(_TAX_ID_ONE in record.getMessage() for record in caplog.records)


def _company() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
    )


def _ledger_facts(
    operation: PinnedAuthorityOperation, year: int, *, bound: bool = True, today: date | None = None
) -> dict[str, LedgerPayerFactDerivation]:
    return derive_ledger_payer_facts(
        year,
        bucket_id=_BUCKET_ID,
        invoice_source_ports=loaded_invoice_source_ports(build_invoice_catalogue(())),
        operation=operation,
        today=date(year + 1, 3, 1) if today is None else today,
        related_party_records=_store() if bound else None,
    )


def test_a_derived_no_waits_for_the_ejercicio_to_end_but_a_derived_yes_stands(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    owed_year, none_year, below_year = _YEARS[-1], _YEARS[-2], _YEARS[-3]
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        over = _thresholds(operation, owed_year).same_related_party_eur + _CENT
        state_m232_operation(_operation(owed_year, amount_eur=over), ports=ports)
        state_m232_none(_none(none_year), ports=ports)
        below = _thresholds(operation, below_year).same_related_party_eur
        state_m232_operation(_operation(below_year, amount_eur=below), ports=ports)
        state_m232_turnover(_turnover(below_year, _ample_turnover(operation, below_year, below)), ports=ports)
        during = {
            year: _ledger_facts(operation, year, today=date(year, 6, 30))[_PAYER_FACT]
            for year in (owed_year, none_year, below_year)
        }
        after = {
            year: _ledger_facts(operation, year, today=date(year + 1, 1, 1))[_PAYER_FACT]
            for year in (owed_year, none_year, below_year)
        }
    assert during[owed_year] is LedgerPayerFactDerivation.DERIVED_YES
    assert during[none_year] is LedgerPayerFactDerivation.UNKNOWN
    assert during[below_year] is LedgerPayerFactDerivation.UNKNOWN
    assert after[owed_year] is LedgerPayerFactDerivation.DERIVED_YES
    assert after[none_year] is LedgerPayerFactDerivation.DERIVED_NO
    assert after[below_year] is LedgerPayerFactDerivation.DERIVED_NO


def _evidence(operation: PinnedAuthorityOperation) -> FilingYearApplicabilityEvidence:
    company = _company()
    return FilingYearApplicabilityEvidence(
        profile_for_year=lambda _year: company,
        ledger_payer_facts_for_year=lambda year: _ledger_facts(operation, year),
    )


def _m232_years(calendar_entries: Iterable[OverviewCalendarEntry]) -> set[int]:
    return {entry.period.filing_year for entry in calendar_entries if entry.modelo == _MODELO.value}


def test_the_232_rule_decides_a_company_from_the_stated_operations_in_the_calendar_and_explain(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    owed_year, none_year, open_year = _YEARS[-1], _YEARS[-2], _YEARS[-3]
    company = _company()
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        amount = _thresholds(operation, owed_year).same_related_party_eur + _CENT
        state_m232_operation(_operation(owed_year, amount_eur=amount), ports=ports)
        state_m232_turnover(_turnover(owed_year, _ample_turnover(operation, owed_year, amount)), ports=ports)
        state_m232_none(_none(none_year), ports=ports)
        evidence = _evidence(operation)
        unbound = FilingYearApplicabilityEvidence(
            profile_for_year=lambda _year: company,
            ledger_payer_facts_for_year=lambda year: _ledger_facts(operation, year, bound=False),
        )
        calendar_range = OverviewCalendarRange(from_date=date(open_year, 1, 1), to_date=date(owed_year + 1, 12, 31))
        today = date(owed_year + 1, 1, 15)
        calendar = build_overview_calendar(
            company, calendar_range, operation=operation, today=today, applicability_evidence=evidence
        )
        without_store = build_overview_calendar(
            company, calendar_range, operation=operation, today=today, applicability_evidence=unbound
        )
        explained = {
            year: build_overview_explain(
                company,
                modelo=_MODELO.value,
                year=year,
                today=today,
                operation=operation,
                applicability_evidence=evidence,
            )
            for year in (owed_year, none_year, open_year)
        }
        facts = {year: _ledger_facts(operation, year) for year in (owed_year, none_year, open_year)}
    assert facts[owed_year][_PAYER_FACT] is LedgerPayerFactDerivation.DERIVED_YES
    assert facts[none_year][_PAYER_FACT] is LedgerPayerFactDerivation.DERIVED_NO
    assert facts[open_year][_PAYER_FACT] is LedgerPayerFactDerivation.UNKNOWN
    assert explained[owed_year].verdict is ApplicabilityVerdict.APPLICABLE
    assert explained[none_year].verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert explained[open_year].verdict is ApplicabilityVerdict.INCOMPLETE
    assert _m232_years(calendar.entries) == {owed_year}
    assert _m232_years(without_store.entries) == set()
    assert _TAX_ID_ONE not in explained[owed_year].rationale
    assert _NAME not in explained[owed_year].rationale


def test_the_bound_evidence_reads_the_store_once_per_year_and_marks_the_verdict_ledger_derived(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    year = filing_year_envelope().horizon
    schema = operation.profile_decode_context().schema
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath((UserProfileFact(path="identity.tax_id", value="X0001500M"),)),
        setup_state=ProfileSetupState.COMPLETE,
    )
    with isolated_runtime_profile(tmp_path=tmp_path):
        ports = _ports(operation)
        state_m232_operation(
            _operation(year, operation_kind=Modelo232OperationKind.TAX_HAVEN_OPERATION, **_haven_fields()),
            ports=ports,
        )
        bound = bind_filing_year_applicability_evidence(
            record=record,
            schema=schema,
            bucket_id=_BUCKET_ID,
            invoice_source_ports=InvoiceSourceResolverPorts(
                catalogue_reader=_EmptyCatalogue(),
            ),
            operation=operation,
            today=date(year + 1, 3, 1),
            related_party_records=_store(),
        )
        unbound = bind_filing_year_applicability_evidence(
            record=record,
            schema=schema,
            bucket_id=_BUCKET_ID,
            invoice_source_ports=InvoiceSourceResolverPorts(catalogue_reader=_EmptyCatalogue()),
            operation=operation,
            today=date(year + 1, 3, 1),
        )
        derived = bound.ledger_payer_facts_for_year(year)
        absent = unbound.ledger_payer_facts_for_year(year)
        explained = build_overview_explain(
            _company(),
            modelo=_MODELO.value,
            year=year,
            today=date(year + 1, 3, 1),
            operation=operation,
            applicability_evidence=FilingYearApplicabilityEvidence(
                profile_for_year=lambda _year: _company(),
                ledger_payer_facts_for_year=bound.ledger_payer_facts_for_year,
            ),
        )
        verdict = derive_modelo_applicability(
            _company(),
            _MODELO.value,
            reference_date=date(year, 12, 31),
            operation=operation,
            ledger_payer_facts=derived,
        )
    assert derived[_PAYER_FACT] is LedgerPayerFactDerivation.DERIVED_YES
    assert _PAYER_FACT not in absent
    assert explained.verdict is ApplicabilityVerdict.APPLICABLE
    assert verdict.provenance is ApplicabilityProvenance.LEDGER_DERIVED
    assert verdict.reason == explained.rationale


def _haven_fields() -> dict[str, object]:
    return {
        "counterparty_tax_id": None,
        "tipo_vinculacion": None,
        "tipo_operacion": None,
        "valuation_method": None,
        "direction": None,
        "description": "Synthetic description",
        "amount_eur": _CENT,
    }


class _EmptyCatalogue:
    def load(self) -> InvoiceCatalogue:
        return build_invoice_catalogue(())
