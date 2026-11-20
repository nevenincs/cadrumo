"""The review queue, its views and the confirm, through the registered operations.

Runs the production registry and supervisor over bundled structured invoices
that a real encrypted profile holds as stored extraction drafts. What a person's
review of a draft carries (the direction they imported it under, the country its
VAT numbers name), what stops every confirm before it starts (the profile's own
fiscal-address postcode), and when a draft leaves the queue (once its confirm
succeeded) are read the way a frontend in another process reads them.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from ...adapters.persistence.storage.tests.profile_capsule_runtime import upsert_test_profile_facts
from ...application.ledger.evidence import PurchaseInvoiceEvidenceService
from ...application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceReviewListProjection,
    LedgerEvidenceReviewListRequest,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from ...application.ledger.extraction_draft_repository import bind_extraction_draft_repository_factory
from ...application.ledger.extraction_draft_store import write_extraction_draft
from ...application.ledger.filer_establishment import (
    FILER_POSTCODE_FACT_PATH,
    FILER_POSTCODE_MISSING_LOCALE_KEY,
)
from ...application.ledger.invoice_confirmation import invoice_draft_review_sha256
from ...application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
from ...application.ledger.invoice_draft_records import InvoiceDraft
from ...application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmProjection,
    LedgerEvidenceConfirmRequest,
)
from ...application.ledger.invoice_evidence_operation_dtos import InvoiceDraftProjectionV1
from ...application.ledger.invoice_extraction_authority import default_invoice_extraction_period
from ...application.ledger.preconditions import LedgerPreconditionCondition
from ...application.operations.error_detail import OperationErrorDetailKind, OperationErrorDetailV1
from ...application.operations.next_step import OperationOpenProfileFieldStepV1
from ...application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from ...core.operations import OperationTerminalCondition
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.iva.regime_legend import resolve_regime_legends
from ...domain.iva.schema import InvoiceKind
from ...domain.user_profile.values import UserProfileFact
from ..evidence_followup_operation_composition import build_ledger_evidence_followup_operation_ports
from ..invoice_evidence_operation_composition import build_invoice_evidence_operation_ports
from . import registered_executor_case_support as conformance
from .dependency_operation_gating_support import OperationRuntime, operation_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CORPUS = Path(__file__).resolve().parents[2] / "application/ledger/tests/_evidence_corpus"
_FACTURAE = _CORPUS / "facturae_32_series_and_parties_invoice.xml"
_UBL_TWO_RATES = _CORPUS / "en16931_ubl_two_rate_invoice.xml"
_UBL_SWEDISH_SUPPLIER = _CORPUS / "en16931_ubl_intracom_german_sek_invoice.xml"


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _enrolled(tmp_path: Path, *, postcode: str | None) -> Iterator[OperationRuntime]:
    """Enrol a profile that states a fiscal-address postcode, or one that does not."""
    with (
        conformance.family_environment_for_operation(LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID),
        operation_runtime(tmp_path, None) as enrolled,
    ):
        stated = () if postcode is None else (UserProfileFact(path=FILER_POSTCODE_FACT_PATH, value=postcode),)
        upsert_test_profile_facts(
            enrolled.profile_id,
            persona_facts_beneath(
                stated, without=("identity.", FILER_POSTCODE_FACT_PATH) if postcode is None else ("identity.",)
            ),
        )
        yield enrolled


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[OperationRuntime]:
    yield from _enrolled(tmp_path, postcode="28013")


@pytest.fixture
def runtime_without_postcode(tmp_path: Path) -> Iterator[OperationRuntime]:
    yield from _enrolled(tmp_path, postcode=None)


class _Stored(NamedTuple):
    evidence_id: str
    source_sha256: str
    draft: InvoiceDraft


def _store_draft(
    runtime: OperationRuntime,
    operation: PinnedAuthorityOperation,
    source: Path,
    *,
    declared_kind: InvoiceKind | None = None,
    suggested_kind: InvoiceKind | None = None,
) -> _Stored:
    """Add a document as evidence, read it, and keep its draft where the review queue looks."""
    bucket_id = str(runtime.profile_id)
    ports = build_invoice_evidence_operation_ports(bucket_id=bucket_id)
    record = (
        PurchaseInvoiceEvidenceService(ports=ports.evidence_ports).add(bucket_id=bucket_id, source_path=source).record
    )
    with validating_governed_facts(operation):
        draft = extract_invoice_draft_from_evidence(
            bucket_id=bucket_id,
            evidence_id=record.evidence_id,
            settings=ports.settings,
            ports=ports.extraction_ports,
            operation=operation,
            legends=resolve_regime_legends(
                operation=operation, effective_date=default_invoice_extraction_period().end_date
            ),
        )
    if suggested_kind is not None:
        draft = draft.model_copy(update={"suggested_kind": suggested_kind})
    followup = build_ledger_evidence_followup_operation_ports(settings=ports.settings)
    with bind_extraction_draft_repository_factory(followup.extraction_draft_repository_factory):
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=record.evidence_id,
            draft=draft,
            extractor="structured-invoice-fixture",
            settings=ports.settings,
            declared_kind=declared_kind,
        )
    return _Stored(evidence_id=record.evidence_id, source_sha256=record.source_sha256, draft=draft)


def _queue(runtime: OperationRuntime) -> LedgerEvidenceReviewListProjection:
    settled = runtime.settle(
        LEDGER_EVIDENCE_REVIEW_LIST_OPERATION_DEFINITION_ID,
        LedgerEvidenceReviewListRequest(profile_id=runtime.profile_id),
        LedgerEvidenceReviewListProjection,
    )
    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    assert isinstance(settled.published, LedgerEvidenceReviewListProjection)
    return settled.published


def _review(runtime: OperationRuntime, stored: _Stored) -> LedgerEvidenceReviewViewProjection:
    settled = runtime.settle(
        LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
        LedgerEvidenceReviewViewRequest(profile_id=runtime.profile_id, evidence_reference=stored.evidence_id),
        LedgerEvidenceReviewViewProjection,
    )
    assert settled.condition is OperationTerminalCondition.SUCCEEDED
    assert isinstance(settled.published, LedgerEvidenceReviewViewProjection)
    return settled.published


def _confirm(runtime: OperationRuntime, stored: _Stored):
    return runtime.settle(
        LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
        LedgerEvidenceConfirmRequest(
            profile_id=runtime.profile_id,
            evidence_id=stored.evidence_id,
            expected_source_sha256=stored.source_sha256,
            expected_draft_review_sha256=invoice_draft_review_sha256(stored.draft),
            kind=InvoiceKind.RECEIVED,
        ),
        LedgerEvidenceConfirmProjection,
    )


# -- the filer's postcode -----------------------------------------------------


def test_a_profile_without_a_postcode_refuses_the_confirm_naming_the_field_that_puts_it_right(
    runtime_without_postcode: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(runtime_without_postcode, operation, _FACTURAE)

    settled = _confirm(runtime_without_postcode, stored)

    assert settled.condition is OperationTerminalCondition.REFUSED
    detail = settled.published
    assert isinstance(detail, OperationErrorDetailV1)
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.message_key == FILER_POSTCODE_MISSING_LOCALE_KEY
    assert isinstance(detail.next_step, OperationOpenProfileFieldStepV1)
    assert detail.next_step.kind == "open_profile_field"
    assert detail.next_step.path == FILER_POSTCODE_FACT_PATH == "contact.postcode"
    assert detail.next_step.words
    verdict = detail.precondition_verdict()
    assert verdict is not None
    assert verdict.failed_condition_id == LedgerPreconditionCondition.FILER_POSTCODE_VALID.value


def test_the_queue_says_before_any_review_that_a_profile_without_a_postcode_cannot_confirm(
    runtime_without_postcode: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    _store_draft(runtime_without_postcode, operation, _FACTURAE)

    precondition = _queue(runtime_without_postcode).confirm_precondition

    assert precondition is not None
    assert precondition.condition is LedgerPreconditionCondition.FILER_POSTCODE_VALID
    assert precondition.words
    assert isinstance(precondition.next_step, OperationOpenProfileFieldStepV1)
    assert precondition.next_step.path == "contact.postcode"


def test_a_queue_with_nothing_to_review_has_no_precondition_to_state(
    runtime_without_postcode: OperationRuntime,
) -> None:
    queue = _queue(runtime_without_postcode)

    assert queue.rows == ()
    assert queue.confirm_precondition is None


def test_a_profile_with_a_postcode_confirms_and_its_queue_states_no_precondition(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(runtime, operation, _FACTURAE)
    assert _queue(runtime).confirm_precondition is None

    settled = _confirm(runtime, stored)

    assert settled.condition is OperationTerminalCondition.SUCCEEDED


# -- the queue holds drafts awaiting a decision -------------------------------


def test_a_confirmed_draft_leaves_the_queue_and_one_still_awaiting_review_stays(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    confirmed = _store_draft(runtime, operation, _FACTURAE)
    waiting = _store_draft(runtime, operation, _UBL_TWO_RATES)
    assert {row.evidence_reference for row in _queue(runtime).rows} == {confirmed.evidence_id, waiting.evidence_id}

    assert _confirm(runtime, confirmed).condition is OperationTerminalCondition.SUCCEEDED

    assert [row.evidence_reference for row in _queue(runtime).rows] == [waiting.evidence_id]


def test_a_refused_confirm_leaves_the_draft_in_the_queue(
    runtime_without_postcode: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(runtime_without_postcode, operation, _FACTURAE)

    assert _confirm(runtime_without_postcode, stored).condition is OperationTerminalCondition.REFUSED

    assert [row.evidence_reference for row in _queue(runtime_without_postcode).rows] == [stored.evidence_id]


# -- the direction a review opens on ------------------------------------------


def test_an_import_direction_the_reading_does_not_contradict_is_what_the_review_opens_on(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(runtime, operation, _FACTURAE, declared_kind=InvoiceKind.ISSUED)

    direction = _review(runtime, stored).direction

    assert direction is not None
    assert direction.declared_kind is InvoiceKind.ISSUED
    assert direction.suggested_kind is None
    assert direction.preselected_kind is InvoiceKind.ISSUED
    assert direction.disagree is False


def test_a_reading_that_agrees_with_the_import_direction_preselects_it(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(
        runtime, operation, _FACTURAE, declared_kind=InvoiceKind.RECEIVED, suggested_kind=InvoiceKind.RECEIVED
    )

    direction = _review(runtime, stored).direction

    assert direction is not None
    assert direction.preselected_kind is InvoiceKind.RECEIVED
    assert direction.disagree is False


def test_a_reading_that_contradicts_the_import_direction_shows_both_and_preselects_neither(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(
        runtime, operation, _FACTURAE, declared_kind=InvoiceKind.ISSUED, suggested_kind=InvoiceKind.RECEIVED
    )

    review = _review(runtime, stored)

    assert review.direction is not None
    assert review.direction.declared_kind is InvoiceKind.ISSUED
    assert review.direction.suggested_kind is InvoiceKind.RECEIVED
    assert review.direction.preselected_kind is None
    assert review.direction.disagree is True
    # The reading's own suggestion on the draft is what it proposed, never overwritten by the import choice.
    assert review.draft.suggested_kind is InvoiceKind.RECEIVED


def test_a_draft_nobody_gave_a_direction_serves_none(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(runtime, operation, _FACTURAE)

    assert _review(runtime, stored).direction is None


# -- the country a VAT number's prefix names ----------------------------------


def test_the_review_serves_the_country_each_vat_prefix_names_apart_from_the_draft(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(runtime, operation, _UBL_SWEDISH_SUPPLIER)

    review = _review(runtime, stored)

    assert review.counterparty_vat_prefix_country is not None
    assert review.counterparty_vat_prefix_country.supplier == "SE"
    assert review.counterparty_vat_prefix_country.customer == "ES"
    # The document states no address country, and the prefix is not taken as one on the draft.
    assert review.draft.supplier_tax_id == "SE556677889901"
    assert review.draft.supplier_country_code is None
    assert review.draft.supplier_stated_country_code is None


def test_a_domestic_number_without_a_prefix_serves_no_suggestion(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation
) -> None:
    stored = _store_draft(runtime, operation, _FACTURAE)

    assert _review(runtime, stored).counterparty_vat_prefix_country is None


# -- a stored review and a fresh read of the same bytes agree -----------------


@pytest.mark.parametrize("source", [_FACTURAE, _UBL_TWO_RATES, _UBL_SWEDISH_SUPPLIER], ids=lambda path: path.stem)
def test_the_served_review_of_a_stored_draft_is_the_draft_a_fresh_read_of_its_bytes_yields(
    runtime: OperationRuntime, operation: PinnedAuthorityOperation, source: Path
) -> None:
    """A frontend compares the review it showed with a re-read taken before it confirms.

    Any fact the stored draft loses on its way through storage would make the
    re-read differ from the review for every document that carries it.
    """
    stored = _store_draft(runtime, operation, source)

    served = _review(runtime, stored).draft

    assert served == InvoiceDraftProjectionV1.from_draft(stored.draft)
