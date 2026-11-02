"""What a registered confirmation does with a document's retención.

Runs the production registry and supervisor over the bundled Facturae specimen,
a real encrypted attachment read by the deterministic structured reader. The
document prints a base of 1000.00, IVA 21 % of 210.00 and a 15 % retención of
150.00, so 1000.00 x 15 / 100 = 150.00 and the cash due on base plus cuota is
1210.00 - 150.00 = 1060.00.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.ledger.confirmation_gate import confirmation_blockers
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.filer_establishment import FILER_POSTCODE_FACT_PATH
from ...application.ledger.invoice_confirmation import invoice_draft_review_sha256
from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from ...application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    FindingResolutionInputV1,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
)
from ...application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from ...application.operations.error_detail import OperationErrorDetailV1
from ...core.confirmation_gate import FindingResolutionAction
from ...core.operations import OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.invoices.figures import settlement_amount
from ...domain.iva.regime_legend import resolve_regime_legends
from ...domain.iva.schema import InvoiceKind
from ...domain.user_profile.values import UserProfileFact
from ..invoice_evidence_operation_composition import build_invoice_evidence_operation_ports
from . import registered_executor_case_support as conformance
from .dependency_operation_gating_support import OperationRuntime, SettledOperation, operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "application/ledger/tests/_evidence_corpus/facturae_32_retencion_suplidos_invoice.xml"
)


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


@pytest.fixture
def runtime(tmp_path: Path, operation: PinnedAuthorityOperation) -> Iterator[OperationRuntime]:
    with (
        conformance.family_environment_for_operation(LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID),
        operation_runtime(tmp_path, None) as enrolled,
    ):
        upsert_test_profile_facts(
            enrolled.profile_id,
            (
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path=FILER_POSTCODE_FACT_PATH, value="28013"),
            ),
        )
        yield enrolled


def _confirm(
    runtime: OperationRuntime,
    operation: PinnedAuthorityOperation,
    *,
    source: Path = _SOURCE,
    expected_reading: Decimal | None = Decimal("150.00"),
    answer_findings: bool = False,
    **statement: Any,
) -> SettledOperation:
    bucket_id = str(runtime.profile_id)
    ports = build_invoice_evidence_operation_ports(bucket_id=bucket_id)
    evidence = PurchaseInvoiceEvidenceService(ports=ports.evidence_ports).add(bucket_id=bucket_id, source_path=source)
    with validating_governed_facts(operation):
        draft = extract_invoice_draft_from_evidence(
            bucket_id=bucket_id,
            evidence_id=evidence.record.evidence_id,
            settings=ports.settings,
            ports=ports.extraction_ports,
            operation=operation,
            legends=resolve_regime_legends(
                operation=operation, effective_date=default_invoice_extraction_period().end_date
            ),
        )
    assert draft.retencion_amount == expected_reading, "the specimen no longer reads its retención as this test says"
    if answer_findings:
        statement["resolutions"] = tuple(
            FindingResolutionInputV1(
                blocker_id=blocker.blocker_id,
                action=FindingResolutionAction.ATTEST,
                note="Revisado contra el documento",
            )
            for blocker in confirmation_blockers(draft)
        )
    return runtime.settle(
        LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        LedgerEvidenceConfirmRequest(
            profile_id=runtime.profile_id,
            evidence_id=evidence.record.evidence_id,
            expected_source_sha256=evidence.record.source_sha256,
            expected_draft_review_sha256=invoice_draft_review_sha256(draft),
            kind=InvoiceKind.RECEIVED,
            **statement,
        ),
        LedgerEvidenceConfirmProjection,
    )


def _stored_retention(runtime: OperationRuntime) -> tuple[Decimal | None, Decimal | None, Decimal]:
    invoices = list(InvoiceCatalogueRepository(bucket_id=str(runtime.profile_id)).load().invoices.values())
    assert len(invoices) == 1
    invoice = invoices[0]
    return (
        invoice.retention_rate,
        invoice.retention_amount,
        settlement_amount(invoice.grand_total, invoice.retention_amount),
    )


def _variant(tmp_path: Path, *replacements: tuple[str, str]) -> Path:
    """Write the specimen with figures changed, so each case states its own document."""
    text = _SOURCE.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text
        text = text.replace(old, new)
    path = tmp_path / "variant.xml"
    path.write_text(text, encoding="utf-8")
    return path


_WITHHELD_BLOCK = (
    "      <TaxesWithheld>\n        <Tax>\n          <TaxTypeCode>04</TaxTypeCode>\n"
    "          <TaxRate>15.00</TaxRate>\n          <TaxableBase>\n"
    "            <TotalAmount>1000.00</TotalAmount>\n          </TaxableBase>\n          <TaxAmount>\n"
    "            <TotalAmount>150.00</TotalAmount>\n          </TaxAmount>\n        </Tax>\n"
    "      </TaxesWithheld>\n"
)


def test_a_reading_left_alone_reaches_the_invoice(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    """The document's 15 % of 1000.00 is kept, so the cash due is 1210.00 - 150.00."""
    settled = _confirm(runtime, operation)

    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    assert _stored_retention(runtime) == (Decimal("0.15"), Decimal("150.00"), Decimal("1060.00"))


def test_a_person_overrides_the_reading(runtime: OperationRuntime, operation: PinnedAuthorityOperation) -> None:
    # 7 % of 1000.00 is 70.00, so the cash due is 1210.00 - 70.00.
    settled = _confirm(runtime, operation, retention_points="7", retention_amount="70.00")

    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    assert _stored_retention(runtime) == (Decimal("0.07"), Decimal("70.00"), Decimal("1140.00"))


def test_a_document_with_no_retention_keeps_none_rather_than_zero(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    source = _variant(
        tmp_path,
        (_WITHHELD_BLOCK, ""),
        ("        <TotalTaxesWithheld>150.00</TotalTaxesWithheld>\n", ""),
    )

    settled = _confirm(runtime, operation, source=source, expected_reading=None)

    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    assert _stored_retention(runtime) == (None, None, Decimal("1210.00"))


def test_a_disagreeing_reading_blocks_until_answered_and_then_keeps_only_the_amount(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation, tmp_path: Path
) -> None:
    # The document says 140.00 withheld and 15 %, but 15 % of 1000.00 is 150.00.
    source = _variant(
        tmp_path,
        ("<TotalAmount>150.00</TotalAmount>", "<TotalAmount>140.00</TotalAmount>"),
        ("<TotalTaxesWithheld>150.00<", "<TotalTaxesWithheld>140.00<"),
    )

    blocked = _confirm(runtime, operation, source=source, expected_reading=Decimal("140.00"))
    assert blocked.condition is OperationTerminalCondition.REFUSED
    assert not InvoiceCatalogueRepository(bucket_id=str(runtime.profile_id)).load().invoices

    answered = _confirm(runtime, operation, source=source, expected_reading=Decimal("140.00"), answer_findings=True)
    assert answered.condition is OperationTerminalCondition.SUCCEEDED
    assert _stored_retention(runtime) == (None, Decimal("140.00"), Decimal("1070.00"))


def test_reconfirming_an_invoice_that_predates_the_reading_changes_nothing_and_says_so(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    repository = InvoiceCatalogueRepository(bucket_id=str(runtime.profile_id))
    assert _confirm(runtime, operation).condition is OperationTerminalCondition.SUCCEEDED
    # An invoice as a confirmation used to leave it: no retention, whatever the page said.
    catalogue = repository.load()
    invoice = next(iter(catalogue.invoices.values()))
    older = invoice.model_copy(update={"retention_rate": None, "retention_amount": None})
    repository.save(catalogue.model_copy(update={"invoices": {invoice.invoice_id: older}}))

    settled = _confirm(runtime, operation)

    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    assert _stored_retention(runtime) == (None, None, Decimal("1210.00"))
    assert isinstance(settled.published, LedgerEvidenceConfirmProjection)
    report = settled.published.confirmation.retention_discrepancy
    assert report is not None
    assert Decimal(report.read_amount.decimal) == Decimal("150.00")
    assert report.recorded_amount is None


def test_reconfirming_with_a_stated_retention_still_refuses(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    assert _confirm(runtime, operation).condition is OperationTerminalCondition.SUCCEEDED

    settled = _confirm(runtime, operation, retention_points="7", retention_amount="70.00")

    assert settled.condition is OperationTerminalCondition.FAILED
    assert _stored_retention(runtime) == (Decimal("0.15"), Decimal("150.00"), Decimal("1060.00"))


def test_reconfirming_unchanged_is_a_no_op_with_nothing_to_report(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    assert _confirm(runtime, operation).condition is OperationTerminalCondition.SUCCEEDED

    settled = _confirm(runtime, operation)

    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    assert isinstance(settled.published, LedgerEvidenceConfirmProjection)
    assert settled.published.confirmation.retention_discrepancy is None
    assert _stored_retention(runtime) == (Decimal("0.15"), Decimal("150.00"), Decimal("1060.00"))


@pytest.mark.parametrize(
    ("statement", "rate"),
    [
        ({"retention_points": "15", "retention_amount": "150.00"}, Decimal("0.15")),
        ({"retention_rate": "0.15", "retention_amount": "150.00"}, Decimal("0.15")),
        # 1000.00 x 15 / 100 = 150.00, and a stated amount one cent away still agrees.
        ({"retention_points": "15", "retention_amount": "150.01"}, Decimal("0.15")),
        # 1 % of 1000.00 is 10.00.
        ({"retention_points": "1", "retention_amount": "10.00"}, Decimal("0.01")),
    ],
    ids=["points", "fraction", "one_cent_above", "one_point"],
)
def test_a_stated_retention_is_kept_on_either_scale(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation, statement: dict[str, Any], rate: Decimal
) -> None:
    settled = _confirm(runtime, operation, **statement)

    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    amount = Decimal(statement["retention_amount"])
    assert _stored_retention(runtime) == (rate, amount, Decimal("1210.00") - amount)


@pytest.mark.parametrize(
    "statement",
    [
        # Two cents past 150.00 no longer agrees with the rate.
        {"retention_points": "15", "retention_amount": "150.02"},
        # 1 % of 1000.00 is 10.00, so the whole base cannot pass as a withheld 1 %.
        {"retention_points": "1", "retention_amount": "1000.00"},
        # 16 % of 1000.00 is 160.00.
        {"retention_points": "16", "retention_amount": "150.00"},
        # Above the whole.
        {"retention_points": "101", "retention_amount": "150.00"},
        # Alone, a rate meets the amount the document read: 16 % of 1000.00 is not 150.00.
        {"retention_points": "16"},
    ],
    ids=["two_cents_above", "one_point_on_the_whole_base", "another_rate", "above_the_whole", "rate_against_reading"],
)
def test_a_retention_that_disagrees_is_refused(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation, statement: dict[str, Any]
) -> None:
    settled = _confirm(runtime, operation, **statement)

    # The invoice's own figure check stops it before anything is written.
    assert settled.condition is OperationTerminalCondition.FAILED
    assert isinstance(settled.published, OperationErrorDetailV1)
    assert "value_error" in settled.published.model_dump_json()
    assert not InvoiceCatalogueRepository(bucket_id=str(runtime.profile_id)).load().invoices


def test_a_retention_cannot_be_stated_on_both_scales() -> None:
    with pytest.raises(ValidationError, match="fraction or in points"):
        LedgerEvidenceConfirmRequest(
            profile_id=UUID(int=1),
            evidence_id="3576d2be417e1226",
            expected_source_sha256="a" * 64,
            expected_draft_review_sha256="b" * 64,
            kind=InvoiceKind.RECEIVED,
            retention_rate="0.15",
            retention_points="15",
        )
