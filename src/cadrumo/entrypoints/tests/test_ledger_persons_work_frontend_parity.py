"""Every ledger act on a row the person worked on takes effect alike on the three frontends.

The production registry, its real executors and the real supervisor run over a
stored profile, under a session host that answers for the frontend each
invocation was admitted on. A row the person classified by hand, attached a
document to or linked an invoice to is excluded, derived on, split, archived,
stashed, restored, detached from, linked and reviewed by the same request on
the command line, the terminal interface and external client, with the same stored effect.

What differs by frontend is what the product records about who acted, and
nothing else: an automation's execution stores its session's label and is recorded
as the one who decided a classification it changed, and a person's stores the
label the request carried and is recorded as the person's.

The reviews need a model. The one function that asks it is stood in for, and
everything from the executor to the store is the product's own.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from decimal import Decimal
from itertools import permutations
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...application.ledger import llm_review_execution
from ...application.ledger.attachment_mutation_operation import LedgerAttachRequest, LedgerDetachRequest
from ...application.ledger.classify_requests import LedgerClassifyPatch, LedgerClassifyRequest
from ...application.ledger.lifecycle_contracts import LedgerLifecycleMutationRequest, LedgerLifecycleOperationResult
from ...application.ledger.link_operation import LedgerLinkRequest
from ...application.ledger.llm_classification_ports import (
    LLMClassificationSuggestion,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
)
from ...application.ledger.llm_review_contracts import LedgerLlmReviewRequest
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest
from ...application.ledger.split_operation import (
    LedgerSplitChildRequest,
    LedgerSplitOperationResult,
    LedgerSplitRequest,
)
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.classification_origin import ClassificationOrigin, classification_facts
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from . import registered_executor_case_support as conformance
from .ledger_frontend_parity_test_support import (
    AUTOMATION_LABEL,
    SwitchableSessionHost,
    attach_as_the_person,
    classify_as_the_person,
    resolve_result,
    review_and_apply,
    seed_invoice,
    seed_row,
    seed_row_a_rule_classified,
    seed_stored_attachment,
    stored_events,
    stored_row,
    stored_state,
    submit,
    succeeded,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_EXTERNAL_CLIENT = OperationFrontendProjection.EXTERNAL_CLIENT
_PERSON = ClassificationOrigin.PERSON
_AUTOMATION = ClassificationOrigin.AUTOMATION
_AUTOMATIC = ClassificationOrigin.AUTOMATIC
_BUSINESS = BusinessClassification.BUSINESS
_PROPOSED_BY = "llm:local-text:synthetic"
_TYPED = "typed by the caller"

_Runtime = tuple[conformance._ExecutionDriver, OperationRegistry, UUID, SwitchableSessionHost]
_Act = tuple[str, BaseModel]

_FRONTENDS = pytest.mark.parametrize(
    ("frontend", "recorded", "origin"),
    [(_CLI, _TYPED, _PERSON), (_TUI, _TYPED, _PERSON), (_EXTERNAL_CLIENT, AUTOMATION_LABEL, _AUTOMATION)],
    ids=["cli", "tui", "external_client"],
)
"""Each frontend with the actor label its execution stores and the origin a classification it changes records."""


@contextmanager
def _runtime(tmp_path: Path) -> Generator[_Runtime]:
    """One stored profile and its real runtime; the host starts as the command line's."""
    host = SwitchableSessionHost(_CLI)
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=host
    ) as (driver, registry, profile_id):
        yield driver, registry, profile_id, host


def _lifecycle(definition_id: str, profile_id: UUID, transaction_id: str) -> _Act:
    return definition_id, LedgerLifecycleMutationRequest(
        profile_id=profile_id, transaction_id=transaction_id, actor=_TYPED, reason="synthetic lifecycle act"
    )


def _exclude(profile_id: UUID, transaction_id: str) -> _Act:
    return _lifecycle("ledger.exclude", profile_id, transaction_id)


def _archive(profile_id: UUID, transaction_id: str) -> _Act:
    return _lifecycle("ledger.archive", profile_id, transaction_id)


def _stash(profile_id: UUID, transaction_id: str) -> _Act:
    return _lifecycle("ledger.stash", profile_id, transaction_id)


def _restore(profile_id: UUID, transaction_id: str) -> _Act:
    return _lifecycle("ledger.restore", profile_id, transaction_id)


def _derive(profile_id: UUID, transaction_id: str, category: str = "domestic_general") -> _Act:
    return "ledger.classify.iva-derive", LedgerOperatorIvaRequest(
        profile_id=profile_id, transaction_id=transaction_id, iva_category=category, actor=_TYPED
    )


def _split(profile_id: UUID, transaction_id: str) -> _Act:
    return "ledger.split.manual", LedgerSplitRequest(
        profile_id=profile_id,
        transaction_id=transaction_id,
        children=(
            LedgerSplitChildRequest(amount="100", description="first part"),
            LedgerSplitChildRequest(amount="21", description="second part"),
        ),
        reason="synthetic split",
        actor=_TYPED,
    )


def _attach(profile_id: UUID, transaction_id: str, attachment_id: str) -> _Act:
    return "ledger.attach", LedgerAttachRequest(
        profile_id=profile_id, transaction_id=transaction_id, attachment_ids=(attachment_id,), actor=_TYPED
    )


def _link_purchase_evidence(profile_id: UUID, transaction_id: str, evidence_id: str) -> _Act:
    return "ledger.attach", LedgerAttachRequest(
        profile_id=profile_id, transaction_id=transaction_id, purchase_invoice_evidence_id=evidence_id, actor=_TYPED
    )


def _detach(profile_id: UUID, transaction_id: str, attachment_id: str) -> _Act:
    return "ledger.detach", LedgerDetachRequest(
        profile_id=profile_id, transaction_id=transaction_id, attachment_ids=(attachment_id,), actor=_TYPED
    )


def _link(profile_id: UUID, transaction_id: str, invoice_id: str) -> _Act:
    return "ledger.link", LedgerLinkRequest(
        profile_id=profile_id, transaction_id=transaction_id, invoice_id=invoice_id, actor=_TYPED
    )


def _classify(profile_id: UUID, transaction_id: str, **further: str) -> _Act:
    """A single classification as business, with any further fact it states."""
    values = {"business_classification": _BUSINESS.value, **further}
    return "ledger.classify.single", LedgerClassifyRequest.model_validate(
        {
            "profile_id": profile_id,
            "transaction_id": transaction_id,
            "patch": LedgerClassifyPatch.model_validate(values),
            "patch_fields": tuple(sorted(values)),
            "actor": _TYPED,
        }
    )


def _classify_review(profile_id: UUID, transaction_id: str) -> _Act:
    return "ledger.classify.review", LedgerLlmReviewRequest(
        profile_id=profile_id,
        transaction_id=transaction_id,
        mode="classification",
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        actor=_TYPED,
    )


def _split_review(profile_id: UUID, transaction_id: str) -> _Act:
    return "ledger.split.review", LedgerLlmReviewRequest(
        profile_id=profile_id,
        transaction_id=transaction_id,
        mode="split",
        origin=LlmReviewInvocationOrigin.SPLIT_LLM,
        actor=_TYPED,
    )


def _take_effect(runtime: _Runtime, frontend: OperationFrontendProjection, act: _Act) -> list[BucketEvent]:
    """Run one act as ``frontend``, require that it took effect, and return the events it stored."""
    driver, _registry, profile_id, host = runtime
    definition_id, payload = act
    before = stored_events(profile_id)
    host.frontend = frontend
    observed = submit(driver, definition_id=definition_id, profile_id=profile_id, payload=payload)
    assert succeeded(observed), (definition_id, frontend.value, observed.projection)
    return [event for event_id, event in stored_events(profile_id).items() if event_id not in before]


def _the_model(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stand in for the two functions that hand a row to the model, and record each row they are handed."""
    asked: list[str] = []

    def classify(*, transaction_id: str, **_options: object) -> LLMClassificationSuggestion:
        asked.append(transaction_id)
        return LLMClassificationSuggestion(
            transaction_id=transaction_id,
            provenance=_PROPOSED_BY,
            classification=_BUSINESS,
            confidence=Decimal("0.9000"),
            reason="synthetic proposal",
        )

    def split(*, transaction_id: str, reviewed_transaction: Transaction, **_options: object) -> LLMSplitSuggestion:
        asked.append(transaction_id)
        return LLMSplitSuggestion(
            transaction_id=transaction_id,
            provenance=_PROPOSED_BY,
            reason="synthetic proposal",
            parent_amount=reviewed_transaction.raw.amount,
            children=(
                LLMSplitChildSuggestion(proportion=Decimal("0.5"), amount=Decimal("60.50"), description="1. first"),
                LLMSplitChildSuggestion(proportion=Decimal("0.5"), amount=Decimal("60.50"), description="2. second"),
            ),
        )

    monkeypatch.setattr(llm_review_execution, "suggest_llm_classification", classify)
    monkeypatch.setattr(llm_review_execution, "suggest_evidence_split", split)
    return asked


def _review(runtime: _Runtime, frontend: OperationFrontendProjection, act: _Act) -> bool:
    """Run one review as ``frontend`` and answer its proposal with an apply; say whether it took effect."""
    driver, _registry, profile_id, host = runtime
    definition_id, payload = act
    host.frontend = frontend
    return succeeded(review_and_apply(driver, definition_id=definition_id, profile_id=profile_id, payload=payload))


@_FRONTENDS
def test_every_row_act_takes_effect_on_a_row_the_person_worked_on_whichever_frontend_submits_it(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    recorded: str,
    origin: ClassificationOrigin,
) -> None:
    """Each act is run on its own row, classified by hand and carrying a document the person attached."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime

        def the_persons_row(purpose: str) -> tuple[str, str]:
            row = seed_row(profile_id, operation, description=f"synthetic hand row {purpose}", classification=_BUSINESS)
            attachment = seed_stored_attachment(profile_id, operation, reference=purpose)
            attach_as_the_person(profile_id, operation, transaction_id=row, attachment_id=attachment)
            assert stored_row(profile_id, row, operation).classification_origin is _PERSON
            return row, attachment

        def run(act: _Act) -> None:
            events = _take_effect(runtime, frontend, act)
            assert events and {event.actor for event in events} == {recorded}, act[0]

        row, _attachment = the_persons_row("to exclude")
        run(_exclude(profile_id, row))
        excluded = stored_row(profile_id, row, operation)
        assert excluded.business_classification is BusinessClassification.REVIEWED_EXCLUDED
        assert excluded.classification_origin is origin

        row, _attachment = the_persons_row("to derive on")
        run(_derive(profile_id, row))
        derived = stored_row(profile_id, row, operation)
        assert (derived.taxable_base, derived.iva_amount) == (Decimal("100.00"), Decimal("21.00"))
        assert derived.classified_by == "derived:iva-category"
        assert derived.classification_origin is origin

        row, attachment = the_persons_row("to detach from")
        run(_detach(profile_id, row, attachment))
        detached = stored_row(profile_id, row, operation)
        assert detached.attachment_ids == ()
        assert detached.classification_origin is _PERSON

        row, attachment = the_persons_row("to split")
        run(_split(profile_id, row))
        parent = stored_row(profile_id, row, operation)
        assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
        assert parent.attachment_ids == (attachment,)
        assert parent.classification_origin is _PERSON

        for set_aside, state in (
            (_archive, TransactionLifecycleState.ARCHIVED),
            (_stash, TransactionLifecycleState.STASHED),
        ):
            row, _attachment = the_persons_row(f"to leave {state.value}")
            run(set_aside(profile_id, row))
            aside = stored_row(profile_id, row, operation)
            assert aside.lifecycle_state is state
            assert aside.lifecycle_lineage[-1].actor == recorded
            run(_restore(profile_id, row))
            assert stored_row(profile_id, row, operation).lifecycle_state is TransactionLifecycleState.ACTIVE

        row, _attachment = the_persons_row("to link")
        first = seed_invoice(profile_id, number="SYNTHETIC-1")
        second = seed_invoice(profile_id, number="SYNTHETIC-2")
        run(_link(profile_id, row, first))
        assert stored_row(profile_id, row, operation).invoice_id == first
        run(_link(profile_id, row, second))
        assert stored_row(profile_id, row, operation).invoice_id == second
        run(_exclude(profile_id, row))

        row, _attachment = the_persons_row("to take figures from an invoice")
        evidence = seed_invoice(profile_id, number="SYNTHETIC-3")
        run(_link_purchase_evidence(profile_id, row, evidence))
        linked = stored_row(profile_id, row, operation)
        assert linked.purchase_invoice_evidence_id == evidence
        assert linked.classification_origin is origin


def test_a_row_set_aside_on_one_frontend_is_archived_and_restored_on_any_other(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The row records who ran each archive, stash and restore, and none of them is refused for that record."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        for index, (first, second) in enumerate(permutations((_CLI, _TUI, _EXTERNAL_CLIENT), 2)):
            for set_aside in (_archive, _stash):
                row = seed_row(
                    profile_id,
                    operation,
                    description=f"synthetic hand row {index} for {set_aside.__name__}",
                    classification=_BUSINESS,
                )
                _take_effect(runtime, first, set_aside(profile_id, row))
                _take_effect(runtime, second, _restore(profile_id, row))
                assert stored_row(profile_id, row, operation).lifecycle_state is TransactionLifecycleState.ACTIVE

            stashed = seed_row(profile_id, operation, description=f"synthetic hand row {index} stashed then archived")
            _take_effect(runtime, first, _stash(profile_id, stashed))
            _take_effect(runtime, second, _archive(profile_id, stashed))
            assert stored_row(profile_id, stashed, operation).lifecycle_state is TransactionLifecycleState.ARCHIVED
            _take_effect(runtime, first, _restore(profile_id, stashed))
            assert stored_row(profile_id, stashed, operation).lifecycle_state is TransactionLifecycleState.ACTIVE


_REVIEWS: tuple[tuple[str, Callable[[UUID, str], _Act]], ...] = (
    ("ledger.classify.review", _classify_review),
    ("ledger.split.review", _split_review),
)


@pytest.mark.parametrize(("definition_id", "review"), _REVIEWS, ids=[definition_id for definition_id, _ in _REVIEWS])
@pytest.mark.parametrize("seeded", ["unprocessed", "classified-by-the-person"])
@_FRONTENDS
def test_a_review_run_to_its_commit_stores_the_session_label_for_an_automation_and_the_typed_label_for_a_person(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    review: Callable[[UUID, str], _Act],
    seeded: str,
    frontend: OperationFrontendProjection,
    recorded: str,
    origin: ClassificationOrigin,
) -> None:
    """The model is asked once and the proposal commits on every frontend, on the person's own row as on any other.

    Every event the commit stored names the party who answered, and each classified row records whose it is.
    """
    asked = _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(
            profile_id,
            operation,
            description="synthetic row to review",
            classification=(
                BusinessClassification.NOT_YET_PROCESSED if seeded == "unprocessed" else BusinessClassification.PERSONAL
            ),
        )
        events_before = stored_events(profile_id)
        rows_before, _events = stored_state(profile_id, operation)

        assert _review(runtime, frontend, review(profile_id, row))

        assert asked == [row]
        committed = [event for event_id, event in stored_events(profile_id).items() if event_id not in events_before]
        assert committed
        assert {event.actor for event in committed} == {recorded}
        rows_after, _events = stored_state(profile_id, operation)
        if definition_id == "ledger.classify.review":
            classified = [rows_after[row]]
        else:
            assert rows_after[row].lifecycle_state is TransactionLifecycleState.SPLIT
            assert rows_after[row].lifecycle_lineage[-1].actor == recorded
            classified = [child for child_id, child in rows_after.items() if child_id not in rows_before]
            assert len(classified) == 2
            assert {child.created_by for child in classified} == {recorded}
        for stored in classified:
            assert stored.business_classification is _BUSINESS
            assert stored.classified_by == _PROPOSED_BY
            assert stored.classification_origin is origin


def test_a_review_whose_row_was_classified_while_its_proposal_waited_settles_alike_on_every_frontend(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The commit is held to the row the proposal was made for, whoever answers it, and the later decision stands."""
    _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        driver, _registry, profile_id, host = runtime
        outcomes: dict[OperationFrontendProjection, tuple[OperationTerminalCondition | None, OperationEffect]] = {}
        for frontend in (_CLI, _TUI, _EXTERNAL_CLIENT):
            row = seed_row(profile_id, operation, description=f"synthetic row reviewed on {frontend.value}")
            after_the_person: list[tuple[dict[str, Transaction], dict[str, BucketEvent]]] = []

            def the_person_classifies(
                row: str = row, after: list[tuple[dict[str, Transaction], dict[str, BucketEvent]]] = after_the_person
            ) -> None:
                classify_as_the_person(
                    profile_id, operation, transaction_id=row, classification=BusinessClassification.PERSONAL
                )
                after.append(stored_state(profile_id, operation))

            host.frontend = frontend
            definition_id, payload = _classify_review(profile_id, row)
            settled = review_and_apply(
                driver,
                definition_id=definition_id,
                profile_id=profile_id,
                payload=payload,
                while_pending=the_person_classifies,
            )

            assert not succeeded(settled), settled.projection
            assert [stored_state(profile_id, operation)] == after_the_person
            kept = stored_row(profile_id, row, operation)
            assert kept.business_classification is BusinessClassification.PERSONAL
            assert kept.classification_origin is _PERSON
            outcomes[frontend] = (settled.projection.terminal_condition, settled.projection.effect)

        assert len(set(outcomes.values())) == 1, outcomes


_BY_ANOTHER_PARTY = pytest.mark.parametrize("party", ["rule", "automation-review", "automation-derivation"])


def _row_another_party_classified(
    runtime: _Runtime, operation: PinnedAuthorityOperation, party: str
) -> tuple[str, ClassificationOrigin]:
    """Store a business row a rule classified, or one an automation then decided through a review or a derivation."""
    _driver, _registry, profile_id, _host = runtime
    if party == "automation-review":
        row = seed_row(profile_id, operation, description="synthetic unprocessed row")
        assert _review(runtime, _EXTERNAL_CLIENT, _classify_review(profile_id, row))
        return row, _AUTOMATION
    row = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
    if party == "rule":
        return row, _AUTOMATIC
    _take_effect(runtime, _EXTERNAL_CLIENT, _derive(profile_id, row))
    return row, _AUTOMATION


@_BY_ANOTHER_PARTY
@pytest.mark.parametrize("confirmed_on", [_CLI, _TUI], ids=["cli", "tui"])
def test_a_person_confirming_a_classification_with_the_same_value_is_recorded_as_having_decided_it(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    party: str,
    confirmed_on: OperationFrontendProjection,
) -> None:
    """Submitting what the row already says is the person accepting it, and the store records that it was.

    The record closes the row to nobody: an automation then derives on it, and is recorded for what it changed.
    """
    _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row, decided_by = _row_another_party_classified(runtime, operation, party)
        given = stored_row(profile_id, row, operation)
        assert given.classification_origin is decided_by

        recorded = _take_effect(runtime, confirmed_on, _classify(profile_id, row))

        confirmed = stored_row(profile_id, row, operation)
        assert classification_facts(confirmed) == classification_facts(given)
        assert confirmed.classification_origin is _PERSON
        assert {event.actor for event in recorded} == {_TYPED}
        assert BucketEventType.LEDGER_TRANSACTION_CLASSIFIED in {event.event_type for event in recorded}

        _take_effect(runtime, _EXTERNAL_CLIENT, _derive(profile_id, row, "domestic_reduced"))
        assert stored_row(profile_id, row, operation).classification_origin is _AUTOMATION


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("counterparty_country", "DE"),
        ("counterparty_identification_state", "DE"),
        ("deduction_fact_kind", "domestic_current"),
        ("investment_asset_id", "bi-0001"),
    ],
)
def test_a_person_completing_an_automations_classification_with_one_further_fact_is_recorded_as_having_decided_it(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    """The class is restated and one fact that bears on the tax is added: the row records the person."""
    _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row, _decided_by = _row_another_party_classified(runtime, operation, "automation-review")

        _take_effect(runtime, _CLI, _classify(profile_id, row, **{field: value}))

        completed = stored_row(profile_id, row, operation)
        assert getattr(completed, field) is not None
        assert completed.classification_origin is _PERSON


def test_an_attachment_changes_the_last_writers_stamp_and_not_whose_classification_it_is_on_any_frontend(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Attaching rewrites the row and leaves the hand stamp on it, on a rule's row and on the person's alike."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        by_rule = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
        by_hand = seed_row(profile_id, operation, description="synthetic hand row", classification=_BUSINESS)

        for frontend in (_CLI, _TUI, _EXTERNAL_CLIENT):
            for row in (by_rule, by_hand):
                attachment = seed_stored_attachment(profile_id, operation, reference=f"{frontend.value}-{row[:8]}")
                _take_effect(runtime, frontend, _attach(profile_id, row, attachment))
                assert stored_row(profile_id, row, operation).classified_by == "manual"

            assert stored_row(profile_id, by_rule, operation).classification_origin is _AUTOMATIC
            assert stored_row(profile_id, by_hand, operation).classification_origin is _PERSON


def test_an_exclusion_and_a_split_of_the_persons_row_return_the_same_result_on_every_frontend(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The settled result says what the act replaced and how it is put back, and says it to every caller."""
    with _runtime(tmp_path) as runtime:
        driver, registry, profile_id, host = runtime
        exclusions: dict[OperationFrontendProjection, object] = {}
        splits: dict[OperationFrontendProjection, object] = {}
        for frontend in (_CLI, _TUI, _EXTERNAL_CLIENT):
            host.frontend = frontend
            for purpose, act in (("exclude", _exclude), ("split", _split)):
                row = seed_row(
                    profile_id,
                    operation,
                    description=f"synthetic hand row to {purpose} on {frontend.value}",
                    classification=_BUSINESS,
                )
                definition_id, payload = act(profile_id, row)
                observed = submit(driver, definition_id=definition_id, profile_id=profile_id, payload=payload)
                assert succeeded(observed), (definition_id, frontend.value, observed.projection)
                if purpose == "exclude":
                    excluded = resolve_result(
                        driver,
                        registry,
                        definition_id=definition_id,
                        observed=observed,
                        result_type=LedgerLifecycleOperationResult,
                    )
                    assert excluded.result is not None
                    exclusions[frontend] = (excluded.outcome, excluded.result.replaced, excluded.result.review_status)
                else:
                    split = resolve_result(
                        driver,
                        registry,
                        definition_id=definition_id,
                        observed=observed,
                        result_type=LedgerSplitOperationResult,
                    )
                    splits[frontend] = (
                        split.parent_business_classification,
                        split.child_business_classification,
                        split.remerged_by,
                        len(split.child_transaction_ids),
                    )

        assert exclusions[_CLI] == exclusions[_TUI] == exclusions[_EXTERNAL_CLIENT]
        assert splits[_CLI] == splits[_TUI] == splits[_EXTERNAL_CLIENT]
