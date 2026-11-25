"""Real-path tests for the verify-time invoice-drift gate.

Modelo 347 worked by hand: two received invoices of 2,500.00 base plus 21 % IVA
are 3,025.00 each, so the supplier's annual record is 6,050.00; without one of
them it is 3,025.00, still above the 3,005.06 floor. Modelo 303 worked by hand:
an issued invoice of 1,000.00 at 21 % carries 210.00, equal to the sale the
ledger already holds, so the invoice screen passes and the draft calculates.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.catalogue_creation import build_catalogue_lifecycle_ports
from cadrumo.adapters.persistence.profile.catalogue_reads import build_invoice_catalogue_read_ports
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.modelo_export_ports_support import modelo_export_ports_for_test
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.operator_scope import build_operator_scope_ports
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.aggregation.invoice_filing_fingerprint import (
    capture_invoice_fingerprint,
    evaluate_invoice_fingerprint,
    invoice_row_fingerprint,
)
from cadrumo.application.aggregation.renta_imputation import declared_imputation_criteria
from cadrumo.application.invoices.catalogue_lifecycle import (
    CatalogueInvoicePatch,
    remove_catalogue_invoice,
    update_catalogue_invoice,
)
from cadrumo.application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.edit_services import calculation_head_digest
from cadrumo.application.modelo.export import export_modelo_revision
from cadrumo.application.modelo.export_contracts import ModeloExportCommand
from cadrumo.application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.invoices.enums import IvaRate, PaymentStatus, operation_performed_role
from cadrumo.domain.invoices.models import Invoice, InvoiceLine, derive_invoice_id
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.iva.classification import TransactionKind
from cadrumo.domain.iva.oss import OssIossRegime
from cadrumo.domain.iva.schema import InvoiceKind
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id_from_revision,
)
from cadrumo.domain.modelos.errors import ModeloValidationError
from cadrumo.domain.modelos.invoice_fingerprint import InvoiceRowFingerprint, invoice_snapshot_fingerprint
from cadrumo.domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationReport,
)
from cadrumo.domain.modelos.work_unit import WorkUnit
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.adapter_composition_work_ports import (
    build_calculation_action_ports,
    build_ledger_membership_ports,
    build_verification_repository_bundle,
)
from cadrumo.entrypoints.tests.profile_persistence.ledger_drift_support import (
    BUCKET_ID as IRENE_BUCKET,
)
from cadrumo.entrypoints.tests.profile_persistence.ledger_drift_support import (
    TAX_ID,
    calculate_irene_revision,
    workflow_profile,
)
from cadrumo.entrypoints.tests.profile_persistence.verification_repository_support import (
    build_test_certificate_secret_backend_factory,
)
from cadrumo.tests.env_scope import ready_clave_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("authority_operation")]

_BUCKET = "34700000-0000-4000-8000-000000000348"
_YEAR = 2025
_REVISION_ID = "2025-y-siguientes"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_LATER = itertools.count()
_DRIFT_KEY = "application.modelo.findings.invoice_fingerprint_drift"
_ABSENT_KEY = "application.modelo.findings.invoice_fingerprint_absent"
_SUPPLIER = "B00015016"
_ROW_IMPORTE = "modelo-347-contraparte-row-importe"
_OPERATOR_SCOPE_PORTS = build_operator_scope_ports()


def _profile_facts() -> tuple[UserProfileFact, ...]:
    return persona_facts_beneath(
        (
            UserProfileFact(path="identity.tax_id", value=TAX_ID),
            UserProfileFact(path="identity.name", value="Ready"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="invoice-drift"),
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            UserProfileFact(path="withholding.colegio_concertado", value=False),
        )
    )


def _later() -> datetime:
    """Each lifecycle step strictly after every calculation and verify before it."""
    return datetime(2026, 4, 20, 12, 0, tzinfo=UTC) + timedelta(hours=next(_LATER))


def _invoice(
    number: str,
    *,
    issued_at: date,
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    bucket_id: str = _BUCKET,
    tax_id: str = _SUPPLIER,
    base: Decimal = Decimal("2500.00"),
    iva: Decimal = Decimal("525.00"),
) -> Invoice:
    grand_total = base + iva
    return Invoice(
        invoice_id=derive_invoice_id(
            kind=kind,
            invoice_number=number,
            issued_at=issued_at,
            counterparty_tax_id=tax_id,
            currency="EUR",
            grand_total=grand_total,
        ),
        bucket_id=bucket_id,
        kind=kind,
        invoice_number=number,
        issued_at=issued_at,
        counterparty_name="PROVEEDOR GRANDE SL",
        counterparty_tax_id=tax_id,
        counterparty_country="ES",
        base_total=base,
        iva_total=iva,
        grand_total=grand_total,
        currency="EUR",
        lines=(
            InvoiceLine(
                description="Operacion interior",
                quantity=Decimal("1"),
                unit_price=base,
                subtotal=base,
                iva_rate=IvaRate.from_registry("RATE_21"),
                iva_amount=iva,
            ),
        ),
        payment_status=PaymentStatus.PAID,
    )


@dataclass(frozen=True)
class _M347:
    objects: SecureObjectRepository
    invoices: InvoiceCatalogueRepository
    calculations: CalculationRevisionCatalogueRepository
    work_unit: WorkUnit
    first: Invoice
    second: Invoice


def _calculate(work_unit: WorkUnit, *, clock: datetime = _T1) -> CalculationRevision:
    with bundled_indexed_authority().operation() as operation:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            ports=build_calculation_action_ports(bucket_id=work_unit.bucket_id, operation=operation),
            clock=clock,
        ).revision


def _verify(revision_id: str, *, bucket_id: str, objects: SecureObjectRepository) -> VerificationReport:
    with bundled_indexed_authority().operation() as operation:
        return verify_modelo_revision_with_preconditions(
            revision_id,
            certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
            actor="operator",
            workflow_profile=workflow_profile(),
            settings=ready_clave_settings(TAX_ID),
            verification_repositories=replace(
                build_verification_repository_bundle(bucket_id, operation=operation),
                ledger_membership_ports=build_ledger_membership_ports(
                    bucket_id=bucket_id,
                    transaction_repository=TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects),
                ),
            ),
            clock=_later(),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).report


def _with_key(report: VerificationReport, key: str) -> list[ModeloVerificationFinding]:
    return [finding for finding in report.findings if finding.message_locale_key == key]


def _drift_counts(report: VerificationReport) -> tuple[object, object, object]:
    (finding,) = _with_key(report, _DRIFT_KEY)
    assert finding.kind is ModeloVerificationFindingKind.STALE_CALCULATION
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    facts = finding.message_facts
    return facts["changed_count"], facts["removed_count"], facts["added_count"]


def _supplier_importe(revision: CalculationRevision) -> Decimal:
    (value,) = revision.row_binding_values[_ROW_IMPORTE].values()
    return Decimal(value)


@pytest.fixture
def m347(tmp_path: Path) -> Iterator[_M347]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        seed_test_profile_record(
            create_user_profile_record(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET,
                facts=_profile_facts(),
                created_at=_T0,
                updated_at=_T0,
                context=profile_creation_context_for_test(),
            ),
        )
        objects = profile.repository
        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=objects)
        first = _invoice("P-001", issued_at=date(_YEAR, 2, 10))
        second = _invoice("P-002", issued_at=date(_YEAR, 8, 10))
        invoices.save(build_invoice_catalogue((first, second)))
        with bundled_indexed_authority().operation() as operation:
            work_unit = create_work_unit(
                bucket_id=_BUCKET,
                modelo="347",
                filing_year=_YEAR,
                period=Period.from_year_and_code(_YEAR, "0A"),
                revision_id=_REVISION_ID,
                ports=WorkLifecyclePorts(
                    work_unit_repository=WorkUnitCatalogueRepository(objects=objects),
                    bucket_event_repository=BucketEventHistoryRepository(objects=objects),
                ),
                operation=operation,
                clock=_T0,
            )
        yield _M347(
            objects=objects,
            invoices=invoices,
            calculations=CalculationRevisionCatalogueRepository(objects=objects),
            work_unit=work_unit,
            first=first,
            second=second,
        )


def _stored(fixture: _M347, revision_id: str) -> CalculationRevision:
    stored = fixture.calculations.load().get(revision_id)
    assert stored is not None
    return stored


def _verify_m347(fixture: _M347, revision: CalculationRevision) -> VerificationReport:
    return _verify(revision.calculation_revision_id, bucket_id=_BUCKET, objects=fixture.objects)


def test_m347_removal_is_reported_and_recalculating_gives_the_worked_figure(m347: _M347) -> None:
    revision = _calculate(m347.work_unit)
    assert _supplier_importe(revision) == Decimal("6050.00")

    remove_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=m347.second.invoice_id,
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
    )

    report = _verify_m347(m347, revision)
    assert _drift_counts(report) == (0, 1, 0)
    assert report.granted_verificado_completo is False
    assert _stored(m347, revision.calculation_revision_id).state is CalculationRevisionState.BORRADOR
    # A finding only: the stored figure stands until the operator recalculates.
    assert _supplier_importe(_stored(m347, revision.calculation_revision_id)) == Decimal("6050.00")

    recalculated = _calculate(m347.work_unit, clock=_later())
    assert _supplier_importe(recalculated) == Decimal("3025.00")
    assert _verify_m347(m347, recalculated).granted_verificado_completo is True


def test_m347_untouched_draft_is_granted_and_a_sealed_revision_refuses_the_write(m347: _M347) -> None:
    """The control for every refusal here, and the limit of the gate.

    A grant seals the revision and verify then returns its report unchanged, so the
    invoice is held at the write, as the participation guard holds a ledger row.
    """
    revision = _calculate(m347.work_unit)
    granted = _verify_m347(m347, revision)
    assert granted.granted_verificado_completo is True
    assert not _with_key(granted, _DRIFT_KEY)

    with pytest.raises(CadrumoError) as refused:
        remove_catalogue_invoice(
            bucket_id=_BUCKET,
            invoice_id=m347.second.invoice_id,
            ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
        )
    assert "sealed_invoice_refused" in str(refused.value.translated_message)
    assert _verify_m347(m347, revision).verification_report_id == granted.verification_report_id


def test_m347_blocked_draft_cannot_be_exported_or_filed(m347: _M347, tmp_path: Path) -> None:
    revision = _calculate(m347.work_unit)
    remove_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=m347.second.invoice_id,
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
    )
    report = _verify_m347(m347, revision)
    assert report.granted_verificado_completo is False
    output = tmp_path / "refused-347.txt"

    with bundled_indexed_authority().operation() as operation, pytest.raises(CadrumoError) as refused:
        export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=revision.calculation_revision_id,
                output_path=output,
                actor="operator",
            ),
            workflow_profile=workflow_profile(),
            export_ports=modelo_export_ports_for_test(bucket_id=_BUCKET),
            clock=_later(),
            operation=operation,
        )
    assert "export_revision_state_refused" in str(refused.value.translated_message)
    assert not output.exists()


def test_m347_addition_is_reported(m347: _M347) -> None:
    revision = _calculate(m347.work_unit)

    added = _invoice("P-003", issued_at=date(_YEAR, 5, 5))
    m347.invoices.save(build_invoice_catalogue((*m347.invoices.load().values(), added)))
    assert _drift_counts(_verify_m347(m347, revision)) == (0, 0, 1)


def test_m347_invoice_of_another_year_is_out_of_scope(m347: _M347) -> None:
    revision = _calculate(m347.work_unit)
    other_year = _invoice("P-OTHER", issued_at=date(_YEAR + 1, 2, 10))
    m347.invoices.save(build_invoice_catalogue((*m347.invoices.load().values(), other_year)))
    assert _verify_m347(m347, revision).granted_verificado_completo is True


@pytest.mark.parametrize(
    "patch",
    [
        CatalogueInvoicePatch(counterparty_name="OTRO NOMBRE SL"),
        CatalogueInvoicePatch(retention_rate=Decimal("0.15"), retention_amount=Decimal("375.00")),
        CatalogueInvoicePatch(payment_status=PaymentStatus.PENDING),
    ],
    ids=["counterparty", "retention", "payment_status"],
)
def test_m347_material_edit_is_reported(m347: _M347, patch: CatalogueInvoicePatch) -> None:
    revision = _calculate(m347.work_unit)
    update_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=m347.first.invoice_id,
        patch=patch,
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
        occurred_at=_T1,
    )
    assert _drift_counts(_verify_m347(m347, revision)) == (1, 0, 0)


@pytest.mark.parametrize(
    "patch",
    [
        CatalogueInvoicePatch(notes="llamar al proveedor"),
        CatalogueInvoicePatch(series="A"),
        CatalogueInvoicePatch(payment_id="f" * 64),
    ],
    ids=["notes", "series", "payment_id"],
)
def test_m347_display_only_edit_is_not_drift(m347: _M347, patch: CatalogueInvoicePatch) -> None:
    revision = _calculate(m347.work_unit)
    update_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=m347.first.invoice_id,
        patch=patch,
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
        occurred_at=_T1,
    )
    assert not _with_key(_verify_m347(m347, revision), _DRIFT_KEY)


def test_an_edit_that_moves_no_figure_clears_on_recalculation(m347: _M347) -> None:
    """Payment status moves no Modelo 347 figure, so the id repeats and the pin must follow."""
    revision = _calculate(m347.work_unit)
    update_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=m347.first.invoice_id,
        patch=CatalogueInvoicePatch(payment_status=PaymentStatus.PENDING),
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
        occurred_at=_T1,
    )
    assert _with_key(_verify_m347(m347, revision), _DRIFT_KEY)

    recalculated = _calculate(m347.work_unit, clock=_later())

    assert recalculated.calculation_revision_id == revision.calculation_revision_id
    assert not _with_key(_verify_m347(m347, recalculated), _DRIFT_KEY)


def test_old_revision_reports_no_fingerprint_and_keeps_its_identity_and_digests(m347: _M347) -> None:
    fingerprinted = _calculate(m347.work_unit)
    assert fingerprinted.invoice_fingerprint is not None
    identity = derive_calculation_revision_id_from_revision(fingerprinted)

    old = fingerprinted.model_copy(update={"invoice_fingerprint": None})
    assert derive_calculation_revision_id_from_revision(old) == identity
    dumped = old.model_dump(mode="json")
    assert "invoice_fingerprint" not in dumped
    # What a build without the field would have digested: the same dump, key absent.
    assert calculation_head_digest(old) == calculation_head_digest(
        fingerprinted.model_copy(update={"invoice_fingerprint": None})
    )
    with_key_dropped = fingerprinted.model_dump(mode="json")
    del with_key_dropped["invoice_fingerprint"]
    assert with_key_dropped == dumped

    m347.calculations.save(upsert_calculation_revision(m347.calculations.load(), old))
    stored = _stored(m347, old.calculation_revision_id)
    assert stored.invoice_fingerprint is None

    remove_catalogue_invoice(
        bucket_id=_BUCKET,
        invoice_id=m347.second.invoice_id,
        ports=build_catalogue_lifecycle_ports(bucket_id=_BUCKET),
    )
    report = _verify_m347(m347, stored)
    (finding,) = _with_key(report, _ABSENT_KEY)
    assert finding.severity is ModeloVerificationFindingSeverity.WARNING
    assert not _with_key(report, _DRIFT_KEY)


def test_fingerprint_round_trips_through_the_encrypted_store(m347: _M347) -> None:
    revision = _calculate(m347.work_unit)
    stored = _stored(m347, revision.calculation_revision_id)
    fingerprint = stored.invoice_fingerprint
    assert fingerprint is not None
    assert fingerprint == revision.invoice_fingerprint
    assert {row.invoice_id for row in fingerprint.rows} == {
        m347.first.invoice_id,
        m347.second.invoice_id,
    }
    # Only digests sit on the record: no figure, name or tax id.
    dumped = fingerprint.model_dump_json()
    assert _SUPPLIER not in dumped
    assert "PROVEEDOR" not in dumped
    assert "2500" not in dumped


def test_m303_invoice_moved_out_of_the_period_registers_and_back_in_clears(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=IRENE_BUCKET) as profile:
        objects = profile.repository
        invoices = InvoiceCatalogueRepository(bucket_id=IRENE_BUCKET, objects=objects)
        # A sale no seeded movement pays: an unlinked movement with the same
        # figures would be the same operation counted twice, a blocking finding.
        sale_invoice = _invoice(
            "V-001",
            kind=InvoiceKind.ISSUED,
            issued_at=date(2026, 2, 15),
            bucket_id=IRENE_BUCKET,
            base=Decimal("400.00"),
            iva=Decimal("84.00"),
        ).model_copy(update={"operation_date": date(2026, 2, 15), "operation_date_role": operation_performed_role()})
        invoices.save(build_invoice_catalogue((sale_invoice,)))
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation)
        assert revision.invoice_fingerprint is not None
        assert [row.invoice_id for row in revision.invoice_fingerprint.rows] == [sale_invoice.invoice_id]

        def verify() -> VerificationReport:
            return _verify(revision.calculation_revision_id, bucket_id=IRENE_BUCKET, objects=objects)

        assert not _with_key(verify(), _DRIFT_KEY)

        ports = build_catalogue_lifecycle_ports(bucket_id=IRENE_BUCKET)
        update_catalogue_invoice(
            bucket_id=IRENE_BUCKET,
            invoice_id=sale_invoice.invoice_id,
            patch=CatalogueInvoicePatch(operation_date=date(2026, 4, 2)),
            ports=ports,
            occurred_at=_T1,
        )
        assert _drift_counts(verify()) == (0, 1, 0)

        update_catalogue_invoice(
            bucket_id=IRENE_BUCKET,
            invoice_id=sale_invoice.invoice_id,
            patch=CatalogueInvoicePatch(operation_date=date(2026, 2, 16)),
            ports=ports,
            occurred_at=_T1,
        )
        assert _drift_counts(verify()) == (1, 0, 0)


def test_m303_second_quarter_invoice_addition_does_not_touch_the_first(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=IRENE_BUCKET) as profile:
        objects = profile.repository
        with bundled_indexed_authority().operation() as operation:
            revision, *_ = calculate_irene_revision(objects, operation=operation)
        invoices = InvoiceCatalogueRepository(bucket_id=IRENE_BUCKET, objects=objects)
        invoices.save(
            build_invoice_catalogue(
                (_invoice("V-Q2", kind=InvoiceKind.ISSUED, issued_at=date(2026, 5, 2), bucket_id=IRENE_BUCKET),)
            )
        )
        report = _verify(revision.calculation_revision_id, bucket_id=IRENE_BUCKET, objects=objects)
        assert not _with_key(report, _DRIFT_KEY)

        invoices.save(
            build_invoice_catalogue(
                (
                    *invoices.load().values(),
                    _invoice("V-Q1", kind=InvoiceKind.ISSUED, issued_at=date(2026, 2, 2), bucket_id=IRENE_BUCKET),
                )
            )
        )
        report = _verify(revision.calculation_revision_id, bucket_id=IRENE_BUCKET, objects=objects)
        assert _drift_counts(report) == (0, 0, 1)


def test_m130_scope_is_the_invoices_linked_to_a_contributor(tmp_path: Path) -> None:
    """Income evidence reads a retention only through the row the invoice is linked to."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        contributor = "a" * 64
        linked = _invoice("V-LINK", kind=InvoiceKind.ISSUED, issued_at=date(2026, 2, 2)).model_copy(
            update={"linked_transaction_ids": (contributor,)}
        )
        unlinked = _invoice("V-LOOSE", kind=InvoiceKind.ISSUED, issued_at=date(2026, 2, 3))
        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)
        invoices.save(build_invoice_catalogue((linked, unlinked)))
        ports = build_invoice_catalogue_read_ports(bucket_id=_BUCKET)
        with bundled_indexed_authority().operation() as operation:
            period = Period.from_year_and_code(2026, "1T")
            revision = operation.snapshot("130", filing_year=2026, period="1T").revision
            work_unit = WorkUnit.model_construct(
                bucket_id=_BUCKET, modelo="130", filing_year=2026, period=period, revision_id=revision.id
            )
            snapshot = capture_invoice_fingerprint(
                work_unit=work_unit,
                revision=revision,
                contributors=frozenset({contributor}),
                ports=ports,
                criteria=declared_imputation_criteria(None),
                captured_at=_T1,
            )
            assert snapshot is not None
            assert [row.invoice_id for row in snapshot.rows] == [linked.invoice_id]

            invoices.save(
                build_invoice_catalogue((linked.model_copy(update={"retention_amount": Decimal("150.00")}), unlinked))
            )
            verdict = evaluate_invoice_fingerprint(
                snapshot,
                work_unit=work_unit,
                revision=revision,
                contributors=frozenset({contributor}),
                ports=ports,
                criteria=declared_imputation_criteria(None),
            )
    assert verdict.changed == (linked.invoice_id,)


def test_m369_exterior_period_scope_has_no_issue_date_span(tmp_path: Path) -> None:
    """An exterior period scopes by devengo in its quarter, not by a calendar span of its own."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        oss = {
            "oss_ioss_regime": OssIossRegime("union_scheme"),
            "oss_transaction_kind": TransactionKind("oss_union_services"),
        }
        inside = _invoice("OSS-1", kind=InvoiceKind.ISSUED, issued_at=date(2026, 2, 2)).model_copy(update=oss)
        other_quarter = _invoice("OSS-2", kind=InvoiceKind.ISSUED, issued_at=date(2026, 5, 2)).model_copy(update=oss)
        domestic = _invoice("V-1", kind=InvoiceKind.ISSUED, issued_at=date(2026, 2, 3))
        invoices = InvoiceCatalogueRepository(bucket_id=_BUCKET, objects=profile.repository)
        invoices.save(build_invoice_catalogue((inside, other_quarter, domestic)))
        with bundled_indexed_authority().operation() as operation:
            revision = operation.snapshot("369", filing_year=2026, period="EXT-1T").revision
            work_unit = WorkUnit.model_construct(
                bucket_id=_BUCKET,
                modelo="369",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "EXT-1T"),
                revision_id=revision.id,
            )
            snapshot = capture_invoice_fingerprint(
                work_unit=work_unit,
                revision=revision,
                contributors=frozenset(),
                ports=build_invoice_catalogue_read_ports(bucket_id=_BUCKET),
                criteria=declared_imputation_criteria(None),
                captured_at=_T1,
            )
    assert snapshot is not None
    assert [row.invoice_id for row in snapshot.rows] == [inside.invoice_id]


def _base_invoice() -> Invoice:
    return _invoice("P-001", issued_at=date(_YEAR, 2, 10))


def _edited(update: dict[str, object]) -> Invoice:
    """Apply a field update, where a ``line.`` key edits the invoice's only line."""
    base = _base_invoice()
    line_update = {key.removeprefix("line."): value for key, value in update.items() if key.startswith("line.")}
    invoice_update = {key: value for key, value in update.items() if not key.startswith("line.")}
    if line_update:
        invoice_update["lines"] = (base.lines[0].model_copy(update=line_update),)
    return base.model_copy(update=invoice_update)


@pytest.mark.parametrize(
    "update",
    [
        {"kind": InvoiceKind.ISSUED},
        {"issued_at": date(_YEAR, 2, 11)},
        {"operation_date": date(_YEAR, 2, 11)},
        {"payment_status": PaymentStatus.PENDING},
        {"counterparty_name": "OTRO SL"},
        {"counterparty_tax_id": "B00010157"},
        {"counterparty_country": "FR"},
        {"base_total": Decimal("2500.01")},
        {"iva_total": Decimal("525.01")},
        {"grand_total": Decimal("3025.01")},
        {"currency": "USD"},
        {"fx_rate": Decimal("0.9")},
        {"linked_transaction_ids": ("b" * 64,)},
        {"is_subvencion_ayuda": True},
        {"outside_economic_activity": False},
        {"retention_amount": Decimal("1")},
        {"recargo_amount": Decimal("1")},
        {"suplido_amount": Decimal("1")},
        {"collected_on_behalf_of_tax_id": "B00010157"},
        {"collected_on_behalf_of_name": "BENEFICIARIO"},
        {"rectifies_invoice_number": "P-000"},
        {"line.subtotal": Decimal("2400.00")},
        {"line.iva_amount": Decimal("500.00")},
    ],
    ids=lambda update: next(iter(update)),
)
def test_every_calculation_fact_moves_the_row_digest(update: dict[str, object]) -> None:
    assert invoice_row_fingerprint(_edited(update)) != invoice_row_fingerprint(_base_invoice())


@pytest.mark.parametrize(
    "update",
    [
        {"notes": "nota"},
        {"series": "A"},
        {"issuer_address": "Calle Mayor 1"},
        {"recipient_address": "Calle Menor 2"},
        {"exemption_reference": "art. 20"},
        {"payment_id": "pago"},
        {"retention_rate": Decimal("0.15")},
        {"fx_rate_date": date(_YEAR, 2, 10)},
        {"fx_rate_source": "BCE"},
        {"updated_at": _T1},
        {"line.description": "Otro texto"},
    ],
    ids=lambda update: next(iter(update)),
)
def test_display_facts_do_not_move_the_row_digest(update: dict[str, object]) -> None:
    assert invoice_row_fingerprint(_edited(update)) == invoice_row_fingerprint(_base_invoice())


def test_the_number_a_correction_names_moves_the_current_digest_and_no_older_one() -> None:
    """Renumbering decides which invoice a correction reduces, so the current digest holds it."""
    edited = _edited({"invoice_number": "P-999"})
    assert invoice_row_fingerprint(edited) != invoice_row_fingerprint(_base_invoice())
    assert invoice_row_fingerprint(edited, field_set_version=3) == invoice_row_fingerprint(
        _base_invoice(), field_set_version=3
    )


def test_a_stored_older_version_keeps_reading_its_own_fields() -> None:
    """A version-1 digest is what a stored draft holds, so what version 2 adds must not move it."""
    edited = _edited({"rectifies_invoice_number": "P-000"})
    assert invoice_row_fingerprint(edited, field_set_version=1) == invoice_row_fingerprint(
        _base_invoice(), field_set_version=1
    )
    assert invoice_row_fingerprint(edited, field_set_version=2) != invoice_row_fingerprint(
        _base_invoice(), field_set_version=2
    )


def test_digest_is_canonical_over_decimal_scale_and_order() -> None:
    base = _base_invoice()
    line = base.lines[0]
    rescaled = base.model_copy(
        update={
            "base_total": Decimal("2500.0"),
            "lines": (line.model_copy(update={"iva_amount": Decimal("525.000")}),),
        }
    )
    assert invoice_row_fingerprint(rescaled) == invoice_row_fingerprint(base)

    other_line = line.model_copy(update={"subtotal": Decimal("1.00"), "iva_amount": Decimal("0.21")})
    forward = base.model_copy(update={"lines": (line, other_line), "linked_transaction_ids": ("a", "b")})
    backward = base.model_copy(update={"lines": (other_line, line), "linked_transaction_ids": ("b", "a")})
    assert invoice_row_fingerprint(forward) == invoice_row_fingerprint(backward)

    first = InvoiceRowFingerprint(invoice_id="a" * 64, fingerprint="c" * 64)
    second = InvoiceRowFingerprint(invoice_id="b" * 64, fingerprint="d" * 64)
    assert invoice_snapshot_fingerprint((first, second)) == invoice_snapshot_fingerprint((second, first))


def test_unknown_field_set_version_is_refused() -> None:
    with pytest.raises(ModeloValidationError):
        invoice_row_fingerprint(_base_invoice(), field_set_version=99)
