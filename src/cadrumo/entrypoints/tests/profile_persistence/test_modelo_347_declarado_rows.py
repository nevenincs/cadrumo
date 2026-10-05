"""Modelo 347 declarado records reach the calculation revision and the filing draft.

The invoice resolver returns the type 2 records on the row-binding channel, the
bucket calculation persists them on the revision, and filing replay hands them
to the draft builder, which emits one row per (counterparty, clave) record.
Operator-supplied rows enter the same channel through ``calculate_modelo_revision``
and arrive at the same draft rows.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.filing.draft_construction import build_draft
from cadrumo.application.filing.runtime import ModeloOperatorProfile, build_runtime_schema_provider
from cadrumo.application.modelo.calculation_actions import (
    calculate_modelo_revision,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.revision_replay_inputs import revision_filing_replay_inputs
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus
from cadrumo.domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import InvoiceKind
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
_BUCKET_ID = "34700000-0000-4000-8000-000000000347"
_FILING_YEAR = 2025
_REVISION_ID = "2025-y-siguientes"
_ROW_PREFIX = "modelo-347-contraparte-row-"

_READY_PROFILE_FACTS = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    UserProfileFact(path="identity.name", value="Ready"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="m347-declarado-rows"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value="false"),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value="false"),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value="false"),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value="false"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
    UserProfileFact(path="withholding.colegio_concertado", value=False),
)


def _invoice(
    *,
    kind: InvoiceKind,
    number: str,
    issued_at: date,
    counterparty_tax_id: str,
    counterparty_name: str,
    base_total: Decimal,
    iva_total: Decimal,
) -> Invoice:
    grand_total = base_total + iva_total
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=issued_at,
            counterparty_tax_id=counterparty_tax_id,
            currency="EUR",
            grand_total=grand_total,
        ),
        bucket_id=_BUCKET_ID,
        kind=kind,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_name=counterparty_name,
        counterparty_tax_id=counterparty_tax_id,
        counterparty_country="ES",
        base_total=base_total,
        iva_total=iva_total,
        grand_total=grand_total,
        currency="EUR",
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


@dataclass(frozen=True)
class _Ledger:
    supplier_q1: Invoice
    supplier_q3: Invoice
    customer_q4: Invoice
    small_supplier: Invoice

    @property
    def invoices(self) -> tuple[Invoice, ...]:
        return (self.supplier_q1, self.supplier_q3, self.customer_q4, self.small_supplier)

    def expected_records(self) -> tuple[dict[str, str | Decimal], ...]:
        """The declarado records RD 1065/2007 art. 33.1 requires from these invoices.

        One per declarable (counterparty, clave), gross amounts split by quarter.
        The supplier at 1.000 EUR stays below the 3.005,06 floor and has no record.
        """
        return (
            {
                "nif": "B12345674",
                "clave": "A",
                "importe": self.supplier_q1.grand_total + self.supplier_q3.grand_total,
                "importe-q1": self.supplier_q1.grand_total,
                "importe-q3": self.supplier_q3.grand_total,
            },
            {
                "nif": "B87654323",
                "clave": "B",
                "importe": self.customer_q4.grand_total,
                "importe-q4": self.customer_q4.grand_total,
            },
        )


def _ledger() -> _Ledger:
    return _Ledger(
        supplier_q1=_invoice(
            kind=InvoiceKind.RECEIVED,
            number="P-001",
            issued_at=date(_FILING_YEAR, 2, 10),
            counterparty_tax_id="B12345674",
            counterparty_name="PROVEEDOR GRANDE SL",
            base_total=Decimal("2500.00"),
            iva_total=Decimal("525.00"),
        ),
        supplier_q3=_invoice(
            kind=InvoiceKind.RECEIVED,
            number="P-002",
            issued_at=date(_FILING_YEAR, 8, 10),
            counterparty_tax_id="B12345674",
            counterparty_name="PROVEEDOR GRANDE SL",
            base_total=Decimal("2500.00"),
            iva_total=Decimal("525.00"),
        ),
        customer_q4=_invoice(
            kind=InvoiceKind.ISSUED,
            number="V-001",
            issued_at=date(_FILING_YEAR, 11, 20),
            counterparty_tax_id="B87654323",
            counterparty_name="CLIENTE GRANDE SL",
            base_total=Decimal("6611.57"),
            iva_total=Decimal("1388.43"),
        ),
        small_supplier=_invoice(
            kind=InvoiceKind.RECEIVED,
            number="P-003",
            issued_at=date(_FILING_YEAR, 5, 5),
            counterparty_tax_id="A58818501",
            counterparty_name="PROVEEDOR PEQUENO SA",
            base_total=Decimal("826.45"),
            iva_total=Decimal("173.55"),
        ),
    )


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        seed_test_profile_record(
            _create_profile_record_for_test(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
                context=_profile_creation_context_for_test(),
            ),
        )
        yield profile.repository


def _work_unit(work_unit_repository: WorkUnitCatalogueRepository) -> WorkUnit:
    with bundled_indexed_authority().operation() as operation:
        return create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="347",
            filing_year=_FILING_YEAR,
            period=Period.from_year_and_code(_FILING_YEAR, "0A"),
            revision_id=_REVISION_ID,
            ports=WorkLifecyclePorts(
                work_unit_repository=work_unit_repository,
                bucket_event_repository=BucketEventHistoryRepository(),
            ),
            operation=operation,
            clock=_T0,
        )


def _records(row_values: Mapping[str, Mapping[str, str]]) -> list[dict[str, str]]:
    """Regroup persisted ``binding -> row -> value`` maps into one record per row index."""
    records: dict[str, dict[str, str]] = {}
    for binding_id, rows in row_values.items():
        if not binding_id.startswith(_ROW_PREFIX):
            continue
        for row_index, value in rows.items():
            records.setdefault(row_index, {})[binding_id.removeprefix(_ROW_PREFIX)] = value
    return sorted(records.values(), key=lambda record: record["nif"])


def _draft_records(revision: CalculationRevision, work_unit: WorkUnit) -> list[dict[str, object]]:
    """Replay a revision into the filing draft and regroup its declarado row bindings."""
    period = Period.from_year_and_code(_FILING_YEAR, "0A")
    draft = build_draft(
        modelo="347",
        period=period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs=revision_filing_replay_inputs(revision=revision, work_unit=work_unit),
        schema_provider=build_runtime_schema_provider(filing_year=_FILING_YEAR, period=period, modelos=("347",)),
    )
    records: dict[int, dict[str, object]] = {}
    for value in draft.binding_values:
        if value.row_index is None or not str(value.binding_id).startswith(_ROW_PREFIX):
            continue
        records.setdefault(value.row_index, {})[str(value.binding_id).removeprefix(_ROW_PREFIX)] = value.value
    return sorted(records.values(), key=lambda record: str(record["nif"]))


def _assert_expected_records(
    records: Sequence[Mapping[str, object]], expected_records: Sequence[Mapping[str, str | Decimal]]
) -> None:
    assert len(records) == len(expected_records)
    for record, expected in zip(records, expected_records, strict=True):
        assert record["nif"] == expected["nif"]
        assert record["clave"] == expected["clave"]
        for field in ("importe", "importe-q1", "importe-q2", "importe-q3", "importe-q4"):
            assert Decimal(str(record[field])) == expected.get(field, Decimal("0")), (expected["nif"], field)


def test_bucket_calculation_persists_and_replays_one_declarado_record_per_counterparty_and_clave(
    secure_objects: SecureObjectRepository,
) -> None:
    """Ledger invoices produce the declarado records on the revision and in the filing draft.

    The fichero itself is not rendered here: the signed amount fields of the
    declarado record are still declared as text in the generated export layout,
    so ``export_draft`` refuses them until that layout is regenerated.
    """
    invoice_repository = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    ledger = _ledger()
    invoice_repository.save(build_invoice_catalogue(ledger.invoices))
    work_unit_repository = WorkUnitCatalogueRepository(objects=secure_objects)
    work_unit = _work_unit(work_unit_repository)

    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=work_unit_repository,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        invoice_repository=invoice_repository,
    ) as ports:
        result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=ports,
            clock=_T1,
        )

    persisted = _records(result.revision.row_binding_values)
    _assert_expected_records(persisted, ledger.expected_records())
    assert {record["nombre"] for record in persisted} == {"PROVEEDOR GRANDE SL", "CLIENTE GRANDE SL"}
    _assert_expected_records(_draft_records(result.revision, work_unit), ledger.expected_records())


def test_operator_supplied_rows_reach_the_same_draft_records(secure_objects: SecureObjectRepository) -> None:
    """Rows an operator supplies on the row-binding channel replay to the same draft records."""
    work_unit_repository = WorkUnitCatalogueRepository(objects=secure_objects)
    work_unit = _work_unit(work_unit_repository)
    expected_records = _ledger().expected_records()
    operator_rows: dict[tuple[str, int], Decimal | str] = {}
    for row_index, expected in enumerate(expected_records, start=1):
        operator_rows[(f"{_ROW_PREFIX}nif", row_index)] = str(expected["nif"])
        operator_rows[(f"{_ROW_PREFIX}nombre", row_index)] = f"CONTRAPARTE {row_index}"
        operator_rows[(f"{_ROW_PREFIX}clave", row_index)] = str(expected["clave"])
        operator_rows[(f"{_ROW_PREFIX}pais-codigo", row_index)] = "ES"
        for field in ("importe", "importe-q1", "importe-q2", "importe-q3", "importe-q4"):
            amount = expected.get(field, Decimal("0"))
            assert isinstance(amount, Decimal)
            operator_rows[(f"{_ROW_PREFIX}{field}", row_index)] = amount

    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=work_unit_repository,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
    ) as ports:
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            ports=ports,
            casilla_inputs={},
            row_binding_values=operator_rows,
            clock=_T2,
        )

    _assert_expected_records(_draft_records(revision, work_unit), expected_records)
