"""An agent's execution leaves a ledger row's classification alone once the person decided it.

The production registry, its real executors and the real supervisor run over a
stored profile, under a session host that answers for the frontend each
invocation was admitted on. Whose decision a row's classification is is
recorded on the row and does not depend on which operation wrote it last, and
one rule is held on every route an agent has to a row: derivation, exclusion,
the manual split, the two model-backed reviews, the invoice link and the
detachment. A refused act settles as a refusal with no effect and leaves every
stored row and event as it was. The same act succeeds for an agent on a row
that is unprocessed or that a rule or an agent classified, and for the
command line on the person's own row.

The reviews need a model. The one function that asks it is stood in for, and
everything from the executor to the store is the product's own.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...application.ledger import llm_review_execution
from ...application.ledger.attachment_mutation_operation import LedgerAttachRequest, LedgerDetachRequest
from ...application.ledger.classify_requests import LedgerClassifyPatch, LedgerClassifyRequest
from ...application.ledger.lifecycle_contracts import LedgerLifecycleMutationRequest
from ...application.ledger.link_operation import LedgerLinkRequest
from ...application.ledger.llm_classification_ports import (
    LLMClassificationSuggestion,
    LLMSplitChildSuggestion,
    LLMSplitSuggestion,
)
from ...application.ledger.llm_review_contracts import LedgerLlmReviewRequest
from ...application.ledger.llm_review_workflow import LlmReviewInvocationOrigin
from ...application.ledger.operator_iva_contracts import LedgerOperatorIvaRequest
from ...application.ledger.split_operation import LedgerSplitChildRequest, LedgerSplitRequest
from ...application.operations.registry import OperationFrontendProjection, OperationRegistry
from ...domain.buckets.event import BucketEvent, BucketEventType
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.transactions.classification_origin import (
    ClassificationOrigin,
    classification_facts,
    resolved_classification_origin,
)
from ...domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from . import test_registered_executor_conformance as conformance
from .ledger_persons_work_test_support import (
    AGENT_LABEL,
    PERSON_LABEL,
    SwitchableSessionHost,
    attach_as_the_person,
    classify_as_the_person,
    refused_for_the_frontend,
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
_MCP = OperationFrontendProjection.MCP
_PERSON = ClassificationOrigin.PERSON
_AGENT = ClassificationOrigin.AGENT
_AUTOMATIC = ClassificationOrigin.AUTOMATIC
_BUSINESS = BusinessClassification.BUSINESS
_PROPOSED_BY = "llm:local-text:synthetic"
_TYPED = "typed by the caller"

_Runtime = tuple[conformance._ExecutionDriver, OperationRegistry, UUID, SwitchableSessionHost]


@contextmanager
def _runtime(tmp_path: Path) -> Generator[_Runtime]:
    """One stored profile and its real runtime; the host starts as the command line's."""
    host = SwitchableSessionHost(_CLI)
    with conformance._runtime(
        tmp_path / "runtime", cleanup=conformance._CloseWitness(), execution_caller_reader=host
    ) as (driver, registry, profile_id):
        yield driver, registry, profile_id, host


def _exclude(profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
    return "ledger.exclude", LedgerLifecycleMutationRequest(
        profile_id=profile_id, transaction_id=transaction_id, actor=_TYPED, reason="synthetic exclusion"
    )


def _lifecycle(definition_id: str, profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
    return definition_id, LedgerLifecycleMutationRequest(
        profile_id=profile_id, transaction_id=transaction_id, actor=_TYPED, reason="synthetic lifecycle act"
    )


def _archive(profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
    return _lifecycle("ledger.archive", profile_id, transaction_id)


def _stash(profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
    return _lifecycle("ledger.stash", profile_id, transaction_id)


def _restore(profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
    return _lifecycle("ledger.restore", profile_id, transaction_id)


def _derive(profile_id: UUID, transaction_id: str, category: str = "domestic_general") -> tuple[str, BaseModel]:
    return "ledger.classify.iva-derive", LedgerOperatorIvaRequest(
        profile_id=profile_id, transaction_id=transaction_id, iva_category=category, actor=_TYPED
    )


def _split(profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
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


def _attach(profile_id: UUID, transaction_id: str, attachment_id: str) -> tuple[str, BaseModel]:
    return "ledger.attach", LedgerAttachRequest(
        profile_id=profile_id, transaction_id=transaction_id, attachment_ids=(attachment_id,), actor=_TYPED
    )


def _detach(profile_id: UUID, transaction_id: str, attachment_id: str) -> tuple[str, BaseModel]:
    return "ledger.detach", LedgerDetachRequest(
        profile_id=profile_id, transaction_id=transaction_id, attachment_ids=(attachment_id,), actor=_TYPED
    )


def _link(profile_id: UUID, transaction_id: str, invoice_id: str) -> tuple[str, BaseModel]:
    return "ledger.link", LedgerLinkRequest(
        profile_id=profile_id, transaction_id=transaction_id, invoice_id=invoice_id, actor=_TYPED
    )


def _classify_review(profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
    return "ledger.classify.review", LedgerLlmReviewRequest(
        profile_id=profile_id,
        transaction_id=transaction_id,
        mode="classification",
        origin=LlmReviewInvocationOrigin.CLASSIFY_LLM_APPLY,
        actor=_TYPED,
    )


def _split_review(profile_id: UUID, transaction_id: str) -> tuple[str, BaseModel]:
    return "ledger.split.review", LedgerLlmReviewRequest(
        profile_id=profile_id,
        transaction_id=transaction_id,
        mode="split",
        origin=LlmReviewInvocationOrigin.SPLIT_LLM,
        actor=_TYPED,
    )


def _act(runtime: _Runtime, frontend: OperationFrontendProjection, act: tuple[str, BaseModel]) -> bool:
    """Run one act as ``frontend`` and say whether it took effect; a refusal must be the frontend's."""
    driver, _registry, profile_id, host = runtime
    definition_id, payload = act
    host.frontend = frontend
    observed = submit(driver, definition_id=definition_id, profile_id=profile_id, payload=payload)
    if succeeded(observed):
        return True
    assert refused_for_the_frontend(observed), observed.projection
    return False


def _refused_and_nothing_changed(
    runtime: _Runtime, operation: PinnedAuthorityOperation, act: tuple[str, BaseModel]
) -> bool:
    """Run one act as an agent, and say whether it was refused with every row and event left as it was."""
    _driver, _registry, profile_id, _host = runtime
    before = stored_state(profile_id, operation)
    took_effect = _act(runtime, _MCP, act)
    return not took_effect and stored_state(profile_id, operation) == before


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


def _review(runtime: _Runtime, frontend: OperationFrontendProjection, act: tuple[str, BaseModel]) -> bool:
    """Run one review as ``frontend`` and answer its proposal with an apply; say whether it took effect."""
    driver, _registry, profile_id, host = runtime
    definition_id, payload = act
    host.frontend = frontend
    return succeeded(review_and_apply(driver, definition_id=definition_id, profile_id=profile_id, payload=payload))


@pytest.mark.parametrize("work", ["classification", "attachment"])
def test_an_agents_exclusion_of_a_row_carrying_the_persons_work_is_refused_and_the_command_lines_is_not(
    tmp_path: Path, operation: PinnedAuthorityOperation, work: str
) -> None:
    """An exclusion replaces the classification, and only an operation closed to an agent puts it back."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        if work == "classification":
            row = seed_row(profile_id, operation, description="synthetic hand row", classification=_BUSINESS)
            assert stored_row(profile_id, row, operation).classification_origin is _PERSON
        else:
            row = seed_row(profile_id, operation, description="synthetic row with the person's document")
            attachment = seed_stored_attachment(profile_id, operation, reference="exclusion")
            attach_as_the_person(profile_id, operation, transaction_id=row, attachment_id=attachment)
            assert stored_row(profile_id, row, operation).classification_origin is None

        assert _refused_and_nothing_changed(runtime, operation, _exclude(profile_id, row))

        assert _act(runtime, _CLI, _exclude(profile_id, row))
        excluded = stored_row(profile_id, row, operation)
        assert excluded.business_classification is BusinessClassification.REVIEWED_EXCLUDED
        assert excluded.classification_origin is _PERSON


def test_an_agent_excludes_an_unprocessed_row_and_a_row_a_rule_classified_and_keeps_what_it_then_decided(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """What an agent decided stays open to an agent: it splits the row it excluded."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        unprocessed = seed_row(profile_id, operation, description="synthetic unprocessed row")
        by_rule = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
        assert stored_row(profile_id, by_rule, operation).classification_origin is _AUTOMATIC

        for row in (unprocessed, by_rule):
            assert _act(runtime, _MCP, _exclude(profile_id, row))
            excluded = stored_row(profile_id, row, operation)
            assert excluded.business_classification is BusinessClassification.REVIEWED_EXCLUDED
            # The exclusion leaves the hand stamp, and the row records that an agent decided it.
            assert excluded.classified_by == "manual"
            assert excluded.classification_origin is _AGENT

        assert _act(runtime, _MCP, _split(profile_id, unprocessed))
        assert stored_row(profile_id, unprocessed, operation).lifecycle_state is TransactionLifecycleState.SPLIT


def test_an_agents_derivation_on_a_row_the_person_classified_is_refused_and_the_command_lines_is_not(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A derivation replaces the IVA category, rate, base and cuota of the row."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic hand row", classification=_BUSINESS)

        assert _refused_and_nothing_changed(runtime, operation, _derive(profile_id, row))

        assert _act(runtime, _CLI, _derive(profile_id, row))
        derived = stored_row(profile_id, row, operation)
        assert (derived.taxable_base, derived.iva_amount) == (Decimal("100.00"), Decimal("21.00"))
        assert derived.classified_by == "derived:iva-category"
        assert derived.classification_origin is _PERSON


def test_an_agent_derives_on_a_row_a_rule_classified_and_again_on_the_row_it_then_decided(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")

        assert _act(runtime, _MCP, _derive(profile_id, row))
        first = stored_row(profile_id, row, operation)
        assert (first.taxable_base, first.iva_amount) == (Decimal("100.00"), Decimal("21.00"))
        assert first.classification_origin is _AGENT

        assert _act(runtime, _MCP, _derive(profile_id, row, "domestic_reduced"))
        second = stored_row(profile_id, row, operation)
        assert second.taxable_base == Decimal("110.00")
        assert second.classification_origin is _AGENT


def test_deriving_then_splitting_does_not_take_a_hand_classified_row_from_the_person(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A derivation replaces the stamp a hand classification leaves, and the row stays the person's."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic hand row", classification=_BUSINESS)
        before = stored_state(profile_id, operation)

        assert not _act(runtime, _MCP, _derive(profile_id, row))
        assert not _act(runtime, _MCP, _split(profile_id, row))

        assert stored_state(profile_id, operation) == before
        assert stored_row(profile_id, row, operation).classified_by == "manual"


def test_a_row_whose_figures_the_person_derived_is_the_persons_whatever_stamp_the_derivation_left(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Running a derivation is the person's decision as much as typing the figures is."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
        assert _act(runtime, _CLI, _derive(profile_id, row))
        derived = stored_row(profile_id, row, operation)
        assert derived.classified_by == "derived:iva-category"
        assert derived.classification_origin is _PERSON

        for act in (_derive(profile_id, row, "domestic_reduced"), _exclude(profile_id, row), _split(profile_id, row)):
            assert _refused_and_nothing_changed(runtime, operation, act), act[0]

        assert _act(runtime, _CLI, _split(profile_id, row))


def test_an_agents_attachment_changes_the_last_writers_stamp_and_not_whose_classification_it_is(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """Attaching rewrites the row and leaves the hand stamp on it, on a rule's row and on the person's alike."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        by_rule = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
        by_hand = seed_row(profile_id, operation, description="synthetic hand row", classification=_BUSINESS)
        for index, row in enumerate((by_rule, by_hand)):
            attachment = seed_stored_attachment(profile_id, operation, reference=f"attachment-{index}")
            assert _act(runtime, _MCP, _attach(profile_id, row, attachment))
            assert stored_row(profile_id, row, operation).classified_by == "manual"

        assert stored_row(profile_id, by_rule, operation).classification_origin is _AUTOMATIC
        assert stored_row(profile_id, by_hand, operation).classification_origin is _PERSON
        # The rule's row is still open to an agent, with the attachment the agent itself linked.
        assert _act(runtime, _MCP, _derive(profile_id, by_rule))
        assert _act(runtime, _MCP, _split(profile_id, by_rule))
        for act in (_derive(profile_id, by_hand), _exclude(profile_id, by_hand), _split(profile_id, by_hand)):
            assert _refused_and_nothing_changed(runtime, operation, act), act[0]


def test_detaching_then_splitting_does_not_take_the_persons_attachment_from_a_row(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """An agent detaches what an agent attached, so it cannot clear the way to a split it is refused."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic row with the person's document")
        the_persons = seed_stored_attachment(profile_id, operation, reference="the-persons")
        attach_as_the_person(profile_id, operation, transaction_id=row, attachment_id=the_persons)
        the_agents = seed_stored_attachment(profile_id, operation, reference="the-agents")
        assert _act(runtime, _MCP, _attach(profile_id, row, the_agents))
        provenance = stored_row(profile_id, row, operation).evidence_provenance
        assert {entry.evidence_id: entry.actor for entry in provenance} == {
            the_persons: PERSON_LABEL,
            the_agents: AGENT_LABEL,
        }

        assert _refused_and_nothing_changed(runtime, operation, _detach(profile_id, row, the_persons))
        assert _refused_and_nothing_changed(runtime, operation, _split(profile_id, row))

        assert _act(runtime, _MCP, _detach(profile_id, row, the_agents))
        assert stored_row(profile_id, row, operation).attachment_ids == (the_persons,)
        assert _refused_and_nothing_changed(runtime, operation, _split(profile_id, row))

        assert _act(runtime, _CLI, _detach(profile_id, row, the_persons))
        assert stored_row(profile_id, row, operation).attachment_ids == ()
        assert _act(runtime, _MCP, _split(profile_id, row))


def test_an_agent_splits_a_row_whose_only_attachment_it_linked_itself(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic unprocessed row")
        attachment = seed_stored_attachment(profile_id, operation, reference="the-agents")
        assert _act(runtime, _MCP, _attach(profile_id, row, attachment))

        assert _act(runtime, _MCP, _split(profile_id, row))

        parent = stored_row(profile_id, row, operation)
        assert parent.lifecycle_state is TransactionLifecycleState.SPLIT
        assert parent.attachment_ids == (attachment,)


def test_an_agents_link_does_not_replace_the_invoice_a_row_already_links_and_the_command_lines_does(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """A link overwrites the row's invoice, and the row does not record who linked the earlier one."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic unprocessed row")
        first = seed_invoice(profile_id, number="SYNTHETIC-1")
        second = seed_invoice(profile_id, number="SYNTHETIC-2")

        assert _act(runtime, _MCP, _link(profile_id, row, first))
        assert stored_row(profile_id, row, operation).invoice_id == first

        assert _refused_and_nothing_changed(runtime, operation, _link(profile_id, row, second))
        # The link, whoever made it, also keeps an agent from setting the row aside.
        assert _refused_and_nothing_changed(runtime, operation, _split(profile_id, row))
        assert _refused_and_nothing_changed(runtime, operation, _exclude(profile_id, row))

        assert _act(runtime, _CLI, _link(profile_id, row, second))
        assert stored_row(profile_id, row, operation).invoice_id == second


_REVIEWS: tuple[tuple[str, Callable[[UUID, str], tuple[str, BaseModel]]], ...] = (
    ("ledger.classify.review", _classify_review),
    ("ledger.split.review", _split_review),
)


@pytest.mark.parametrize(("definition_id", "review"), _REVIEWS, ids=[definition_id for definition_id, _ in _REVIEWS])
@pytest.mark.parametrize(
    ("frontend", "recorded", "origin"), [(_MCP, AGENT_LABEL, _AGENT), (_CLI, _TYPED, _PERSON)], ids=["mcp", "cli"]
)
def test_a_review_run_to_its_commit_stores_the_session_label_for_an_agent_and_the_typed_label_for_a_person(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    review: Callable[[UUID, str], tuple[str, BaseModel]],
    frontend: OperationFrontendProjection,
    recorded: str,
    origin: ClassificationOrigin,
) -> None:
    """Every event the commit stored names the party who answered, and each classified row records whose it is."""
    asked = _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic unprocessed row")
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


@pytest.mark.parametrize(("definition_id", "review"), _REVIEWS, ids=[definition_id for definition_id, _ in _REVIEWS])
def test_an_agents_review_of_a_row_the_person_classified_never_reaches_the_model_and_the_command_lines_commits(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    definition_id: str,
    review: Callable[[UUID, str], tuple[str, BaseModel]],
) -> None:
    """The agent that submits a review also answers it, so the refusal comes before the proposal exists."""
    asked = _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(
            profile_id, operation, description="synthetic hand row", classification=BusinessClassification.PERSONAL
        )

        assert _refused_and_nothing_changed(runtime, operation, review(profile_id, row))
        assert asked == []

        assert _review(runtime, _CLI, review(profile_id, row))
        assert asked == [row]
        replaced = stored_row(profile_id, row, operation)
        if definition_id == "ledger.classify.review":
            assert replaced.business_classification is _BUSINESS
            assert replaced.classification_origin is _PERSON
        else:
            assert replaced.lifecycle_state is TransactionLifecycleState.SPLIT


def test_a_classification_the_person_accepted_from_a_model_is_the_persons_and_an_agent_does_not_replace_it(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row carries the model's stamp, and no hand stamp, yet the decision to accept it was the person's."""
    asked = _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic unprocessed row")
        assert _review(runtime, _CLI, _classify_review(profile_id, row))
        accepted = stored_row(profile_id, row, operation)
        assert accepted.classified_by == _PROPOSED_BY
        assert resolved_classification_origin(accepted) is _PERSON
        asked.clear()

        for act in (
            _derive(profile_id, row),
            _exclude(profile_id, row),
            _split(profile_id, row),
            _classify_review(profile_id, row),
            _split_review(profile_id, row),
        ):
            assert _refused_and_nothing_changed(runtime, operation, act), act[0]
        assert asked == []


def test_an_agent_acts_again_on_a_row_it_classified_through_a_review(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A proposal an agent accepted is the agent's decision, and stays open to an agent on every route."""
    _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row = seed_row(profile_id, operation, description="synthetic unprocessed row")
        assert _review(runtime, _MCP, _classify_review(profile_id, row))
        assert stored_row(profile_id, row, operation).classification_origin is _AGENT

        assert _act(runtime, _MCP, _derive(profile_id, row))
        assert stored_row(profile_id, row, operation).classification_origin is _AGENT
        assert _act(runtime, _MCP, _exclude(profile_id, row))
        assert _review(runtime, _MCP, _split_review(profile_id, row))
        assert stored_row(profile_id, row, operation).lifecycle_state is TransactionLifecycleState.SPLIT


_BY_ANOTHER_PARTY = pytest.mark.parametrize("party", ["rule", "agent-review", "agent-derivation"])


def _row_another_party_classified(
    runtime: _Runtime, operation: PinnedAuthorityOperation, party: str
) -> tuple[str, ClassificationOrigin]:
    """Store a business row a rule classified, or one an agent then decided through a review or a derivation."""
    _driver, _registry, profile_id, _host = runtime
    if party == "agent-review":
        row = seed_row(profile_id, operation, description="synthetic unprocessed row")
        assert _review(runtime, _MCP, _classify_review(profile_id, row))
        return row, _AGENT
    row = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
    if party == "rule":
        return row, _AUTOMATIC
    assert _act(runtime, _MCP, _derive(profile_id, row))
    return row, _AGENT


def _classify(profile_id: UUID, transaction_id: str, **further: str) -> tuple[str, BaseModel]:
    """The person's single classification as business, with any further fact it states."""
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


@_BY_ANOTHER_PARTY
def test_a_person_confirming_a_classification_with_the_same_value_owns_it_and_an_agent_no_longer_replaces_it(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, party: str
) -> None:
    """Submitting what the row already says is the person accepting it, and the store records that it was."""
    asked = _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row, decided_by = _row_another_party_classified(runtime, operation, party)
        given = stored_row(profile_id, row, operation)
        assert given.classification_origin is decided_by
        events_before = stored_events(profile_id)
        asked.clear()

        assert _act(runtime, _CLI, _classify(profile_id, row))

        confirmed = stored_row(profile_id, row, operation)
        assert classification_facts(confirmed) == classification_facts(given)
        assert confirmed.classification_origin is _PERSON
        recorded = [event for event_id, event in stored_events(profile_id).items() if event_id not in events_before]
        assert {event.actor for event in recorded} == {_TYPED}
        assert BucketEventType.LEDGER_TRANSACTION_CLASSIFIED in {event.event_type for event in recorded}
        for act in (
            _derive(profile_id, row, "domestic_reduced"),
            _exclude(profile_id, row),
            _split(profile_id, row),
            _archive(profile_id, row),
            _classify_review(profile_id, row),
            _split_review(profile_id, row),
        ):
            assert _refused_and_nothing_changed(runtime, operation, act), act[0]
        assert asked == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("counterparty_country", "DE"),
        ("counterparty_identification_state", "DE"),
        ("deduction_fact_kind", "domestic_current"),
        ("investment_asset_id", "bi-0001"),
    ],
)
def test_a_person_completing_an_agents_classification_with_one_further_fact_owns_it(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    """The class is restated and one fact that bears on the tax is added: the row is the person's."""
    _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        row, _decided_by = _row_another_party_classified(runtime, operation, "agent-review")

        assert _act(runtime, _CLI, _classify(profile_id, row, **{field: value}))

        completed = stored_row(profile_id, row, operation)
        assert getattr(completed, field) is not None
        assert completed.classification_origin is _PERSON
        for act in (_exclude(profile_id, row), _split(profile_id, row), _derive(profile_id, row)):
            assert _refused_and_nothing_changed(runtime, operation, act), act[0]


def test_a_review_an_agent_started_does_not_commit_over_a_classification_the_person_made_meanwhile(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stored row is read at the commit, before any effect is declared, so the answer settles as a refusal."""
    _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        driver, _registry, profile_id, host = runtime
        row = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
        after_the_person: list[tuple[dict[str, Transaction], dict[str, BucketEvent]]] = []

        def the_person_classifies() -> None:
            classify_as_the_person(
                profile_id, operation, transaction_id=row, classification=BusinessClassification.PERSONAL
            )
            after_the_person.append(stored_state(profile_id, operation))

        host.frontend = _MCP
        definition_id, payload = _classify_review(profile_id, row)
        settled = review_and_apply(
            driver,
            definition_id=definition_id,
            profile_id=profile_id,
            payload=payload,
            while_pending=the_person_classifies,
        )

        assert refused_for_the_frontend(settled), settled.projection
        assert [stored_state(profile_id, operation)] == after_the_person
        kept = stored_row(profile_id, row, operation)
        assert kept.business_classification is BusinessClassification.PERSONAL
        assert kept.classification_origin is _PERSON


_SET_ASIDE = pytest.mark.parametrize(
    ("set_aside", "state"),
    [(_archive, TransactionLifecycleState.ARCHIVED), (_stash, TransactionLifecycleState.STASHED)],
    ids=["archive", "stash"],
)


@_SET_ASIDE
@pytest.mark.parametrize("work", ["classification", "attachment", "invoice"])
def test_an_agent_does_not_archive_or_stash_a_row_carrying_the_persons_work_and_the_command_line_does(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    set_aside: Callable[[UUID, str], tuple[str, BaseModel]],
    state: TransactionLifecycleState,
    work: str,
) -> None:
    """A row set aside leaves every calculation, and an agent may run a calculation."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        if work == "classification":
            row = seed_row(profile_id, operation, description="synthetic hand row", classification=_BUSINESS)
        else:
            row = seed_row(profile_id, operation, description="synthetic row with the person's work")
            if work == "attachment":
                attachment = seed_stored_attachment(profile_id, operation, reference="set-aside")
                attach_as_the_person(profile_id, operation, transaction_id=row, attachment_id=attachment)
            else:
                assert _act(runtime, _CLI, _link(profile_id, row, seed_invoice(profile_id, number="SYNTHETIC-1")))

        assert _refused_and_nothing_changed(runtime, operation, set_aside(profile_id, row))

        assert _act(runtime, _CLI, set_aside(profile_id, row))
        assert stored_row(profile_id, row, operation).lifecycle_state is state
        # The person set it aside, so bringing it back is the person's to do.
        assert _refused_and_nothing_changed(runtime, operation, _restore(profile_id, row))
        assert _act(runtime, _CLI, _restore(profile_id, row))
        assert stored_row(profile_id, row, operation).lifecycle_state is TransactionLifecycleState.ACTIVE


@_SET_ASIDE
def test_an_agent_archives_stashes_and_restores_a_row_that_is_unprocessed_or_its_own(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
    set_aside: Callable[[UUID, str], tuple[str, BaseModel]],
    state: TransactionLifecycleState,
) -> None:
    _the_model(monkeypatch)
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        unprocessed = seed_row(profile_id, operation, description="synthetic unprocessed row")
        by_rule = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
        its_own, _decided_by = _row_another_party_classified(runtime, operation, "agent-review")

        for row in (unprocessed, by_rule, its_own):
            assert _act(runtime, _MCP, set_aside(profile_id, row))
            aside = stored_row(profile_id, row, operation)
            assert aside.lifecycle_state is state
            assert aside.lifecycle_lineage[-1].actor == AGENT_LABEL

            assert _act(runtime, _MCP, _restore(profile_id, row))
            assert stored_row(profile_id, row, operation).lifecycle_state is TransactionLifecycleState.ACTIVE


def test_an_agent_restores_what_an_agent_set_aside_and_not_what_the_person_did(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    """The row records who ran each archive, stash and restore; the last one set the state the row is in."""
    with _runtime(tmp_path) as runtime:
        _driver, _registry, profile_id, _host = runtime
        by_the_person = seed_row_a_rule_classified(profile_id, operation, description="synthetic row for a rule")
        by_the_agent = seed_row(profile_id, operation, description="synthetic unprocessed row")
        assert _act(runtime, _CLI, _stash(profile_id, by_the_person))
        assert _act(runtime, _MCP, _stash(profile_id, by_the_agent))

        assert _refused_and_nothing_changed(runtime, operation, _restore(profile_id, by_the_person))
        # Archiving it would make an agent the last to set it aside, and so let an agent restore it.
        assert _refused_and_nothing_changed(runtime, operation, _archive(profile_id, by_the_person))

        assert _act(runtime, _MCP, _archive(profile_id, by_the_agent))
        assert _act(runtime, _MCP, _restore(profile_id, by_the_agent))
        assert _act(runtime, _CLI, _restore(profile_id, by_the_person))
        # Active again, the rule's row is an agent's to archive as it was before the person stashed it.
        assert _act(runtime, _MCP, _archive(profile_id, by_the_person))
        assert _act(runtime, _CLI, _restore(profile_id, by_the_person))
        for row in (by_the_person, by_the_agent):
            assert stored_row(profile_id, row, operation).lifecycle_state is TransactionLifecycleState.ACTIVE
