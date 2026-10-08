"""Registered-executor conformance scenarios for ledger classification, LLM review and LLM diagnostics."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from ...adapters.outbound.llm.models import UsageRecord
from ...adapters.persistence.llm.usage import UsageRecorder
from ...application.ledger.actions_manual import attach_manual_transaction_evidence
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ...application.ledger.llm_classification import apply_llm_classification
from ...application.ledger.llm_classification_ports import LLMClassificationSuggestion
from ...application.ledger.llm_diagnostics_operation import (
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
    LedgerLlmDiagnosticsProjection,
    LedgerLlmDiagnosticsRequest,
)
from ...application.ledger.llm_review_contracts import (
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID,
    LedgerLlmReviewRequest,
)
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.ledger.operator_iva_contracts import (
    LEDGER_OPERATOR_IVA_DEFINITION_ID,
    LedgerOperatorIvaRequest,
    LedgerOperatorIvaResult,
)
from ...application.operations.public_scalar import PublicDecimal
from ...core.config_support import LLMProvider
from ...core.errors.error_codes import get_registered_error_code
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.service import AttachmentBytesContent, AttachmentIngestionRequest, add_attachment
from ...domain.buckets.event import BucketEventType
from ...domain.transactions.enums import BusinessClassification
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .conformance_ledger_seed_support import (
    SEED_ACTOR,
    ledger_action_ports,
    ledger_unchanged_verifier,
    seed_manual_transaction,
)

# A 1x1 greyscale PNG: the smallest image the on-host document-shape probe
# classifies as IMAGE, so evidence reading routes to the vision reader.
_PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x00\x00\x00\x00:~\x9bU"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)
_ACQUIRE_PHASE = "ledger.llm.acquire"


def _prepare_iva_derive(context: ConformanceFamilyContext) -> ConformancePreparation:
    # Ley 37/1992 art. 90.Uno: the general rate is 21%, so a 121.00 gross splits
    # into a 100.00 base and 21.00 of IVA.
    transaction_id = seed_manual_transaction(
        context,
        booked_date=date(2025, 3, 10),
        amount=Decimal("121.00"),
        description="operator IVA derivation row",
        business_classification=BusinessClassification.BUSINESS,
    )
    ports = ledger_action_ports(context)
    events_before = frozenset(ports.bucket_event_repository.load().events)
    before = ports.transaction_repository.load().transactions[transaction_id]
    category = "domestic_general"

    def verify(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(LedgerOperatorIvaResult)
        assert result.profile_id == context.profile_id
        assert result.outcome == "derived"
        assert result.transaction_id == transaction_id
        assert result.iva_category == category
        assert result.derivable is True
        assert result.validation_messages == ()
        assert result.iva_rate is not None
        assert result.taxable_base is not None
        assert result.iva_amount is not None
        assert Decimal(result.iva_rate) == Decimal("0.21")
        assert Decimal(result.taxable_base) == Decimal("100.00")
        assert Decimal(result.iva_amount) == Decimal("21.00")

        # Only the IVA substrate changes; the business classification stays as the operator set it.
        # llm_classification.py `derive_operator_iva_substrate`.
        after_ports = ledger_action_ports(context)
        after = after_ports.transaction_repository.load().transactions[transaction_id]
        assert after.business_classification is before.business_classification
        assert after.iva_category == category
        assert after.iva_rate == Decimal("0.21")
        assert after.taxable_base == Decimal("100.00")
        assert after.iva_amount == Decimal("21.00")
        assert after.raw.amount == before.raw.amount

        # The write changes the stored tax figures, which the update path audits as an edit
        # event; the result must cite exactly the events that were appended.
        # actions_manual.py `_update_event_specs`.
        events = after_ports.bucket_event_repository.load().events
        new_events = tuple(event for event_id, event in events.items() if event_id not in events_before)
        assert result.classification is not None
        assert {event.event_id for event in new_events} == set(result.classification.bucket_event_ids)
        assert all(event.object_id == transaction_id for event in new_events)
        assert BucketEventType.LEDGER_TRANSACTION_UPDATED in {event.event_type for event in new_events}

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=LedgerOperatorIvaRequest(
            profile_id=context.profile_id, transaction_id=transaction_id[:12], iva_category=category
        ),
        verify=verify,
    )


def _prepare_classify_review(context: ConformanceFamilyContext) -> ConformancePreparation:
    transaction_id = seed_manual_transaction(
        context, booked_date=date(2025, 2, 11), amount=Decimal("18.00"), description="classification review row"
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        # A preview settles terminally; a full review would otherwise suspend for an
        # operator response before reaching a result.
        request=LedgerLlmReviewRequest(
            profile_id=context.profile_id,
            transaction_id=transaction_id[:12],
            mode="classification",
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
            preview=True,
        ),
        verify=ledger_unchanged_verifier(context),
    )


def _prepare_split_review(context: ConformanceFamilyContext) -> ConformancePreparation:
    transaction_id = seed_manual_transaction(
        context, booked_date=date(2025, 2, 12), amount=Decimal("60.00"), description="split review row"
    )
    ports = ledger_action_ports(context)
    # A split proposal is only ever read from image evidence by the on-host vision reader.
    # llm_classification.py `_split_with_evidence`.
    attachment = add_attachment(
        ports.attachment_store,
        content=AttachmentBytesContent(data=_PNG_1X1),
        request=AttachmentIngestionRequest(
            kind=AttachmentKind.RECEIPT_IMAGE,
            source=AttachmentSource.INLINE,
            source_reference=f"split-review-conformance:{context.profile_id}",
            mime_type="image/png",
            captured_at=now(),
            bucket_id=str(context.profile_id),
            captured_by=SEED_ACTOR,
            source_command="registered executor conformance seed",
        ),
    )
    attach_manual_transaction_evidence(
        bucket_id=str(context.profile_id),
        transaction_id=transaction_id,
        attachment_ids=(attachment.attachment_id,),
        actor=SEED_ACTOR,
        source_command="registered executor conformance seed",
        ports=ports,
        occurred_at=now(),
    )
    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=LedgerLlmReviewRequest(
            profile_id=context.profile_id,
            transaction_id=transaction_id[:12],
            mode="split",
            origin=LlmReviewInvocationOrigin.SPLIT_LLM,
            read_evidence=True,
            preview=True,
        ),
        verify=ledger_unchanged_verifier(context),
    )


_USAGE_WINDOW_START = date(2026, 4, 1)
_USAGE_WINDOW_END = date(2026, 4, 30)
_LOW_CONFIDENCE_FLOOR = "0.7"


def _usage_record(
    request_id: str,
    created: datetime,
    *,
    provider: LLMProvider,
    input_tokens: int,
    output_tokens: int,
    cost: Decimal | None,
    cache_hit: bool = False,
) -> UsageRecord:
    return UsageRecord(
        prompt_id="conformance",
        caller="cadrumo.application.ledger.llm_classification",
        text="synthetic response",
        provider=provider,
        model="conformance-model",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_estimate_usd=cost,
        cache_hit=cache_hit,
        created_at=created,
        request_id=request_id,
    )


def _seed_diagnostics_usage() -> None:
    recorder = UsageRecorder()
    for record in (
        # Dated outside the requested window, so neither may be counted.
        _usage_record(
            "before-window",
            datetime(2026, 3, 30, 9, 0, tzinfo=UTC),
            provider=LLMProvider.ANTHROPIC,
            input_tokens=9000,
            output_tokens=900,
            cost=Decimal("9.00"),
        ),
        _usage_record(
            "after-window",
            datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
            provider=LLMProvider.ANTHROPIC,
            input_tokens=8000,
            output_tokens=800,
            cost=Decimal("8.00"),
        ),
        _usage_record(
            "anthropic-priced-first",
            datetime(2026, 4, 2, 9, 0, tzinfo=UTC),
            provider=LLMProvider.ANTHROPIC,
            input_tokens=1000,
            output_tokens=200,
            cost=Decimal("1.50"),
        ),
        _usage_record(
            "anthropic-priced-cached",
            datetime(2026, 4, 5, 9, 0, tzinfo=UTC),
            provider=LLMProvider.ANTHROPIC,
            input_tokens=500,
            output_tokens=100,
            cost=Decimal("0.25"),
            cache_hit=True,
        ),
        _usage_record(
            "local-unpriced",
            datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
            provider=LLMProvider.LOCAL,
            input_tokens=300,
            output_tokens=50,
            cost=None,
        ),
    ):
        recorder.record(record)


def _seed_diagnostics_confidence(context: ConformanceFamilyContext) -> None:
    ports = ledger_action_ports(context)
    for index, (provenance, confidence) in enumerate(
        (
            ("llm:local:conformance-model-a", Decimal("0.90")),
            ("llm:local:conformance-model-a", Decimal("0.40")),
            ("llm:claude:conformance-model-b", Decimal("0.60")),
        )
    ):
        transaction_id = seed_manual_transaction(
            context,
            booked_date=date(2026, 4, 10 + index),
            amount=Decimal("10.00") + index,
            description=f"diagnostics confidence row {index}",
        )
        apply_llm_classification(
            LLMClassificationSuggestion(
                transaction_id=transaction_id,
                provenance=provenance,
                classification=BusinessClassification.BUSINESS,
                confidence=confidence,
                reason="synthetic model reason",
            ),
            bucket_id=str(context.profile_id),
            actor=SEED_ACTOR,
            source_command="registered executor conformance seed",
            transaction_repository=ports.transaction_repository,
            bucket_event_repository=ports.bucket_event_repository,
        )
    # Manually classified, so it carries no llm: provenance and is not a model decision.
    seed_manual_transaction(
        context,
        booked_date=date(2026, 4, 20),
        amount=Decimal("77.00"),
        description="diagnostics non-model row",
        business_classification=BusinessClassification.BUSINESS,
    )


def _prepare_llm_diagnostics(context: ConformanceFamilyContext) -> ConformancePreparation:
    _seed_diagnostics_usage()
    _seed_diagnostics_confidence(context)

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(LedgerLlmDiagnosticsProjection)
        assert projection.profile_id == context.profile_id
        assert projection.operation_id == LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID
        assert projection.outcome == "completed"
        assert projection.effect is OperationEffect.NONE
        assert (projection.since, projection.until) == (_USAGE_WINDOW_START, _USAGE_WINDOW_END)
        report = projection.report

        # Providers are folded in provider order; only calls dated inside the window count.
        # llm_diagnostics.py `_aggregate_usage`.
        assert [row.provider for row in report.usage_providers] == ["ANTHROPIC", "LOCAL"]
        anthropic, local = report.usage_providers
        assert (anthropic.calls, anthropic.cache_hits, anthropic.unpriced_calls) == (2, 1, 0)
        assert (anthropic.input_tokens, anthropic.output_tokens, anthropic.total_tokens) == (1500, 300, 1800)
        assert anthropic.cost_estimate_usd is not None
        assert Decimal(anthropic.cost_estimate_usd.decimal) == Decimal("1.75")
        assert (local.calls, local.cache_hits, local.unpriced_calls) == (1, 0, 1)
        assert (local.input_tokens, local.output_tokens, local.total_tokens) == (300, 50, 350)
        # One unpriced call withholds the provider's cost instead of totalling the priced subset.
        assert local.cost_estimate_usd is None
        assert (report.total_calls, report.total_cache_hits, report.total_unpriced_calls) == (3, 1, 1)
        assert (report.total_input_tokens, report.total_output_tokens) == (1800, 350)
        assert report.total_cost_estimate_usd is None

        # Confidence is read from llm:-attributed rows only, split at the requested floor and
        # the fixed 0.8 and 0.5 distribution floors. llm_diagnostics.py `_confidence_row`.
        assert [row.provider for row in report.confidence_providers] == ["claude", "local"]
        claude, local_model = report.confidence_providers
        assert (claude.classified_count, claude.low_confidence_count) == (1, 1)
        assert (claude.high_confidence_count, claude.medium_confidence_count) == (0, 1)
        assert local_model.classified_count == 2
        assert (local_model.low_confidence_count, local_model.high_confidence_count) == (1, 1)
        assert local_model.medium_confidence_count == 0
        assert local_model.min_confidence is not None
        assert local_model.max_confidence is not None
        assert local_model.mean_confidence is not None
        assert Decimal(local_model.min_confidence.decimal) == Decimal("0.40")
        assert Decimal(local_model.max_confidence.decimal) == Decimal("0.90")
        assert Decimal(local_model.mean_confidence.decimal) == Decimal("0.65")
        assert (report.total_classified, report.total_low_confidence) == (3, 2)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(context.profile_id)),
        request=LedgerLlmDiagnosticsRequest(
            profile_id=context.profile_id,
            since=_USAGE_WINDOW_START,
            until=_USAGE_WINDOW_END,
            low_confidence_threshold=PublicDecimal(decimal=_LOW_CONFIDENCE_FLOOR),
        ),
        verify=verify,
    )


_PREPARE = {
    LEDGER_OPERATOR_IVA_DEFINITION_ID: _prepare_iva_derive,
    LEDGER_CLASSIFY_REVIEW_DEFINITION_ID: _prepare_classify_review,
    LEDGER_SPLIT_REVIEW_DEFINITION_ID: _prepare_split_review,
    LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID: _prepare_llm_diagnostics,
}


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    prepare = _PREPARE.get(context.definition.definition_id)
    if prepare is None:
        raise AssertionError(f"no ledger classification conformance scenario for {context.definition.definition_id}")
    return prepare(context)


# With no local model runtime, the first reader call fails and the reader probe finds the
# runtime unreachable, which the composition raises as this registered refusal.
# ledger_llm_composition.py `run_reader`.
_READER_UNAVAILABLE_REFUSAL = get_registered_error_code(PurchaseInvoiceEvidenceReaderError).code

LEDGER_CLASSIFICATION_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            LEDGER_OPERATOR_IVA_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (LEDGER_OPERATOR_IVA_DEFINITION_ID,),
        ),
        # The refusal is raised while acquiring the proposal, before the review phase
        # and before any write, so no later phase is published and no effect is recorded.
        # llm_review_execution.py `LedgerLlmReviewExecutor.execute`.
        RegisteredExecutorConformanceCase(
            LEDGER_CLASSIFY_REVIEW_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (_ACQUIRE_PHASE,),
            expected_refusal_ref=_READER_UNAVAILABLE_REFUSAL,
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_SPLIT_REVIEW_DEFINITION_ID,
            OperationTerminalCondition.REFUSED,
            OperationEffect.NONE,
            (_ACQUIRE_PHASE,),
            expected_refusal_ref=_READER_UNAVAILABLE_REFUSAL,
        ),
        RegisteredExecutorConformanceCase(
            LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (LEDGER_LLM_DIAGNOSTICS_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
    closes_model_runtime=True,
)
