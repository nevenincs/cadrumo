"""CLI surface tests for the calculation summary PDF and ``work report-verify``.

Exports and store checks drive the native worker against a real encrypted
profile and sealed revision. Document-only checks run after that worker closes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterator
from contextlib import AbstractContextManager
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pikepdf
import pytest
from click.testing import Result

from ....adapters.outbound.calculation_summary_pdf.summary_reading import read_calculation_summary_pdf
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.operator_scope import build_operator_scope_ports
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    bound_test_profile_record,
    upsert_test_profile_facts,
)
from ....application.aggregation.invoice_retencion import (
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from ....application.aggregation.tests.ledger_transaction_support import iva_transaction
from ....application.aggregation.withholding_filing_cadence import load_bucket_withholding_filer_cadence
from ....application.aggregation.withholding_producer import WithholdingProducer
from ....application.calculations.tests.filing_evidence import general_m303_filing_evidence
from ....application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_report_verification_operation import (
    MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
)
from ....application.modelo.calculation_summary_pdf_ports import (
    REPORT_ATTACHMENT_NAME,
    SIGNATURE_ATTACHMENT_NAME,
    STATEMENT_ATTACHMENT_NAME,
)
from ....application.modelo.metadata_read_operation import MODELO_WORK_METADATA_OPERATION_DEFINITION_ID
from ....application.modelo.operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    resolve_active_workflow_profile,
)
from ....application.modelo.revision_selection_operation import MODELO_WORK_REVISION_OPERATION_DEFINITION_ID
from ....application.modelo.verification_actions import verify_modelo_revision_with_preconditions
from ....application.modelo.work_addressing import law_selected_revision_for_work_target
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ....application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from ....application.user_profile.tests.profile_values import complete_profile_facts
from ....core.calculation_report_format import CalculationReportDocumentFormat
from ....core.config import override_settings
from ....core.optional_extras import PDF_EXTRA
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
from ....domain.modelos.verification_report import VerificationCompletenessStatus
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ....tests.cli_envelope import require_error_document
from ....tests.cli_envelope import unwrap_envelope_notices as _notices
from ....tests.cli_envelope import unwrap_schema_envelope as _payload
from ....tests.optional_extra_absence import optional_extra_absent
from ...adapter_composition import (
    build_calculation_action_ports,
    build_verification_repository_bundle,
    build_withholding_observation_service,
    build_work_lifecycle_ports,
)
from ...tests.profile_persistence.verification_repository_support import build_test_certificate_secret_backend_factory
from ._modelo_work_ux_support import m111_withholding_aggregate_arguments
from .cli_runner import invoke_cached_cli
from .native_api_cli_support import NativeApiCliSession, native_api_cli_session
from .test_runtime_invoice_add import password_profile_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_REPORT_OPERATIONS = frozenset(
    {
        MODELO_EXPORT_OPERATION_DEFINITION_ID,
        MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        MODELO_WORK_REVISION_OPERATION_DEFINITION_ID,
        MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
    }
)


def _scope(client_id: UUID) -> AccessScope:
    return AccessScope(
        operations=_REPORT_OPERATIONS,
        actions=frozenset(AccessAction),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=client_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                *(
                    DisclosurePermission(
                        destination_id=client_id,
                        projection_id=f"{definition_id}.result",
                        category=DisclosureCategory.TAX_VALUES,
                    )
                    for definition_id in _REPORT_OPERATIONS
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _report_session(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> AbstractContextManager[NativeApiCliSession[None]]:
    def prepare_profile(profile_id: UUID, root: Path) -> None:
        values = {
            "taxpayer_type.entity_type": "natural_person",
            "identity.tax_id": "12345678Z",
            "identity.name": "Report",
            "identity.surnames": "Operator",
            "activities.description": "consulting",
            "censo.activity_start_date": "2026-01-01",
            "tax_residence.jurisdiction_scope": "common_regime",
            "withholding.colegio_concertado": "false",
            "iva.regime": "GENERAL",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        }
        facts = complete_profile_facts(
            operation.profile_schema(),
            facts=tuple(UserProfileFact(path=path, value=value) for path, value in values.items()),
        )
        populated = upsert_test_profile_facts(profile_id, facts, root=root)
        with bound_test_profile_record(profile_id, root=root) as repository:
            ready = repository.complete_setup(
                profile_id,
                expected_revision=populated.record_revision,
                expected_content_digest=populated.content_digest,
            )
        assert ready.setup_state is ProfileSetupState.COMPLETE

    return native_api_cli_session(tmp_path, scope_for_destination=_scope, prepare_profile=prepare_profile)


@pytest.fixture
def report_session(tmp_path: Path, operation: PinnedAuthorityOperation) -> Iterator[NativeApiCliSession[None]]:
    with _report_session(tmp_path, operation) as session:
        yield session


def _seed_current_sealed_revision(
    *,
    session: NativeApiCliSession[None],
    operation: PinnedAuthorityOperation,
    modelo: str = "111",
    filing_instance_evidence: FilingInstanceEvidence | None = None,
) -> str:
    """Seed a sealed revision of ``modelo`` as its work unit's current one; return the work unit id."""
    with password_profile_session(session.profile_id, operation):
        return _seed_current_sealed_revision_in_profile(
            profile_id=session.profile_id,
            operation=operation,
            modelo=modelo,
            filing_instance_evidence=filing_instance_evidence,
        )


def _seed_current_sealed_revision_in_profile(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    modelo: str,
    filing_instance_evidence: FilingInstanceEvidence | None,
) -> str:
    bucket_id = str(profile_id)
    period = Period.from_year_and_code(2026, "1T")
    if modelo == "111":
        _capture_professional_withholding(bucket_id=bucket_id, operation=operation)
    else:
        assert modelo == "303"
        with validating_governed_facts(operation):
            sale = iva_transaction(
                "report-sale-2026-1T",
                direction=TransactionDirection.INCOMING,
                amount=Decimal("121"),
                taxable_base=Decimal("100"),
                iva_amount=Decimal("21"),
            )
        TransactionCatalogueRepository(bucket_id=bucket_id).save(TransactionCatalogue.from_transactions((sale,)))
    unit = create_work_unit(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=2026,
        period=period,
        revision_id=law_selected_revision_for_work_target(
            modelo=modelo, filing_year=2026, period=period, requested_revision_id=None, operation=operation
        ),
        actor="operator",
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        operation=operation,
    )
    calculation = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        unit.work_unit_id,
        ports=build_calculation_action_ports(bucket_id=bucket_id, operation=operation),
        actor="operator",
        filing_instance_evidence=filing_instance_evidence,
    )
    report = verify_modelo_revision_with_preconditions(
        str(calculation.revision.calculation_revision_id),
        certificate_secret_backend_factory=build_test_certificate_secret_backend_factory(),
        verification_repositories=build_verification_repository_bundle(bucket_id, operation=operation),
        actor="operator",
        workflow_profile=resolve_active_workflow_profile(operation),
        operator_scope_ports=build_operator_scope_ports(),
        operation=operation,
    ).report
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE, (
        report.completeness_status,
        tuple((finding.kind.value, finding.severity.value, dict(finding.message_facts)) for finding in report.findings),
    )
    return unit.work_unit_id


def _capture_professional_withholding(*, bucket_id: str, operation: PinnedAuthorityOperation) -> None:
    """Capture the paid perception the canonical Modelo 111 calculation requires."""
    paid_on = date(2026, 2, 15)
    with validating_governed_facts(operation):
        line = InvoiceLine(
            description="Report fixture professional service",
            quantity=Decimal("1"),
            unit_price=Decimal("1000"),
            subtotal=Decimal("1000"),
            iva_rate=IvaRate.from_registry("RATE_21"),
            iva_amount=Decimal("210"),
        )
        invoice = Invoice.model_validate(
            {
                "kind": InvoiceKind.RECEIVED,
                "bucket_id": bucket_id,
                "invoice_number": "REPORT-PROF-2026-001",
                "issued_at": paid_on,
                "counterparty_name": "Synthetic Professional",
                "counterparty_tax_id": "B12345674",
                "counterparty_country": "ES",
                "base_total": Decimal("1000"),
                "iva_total": Decimal("210"),
                "grand_total": Decimal("1210"),
                "currency": "EUR",
                "lines": (line,),
                "payment_status": PaymentStatus.PAID,
                "iva_category": IvaCategory("domestic_general"),
                "retention_rate": Decimal("0.15"),
                "retention_amount": Decimal("150"),
            }
        )
        evidence = InvoiceWithholdingEvidenceRequest.model_validate_json(
            m111_withholding_aggregate_arguments(str(invoice.invoice_id))[-1]
        )
        detail = evidence.modelo_190_detail
        assert detail is not None
        evidence = evidence.model_copy(
            update={
                "payment_event_id": "report-professional-payment-2026-02-15",
                "payment_occurred_on": paid_on,
                "modelo_190_detail": detail.model_copy(
                    update={
                        "transaction_date": paid_on,
                        "perceptor_tax_id": invoice.counterparty_tax_id,
                        "perceptor_legal_name": invoice.counterparty_name,
                    }
                ),
            }
        )
        repository = InvoiceCatalogueRepository(bucket_id=bucket_id)
        repository.save(InvoiceCatalogue(invoices={invoice.invoice_id: invoice}))
        _, source_revision_id = repository.load_revisioned()
        cadence = load_bucket_withholding_filer_cadence(bucket_id=bucket_id, filing_year=2026, operation=operation)
        capture = build_invoice_withholding_capture(
            invoice, catalogue_revision_id=source_revision_id, request=evidence, applicable_year=2026, cadence=cadence
        )
        WithholdingProducer(service=build_withholding_observation_service(bucket_id=bucket_id)).capture(
            capture.command, cadence=cadence, source_catalogue_revision_id=capture.catalogue_read_revision_id
        )


def _summary(work_unit_id: str, output: Path, *extra: str, session: NativeApiCliSession[None]) -> Result:
    command = (
        "app",
        "modelo",
        "work",
        "report",
        work_unit_id,
        "--document-format",
        CalculationReportDocumentFormat.PDF.value,
        "--output",
        str(output),
        *extra,
    )
    return session.invoke_password(*command)


def _verify(path: Path, *extra: str, session: NativeApiCliSession[None] | None = None) -> Result:
    command = ("app", "modelo", "work", "report-verify", str(path), *extra)
    if session is None:
        return invoke_cached_cli(("--format", "json", *command))
    return session.invoke_password(*command)


def _signed_by(path: Path) -> str:
    with pikepdf.open(path) as pdf:
        statement = pdf.attachments[STATEMENT_ATTACHMENT_NAME].get_file().read_bytes()
    return str(json.loads(statement)["signing_key"]["public_key_hex"])


@pytest.fixture
def summary_path(tmp_path: Path, operation: PinnedAuthorityOperation) -> Iterator[Path]:
    output = tmp_path / "modelo-111-summary.pdf"
    with _report_session(tmp_path, operation) as session:
        work_unit_id = _seed_current_sealed_revision(session=session, operation=operation)
        result = _summary(work_unit_id, output, session=session)
        assert result.exit_code == 0, result.output
    with override_settings(cadrumo_local_storage_root=tmp_path / "document-only-storage"):
        yield output


def test_the_summary_lands_and_names_the_key_it_is_signed_with(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
    report_session: NativeApiCliSession[None],
) -> None:
    work_unit_id = _seed_current_sealed_revision(session=report_session, operation=operation)
    output = tmp_path / "modelo-111-summary.pdf"

    result = _summary(work_unit_id, output, session=report_session)

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    landed = output.read_bytes()
    assert landed.startswith(b"%PDF-1.7")
    assert payload["document_format"] == CalculationReportDocumentFormat.PDF.value
    assert payload["file_sha256"] == hashlib.sha256(landed).hexdigest()
    assert payload["signing_key_fingerprint"] == hashlib.sha256(bytes.fromhex(_signed_by(output))).hexdigest()
    codes = {notice["code"] for notice in _notices(result.output)}
    assert "modelo.work.report.local_calculation_not_official_evidence" in codes


def test_an_existing_file_is_refused_and_replaced_only_on_explicit_choice(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
    report_session: NativeApiCliSession[None],
) -> None:
    work_unit_id = _seed_current_sealed_revision(session=report_session, operation=operation)
    output = tmp_path / "modelo-111-summary.pdf"
    output.write_bytes(b"an earlier summary")

    refused = _summary(work_unit_id, output, session=report_session)

    assert refused.exit_code != 0
    assert "existing file" in str(require_error_document(refused.output)["error"]["message"])
    assert output.read_bytes() == b"an earlier summary"
    replaced = _summary(work_unit_id, output, "--replace", session=report_session)
    assert replaced.exit_code == 0, replaced.output
    assert output.read_bytes().startswith(b"%PDF")


def test_a_summary_verifies_against_the_store_and_exits_zero(
    tmp_path: Path, operation: PinnedAuthorityOperation, report_session: NativeApiCliSession[None]
) -> None:
    work_unit_id = _seed_current_sealed_revision(session=report_session, operation=operation)
    output = tmp_path / "modelo-111-summary.pdf"
    written = _summary(work_unit_id, output, session=report_session)
    assert written.exit_code == 0, written.output
    result = _verify(output, session=report_session)

    assert result.exit_code == 0, result.output
    payload = _payload(result.output)
    assert payload["operation"] == "modelo.work.report_verify"
    assert payload["outcome"] == "verified"
    assert payload["store_checked"] is True
    assert payload["reasons"] == []
    assert {check["layer"] for check in payload["checks"]} == {"document", "store"}
    assert all(check["reason"] is None for check in payload["checks"])


def test_a_modelo_303_summary_verifies_with_every_check_ok(
    tmp_path: Path,
    *,
    operation: PinnedAuthorityOperation,
    report_session: NativeApiCliSession[None],
) -> None:
    """Modelo 303 declares casilla identifiers that break across the casilla column at a hyphen."""
    evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "1T"),
        reference="test:calculation-summary-303",
        operation=operation,
    )
    work_unit_id = _seed_current_sealed_revision(
        session=report_session, operation=operation, modelo="303", filing_instance_evidence=evidence
    )
    output = tmp_path / "modelo-303-summary.pdf"

    written = _summary(work_unit_id, output, session=report_session)
    verified = _verify(output, session=report_session)

    assert written.exit_code == 0, written.output
    assert verified.exit_code == 0, verified.output
    payload = _payload(verified.output)
    assert payload["outcome"] == "verified"
    assert payload["store_checked"] is True
    assert payload["reasons"] == []
    assert "text_layer" in {check["check"] for check in payload["checks"]}
    assert all(check["reason"] is None for check in payload["checks"])
    contents = read_calculation_summary_pdf(output.read_bytes())
    report = json.loads(contents.attachments[REPORT_ATTACHMENT_NAME])
    hyphenated = [row["number"] for row in report["rows"] if "-" in row["number"]]
    page = "".join(contents.page_text.split())
    assert hyphenated
    assert [number for number in hyphenated if number not in page] == []


def test_a_document_only_check_is_unpinned_until_a_key_is_trusted(summary_path: Path) -> None:
    unpinned = _verify(summary_path, "--document-only")
    pinned = _verify(summary_path, "--document-only", "--trusted-key", _signed_by(summary_path))

    assert unpinned.exit_code == 0, unpinned.output
    assert _payload(unpinned.output)["outcome"] == "valid_unpinned"
    assert _payload(unpinned.output)["store_checked"] is False
    assert "modelo.work.report_verify.valid_unpinned" in {notice["code"] for notice in _notices(unpinned.output)}
    assert pinned.exit_code == 0, pinned.output
    assert _payload(pinned.output)["outcome"] == "verified"


def test_a_tampered_summary_is_refused_with_a_non_zero_exit(summary_path: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "tampered.pdf"
    with pikepdf.open(summary_path) as pdf:
        signature = bytearray(pdf.attachments[SIGNATURE_ATTACHMENT_NAME].get_file().read_bytes())
        signature[0] ^= 0x01
        pdf.attachments[SIGNATURE_ATTACHMENT_NAME].obj.EF.F.write(bytes(signature))
        pdf.save(tampered)

    result = _verify(tampered, "--document-only")

    assert result.exit_code == 1
    payload = _payload(result.output)
    assert payload["outcome"] == "refused"
    assert payload["reasons"] == ["signature_invalid"]


def test_another_trusted_key_refuses_the_summary(summary_path: Path) -> None:
    result = _verify(summary_path, "--document-only", "--trusted-key", "ab" * 32)

    assert result.exit_code == 1
    assert _payload(result.output)["reasons"] == ["signing_key_untrusted"]


def test_a_malformed_trusted_key_and_a_missing_file_are_refused(summary_path: Path, tmp_path: Path) -> None:
    malformed = _verify(summary_path, "--document-only", "--trusted-key", "not-a-key")
    missing = _verify(tmp_path / "absent.pdf", "--document-only")

    assert malformed.exit_code != 0
    assert "64" in malformed.output
    assert missing.exit_code != 0
    assert "absent.pdf" in missing.output


@pytest.fixture
def pdf_extra_absent() -> Iterator[None]:
    """Run the production spec probe against a real absence of the ``pdf`` extra."""
    with optional_extra_absent(PDF_EXTRA):
        yield


@pytest.mark.usefixtures("pdf_extra_absent")
@pytest.mark.parametrize(
    ("language", "phrase"),
    (("es", "complemento opcional"), ("en", "optional")),
)
def test_without_the_pdf_extra_the_summary_is_refused_before_the_work_unit_is_read(
    tmp_path: Path,
    language: str,
    phrase: str,
    report_session: NativeApiCliSession[None],
) -> None:
    """An absent work unit proves the refusal precedes its private catalogue read."""
    output = tmp_path / "summary.pdf"

    refused = _summary("0" * 64, output, "--output-language", language, session=report_session)

    assert refused.exit_code != 0
    error = require_error_document(refused.output)["error"]
    assert error["code"] == "REFUSED_CALCULATION_SUMMARY_PDF_UNAVAILABLE"
    assert phrase in error["message"]
    assert "cadrumo[pdf]" in error["message"]
    assert not output.exists()


def test_verification_needs_no_pdf_extra(summary_path: Path, pdf_extra_absent: None) -> None:
    result = _verify(summary_path, "--document-only")

    assert result.exit_code == 0, result.output
    assert _payload(result.output)["outcome"] == "valid_unpinned"
