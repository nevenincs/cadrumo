"""Real-behaviour tests for the LLM review workflow dispatch.

Proves ``execute_reviewed_decision`` COMPOSES the canonical ledger persistence
primitives (introducing no write path) and that the durable ``source_command``
audit label is DERIVED from the mandatory invocation origin, not defaulted.
Exercised against real SQLite persistence in an isolated profile, no mocks.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import STR_KEYED_MAPPING_ADAPTER
from ....domain.buckets import BucketEvent, BucketEventType
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    LLMSplitResponse,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
)
from ....llm.suggestions import (
    LLMClassificationSuggestion,
    LLMSaturatedSuggestion,
    LLMSplitApplyResult,
    LLMSplitSuggestion,
)
from ....tests.secure_sql import isolated_runtime_profile
from ..llm_classification import (
    apply_evidence_split,
    apply_llm_classification,
    saturate_llm_classification,
    suggest_evidence_split,
)
from ..llm_review_workflow import (
    LlmReviewDecision,
    LlmReviewInvocationOrigin,
    execute_reviewed_decision,
)
from ..models import ManualLedgerTransactionResult
from ._llm_evidence_split_support import (
    _single_line_proposal,
    _split_subprocess_proposer,
    _two_line_proposal,
)
from ._llm_saturation_support import _saturating_subprocess_classifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
_BUCKET = "a8de1d73-fd40-4766-bc01-b591ea364997"  # was 'bucket-review-workflow'
_UNKNOWN_TRANSACTION_ID = "f" * 64


@pytest.fixture
def repositories(tmp_path: Path) -> Iterator[tuple[TransactionCatalogueRepository, BucketEventHistoryRepository]]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        objects = profile.repository
        yield (
            TransactionCatalogueRepository(bucket_id=_BUCKET, objects=objects),
            BucketEventHistoryRepository(objects=objects),
        )


def _run_in_fresh_profile[T](
    tmp_path: Path,
    bucket_id: str,
    scenario: Callable[[TransactionCatalogueRepository, BucketEventHistoryRepository], T],
) -> T:
    """Run ``scenario`` against a real, independent isolated SQLite profile.

    Used by the CLI-route parity tests so the pre-cutover direct-primitive path
    and the post-cutover workflow path each run in a fully separate store, and
    their persisted results are compared without cross-contamination.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as profile:
        objects = profile.repository
        repository = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
        events = BucketEventHistoryRepository(objects=objects)
        return scenario(repository, events)


def _seed_parent(repository: TransactionCatalogueRepository) -> str:
    raw = RawTransaction(
        provider_transaction_id="row-review",
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor SL",
        description="supplier invoice",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=_NOW,
            provider_name="csv",
        ),
        raw_fields={"Concepto": "supplier invoice"},
    )
    tx = Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    repository.save(TransactionCatalogue.from_transactions([tx]))
    return tx.transaction_id


def _classification_suggestion(tx_id: str) -> LLMClassificationSuggestion:
    return LLMClassificationSuggestion(
        transaction_id=tx_id,
        provenance="llm:claude:test-model",
        classification=BusinessClassification.BUSINESS,
        category=SpendingCategory.MATERIAL_OFICINA,
        confidence=Decimal("0.9"),
        reason="looks like office supplies",
    )


def _events_of(events: BucketEventHistoryRepository, event_type: BucketEventType) -> tuple[BucketEvent, ...]:
    return events.load().for_bucket(_BUCKET, event_types=(event_type,))


# Wall-clock stamps assigned by the write (independent of the injected
# ``occurred_at`` event clock); excluded from the CLI-route parity comparison so
# every substantive persisted field (classification, category, IVA substrate,
# provenance, source_command, lineage) is compared and only the non-deterministic
# timestamps are ignored.
_VOLATILE_TIMESTAMP_KEYS = ("classified_at", "created_at", "modified_at")


def _stable_dump(transaction: Transaction) -> dict[str, object]:
    dumped = STR_KEYED_MAPPING_ADAPTER.validate_python(transaction.model_dump(mode="json"))
    for key in _VOLATILE_TIMESTAMP_KEYS:
        dumped.pop(key, None)
    return dumped


def _child_business_projection(child: Transaction) -> dict[str, object]:
    """The deterministic, business-meaningful slice of a persisted split child.

    The split write regenerates per-child ingest provenance and event ids with
    wall-clock/uuid entropy (``source_sha256``, ``created_event_id``, the
    ``edit_lineage`` event ids), so a full model dump is non-deterministic across
    runs. This projects only the fields the CLI-route parity claim is about: the
    amount, classification, expense/IVA substrate, provenance labels, and split
    lineage — every one of which MUST be identical between the direct-primitive
    and workflow-routed paths.
    """
    lineage = child.split_lineage
    return {
        "transaction_id": child.transaction_id,
        "amount": format(child.raw.amount, "f"),
        "description": child.raw.description,
        "business_classification": child.business_classification.value,
        "category_id": child.category_id,
        "iva_category": child.iva_category.value if child.iva_category is not None else None,
        "iva_rate": format(child.iva_rate, "f") if child.iva_rate is not None else None,
        "taxable_base": format(child.taxable_base, "f") if child.taxable_base is not None else None,
        "iva_amount": format(child.iva_amount, "f") if child.iva_amount is not None else None,
        "classified_by": child.classified_by,
        "source_command": child.source_command,
        "split_role": lineage.role.value if lineage is not None else None,
        "split_group_id": lineage.split_group_id if lineage is not None else None,
        "sibling_transaction_ids": sorted(lineage.sibling_transaction_ids) if lineage is not None else None,
    }


def test_apply_composes_classification_primitive_with_derived_source_command(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_parent(repository)

    result = execute_reviewed_decision(
        _classification_suggestion(tx_id),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        decision=LlmReviewDecision.APPLY,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    # Delegation happened: the transaction is now classified in real storage.
    assert isinstance(result, ManualLedgerTransactionResult)
    assert result.transaction.transaction_id == tx_id
    assert result.transaction.business_classification is BusinessClassification.BUSINESS

    # Provenance is the DERIVED origin label, never an application default.
    classified = _events_of(events, BucketEventType.LEDGER_TRANSACTION_CLASSIFIED)
    assert len(classified) == 1
    assert classified[0].payload["source_command"] == "aeat app ledger classify --llm --apply"
    assert classified[0].payload["source_command"] == LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY.source_command


def test_reject_composes_reject_primitive_and_mutates_nothing(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_parent(repository)

    execute_reviewed_decision(
        _classification_suggestion(tx_id),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_REJECT,
        decision=LlmReviewDecision.REJECT,
        bucket_id=_BUCKET,
        reason="wrong category, this is personal",
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    rejected = _events_of(events, BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED)
    assert len(rejected) == 1
    assert rejected[0].payload["source_command"] == "aeat app ledger classify --llm --reject"
    # Reject mutates nothing: it emits no classification event.
    assert _events_of(events, BucketEventType.LEDGER_TRANSACTION_CLASSIFIED) == ()


def test_split_decision_on_classification_suggestion_refuses() -> None:
    with pytest.raises(TransactionValidationError):
        execute_reviewed_decision(
            _classification_suggestion(_UNKNOWN_TRANSACTION_ID),
            origin=LlmReviewInvocationOrigin.SPLIT_LLM,
            decision=LlmReviewDecision.SPLIT,
            bucket_id=_BUCKET,
        )


@pytest.mark.parametrize("decision", [LlmReviewDecision.SUGGEST, LlmReviewDecision.NO_SPLIT])
def test_non_persisting_terminals_refuse_durable_execution(decision: LlmReviewDecision) -> None:
    with pytest.raises(TransactionValidationError):
        execute_reviewed_decision(
            _classification_suggestion(_UNKNOWN_TRANSACTION_ID),
            origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
            decision=decision,
            bucket_id=_BUCKET,
        )


# ── saturation / split matrix, origin attribution, CLI-route parity ──


def _saturated_suggestion(repository: TransactionCatalogueRepository, tx_id: str) -> LLMSaturatedSuggestion:
    """Build a real saturated suggestion through the subprocess classifier boundary."""
    return saturate_llm_classification(
        bucket_id=repository.bucket_id,
        transaction_id=tx_id,
        classifier=_saturating_subprocess_classifier(iva_category=IvaCategory.DOMESTIC_GENERAL),
        transaction_repository=repository,
    )


def _split_suggestion(
    repository: TransactionCatalogueRepository,
    tx_id: str,
    *,
    proposal: LLMSplitResponse,
) -> LLMSplitSuggestion:
    """Build a real split suggestion through the subprocess proposer boundary."""
    return suggest_evidence_split(
        bucket_id=repository.bucket_id,
        transaction_id=tx_id,
        proposer=_split_subprocess_proposer(response=proposal),
        transaction_repository=repository,
        read_evidence=False,
    )


def test_saturate_apply_composes_saturated_primitive_with_derived_source_command(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_parent(repository)

    result = execute_reviewed_decision(
        _saturated_suggestion(repository, tx_id),
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY,
        decision=LlmReviewDecision.APPLY,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    # Delegation to the saturated primitive: registry-derived IVA substrate lands.
    assert isinstance(result, ManualLedgerTransactionResult)
    assert result.transaction.iva_category is IvaCategory.DOMESTIC_GENERAL
    assert result.transaction.taxable_base == Decimal("100.00")
    assert result.transaction.iva_amount == Decimal("21.00")

    classified = _events_of(events, BucketEventType.LEDGER_TRANSACTION_CLASSIFIED)
    assert classified
    assert classified[0].payload["source_command"] == "aeat app ledger classify --llm --saturate --apply"
    assert (
        classified[0].payload["source_command"] == LlmReviewInvocationOrigin.CLASSIFY_LLM_SATURATE_APPLY.source_command
    )


def test_multi_child_split_apply_stamps_the_auto_split_origin_label(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_parent(repository)

    applied = execute_reviewed_decision(
        _split_suggestion(repository, tx_id, proposal=_two_line_proposal()),
        origin=LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
        decision=LlmReviewDecision.SPLIT,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert isinstance(applied, LLMSplitApplyResult)
    assert len(applied.child_transaction_ids) == 2
    catalogue = repository.load()
    parent = catalogue.get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
    for child_id in applied.child_transaction_ids:
        child = catalogue.get(child_id)
        assert child is not None
        assert child.business_classification is BusinessClassification.BUSINESS
        # The durable per-child source_command is the DERIVED auto-split origin label.
        assert child.source_command == "aeat app ledger classify --read-evidence --auto-split --apply"
        assert child.source_command == LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT.source_command


def test_split_llm_origin_stamps_its_own_distinct_source_command(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    repository, events = repositories
    tx_id = _seed_parent(repository)

    applied = execute_reviewed_decision(
        _split_suggestion(repository, tx_id, proposal=_two_line_proposal()),
        origin=LlmReviewInvocationOrigin.SPLIT_LLM,
        decision=LlmReviewDecision.SPLIT,
        bucket_id=_BUCKET,
        transaction_repository=repository,
        bucket_event_repository=events,
        occurred_at=_NOW,
    )

    assert isinstance(applied, LLMSplitApplyResult)
    child = repository.load().get(applied.child_transaction_ids[0])
    assert child is not None
    assert child.source_command == "aeat app ledger split --llm"
    assert child.source_command == LlmReviewInvocationOrigin.SPLIT_LLM.source_command
    # The two split routes are deliberately distinct origins with distinct labels.
    assert (
        LlmReviewInvocationOrigin.SPLIT_LLM.source_command
        != LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT.source_command
    )


def test_no_split_verdict_refuses_a_split_decision(
    repositories: tuple[TransactionCatalogueRepository, BucketEventHistoryRepository],
) -> None:
    # A single-child proposal is the model's "no split warranted" verdict; asking
    # the workflow to SPLIT it must refuse and persist nothing.
    repository, events = repositories
    tx_id = _seed_parent(repository)

    with pytest.raises(TransactionValidationError):
        execute_reviewed_decision(
            _split_suggestion(repository, tx_id, proposal=_single_line_proposal()),
            origin=LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT,
            decision=LlmReviewDecision.SPLIT,
            bucket_id=_BUCKET,
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )

    parent = repository.load().get(tx_id)
    assert parent is not None
    assert parent.lifecycle_state is TransactionLifecycleState.ACTIVE


def test_every_invocation_origin_derives_a_distinct_nonblank_source_command() -> None:
    # Origin attribution is DERIVED, total, non-blank, and unique — the audit
    # label can never silently default or collide across the six routes.
    commands = {origin: origin.source_command for origin in LlmReviewInvocationOrigin}
    assert all(cmd.strip().startswith("aeat app ledger") for cmd in commands.values())
    assert len(set(commands.values())) == len(LlmReviewInvocationOrigin)


def test_cli_route_parity_classify_apply_matches_direct_primitive(tmp_path: Path) -> None:
    # The cutover is behaviour-preserving: routing classify --llm --apply through
    # the workflow persists an IDENTICAL transaction and audit label to the
    # pre-cutover direct primitive call carrying the same source_command.
    origin = LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY

    def _direct(
        repository: TransactionCatalogueRepository, events: BucketEventHistoryRepository
    ) -> tuple[dict[str, object], str]:
        tx_id = _seed_parent(repository)
        result = apply_llm_classification(
            _classification_suggestion(tx_id),
            bucket_id=repository.bucket_id,
            source_command=origin.source_command,
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )
        classified = events.load().for_bucket(
            repository.bucket_id,
            event_types=(BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,),
        )
        return _stable_dump(result.transaction), classified[0].payload["source_command"]

    def _workflow(
        repository: TransactionCatalogueRepository, events: BucketEventHistoryRepository
    ) -> tuple[dict[str, object], str]:
        tx_id = _seed_parent(repository)
        result = execute_reviewed_decision(
            _classification_suggestion(tx_id),
            origin=origin,
            decision=LlmReviewDecision.APPLY,
            bucket_id=repository.bucket_id,
            transaction_repository=repository,
            bucket_event_repository=events,
            occurred_at=_NOW,
        )
        assert isinstance(result, ManualLedgerTransactionResult)
        classified = events.load().for_bucket(
            repository.bucket_id,
            event_types=(BucketEventType.LEDGER_TRANSACTION_CLASSIFIED,),
        )
        return _stable_dump(result.transaction), classified[0].payload["source_command"]

    direct_tx, direct_cmd = _run_in_fresh_profile(tmp_path / "direct", "4ad6f74a-2d46-4e6f-ae46-58bb910137a1", _direct)
    workflow_tx, workflow_cmd = _run_in_fresh_profile(
        tmp_path / "workflow", "3e9f396c-0fd2-4357-9de3-0597d58893c3", _workflow
    )

    assert direct_tx == workflow_tx
    assert direct_cmd == workflow_cmd == origin.source_command


def test_cli_route_parity_split_apply_matches_direct_primitive(tmp_path: Path) -> None:
    # Routing the auto-split apply through the workflow persists IDENTICAL children
    # to the pre-cutover direct apply_evidence_split with the same source_command.
    origin = LlmReviewInvocationOrigin.CLASSIFY_AUTO_SPLIT

    def _scenario(use_workflow: bool):
        def _run(
            repository: TransactionCatalogueRepository,
            events: BucketEventHistoryRepository,
        ) -> list[dict[str, object]]:
            tx_id = _seed_parent(repository)
            suggestion = _split_suggestion(repository, tx_id, proposal=_two_line_proposal())
            if use_workflow:
                applied = execute_reviewed_decision(
                    suggestion,
                    origin=origin,
                    decision=LlmReviewDecision.SPLIT,
                    bucket_id=repository.bucket_id,
                    transaction_repository=repository,
                    bucket_event_repository=events,
                    occurred_at=_NOW,
                )
            else:
                applied = apply_evidence_split(
                    suggestion,
                    bucket_id=repository.bucket_id,
                    source_command=origin.source_command,
                    transaction_repository=repository,
                    bucket_event_repository=events,
                    occurred_at=_NOW,
                )
            assert isinstance(applied, LLMSplitApplyResult)
            catalogue = repository.load()
            children: list[dict[str, object]] = []
            for child_id in applied.child_transaction_ids:
                child = catalogue.get(child_id)
                assert child is not None
                children.append(_child_business_projection(child))
            return children

        return _run

    direct = _run_in_fresh_profile(
        tmp_path / "split-direct", "f6b3236e-cc08-48f3-90f4-6a2dce620f79", _scenario(use_workflow=False)
    )
    workflow = _run_in_fresh_profile(
        tmp_path / "split-workflow", "bd6b0d50-aa23-487d-a27e-eedeb99d2f2f", _scenario(use_workflow=True)
    )

    assert direct == workflow
