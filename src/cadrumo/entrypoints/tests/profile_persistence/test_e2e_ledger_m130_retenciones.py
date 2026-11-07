"""E2E: issued invoices with a stated retención reach Modelo 130 casilla 06 at filing grade.

A suffered retención is credited in the period of its income (RIRPF art. 79),
and the declared criterion places each row in its period (RIRPF art. 7), so the
casilla 06 binding is filing grade. This module drives it through the live
bucket-aggregation calculation over an encrypted profile store and the real
verification action, then reads the persisted revision back through the real
calculation-note gate, which export and local filing call, and the real
work-form service, which the TUI and MCP read:

* the calculation succeeds, casilla 06 carries the invoices' stated retención,
  and the revision carries no capped-value note;
* the revision is stamped with the current screen, and calculating the same
  inputs again addresses the same content-addressed revision;
* the form withholds nothing on box 06, and the gate admits check, export and
  local filing; verification passes the gate and raises no blocker on box 06;
* the review workbook shows casilla 06 with no note beside it;
* a revision recorded as filed before screen stamps existed, holding a figure
  in casilla 06, is no longer refused its export;
* a quarter whose receipts carry no retención states casilla 06 as zero with
  no note, and passes the gate.

Every figure is invoice arithmetic worked out here, with synthetic data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.calculation_note_gate import (
    ModeloCalculationBlockedError,
    calculation_filed_before_grade_cap,
    require_work_unit_calculation_unblocked,
)
from cadrumo.application.modelo.calculation_notes import (
    FILED_BEFORE_GRADE_CAP_REASON,
)
from cadrumo.application.modelo.calculation_screen import calculation_screen_is_current, calculation_screen_stamp
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_form_service import load_modelo_work_form
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.storage.calc_sheets.review_labels import ReviewWorkbookLabels
from cadrumo.application.storage.calc_sheets.review_workbook import build_review_workbook
from cadrumo.application.storage.calc_sheets.workbook_cells import plan_value_blocks
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.contribuyente.entity_type import EntityType
from cadrumo.domain.deadlines.models import IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from cadrumo.domain.invoices.models import Invoice, InvoiceLine
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.schema import InvoiceKind, IvaCategory
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.verification_report import ModeloVerificationFindingSeverity, VerificationReport
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.transactions.service import link_invoice
from cadrumo.domain.user_profile.tests.imputation_criterion_facts import cash_criterion_facts
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
)
from cadrumo.entrypoints.calculation_review_snapshot_composition import load_calculation_review_snapshot
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
    build_test_verification_repository_bundle,
)

from .general_iva_profile_facts_support import renta_single_taxpayer_facts

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

__all__ = ["secure_objects"]

_BUCKET_ID: Final = "13010000-0000-4000-8000-000000000130"
_TAX_ID: Final = "12345678Z"
_T0: Final = datetime(2026, 4, 6, 10, 0, tzinfo=UTC)
_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()

_WITHHELD_YEAR: Final = 2026
_ZERO_YEAR: Final = 2025
_QUARTER: Final = "1T"
_M130_REVISION: Final = "2019-y-siguientes"
_RETENCIONES_BOX: CasillaId = validated_casilla_id("06")
_REASON: Final = "advisory_binding_value"

# Hand-derived invoice arithmetic at the general 15 % professional rate (RIRPF art. 95.1)
# and 21 % IVA: 1.000,00 leaves 150,00 withheld and 1.000,00 + 210,00 - 150,00 = 1.060,00 paid;
# 2.400,00 leaves 360,00 withheld and 2.400,00 + 504,00 - 360,00 = 2.544,00 paid.
_INVOICES: Final[tuple[tuple[str, Decimal, Decimal, Decimal], ...]] = (
    ("F-2026-001", Decimal("1000.00"), Decimal("150.00"), Decimal("1060.00")),
    ("F-2026-002", Decimal("2400.00"), Decimal("360.00"), Decimal("2544.00")),
)
# Hand-derived: 150,00 + 360,00.
_STATED_RETENCION: Final = Decimal("510.00")
# Hand-derived: a 2.000,00 receipt with its 420,00 IVA paid in full carries no retención.
_UNWITHHELD_BASE: Final = Decimal("2000.00")
_UNWITHHELD_IVA: Final = Decimal("420.00")

_ZERO_MANUAL_INPUTS: dict[CasillaId, Decimal] = {
    validated_casilla_id(casilla): Decimal("0") for casilla in ("16", "18")
}
_PRIOR_BINDINGS: dict[BindingId, Decimal] = {
    "irpf.previous_year_economic_activity_net_income": Decimal("50000"),
}


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _seed_taxpayer_profile() -> None:
    seed_test_profile_record(
        create_user_profile_record(
            context=profile_creation_context_for_test(),
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                    UserProfileFact(path="identity.name", value="Withheld"),
                    UserProfileFact(path="identity.surnames", value="Retencion Tester"),
                    UserProfileFact(path="activities.description", value="design services"),
                    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
                    *renta_single_taxpayer_facts(birth_date=date(1980, 3, 15)),
                    *cash_criterion_facts(_WITHHELD_YEAR, _ZERO_YEAR),
                )
            ),
            created_at=_T0,
            updated_at=_T0,
        )
    )


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        entity_type=EntityType.from_registry("natural_person"),
        irpf_income_categories=frozenset({IrpfIncomeCategory.from_registry("actividad_economica")}),
        irpf_estimation_regime=IrpfEstimationRegime.from_registry("directa_normal"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        pays_rent_with_retencion=False,
        pays_capital_income_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=False,
    )


def _receipt(
    provider_id: str,
    *,
    value_date: date,
    cash: Decimal,
    taxable_base: Decimal | None = None,
    iva: Decimal | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=value_date,
                value_date=value_date,
                amount=cash,
                currency="EUR",
                counterparty="Cliente SL",
                description="cobro factura",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=_T0,
                    provider_name="CSV provider",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "taxable_base": taxable_base,
            "iva_rate": None if iva is None else Decimal("0.21"),
            "iva_amount": iva,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _issued_invoice(
    number: str,
    *,
    base: Decimal,
    retencion: Decimal,
    linked: str | None,
    issued_at: date | None = None,
) -> Invoice:
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(_WITHHELD_YEAR, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=base * rate,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": date(_WITHHELD_YEAR, 2, 10) if issued_at is None else issued_at,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": _BUCKET_ID,
            "base_total": base,
            "iva_total": line.iva_amount,
            "grand_total": base + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.15"),
            "retention_amount": retencion,
            "linked_transaction_ids": () if linked is None else (linked,),
        },
    )


def _persist_ledger(secure_objects: SecureObjectRepository, *, older: tuple[Invoice, ...] = ()) -> None:
    """The capped quarter's two invoiced receipts, and an earlier year's receipt paid in full."""
    receipts = [_receipt(number, value_date=date(_WITHHELD_YEAR, 2, 10), cash=cash) for number, _, _, cash in _INVOICES]
    unwithheld = _receipt(
        "cobro-integro",
        value_date=date(_ZERO_YEAR, 2, 10),
        cash=_UNWITHHELD_BASE + _UNWITHHELD_IVA,
        taxable_base=_UNWITHHELD_BASE,
        iva=_UNWITHHELD_IVA,
    )
    catalogue = TransactionCatalogue.from_transactions((*receipts, unwithheld))
    invoices = tuple(
        _issued_invoice(number, base=base, retencion=retencion, linked=receipt.transaction_id)
        for (number, base, retencion, _), receipt in zip(_INVOICES, receipts, strict=True)
    )
    for invoice, receipt in zip(invoices, receipts, strict=True):
        catalogue = link_invoice(catalogue, receipt.transaction_id, invoice.invoice_id)
    TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(catalogue)
    InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(
        build_invoice_catalogue((*invoices, *older)),
    )


def _work_unit(secure_objects: SecureObjectRepository, year: int, operation: PinnedAuthorityOperation) -> WorkUnit:
    return create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=year,
        period=Period.from_year_and_code(year, _QUARTER),
        revision_id=_M130_REVISION,
        ports=WorkLifecyclePorts(
            work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
            bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        ),
        operation=operation,
        clock=_T0,
    )


def _calculate(work_unit: WorkUnit, operation: PinnedAuthorityOperation) -> CalculationRevision:
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=_BUCKET_ID, operation=operation),
        casilla_inputs=_ZERO_MANUAL_INPUTS,
        binding_values=_PRIOR_BINDINGS,
        clock=_T0,
    ).revision


def _gate_reasons(work_unit: WorkUnit, revision: CalculationRevision, operation: PinnedAuthorityOperation):
    """The reasons the gate refuses each of check, export and recording with; empty where it admits."""
    reasons: dict[str, str] = {}
    for action in ("verify", "export", "file"):
        try:
            require_work_unit_calculation_unblocked(
                work_unit=work_unit, revision=revision, action=action, operation=operation
            )
        except ModeloCalculationBlockedError as refused:
            reasons[action] = str((refused.context or {})["reasons"])
    return reasons


def _form(secure_objects: SecureObjectRepository, year: int, operation: PinnedAuthorityOperation):
    return load_modelo_work_form(
        _BUCKET_ID,
        ModeloCode("130"),
        year,
        Period.from_year_and_code(year, _QUARTER),
        operation=operation,
        work_unit_repository=WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        verification_repository=VerificationReportCatalogueRepository(objects=secure_objects),
        admission=None,
        language=OutputLanguage.EN,
    )


_NOTE_COLUMN: Final = "M"
"""The results tab's calculation-note column, after amount, box, row, values, units, sources and references."""


def _review_notes_by_box(
    revision: CalculationRevision, language: OutputLanguage, operation: PinnedAuthorityOperation
) -> dict[str, object]:
    """The review workbook's note beside each saved box, from the persisted revision through the real composition."""
    snapshot = load_calculation_review_snapshot(
        revision.calculation_revision_id, profile_id=UUID(_BUCKET_ID), operation=operation
    )
    plan = build_review_workbook(
        snapshot, publication_id=UUID(int=7), exported_at=_T0, label=ReviewWorkbookLabels(language)
    )
    cells = {
        address.qualified(): value for block in plan_value_blocks(plan) for address, value in block.addressed_values()
    }
    rows = {
        int(address.removeprefix("'Cálculos'!B")): value
        for address, value in cells.items()
        if address.startswith("'Cálculos'!B") and address.removeprefix("'Cálculos'!B").isdigit()
    }
    return {str(box): cells.get(f"'Cálculos'!{_NOTE_COLUMN}{row}") for row, box in rows.items() if row >= 5}


def _verify(revision: CalculationRevision, operation: PinnedAuthorityOperation) -> VerificationReport:
    return verify_modelo_revision_with_preconditions(
        revision.calculation_revision_id,
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_test_verification_repository_bundle(),
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        actor="operator",
        workflow_profile=_workflow_profile(),
        clock=_T0,
        operation=operation,
    ).report


def test_stated_retenciones_reach_casilla_06_at_filing_grade(secure_objects: SecureObjectRepository) -> None:
    _seed_taxpayer_profile()
    _persist_ledger(secure_objects)

    with bundled_indexed_authority().operation() as operation:
        work_unit = _work_unit(secure_objects, _WITHHELD_YEAR, operation)
        revision = _calculate(work_unit, operation)

        assert Decimal(revision.casilla_values[_RETENCIONES_BOX]) == _STATED_RETENCION
        assert not [issue for issue in revision.source_issues if issue.reason == _REASON]
        snapshot = operation.snapshot("130", filing_year=_WITHHELD_YEAR, period=_QUARTER)
        assert revision.screen_stamp is not None
        assert calculation_screen_is_current(revision, calculation_screen_stamp(snapshot, operation=operation))
        # The same inputs address the same content-addressed revision.
        assert _calculate(work_unit, operation).calculation_revision_id == revision.calculation_revision_id

        load = _form(secure_objects, _WITHHELD_YEAR, operation)
        assert not [item for item in load.form.calculation_notes if item.withholds_filing]
        assert _gate_reasons(work_unit, revision, operation) == {}

        report = _verify(revision, operation)
        assert not [
            finding
            for finding in report.findings
            if finding.casilla_id == _RETENCIONES_BOX and finding.severity is ModeloVerificationFindingSeverity.BLOCKING
        ], report.findings

        # The review workbook shows the figure with no note beside it.
        for language in (OutputLanguage.ES, OutputLanguage.EN):
            notes = _review_notes_by_box(revision, language, operation)
            assert "06" in notes and not notes["06"], language


def test_an_invoice_older_than_the_filing_years_stays_readable_and_moves_no_box(
    secure_objects: SecureObjectRepository,
) -> None:
    _seed_taxpayer_profile()
    with bundled_indexed_authority().operation() as operation:
        floor = operation.supported_filing_years().floor
        older = _issued_invoice(
            "F-ANTERIOR",
            base=Decimal("1000.00"),
            retencion=Decimal("150.00"),
            linked=None,
            issued_at=date(floor - 1, 2, 10),
        )
        _persist_ledger(secure_objects, older=(older,))
        work_unit = _work_unit(secure_objects, _WITHHELD_YEAR, operation)
        revision = _calculate(work_unit, operation)

        assert Decimal(revision.casilla_values[_RETENCIONES_BOX]) == _STATED_RETENCION
        assert older.invoice_id in {
            invoice.invoice_id
            for invoice in InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects).load()
        }


def test_receipts_without_a_retencion_state_casilla_06_zero_and_pass_the_gate(
    secure_objects: SecureObjectRepository,
) -> None:
    _seed_taxpayer_profile()
    _persist_ledger(secure_objects)

    with bundled_indexed_authority().operation() as operation:
        work_unit = _work_unit(secure_objects, _ZERO_YEAR, operation)
        calculated = _calculate(work_unit, operation)

        # Read back from the encrypted store, as a declaration opened afresh reads it.
        revision = (
            CalculationRevisionCatalogueRepository(objects=secure_objects)
            .load(operation=operation)
            .get(calculated.calculation_revision_id)
        )
        assert revision is not None
        assert Decimal(revision.casilla_values[_RETENCIONES_BOX]) == Decimal("0")
        assert not [issue for issue in revision.source_issues if issue.reason == _REASON]
        assert _gate_reasons(work_unit, revision, operation) == {}
        load = _form(secure_objects, _ZERO_YEAR, operation)
        assert not [item for item in load.form.calculation_notes if item.withholds_filing]


def _store_as_filed_before_stamps(
    secure_objects: SecureObjectRepository,
    work_unit: WorkUnit,
    calculated: CalculationRevision,
    operation: PinnedAuthorityOperation,
) -> CalculationRevision:
    """Store ``calculated`` as a revision recorded filed before screen stamps existed, and point the unit at it."""
    revisions = CalculationRevisionCatalogueRepository(objects=secure_objects)
    units = WorkUnitCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    old_shape = calculated.model_copy(
        update={
            "screen_stamp": None,
            "state": CalculationRevisionState.PRESENTADO,
            "verified_at": _T0,
            "verified_by": "operator",
            "filed_at": _T0,
            "filed_by": "operator",
        }
    )
    filed = CalculationRevision.model_validate(
        {
            **old_shape.model_dump(),
            "calculation_revision_id": derive_calculation_revision_id_from_revision(old_shape),
        }
    )
    revisions.save(upsert_calculation_revision(revisions.load(operation=operation), filed))
    unit = units.load().work_units[work_unit.work_unit_id]
    units.save(
        upsert_work_unit(
            units.load(),
            unit.model_copy(
                update={
                    "current_calculation_revision_id": filed.calculation_revision_id,
                    "filed_calculation_revision_id": filed.calculation_revision_id,
                }
            ),
        )
    )
    return filed


def test_a_revision_filed_before_screen_stamps_with_a_casilla_06_figure_still_exports(
    secure_objects: SecureObjectRepository,
) -> None:
    _seed_taxpayer_profile()
    _persist_ledger(secure_objects)

    with bundled_indexed_authority().operation() as operation:
        work_unit = _work_unit(secure_objects, _WITHHELD_YEAR, operation)
        filed = _store_as_filed_before_stamps(secure_objects, work_unit, _calculate(work_unit, operation), operation)
        assert filed.screen_stamp is None
        assert Decimal(filed.casilla_values[_RETENCIONES_BOX]) == _STATED_RETENCION

        assert (
            calculation_filed_before_grade_cap(
                filed, modelo="130", filing_year=_WITHHELD_YEAR, period=work_unit.period, operation=operation
            )
            is None
        )
        assert "export" not in _gate_reasons(work_unit, filed, operation)
        load = _form(secure_objects, _WITHHELD_YEAR, operation)
        assert load.filed
        assert not [item for item in load.form.calculation_notes if item.reason == FILED_BEFORE_GRADE_CAP_REASON]
