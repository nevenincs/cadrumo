"""An annual withholding summary with an empty detail store must not reach filing grade.

Drives the real published Modelo 190 ejercicio-2022 revision, real ``Invoice``
records and the canonical retenedor-liability predicate. The zero percepciones
count the calculate path materialises is the state under test: it is legitimate
to CALCULATE, and never legitimate to FILE unless the taxpayer attested every
quarterly Modelo 111 window of the year as carrying no retención.

Grounded in Orden EHA/3127/2009 art. 2.1, which triggers the Modelo 190
obligation on SATISFYING the declared rentas rather than on having withheld, and
in RIRPF art. 108.1, whose declaración negativa exists only where those rentas
were satisfied. A summary with no type-2 record therefore either omits
percepciones or is not owed; neither is a filing.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import CasillaObservation
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingSeverity
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.enums import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.transactions.irpf_categories import ledger_irpf_category_catalogue
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...calculations.m111_no_retenciones import M111_NO_RETENCIONES_PROFILE_PATH
from ..preconditions import ModeloPreconditionFailure
from ..withholding_detail_gate import (
    WithholdingDetailAbsence,
    append_withholding_detail_findings,
    resolve_withholding_detail_absence,
    withholding_detail_absence_finding,
)
from .invoice_catalogue_fake import InvoiceCatalogueFake
from .transaction_catalogue_fake import TransactionCatalogueFake

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "19019019-0190-4190-8190-000000002022"
_NOW = datetime(2023, 1, 15, 9, 0, tzinfo=UTC)
_FILING_YEAR = 2022
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "0A")
_TOTAL_PERCEPCIONES: CasillaId = validated_casilla_id("decl.total-percepciones")
_ALL_QUARTERS_ATTESTED = "2022:1T,2022:2T,2022:3T,2022:4T"


def _snapshot() -> RegistrySnapshot:
    return published_snapshot("190", filing_year=_FILING_YEAR, period="0A")


def _work_unit(*, modelo: str = "190", revision_id: str) -> WorkUnit:
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=_FILING_YEAR,
            period=_PERIOD,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_FILING_YEAR,
        period=_PERIOD,
        revision_id=revision_id,
        name=f"{modelo}-{_FILING_YEAR}-0A",
        created_at=_NOW,
        updated_at=_NOW,
    )


def _revision(work_unit: WorkUnit, *, source_issues: tuple[CalculationSourceIssue, ...]) -> CalculationRevision:
    casilla_values: dict[CasillaId, Decimal] = {_TOTAL_PERCEPCIONES: Decimal("0")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
        source_transaction_ids=(),
        source_issues=source_issues,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=str(work_unit.modelo),
            revision_id=work_unit.revision_id,
            modelo_year=_FILING_YEAR,
            period="0A",
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values=casilla_values,
        observations=(
            CasillaObservation(
                casilla_id=_TOTAL_PERCEPCIONES,
                value=Decimal("0"),
                legal_refs=("rd-439-2007:art-108",),
                source_refs=("aeat-dr-190-2020",),
            ),
        ),
        created_at=_NOW,
        updated_at=_NOW,
        source_issues=source_issues,
        source_provenance=(),
        filing_instance_evidence=None,
    )


def _detail_absent_issue() -> CalculationSourceIssue:
    """The issue the calculate path persists for an empty per-perceptor window."""
    return CalculationSourceIssue(
        reason="withholding_detail_absent",
        binding_source=BindingSourceKind.WITHHOLDING,
        message="no per-perceptor-clave observations are persisted; the count is materialised as zero",
        resolver_id="withholding",
    )


def _professional_invoice(
    *,
    number: str,
    issued_at: date,
    retention_amount: str | None = "150.00",
    kind: InvoiceKind = InvoiceKind.RECEIVED,
) -> Invoice:
    subtotal = Decimal("1000.00")
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), issued_at)
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales de asesoría",
        quantity=Decimal("1"),
        unit_price=subtotal,
        subtotal=subtotal,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=subtotal * rate,
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": number,
            "issued_at": issued_at,
            "counterparty_name": "Asesoría Profesional SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": subtotal,
            "iva_total": line.iva_amount,
            "grand_total": subtotal + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": None if retention_amount is None else Decimal("0.15"),
            "retention_amount": None if retention_amount is None else Decimal(retention_amount),
        },
    )


def _quarterly_invoices() -> tuple[Invoice, ...]:
    """Four quarterly professional invoices, each with 15% practised withholding."""
    return tuple(
        _professional_invoice(number=f"F-ASESOR-2022-{index:03d}", issued_at=issued_at)
        for index, issued_at in enumerate(
            (date(2022, 3, 20), date(2022, 6, 20), date(2022, 9, 20), date(2022, 12, 20)),
            start=1,
        )
    )


def _activity_irpf_category() -> str:
    """Return the registry-declared activity-income withholding category token."""
    return next(
        descriptor.id
        for descriptor in ledger_irpf_category_catalogue()
        if descriptor.purpose == "activity_income_withholding"
    )


def _professional_payment_row(
    *,
    reference: str,
    paid_on: date,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    """Build one ledger row paying a professional, the retenedor-side renta."""
    return _payment_row(
        reference=reference,
        paid_on=paid_on,
        direction=direction,
        lifecycle_state=lifecycle_state,
        irpf_category=_activity_irpf_category(),
    )


def _uncategorised_payment_row(*, reference: str, paid_on: date) -> Transaction:
    """Build one outgoing ledger row the operator gave no IRPF category."""
    return _payment_row(
        reference=reference,
        paid_on=paid_on,
        direction=TransactionDirection.OUTGOING,
        lifecycle_state=TransactionLifecycleState.ACTIVE,
        irpf_category=None,
    )


def _payment_row(
    *,
    reference: str,
    paid_on: date,
    direction: TransactionDirection,
    lifecycle_state: TransactionLifecycleState,
    irpf_category: str | None,
) -> Transaction:
    amount = Decimal("1000.00")
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=reference,
                booked_date=paid_on,
                value_date=paid_on,
                amount=amount,
                currency="EUR",
                counterparty="Asesoría Profesional SL",
                description=f"pago asesoría {reference}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="b" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=datetime(2023, 1, 10, 12, 0, tzinfo=UTC),
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": reference},
            ),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "irpf_category": irpf_category,
            "taxable_base": amount,
            "iva_rate": None,
            "iva_amount": Decimal("0.00"),
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2023, 1, 10, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _absence(
    *,
    operation: PinnedAuthorityOperation,
    invoices: tuple[Invoice, ...],
    profile_values: dict[str, str] | None,
    modelo: str = "190",
    ledger_rows: tuple[Transaction, ...] = (),
) -> tuple[RegistrySnapshot, WorkUnit, WithholdingDetailAbsence | None]:
    snapshot = _snapshot()
    work_unit = _work_unit(modelo=modelo, revision_id=snapshot.revision.id)
    return (
        snapshot,
        work_unit,
        resolve_withholding_detail_absence(
            work_unit=work_unit,
            target=_revision(work_unit, source_issues=(_detail_absent_issue(),)),
            invoice_repository=InvoiceCatalogueFake(*invoices),
            transaction_repository=TransactionCatalogueFake(*ledger_rows),
            profile_path_values=profile_values,
            operation=operation,
        ),
    )


def test_invoice_evidence_of_practised_withholding_blocks_an_empty_summary(
    operation: PinnedAuthorityOperation,
) -> None:
    """Four received professional invoices against an empty store is a blocking disagreement."""
    snapshot, _work, absence = _absence(operation=operation, invoices=_quarterly_invoices(), profile_values=None)
    assert absence is not None

    assert len(absence.contradicting_invoice_ids) == 4
    assert absence.contradicted_by_ledger is True
    assert absence.is_filing_grade is False
    finding = withholding_detail_absence_finding(absence, snapshot=snapshot)
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == (
        "application.modelo.findings.withholding_detail_absent_against_ledger_evidence"
    )
    assert finding.message_facts["modelo"] == "190"
    assert finding.message_facts["filing_year"] == 2022
    assert finding.message_facts["source_family"] == "withholding"
    assert finding.message_facts["source_modelo"] == "111"
    assert finding.message_facts["contradicting_invoice_count"] == 4
    assert finding.message_facts["contradicting_ledger_row_count"] == 0
    assert finding.legal_refs != ()


def test_an_attestation_does_not_silence_contradicting_invoice_evidence(
    operation: PinnedAuthorityOperation,
) -> None:
    """A no-retención attestation contradicted by the invoices stays a blocking disagreement."""
    snapshot, _work, absence = _absence(
        operation=operation,
        invoices=_quarterly_invoices(),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.absence_is_proven is True
    assert absence.is_filing_grade is False
    finding = withholding_detail_absence_finding(absence, snapshot=snapshot)
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING


def test_an_outgoing_professional_payment_row_contradicts_an_attested_nil_summary(
    operation: PinnedAuthorityOperation,
) -> None:
    """A paid professional recorded only in the ledger is evidence the summary is owed.

    The obligation turns on satisfying the renta, so a payment carrying no
    invoice record of a retención still contradicts an attested nil year.
    """
    snapshot, _work, absence = _absence(
        operation=operation,
        invoices=(),
        ledger_rows=(_professional_payment_row(reference="PAGO-ASESOR-1", paid_on=date(2022, 7, 4)),),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_invoice_ids == ()
    assert len(absence.contradicting_ledger_row_ids) == 1
    assert absence.absence_is_proven is True
    assert absence.is_filing_grade is False
    finding = withholding_detail_absence_finding(absence, snapshot=snapshot)
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == (
        "application.modelo.findings.withholding_detail_absent_against_ledger_evidence"
    )
    assert finding.message_facts["contradicting_ledger_row_count"] == 1


def test_an_incoming_activity_row_is_the_taxpayers_own_income(operation: PinnedAuthorityOperation) -> None:
    """The same category incoming is the taxpayer's revenue, which no summary of theirs declares."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(),
        ledger_rows=(
            _professional_payment_row(
                reference="COBRO-CLIENTE-1",
                paid_on=date(2022, 7, 4),
                direction=TransactionDirection.INCOMING,
            ),
        ),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_ledger_row_ids == ()
    assert absence.is_filing_grade is True


def test_a_ledger_row_outside_the_declared_year_is_not_evidence(operation: PinnedAuthorityOperation) -> None:
    """The ledger comparison reads the declared period's window, not the whole catalogue."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(),
        ledger_rows=(_professional_payment_row(reference="PAGO-2023", paid_on=date(2023, 2, 1)),),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_ledger_row_ids == ()
    assert absence.is_filing_grade is True


def test_a_row_the_operator_archived_is_not_evidence(operation: PinnedAuthorityOperation) -> None:
    """A row outside the active lifecycle feeds no aggregation, so it contradicts nothing."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(),
        ledger_rows=(
            _professional_payment_row(
                reference="PAGO-ARCHIVADO",
                paid_on=date(2022, 7, 4),
                lifecycle_state=TransactionLifecycleState.ARCHIVED,
            ),
        ),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_ledger_row_ids == ()
    assert absence.is_filing_grade is True


def test_a_row_in_no_withholding_irpf_category_is_not_evidence(operation: PinnedAuthorityOperation) -> None:
    """Most outgoing rows carry no withholding category and must not fire the gate."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(),
        ledger_rows=(_uncategorised_payment_row(reference="PAGO-MATERIAL", paid_on=date(2022, 7, 4)),),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_ledger_row_ids == ()
    assert absence.is_filing_grade is True


def test_an_unattested_empty_summary_is_blocked_without_any_ledger_evidence(
    operation: PinnedAuthorityOperation,
) -> None:
    """Absence that nothing proves is refused on its own, not only when contradicted."""
    snapshot, _work, absence = _absence(operation=operation, invoices=(), profile_values=None)
    assert absence is not None

    assert absence.contradicted_by_ledger is False
    assert absence.absence_is_proven is False
    assert absence.unattested_periods == ("1T", "2T", "3T", "4T")
    finding = withholding_detail_absence_finding(absence, snapshot=snapshot)
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == "application.modelo.findings.withholding_detail_absent_unproven"
    assert finding.message_facts["unattested_periods"] == "1T|2T|3T|4T"
    assert finding.message_facts["attestation_profile_path"] == M111_NO_RETENCIONES_PROFILE_PATH


def test_a_partially_attested_year_is_still_unproven(operation: PinnedAuthorityOperation) -> None:
    """Three attested quarters leave the fourth's percepciones unaccounted for."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: "2022:1T,2022:2T,2022:3T"},
    )
    assert absence is not None

    assert absence.attested_periods == ("1T", "2T", "3T")
    assert absence.unattested_periods == ("4T",)
    assert absence.absence_is_proven is False


def test_a_fully_attested_year_with_a_clean_ledger_stays_advisory(operation: PinnedAuthorityOperation) -> None:
    """The proven-nil filer keeps a visible disclosure without a refusal."""
    snapshot, _work, absence = _absence(
        operation=operation,
        invoices=(),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.absence_is_proven is True
    assert absence.is_filing_grade is True
    finding = withholding_detail_absence_finding(absence, snapshot=snapshot)
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert finding.message_locale_key == "application.modelo.findings.withholding_detail_absent_attested"
    assert finding.message_facts["attested_periods"] == "1T|2T|3T|4T"


def test_an_issued_invoice_is_not_evidence_of_a_retenedor_liability(operation: PinnedAuthorityOperation) -> None:
    """Retención suffered on an issued invoice is a credit, never this store's liability."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(_professional_invoice(number="F-CLIENTE-1", issued_at=date(2022, 5, 5), kind=InvoiceKind.ISSUED),),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_invoice_ids == ()
    assert absence.is_filing_grade is True


def test_an_invoice_outside_the_filing_year_is_not_this_years_evidence(
    operation: PinnedAuthorityOperation,
) -> None:
    """The comparison is scoped to the year under declaration."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(_professional_invoice(number="F-ASESOR-2023-001", issued_at=date(2023, 1, 30)),),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_invoice_ids == ()


def test_a_received_invoice_declaring_no_retencion_is_not_evidence(operation: PinnedAuthorityOperation) -> None:
    """Most received invoices carry no retención at all and must not fire the gate."""
    _snap, _work, absence = _absence(
        operation=operation,
        invoices=(_professional_invoice(number="F-PROV-NO-RET", issued_at=date(2022, 4, 4), retention_amount=None),),
        profile_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
    )
    assert absence is not None

    assert absence.contradicting_invoice_ids == ()


def test_no_absence_is_classified_when_the_calculate_path_recorded_none(
    operation: PinnedAuthorityOperation,
) -> None:
    """A revision whose store held observations is outside this gate entirely."""
    snapshot = _snapshot()
    work_unit = _work_unit(revision_id=snapshot.revision.id)

    assert (
        resolve_withholding_detail_absence(
            work_unit=work_unit,
            target=_revision(work_unit, source_issues=()),
            invoice_repository=InvoiceCatalogueFake(*_quarterly_invoices()),
            transaction_repository=TransactionCatalogueFake(
                _professional_payment_row(reference="PAGO-ASESOR-1", paid_on=date(2022, 7, 4)),
            ),
            profile_path_values=None,
            operation=operation,
        )
        is None
    )


def test_a_source_modelo_without_an_attestation_channel_can_never_prove_absence(
    operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 193 folds captured Modelo 123 allocations, which carry no attestation.

    Naming the missing channel matters: an operator reading "no attestation
    covers this" would otherwise look for a profile fact that does not exist.
    The activity ledger row is NOT counted against this summary: the registry
    gives that category the activity-withholding purpose, which Modelo 123 and
    its resumen anual do not own.
    """
    snapshot = published_snapshot("193", filing_year=_FILING_YEAR, period="0A")
    work_unit = _work_unit(modelo="193", revision_id=snapshot.revision.id)
    absence = resolve_withholding_detail_absence(
        work_unit=work_unit,
        target=_revision(work_unit, source_issues=(_detail_absent_issue(),)),
        invoice_repository=InvoiceCatalogueFake(),
        transaction_repository=TransactionCatalogueFake(
            _professional_payment_row(reference="PAGO-ASESOR-1", paid_on=date(2022, 7, 4)),
        ),
        profile_path_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
        operation=operation,
    )
    assert absence is not None

    assert absence.source_modelo == "123"
    assert absence.attestation_profile_path is None
    assert absence.contradicting_ledger_row_ids == ()
    assert absence.absence_is_proven is False
    finding = withholding_detail_absence_finding(absence, snapshot=snapshot)
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == "application.modelo.findings.withholding_detail_absent_unproven"
    assert finding.message_facts["attestation_profile_path"] == "absent"


def test_the_blocking_finding_carries_a_typed_precondition_failure(operation: PinnedAuthorityOperation) -> None:
    """A refusal an operator meets must name its condition, not only its prose."""
    snapshot = _snapshot()
    work_unit = _work_unit(revision_id=snapshot.revision.id)
    target = _revision(work_unit, source_issues=(_detail_absent_issue(),))
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}

    append_withholding_detail_findings(
        work_unit=work_unit,
        target=target,
        snapshot=snapshot,
        invoice_repository=InvoiceCatalogueFake(*_quarterly_invoices()),
        transaction_repository=TransactionCatalogueFake(
            _professional_payment_row(reference="PAGO-ASESOR-1", paid_on=date(2022, 7, 4)),
        ),
        profile_path_values=None,
        operation=operation,
        findings=findings,
        failures_by_finding_id=failures,
    )

    assert len(findings) == 1
    failure = failures[id(findings[0])]
    assert failure.identity == (
        "modelo.work.verify",
        "modelo.work.verify.withholding_detail.proven",
        "modelo.work.verify.withholding_detail.contradicted",
    )
    evidence = failure.verdict.evidence[0]
    assert evidence.evidence_id == "modelo.work.verify.withholding_detail"
    assert evidence.values["contradicting_invoice_count"] == 4
    assert evidence.values["contradicting_ledger_row_count"] == 1
    assert evidence.values["absence_proven"] is False
    assert evidence.values["source_modelo"] == "111"


def test_the_advisory_finding_carries_no_precondition_failure(operation: PinnedAuthorityOperation) -> None:
    """A proven-nil disclosure is not a refusal, so it binds no recovery verdict."""
    snapshot = _snapshot()
    work_unit = _work_unit(revision_id=snapshot.revision.id)
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}

    append_withholding_detail_findings(
        work_unit=work_unit,
        target=_revision(work_unit, source_issues=(_detail_absent_issue(),)),
        snapshot=snapshot,
        invoice_repository=InvoiceCatalogueFake(),
        transaction_repository=TransactionCatalogueFake(),
        profile_path_values={M111_NO_RETENCIONES_PROFILE_PATH: _ALL_QUARTERS_ATTESTED},
        operation=operation,
        findings=findings,
        failures_by_finding_id=failures,
    )

    assert len(findings) == 1
    assert findings[0].severity is ModeloVerificationFindingSeverity.WARNING
    assert failures == {}
