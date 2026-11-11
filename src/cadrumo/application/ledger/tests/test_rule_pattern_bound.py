"""A person's pattern cannot stall the worker: trial and apply answer in bounded time, the same matches otherwise."""

from __future__ import annotations

import asyncio
import re
import subprocess
import time
from collections.abc import AsyncGenerator, Coroutine, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import IO, Final, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core import pattern_search
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.classification_rule import RULE_PATTERN_ENTRY_MAX_LENGTH, LedgerClassificationRule
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...operations import profile_guard
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.refusal_evidence import OperationRefusalEvidence
from .. import rule_trial_operation
from ..action_ports import LedgerActionPorts
from ..actions_classification import plan_classification_rules
from ..rule_contracts import (
    LedgerRuleAddExecutionResult,
    LedgerRuleAddRequest,
    LedgerRuleApplyExecutionResult,
    LedgerRuleApplyRequest,
)
from ..rule_operation import (
    LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
    LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
    LedgerRuleAddExecutor,
    LedgerRuleApplyExecutor,
)
from ..rule_remove_operation import (
    LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRuleRemoveExecutor,
    LedgerRuleRemoveProjection,
    LedgerRuleRemoveRequest,
)
from ..rule_repository import LedgerClassificationRuleRepositoryProtocol
from ..rule_results import LEDGER_RULE_VALIDATION_REFUSAL_CODE
from ..rule_trial_operation import (
    LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID,
    LedgerRuleTrialExecutionResult,
    LedgerRuleTrialExecutor,
    LedgerRuleTrialRequest,
)

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE: Final = UUID("5aa00000-0000-4000-8000-0000000000aa")
_CATASTROPHIC: Final = r"(a+)+$"
_STUCK_TEXT: Final = "a" * 27 + "!"
_MOMENT: Final = datetime(_YEAR, 4, 14, 9, 30, tzinfo=UTC)
_MOST_THE_LOOP_MAY_STALL: Final = 0.5
_RESULT_REF: Final = "d" * 64


def _row(
    description: str, *, classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=description,
        booked_date=date(_YEAR, 4, 10),
        value_date=date(_YEAR, 4, 10),
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_MOMENT,
            provider_name="test",
        ),
        raw_fields={},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": classification,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": _MOMENT,
            "modified_at": _MOMENT,
        }
    )


def _rule(pattern: str, priority: int) -> LedgerClassificationRule:
    return LedgerClassificationRule.create(
        description_pattern=pattern,
        classification=BusinessClassification.BUSINESS,
        priority=priority,
        actor="t",
        created_at=_MOMENT,
    )


class _Rules:
    def __init__(self, *rules: LedgerClassificationRule) -> None:
        self._rules: tuple[LedgerClassificationRule, ...] = rules
        self.saved: list[LedgerClassificationRule] = []

    def save(self, payload: LedgerClassificationRule) -> None:
        self.saved.append(payload)

    def list_rules(self) -> tuple[LedgerClassificationRule, ...]:
        return self._rules

    def delete(self, identifier: str) -> bool:
        kept = tuple(rule for rule in self._rules if rule.rule_id != identifier)
        self.deleted = len(kept) != len(self._rules)
        self._rules = kept
        return self.deleted

    deleted = False


class _Movements:
    """Holds rows; any write fails the test, since a refused scan must not reach one."""

    def __init__(self, *rows: Transaction) -> None:
        self.bucket_id = str(_PROFILE)
        self._rows = {row.transaction_id: row for row in rows}

    def load(self) -> TransactionCatalogue:
        return TransactionCatalogue(transactions=self._rows)

    def load_by_ids(self, transaction_ids: tuple[str, ...]) -> SimpleNamespace:
        return SimpleNamespace(transactions={item: self._rows[item] for item in transaction_ids})

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"a refused scan reached {name}")


def _ports(movements: _Movements, operation: object) -> LedgerActionPorts:
    return cast(
        LedgerActionPorts,
        SimpleNamespace(
            operation=operation,
            transaction_repository=movements,
            invoice_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
            work_unit_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
            calculation_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
        ),
    )


@asynccontextmanager
async def _irreversible_section() -> AsyncGenerator[None]:
    yield


def _context(definition_id: str) -> tuple[OperationExecutorContext, list[OperationEffect], list[BaseModel]]:
    effects: list[OperationEffect] = []
    operands: list[BaseModel] = []

    async def phase(_value: str) -> None:
        return None

    async def effect(value: OperationEffect) -> None:
        effects.append(value)

    async def put(operand: BaseModel, *, written_at: datetime) -> str:
        assert written_at.tzinfo is not None
        operands.append(operand)
        return _RESULT_REF

    context = cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=OperationIdentity(
                operation_id="c" * 64,
                definition_id=definition_id,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            authority_operation=cast(PinnedAuthorityOperation, object()),
            events=SimpleNamespace(phase=phase, effect=effect),
            operands=SimpleNamespace(put=put),
            cancellation=SimpleNamespace(irreversible_section=_irreversible_section),
        ),
    )
    return context, effects, operands


class _ChildStarts:
    """When each pattern-search child was launched and when it could first take its request.

    The product's budget begins once a child is ready, since starting one is the
    host's cost; the time a test may hold the product to leaves the same start out.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.windows: list[list[float]] = []
        by_stream: dict[int, list[float]] = {}
        launch = pattern_search._launch

        def launched(neutral_root: Path) -> subprocess.Popen[bytes]:
            window = [time.monotonic()]
            process = launch(neutral_root)
            self.windows.append(window)
            by_stream[id(process.stdout)] = window
            return process

        def stamped(stream: IO[bytes], window: list[float]) -> Iterator[bytes]:
            for line in stream:
                if len(window) == 1:
                    window.append(time.monotonic())
                yield line

        class StampedLines(pattern_search._ChildLines):
            def __init__(self, stream: IO[bytes]) -> None:
                super().__init__(cast(IO[bytes], stamped(stream, by_stream[id(stream)])))

        monkeypatch.setattr(pattern_search, "_launch", launched)
        monkeypatch.setattr(pattern_search, "_ChildLines", StampedLines)

    def starting_seconds(self) -> float:
        """The time during which some child was starting, overlapping starts counted once."""
        total, reached = 0.0, float("-inf")
        for launched, ready in sorted((window[0], window[1]) for window in self.windows if len(window) == 2):
            begin = max(launched, reached)
            if ready > begin:
                total += ready - begin
            reached = max(reached, ready)
        return total


def _run_watching_the_loop[T](
    monkeypatch: pytest.MonkeyPatch, work: Coroutine[object, object, T]
) -> tuple[T, float, float]:
    """Run ``work`` on one loop beside a heartbeat.

    Answer its result, the time it took less the children's start, which the
    product's budget leaves out, and the longest the heartbeat waited.
    """
    starts = _ChildStarts(monkeypatch)

    async def main() -> tuple[T, float, float]:
        longest = 0.0

        async def beat() -> None:
            nonlocal longest
            last = time.monotonic()
            while True:
                await asyncio.sleep(0.01)
                moment = time.monotonic()
                longest = max(longest, moment - last)
                last = moment

        beating = asyncio.create_task(beat())
        started = time.monotonic()
        result = await work
        elapsed = time.monotonic() - started
        beating.cancel()
        return result, elapsed, longest

    result, elapsed, longest = asyncio.run(main())
    assert starts.windows, "no pattern-search child was started, so no budget was measured"
    return result, elapsed - starts.starting_seconds(), longest


def _apply(
    monkeypatch: pytest.MonkeyPatch, rules: _Rules, movements: _Movements, *, dry_run: bool
) -> tuple[str | OperationRefusalEvidence, float, float, list[OperationEffect], list[BaseModel]]:
    context, effects, operands = _context(LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID)
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))

    def ports_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        assert bucket_id == str(_PROFILE)
        return _ports(movements, operation)

    def repository_factory(*, bucket_id: str) -> LedgerClassificationRuleRepositoryProtocol:
        assert bucket_id == str(_PROFILE)
        return rules

    request = OperationRequest[LedgerRuleApplyRequest](
        definition_id=LEDGER_RULE_APPLY_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerRuleApplyRequest(profile_id=_PROFILE, dry_run=dry_run),
    )
    result, elapsed, longest = _run_watching_the_loop(
        monkeypatch, LedgerRuleApplyExecutor(ports_factory, repository_factory).execute(request, context)
    )
    return result, elapsed, longest, effects, operands


@pytest.mark.parametrize("dry_run", [True, False])
def test_an_overrunning_stored_rule_refuses_apply_typed_before_any_write_while_the_loop_runs(
    monkeypatch: pytest.MonkeyPatch, dry_run: bool
) -> None:
    culprit = _rule(_CATASTROPHIC, 2)
    rules = _Rules(_rule("^nada$", 1), culprit)
    result, elapsed, longest, effects, operands = _apply(
        monkeypatch, rules, _Movements(_row(_STUCK_TEXT), _row("OTRA COSA")), dry_run=dry_run
    )

    assert isinstance(result, OperationRefusalEvidence)
    assert result.refusal_code == LEDGER_RULE_VALIDATION_REFUSAL_CODE
    assert effects == [OperationEffect.NONE]
    assert rules.saved == []
    projection = cast(LedgerRuleApplyExecutionResult, operands[0]).projection
    assert projection.outcome == "validation_error"
    assert projection.validation_code == "pattern_overrun"
    assert projection.refused_rule_id == culprit.rule_id
    assert projection.bucket_event_count == 0
    assert elapsed < 8
    assert longest < _MOST_THE_LOOP_MAY_STALL


def test_an_overrunning_trial_is_a_typed_answer_while_the_loop_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    stuck = _row(_STUCK_TEXT)
    context, _, operands = _context(LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID)
    monkeypatch.setattr(rule_trial_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        rule_trial_operation, "transaction_catalogue_repository", lambda *, bucket_id: _Movements(stuck)
    )
    request = OperationRequest[LedgerRuleTrialRequest](
        definition_id=LEDGER_RULE_TRIAL_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerRuleTrialRequest(
            profile_id=_PROFILE, description_pattern=_CATASTROPHIC, transaction_ids=(stuck.transaction_id,)
        ),
    )

    result, elapsed, longest = _run_watching_the_loop(monkeypatch, LedgerRuleTrialExecutor().execute(request, context))

    assert result == _RESULT_REF
    answer = cast(LedgerRuleTrialExecutionResult, operands[0]).result
    assert (answer.outcome, answer.hits, answer.pending) == ("overrun", (), ())
    assert elapsed < 8
    assert longest < _MOST_THE_LOOP_MAY_STALL


def _row_by_row(rows: tuple[Transaction, ...], rules: tuple[LedgerClassificationRule, ...]) -> list[tuple[str, str]]:
    """The first match as stored rules were evaluated before the search moved to a child."""
    answer: list[tuple[str, str]] = []
    for row in rows:
        for rule in rules:
            if re.search(rule.description_pattern, row.raw.description, re.IGNORECASE):
                answer.append((row.transaction_id, rule.rule_id))
                break
    return answer


def test_the_plan_finds_what_row_by_row_matching_found_over_a_table_of_rules() -> None:
    rows = tuple(
        _row(text)
        for text in (
            "RECIBO TELEFONIA ALBOR MOVIL",
            "fibra albor",
            "COMISION MANTENIMIENTO CUENTA",
            "PAGO AEAT MODELO 303",
            "PAGO AEAT MODELO 130",
            "línea\nsegunda ÑANDÚ",
            "TRANSFERENCIA 0412",
            "nada que ver",
        )
    )
    rules = (
        _rule(r"^PAGO AEAT MODELO 303$", 1),
        _rule(r"(?-i:albor)", 2),
        _rule(r"ALBOR", 3),
        _rule(r"modelo\s+\d+", 4),
        _rule(r"ñandú", 5),
        _rule(r"(?P<n>\d)(?P=n)?\d{2}", 6),
        _rule(r"(?m)^segunda", 7),
        _rule(r"comision|mantenimiento", 8),
    )
    plan = plan_classification_rules(
        bucket_id=str(_PROFILE),
        ports=_ports(_Movements(*rows), object()),
        rule_repository=_Rules(*rules),
    )
    expected = _row_by_row(rows, rules)
    assert [(row.transaction_id, row.matched_rule_id) for row in plan.matches] == expected
    assert plan.no_match == len(rows) - len(expected)
    assert plan.rules_evaluated == len(rules)
    assert plan.transactions_scanned == len(rows)
    assert len(expected) == 7


def test_a_stored_rule_past_the_entry_limit_still_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _row("RECIBO ALBOR")
    longer = _rule("albor|" + "x" * RULE_PATTERN_ENTRY_MAX_LENGTH, 1)
    result, _, _, _, operands = _apply(monkeypatch, _Rules(longer), _Movements(row), dry_run=True)
    assert result == _RESULT_REF
    projection = cast(LedgerRuleApplyExecutionResult, operands[0]).projection
    assert [match.matched_rule_id for match in projection.would_match or ()] == [longer.rule_id]


@pytest.mark.parametrize(
    ("pattern", "code"),
    [
        ("a{99999999999}", "invalid_pattern"),
        ("(" * 1000 + ")" * 1000, "invalid_pattern"),
        ("(?L)a", "invalid_pattern"),
        ("x" * (RULE_PATTERN_ENTRY_MAX_LENGTH + 1), "pattern_too_long"),
    ],
)
def test_adding_a_pattern_the_engine_will_not_take_refuses_typed_and_saves_nothing(
    monkeypatch: pytest.MonkeyPatch, pattern: str, code: str
) -> None:
    context, effects, operands = _context(LEDGER_RULE_ADD_OPERATION_DEFINITION_ID)
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    rules = _Rules()

    def repository_factory(*, bucket_id: str) -> LedgerClassificationRuleRepositoryProtocol:
        assert bucket_id == str(_PROFILE)
        return rules

    request = OperationRequest[LedgerRuleAddRequest](
        definition_id=LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerRuleAddRequest(
            profile_id=_PROFILE, description_pattern=pattern, classification=BusinessClassification.BUSINESS
        ),
    )
    result = asyncio.run(LedgerRuleAddExecutor(repository_factory).execute(request, context))

    assert isinstance(result, OperationRefusalEvidence)
    assert effects == [OperationEffect.NONE]
    assert rules.saved == []
    projection = cast(LedgerRuleAddExecutionResult, operands[0]).projection
    assert (projection.outcome, projection.validation_code) == ("validation_error", code)


def test_adding_a_pattern_that_overruns_the_ledger_refuses_typed_and_saves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, effects, operands = _context(LEDGER_RULE_ADD_OPERATION_DEFINITION_ID)
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(
        rule_trial_operation, "transaction_catalogue_repository", lambda *, bucket_id: _Movements(_row(_STUCK_TEXT))
    )
    rules = _Rules()

    request = OperationRequest[LedgerRuleAddRequest](
        definition_id=LEDGER_RULE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerRuleAddRequest(
            profile_id=_PROFILE, description_pattern=_CATASTROPHIC, classification=BusinessClassification.BUSINESS
        ),
    )
    result, elapsed, longest = _run_watching_the_loop(
        monkeypatch, LedgerRuleAddExecutor(lambda *, bucket_id: rules).execute(request, context)
    )

    assert isinstance(result, OperationRefusalEvidence)
    assert effects == [OperationEffect.NONE]
    assert rules.saved == []
    projection = cast(LedgerRuleAddExecutionResult, operands[0]).projection
    assert (projection.outcome, projection.validation_code) == ("validation_error", "pattern_overrun")
    assert elapsed < 8
    assert longest < _MOST_THE_LOOP_MAY_STALL


def _remove(
    monkeypatch: pytest.MonkeyPatch, rules: _Rules, *, rule_id: str, created_at: datetime
) -> tuple[list[OperationEffect], LedgerRuleRemoveProjection]:
    context, effects, operands = _context(LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID)
    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    request = OperationRequest[LedgerRuleRemoveRequest](
        definition_id=LEDGER_RULE_REMOVE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerRuleRemoveRequest(profile_id=_PROFILE, rule_id=rule_id, expected_created_at=created_at),
    )
    asyncio.run(LedgerRuleRemoveExecutor(lambda *, bucket_id: rules).execute(request, context))
    return effects, cast(LedgerRuleRemoveProjection, operands[0])


def test_a_stored_overrunning_rule_can_be_removed_and_apply_then_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    culprit = _rule(_CATASTROPHIC, 2)
    kept = _rule("^nada$", 1)
    rules = _Rules(kept, culprit)

    effects, answer = _remove(monkeypatch, rules, rule_id=culprit.rule_id, created_at=culprit.created_at)

    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert answer.outcome == "removed"
    assert answer.rule is not None and answer.rule.rule_id == culprit.rule_id
    assert rules.list_rules() == (kept,)
    rows = _Movements(_row(_STUCK_TEXT))
    assert (
        plan_classification_rules(
            bucket_id=str(_PROFILE),
            ports=_ports(rows, object()),
            rule_repository=rules,
        ).rules_evaluated
        == 1
    )


def test_removal_is_refused_when_the_rule_was_saved_again_since_it_was_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored = _rule(_CATASTROPHIC, 2)
    rules = _Rules(stored)

    effects, answer = _remove(monkeypatch, rules, rule_id=stored.rule_id, created_at=datetime(1980, 1, 1, tzinfo=UTC))

    assert effects == [OperationEffect.NONE]
    assert answer.outcome == "stale"
    assert rules.list_rules() == (stored,)
    assert not rules.deleted


def test_removing_a_rule_that_is_not_stored_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = _rule("^nada$", 1)
    rules = _Rules(stored)

    effects, answer = _remove(monkeypatch, rules, rule_id="e" * 64, created_at=stored.created_at)

    assert effects == [OperationEffect.NONE]
    assert (answer.outcome, answer.rule) == ("not_found", None)
    assert rules.list_rules() == (stored,)
