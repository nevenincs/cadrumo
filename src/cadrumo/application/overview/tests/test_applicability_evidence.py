"""The per-year ledger and profile evidence Modelo 347 applicability is decided on.

The ledger signal is read off the real invoice source resolver over synthetic
in-memory catalogues, against the published authority: the same observations,
per-counterparty-and-direction threshold and declarado record count the
filing itself is built from. RGAT art. 33.1 relates a counterparty whose
operations "hayan superado la cifra de 3.005,06 euros durante el año natural
correspondiente", computing "de forma separada las entregas y las
adquisiciones de bienes y servicios".
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.modelo import Modelo
from ....domain.calculations.registry.applicability import (
    ApplicabilityProvenance,
    ApplicabilityVerdict,
    LedgerPayerFactDerivation,
    ModeloApplicability,
    derive_modelo_applicability,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.third_party_declaration_roles import require_third_party_declaration_role
from ....domain.contribuyente.entity_type import EntityType
from ....domain.deadlines.models import (
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine, derive_invoice_id
from ....domain.iva.classification import InvoiceKind
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...invoices.source_resolver_ports import InvoiceSourcePersistenceError, InvoiceSourceResolverPorts
from ...user_profile.projections import projection_for_taxpayer
from ..agenda import build_overview_agenda
from ..applicability_evidence import (
    FilingYearApplicabilityEvidence,
    bind_filing_year_applicability_evidence,
    derive_ledger_payer_facts,
)
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendarEntry, OverviewCalendarRange

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "34734734-7347-4347-8347-347347347347"
_THRESHOLD_FACT = "exceeds_third_party_threshold"
_FILING_YEAR = 2025
_AFTER_YEAR_END = date(2026, 3, 1)
_DISAGREEMENT_WARNING = "applicability.evidence_disagreement"


class _CatalogueReader:
    def __init__(self, catalogue: InvoiceCatalogue) -> None:
        self._catalogue = catalogue

    def load(self) -> InvoiceCatalogue:
        return self._catalogue


class _DegradedReader:
    def load(self) -> InvoiceCatalogue:
        raise InvoiceSourcePersistenceError("invoice_catalogue_load")


def _invoice(
    *,
    kind: InvoiceKind,
    number: str,
    tax_id: str,
    base: str,
    iva: str,
    issued_at: date = date(_FILING_YEAR, 6, 10),
    currency: str = "EUR",
) -> Invoice:
    """A domestic invoice at 21 % whose gross total is the amount Modelo 347 sums."""
    base_total = Decimal(base)
    iva_total = Decimal(iva)
    grand_total = base_total + iva_total
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=issued_at,
            counterparty_tax_id=tax_id,
            currency=currency,
            grand_total=grand_total,
        ),
        bucket_id=_BUCKET_ID,
        kind=kind,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_name="CONTRAPARTE SL",
        counterparty_tax_id=tax_id,
        counterparty_country="ES",
        base_total=base_total,
        iva_total=iva_total,
        grand_total=grand_total,
        currency=currency,
        lines=(
            InvoiceLine(
                description="Operacion interior",
                quantity=Decimal("1"),
                unit_price=base_total,
                subtotal=base_total,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva_total,
            ),
        ),
        payment_status=PaymentStatus.PAID,
    )


def _ports(*invoices: Invoice) -> InvoiceSourceResolverPorts:
    return InvoiceSourceResolverPorts(catalogue_reader=_CatalogueReader(build_invoice_catalogue(invoices)))


def _derive(
    operation: PinnedAuthorityOperation,
    *invoices: Invoice,
    today: date = _AFTER_YEAR_END,
) -> LedgerPayerFactDerivation:
    derived = derive_ledger_payer_facts(
        _FILING_YEAR,
        bucket_id=_BUCKET_ID,
        invoice_source_ports=_ports(*invoices),
        operation=operation,
        today=today,
    )
    return derived[_THRESHOLD_FACT]


# 2.483,53 + 21 % = 3.005,07; 2.483,52 + 21 % = 3.005,06; 1.652,89 + 21 % = 2.000,00.
def _sale(number: str, *, base: str = "2483.53", iva: str = "521.54", tax_id: str = "B87654323") -> Invoice:
    return _invoice(kind=InvoiceKind.ISSUED, number=number, tax_id=tax_id, base=base, iva=iva)


def test_counterparty_one_cent_above_the_floor_derives_yes(operation: PinnedAuthorityOperation) -> None:
    assert _derive(operation, _sale("V-1")) is LedgerPayerFactDerivation.DERIVED_YES


def test_counterparty_exactly_on_the_floor_derives_no(operation: PinnedAuthorityOperation) -> None:
    """The floor must be exceeded ("hayan superado"), so 3.005,06 itself is not declarable."""
    assert _derive(operation, _sale("V-1", base="2483.52")) is LedgerPayerFactDerivation.DERIVED_NO


def test_entregas_and_adquisiciones_are_judged_apart(operation: PinnedAuthorityOperation) -> None:
    """2.000 sold to and 2.000 bought from one counterparty is 4.000 combined but below each floor."""
    sale = _sale("V-1", base="1652.89", iva="347.11")
    purchase = _invoice(
        kind=InvoiceKind.RECEIVED,
        number="P-1",
        tax_id="B87654323",
        base="1652.89",
        iva="347.11",
    )
    assert _derive(operation, sale, purchase) is LedgerPayerFactDerivation.DERIVED_NO


def test_a_year_not_yet_ended_never_derives_no(operation: PinnedAuthorityOperation) -> None:
    below = _sale("V-1", base="2483.52")
    assert _derive(operation, below, today=date(_FILING_YEAR, 7, 1)) is LedgerPayerFactDerivation.UNKNOWN
    assert _derive(operation, _sale("V-2"), today=date(_FILING_YEAR, 7, 1)) is LedgerPayerFactDerivation.DERIVED_YES


def test_an_empty_ledger_is_not_evidence_of_no_operations(operation: PinnedAuthorityOperation) -> None:
    assert _derive(operation) is LedgerPayerFactDerivation.UNKNOWN


def test_a_withheld_operation_makes_a_zero_count_unknown(operation: PinnedAuthorityOperation) -> None:
    """A foreign invoice with no euro value is withheld with a diagnostic, so the ledger is incomplete."""
    below = _sale("V-1", base="2483.52")
    foreign = _invoice(
        kind=InvoiceKind.ISSUED,
        number="V-USD",
        tax_id="B12345674",
        base="100.00",
        iva="21.00",
        currency="USD",
    )
    assert _derive(operation, below, foreign) is LedgerPayerFactDerivation.UNKNOWN


def test_an_unreadable_catalogue_derives_unknown(operation: PinnedAuthorityOperation) -> None:
    derived = derive_ledger_payer_facts(
        _FILING_YEAR,
        bucket_id=_BUCKET_ID,
        invoice_source_ports=InvoiceSourceResolverPorts(catalogue_reader=_DegradedReader()),
        operation=operation,
        today=_AFTER_YEAR_END,
    )
    assert derived == {_THRESHOLD_FACT: LedgerPayerFactDerivation.UNKNOWN}


def _iva_outside_sii() -> ModeloIVAProfile:
    return ModeloIVAProfile(
        tax_territory=M303TaxTerritory.from_registry("COMMON_REGIME"),
        regime_composition=M303RegimeComposition.from_registry("GENERAL"),
        redeme_enrolled=False,
        cash_accounting_regime_enrolled=False,
        voluntary_sii_enrolled=False,
        hydrocarbon_deposit_advance_payment_deduction_entitled=False,
    )


def _autonomo(*, threshold: bool | None, collector: bool = False, sii: bool = False) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_normal"),
        iva_regime=IVARegime("GENERAL"),
        iva=_iva_outside_sii().model_copy(update={"voluntary_sii_enrolled": sii}),
        third_party_transactions_above_347_threshold=threshold,
        declaration_roles=(
            frozenset({require_third_party_declaration_role("third_party_fee_collector")}) if collector else frozenset()
        ),
    )


def _verdict(
    operation: PinnedAuthorityOperation,
    profile: TaxpayerProfile,
    derivation: LedgerPayerFactDerivation | None,
) -> ModeloApplicability:
    ledger = dict[str, LedgerPayerFactDerivation]()
    if derivation is not None:
        ledger[_THRESHOLD_FACT] = derivation
    return derive_modelo_applicability(
        profile,
        "347",
        today=_AFTER_YEAR_END,
        operation=operation,
        ledger_payer_facts=ledger,
    )


def test_ledger_yes_with_an_unanswered_profile_is_applicable_as_a_local_derivation(
    operation: PinnedAuthorityOperation,
) -> None:
    unanswered = _autonomo(threshold=None)
    assert _verdict(operation, unanswered, None).verdict is ApplicabilityVerdict.INCOMPLETE

    derived = _verdict(operation, unanswered, LedgerPayerFactDerivation.DERIVED_YES)

    assert derived.verdict is ApplicabilityVerdict.APPLICABLE
    assert derived.provenance is ApplicabilityProvenance.LEDGER_DERIVED
    assert derived.evidence_disagreement is None


def test_ledger_yes_against_a_profile_no_keeps_the_obligation_and_the_disagreement(
    operation: PinnedAuthorityOperation,
) -> None:
    declared_no = _autonomo(threshold=False)
    assert _verdict(operation, declared_no, None).verdict is ApplicabilityVerdict.NOT_APPLICABLE

    contradicted = _verdict(operation, declared_no, LedgerPayerFactDerivation.DERIVED_YES)

    assert contradicted.verdict is ApplicabilityVerdict.APPLICABLE
    assert contradicted.provenance is ApplicabilityProvenance.LEDGER_DERIVED
    disagreement = contradicted.evidence_disagreement
    assert disagreement is not None
    assert disagreement.payer_fact == _THRESHOLD_FACT
    assert disagreement.ledger_derivation is LedgerPayerFactDerivation.DERIVED_YES


def test_ledger_no_against_a_profile_yes_keeps_the_obligation_and_the_disagreement(
    operation: PinnedAuthorityOperation,
) -> None:
    verdict = _verdict(operation, _autonomo(threshold=True), LedgerPayerFactDerivation.DERIVED_NO)

    assert verdict.verdict is ApplicabilityVerdict.APPLICABLE
    assert verdict.provenance is ApplicabilityProvenance.PROFILE_DECLARED
    assert verdict.evidence_disagreement is not None


@pytest.mark.parametrize("derivation", [LedgerPayerFactDerivation.DERIVED_NO, LedgerPayerFactDerivation.UNKNOWN])
def test_a_ledger_that_does_not_show_the_fact_never_answers_an_unanswered_profile(
    operation: PinnedAuthorityOperation,
    derivation: LedgerPayerFactDerivation,
) -> None:
    verdict = _verdict(operation, _autonomo(threshold=None), derivation)

    assert verdict.verdict is ApplicabilityVerdict.INCOMPLETE


def test_the_sii_exclusion_still_decides_against_a_ledger_yes(operation: PinnedAuthorityOperation) -> None:
    verdict = _verdict(operation, _autonomo(threshold=None, sii=True), LedgerPayerFactDerivation.DERIVED_YES)

    assert verdict.verdict is ApplicabilityVerdict.NOT_APPLICABLE


def test_a_conclusive_ledger_settles_the_collector_floor_a_profile_no_cannot(
    operation: PinnedAuthorityOperation,
) -> None:
    """RGAT art. 32.c gives fee collectors a 300,51 floor the profile question does not ask about.

    A collector's "no" stays undetermined on its own; the ledger, whose
    buckets include clave C at its own floor, settles it either way.
    """
    collector_no = _autonomo(threshold=False, collector=True)

    assert _verdict(operation, collector_no, None).verdict is ApplicabilityVerdict.INCOMPLETE
    assert (
        _verdict(operation, collector_no, LedgerPayerFactDerivation.UNKNOWN).verdict is ApplicabilityVerdict.INCOMPLETE
    )
    assert (
        _verdict(operation, collector_no, LedgerPayerFactDerivation.DERIVED_NO).verdict
        is ApplicabilityVerdict.NOT_APPLICABLE
    )
    exceeded = _verdict(operation, collector_no, LedgerPayerFactDerivation.DERIVED_YES)
    assert exceeded.verdict is ApplicabilityVerdict.APPLICABLE
    assert exceeded.evidence_disagreement is not None


_RANGE_2026 = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))


def _fixed_evidence(
    profile: TaxpayerProfile,
    derivation: LedgerPayerFactDerivation,
) -> FilingYearApplicabilityEvidence:
    return FilingYearApplicabilityEvidence(
        profile_for_year=lambda _year: profile,
        ledger_payer_facts_for_year=lambda _year: {_THRESHOLD_FACT: derivation},
    )


def _m347_years(calendar_entries: Iterable[OverviewCalendarEntry]) -> set[int]:
    return {entry.period.filing_year for entry in calendar_entries if entry.modelo == Modelo("347").value}


def test_calendar_keeps_a_contradicted_row_and_warns(operation: PinnedAuthorityOperation) -> None:
    declared_no = _autonomo(threshold=False)

    plain = build_overview_calendar(declared_no, _RANGE_2026, operation=operation, today=_AFTER_YEAR_END)
    calendar = build_overview_calendar(
        declared_no,
        _RANGE_2026,
        operation=operation,
        today=_AFTER_YEAR_END,
        applicability_evidence=_fixed_evidence(declared_no, LedgerPayerFactDerivation.DERIVED_YES),
    )

    assert _FILING_YEAR not in _m347_years(plain.entries)
    assert _FILING_YEAR in _m347_years(calendar.entries)
    warnings = [warning for warning in calendar.warnings if warning.code == _DISAGREEMENT_WARNING]
    assert len(warnings) == 1
    assert warnings[0].affected_modelos == ("347",)
    assert not any(warning.code == _DISAGREEMENT_WARNING for warning in plain.warnings)


def test_calendar_shows_a_ledger_derived_row_for_an_unanswered_profile(operation: PinnedAuthorityOperation) -> None:
    unanswered = _autonomo(threshold=None)

    calendar = build_overview_calendar(
        unanswered,
        _RANGE_2026,
        operation=operation,
        today=_AFTER_YEAR_END,
        applicability_evidence=_fixed_evidence(unanswered, LedgerPayerFactDerivation.DERIVED_YES),
    )

    assert _FILING_YEAR in _m347_years(calendar.entries)
    assert not any(warning.code == _DISAGREEMENT_WARNING for warning in calendar.warnings)


def test_calendar_advises_rather_than_excludes_on_an_incomplete_ledger(operation: PinnedAuthorityOperation) -> None:
    unanswered = _autonomo(threshold=None)

    calendar = build_overview_calendar(
        unanswered,
        _RANGE_2026,
        operation=operation,
        today=_AFTER_YEAR_END,
        applicability_evidence=_fixed_evidence(unanswered, LedgerPayerFactDerivation.UNKNOWN),
    )

    assert _FILING_YEAR not in _m347_years(calendar.entries)
    assert "347" in calendar.coverage.advised_modelos
    assert "347" not in calendar.coverage.confidently_excluded


def test_calendar_and_agenda_decide_the_same_ledger_derived_obligation(operation: PinnedAuthorityOperation) -> None:
    unanswered = _autonomo(threshold=None)
    evidence = _fixed_evidence(unanswered, LedgerPayerFactDerivation.DERIVED_YES)
    as_of = date(2026, 2, 20)

    calendar = build_overview_calendar(
        unanswered,
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 3, 31)),
        operation=operation,
        today=as_of,
        applicability_evidence=evidence,
    )
    agenda = build_overview_agenda(unanswered, as_of=as_of, operation=operation, applicability_evidence=evidence)
    agenda_rows = (*agenda.due_today, *agenda.due_soon, *agenda.overdue)

    assert _FILING_YEAR in _m347_years(calendar.entries)
    assert _FILING_YEAR in _m347_years(agenda_rows)


_AUTONOMO_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="X1234567L"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def test_calendar_reads_the_threshold_answer_for_each_filing_year(operation: PinnedAuthorityOperation) -> None:
    """A profile answering no for 2024 and yes for 2025 owes only the 2025 declaration."""
    threshold = "obligations.third_party_transactions_above_347_threshold"
    record = create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=_BUCKET_ID,
        facts=(
            *_AUTONOMO_FACTS,
            UserProfileFact(path=threshold, value=False, valid_from=date(2024, 1, 1), valid_to=date(2024, 12, 31)),
            UserProfileFact(path=threshold, value=True, valid_from=date(2025, 1, 1)),
        ),
        setup_state=ProfileSetupState.COMPLETE,
    )
    schema = operation.profile_decode_context().schema
    evidence = bind_filing_year_applicability_evidence(
        record=record,
        schema=schema,
        bucket_id=_BUCKET_ID,
        invoice_source_ports=_ports(),
        operation=operation,
        today=_AFTER_YEAR_END,
    )
    years = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2026, 12, 31))
    current = projection_for_taxpayer(record, schema=schema)

    undated = build_overview_calendar(current, years, operation=operation, today=_AFTER_YEAR_END)
    per_year = build_overview_calendar(
        current,
        years,
        operation=operation,
        today=_AFTER_YEAR_END,
        applicability_evidence=evidence,
    )

    assert _m347_years(undated.entries) == {2024, 2025}
    assert _m347_years(per_year.entries) == {2025}
