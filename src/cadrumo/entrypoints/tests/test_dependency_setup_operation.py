"""The registered setup operations through the real supervisor, journal and encrypted operand store.

Each item is a recording stand-in for the browser, model and Google adapters,
which own their own tests; what runs for real here is the operation: the plan
review and its digest binding, the per-item order, lock and events, the
independent verification, the failure records and the settled result.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.dependency_activity import DependencyActivityStore
from ...application.dependency_contracts import (
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyProvisionResult,
    DependencySetupEvents,
    DependencySetupStep,
    DependencyState,
    dependency_plan_digest,
    parse_dependency_retry_notice,
)
from ...application.dependency_receipts import dependency_receipts_root
from ...application.dependency_registry import DependencyReachability, DependencyRegistry, dependency_item_declarations
from ...application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID,
    DependencySetupOutcome,
    DependencySetupProposal,
    DependencySetupRequest,
    DependencySetupResultV1,
    DependencySetupReviewV2,
    DependencyStatusRequest,
    DependencyStatusResultV1,
    build_dependency_operation_definitions,
    build_dependency_operation_registrations,
)
from ...application.dependency_wording import dependency_name_key, dependency_sentence_key
from ...application.operations.interactions import OperationApplyResponse, OperationRejectResponse
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.persistence.events import (
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationProgressEvent,
)
from ...application.operations.persistence.journal import OperationPersistedSnapshot, OperationSecureReferenceStore
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.operations.tests.authority_test_support import unread_authority_operation
from ...core.config import override_settings
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.operations import OperationEffect, OperationLifecycle, OperationTerminalCondition

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TOKEN = "a" * 64
_NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
_BROWSER_BYTES = 200 * 1024 * 1024


@dataclass
class _Item:
    """A recording setup item: absent until provisioned, then present unless told to stay broken."""

    declaration: DependencyItemDeclaration
    present: bool = True
    breaks_on_verify: bool = False
    size: int = 1024
    provisions: int = 0
    finished: int = 0
    log: list[str] = field(default_factory=list)

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        outcome = DependencyProbeOutcome.PRESENT if self.present else DependencyProbeOutcome.ABSENT
        return DependencyProbeReading(item_id=self.declaration.item_id, mode=mode, outcome=outcome)


@dataclass
class _Provisioned(_Item):
    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        del model_name
        return DependencyPlanEntry(
            item_id=self.declaration.item_id,
            download_bytes=self.size,
            source_hosts=("example.org",),
            destination=self.declaration.storage_category,
            target_version="1",
        )

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        self.provisions += 1
        self.log.append(entry.item_id)
        await events.step(DependencySetupStep.DOWNLOAD)
        await events.retrying(attempt=2, delay_s=2.0)
        for completed in range(0, self.size + 1, max(1, self.size // 400)):
            await events.transferred(completed=completed, total=self.size)
        await events.transferred(completed=self.size, total=self.size)
        self.present = not self.breaks_on_verify
        return DependencyProvisionResult(item_id=entry.item_id, changed=True, transferred_bytes=self.size)

    async def after_verified(self, entry: DependencyPlanEntry) -> None:
        del entry
        self.finished += 1


def _items(*, absent: tuple[str, ...] = (), broken: tuple[str, ...] = ()) -> dict[str, _Item]:
    items: dict[str, _Item] = {}
    for declaration in dependency_item_declarations():
        size = _BROWSER_BYTES if declaration.item_id == "browser" else 1024
        items[declaration.item_id] = _Provisioned(
            declaration,
            present=declaration.item_id not in absent,
            breaks_on_verify=declaration.item_id in broken,
            size=size,
        )
    return items


async def _reachable(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
    del hosts
    return None


def _registry(items: dict[str, _Item], *, reachability: DependencyReachability = _reachable) -> OperationRegistry:
    def factory(identity: OperationIdentity, loop: asyncio.AbstractEventLoop) -> DependencyRegistry:
        del identity, loop
        return DependencyRegistry(items.values(), reachability=reachability, hosts_for=lambda group: (f"{group}.org",))

    definitions = build_dependency_operation_definitions(factory)
    return OperationRegistry(
        definitions=definitions, public_registrations=build_dependency_operation_registrations(definitions)
    )


@dataclass(frozen=True)
class _Host:
    supervisor: OperationSupervisor
    journal: OperationJournalRepository
    operands: OperationSecureReferenceStore


def _host(root: Path, registry: OperationRegistry) -> _Host:
    journal = OperationJournalRepository(storage_root=root)
    operands = operation_secure_reference_repository()
    supervisor = OperationSupervisor(
        authority_operation=unread_authority_operation(),
        registry=registry,
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operands,
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(minutes=5),
        cleanup_timeout=timedelta(seconds=30),
        response_token_factory=lambda: _TOKEN,
    )
    return _Host(supervisor, journal, operands)


@asynccontextmanager
async def _running(root: Path, registry: OperationRegistry) -> AsyncGenerator[_Host]:
    host = _host(root, registry)
    try:
        yield host
    finally:
        await host.supervisor.shutdown()


def _request[PayloadT: BaseModel](payload: PayloadT, definition_id: str) -> OperationRequest[PayloadT]:
    return OperationRequest(definition_id=definition_id, subject_ref=DEPENDENCIES_OPERATION_SUBJECT, payload=payload)


async def _submit_to_review(supervisor: OperationSupervisor, operation_id: str, payload: DependencySetupRequest):
    await supervisor.submit(_request(payload, DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID), operation_id=operation_id)
    await supervisor.start(operation_id)
    deadline = asyncio.get_running_loop().time() + 10
    while asyncio.get_running_loop().time() < deadline:
        snapshot = await supervisor.inspect(operation_id)
        if snapshot.lifecycle in {OperationLifecycle.WAITING_FOR_INTERACTION, OperationLifecycle.TERMINAL}:
            return snapshot
        await asyncio.sleep(0.01)
    raise AssertionError("setup did not reach its review")


async def _answer(supervisor: OperationSupervisor, operation_id: str, *, apply: bool):
    snapshot = await supervisor.inspect(operation_id)
    pending = snapshot.pending_interaction
    assert pending is not None
    responded_at = datetime.now(UTC)
    if apply:
        assert pending.baseline_digest is not None and pending.proposed_effect_digest is not None
        await supervisor.respond(
            OperationApplyResponse(
                interaction_id=pending.request.interaction_id,
                operation_id=operation_id,
                revision=pending.request.revision,
                response_token=_TOKEN,
                continuation_digest=pending.request.continuation_digest,
                reviewed_proposal_digest=pending.reviewed_proposal_digest,
                actor_ref="operator:dependency-test",
                responded_at=responded_at,
                baseline_digest=pending.baseline_digest,
                proposed_effect_digest=pending.proposed_effect_digest,
            )
        )
    else:
        await supervisor.respond(
            OperationRejectResponse(
                interaction_id=pending.request.interaction_id,
                operation_id=operation_id,
                revision=pending.request.revision,
                response_token=_TOKEN,
                continuation_digest=pending.request.continuation_digest,
                reviewed_proposal_digest=pending.reviewed_proposal_digest,
                actor_ref="operator:dependency-test",
                responded_at=responded_at,
            )
        )
    return await supervisor.await_terminal(operation_id)


async def _result(host: _Host, terminal: OperationPersistedSnapshot) -> DependencySetupResultV1:
    assert terminal.terminal_receipt is not None and terminal.terminal_receipt.result_ref is not None
    return await host.operands.resolve(terminal.terminal_receipt.result_ref, DependencySetupResultV1)


@pytest.fixture
def root(tmp_path: Path):
    with (
        isolated_runtime_profile(tmp_path=tmp_path) as profile,
        override_settings(cadrumo_local_storage_root=tmp_path / "storage"),
    ):
        yield profile.storage_root


def test_setup_asks_once_for_the_plan_then_runs_verifies_and_reports_each_item(root: Path) -> None:
    items = _items(absent=("browser", "local_ai"))
    registry = _registry(items)

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            waiting = await _submit_to_review(supervisor, "3" * 64, DependencySetupRequest())
            pending = waiting.pending_interaction
            assert pending is not None
            proposal = await host.operands.resolve(pending.reviewed_proposal_digest, DependencySetupProposal)
            assert [entry.item_id for entry in proposal.plan.entries] == ["browser", "local_ai"]
            assert pending.proposed_effect_digest == dependency_plan_digest(proposal.plan)
            assert items["browser"].provisions == 0

            terminal = await _answer(supervisor, "3" * 64, apply=True)
            assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
            assert terminal.effect is OperationEffect.UPDATED
            result = await _result(host, terminal)
            history = (await host.journal.read_after("3" * 64, 0, limit=1000)).events

        assert result.outcome is DependencySetupOutcome.COMPLETED
        assert [(item.item_id, item.changed, item.failure_category) for item in result.items] == [
            ("browser", True, None),
            ("local_ai", True, None),
        ]
        assert result.complete is True
        assert items["browser"].finished == 1
        phases = [event.phase_code for event in history if isinstance(event, OperationPhaseEvent)]
        browser_steps = [code for code in phases if code.startswith("dependencies.setup.browser.")]
        assert browser_steps == [
            "dependencies.setup.browser.preflight",
            "dependencies.setup.browser.download",
            "dependencies.setup.browser.verify",
            "dependencies.setup.browser.cleanup",
        ]
        progress = [event for event in history if isinstance(event, OperationProgressEvent)]
        browser_progress = [event for event in progress if event.subject_code == "browser"]
        assert browser_progress and all(event.unit_code == "bytes" for event in browser_progress)
        assert browser_progress[-1].completed == _BROWSER_BYTES
        assert len(browser_progress) < 120, "progress is throttled to whole-percent steps"
        notices = [
            parse_dependency_retry_notice(event.notice_code)
            for event in history
            if isinstance(event, OperationNoticeEvent)
        ]
        assert ("browser", 2, 2) in notices

    asyncio.run(scenario())


def test_a_rejected_plan_downloads_nothing(root: Path) -> None:
    items = _items(absent=("browser",))
    registry = _registry(items)

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            await _submit_to_review(supervisor, "4" * 64, DependencySetupRequest())
            terminal = await _answer(supervisor, "4" * 64, apply=False)
            result = await _result(host, terminal)
        assert result.outcome is DependencySetupOutcome.REJECTED
        assert terminal.effect is OperationEffect.NONE
        assert items["browser"].provisions == 0

    asyncio.run(scenario())


def test_a_plan_that_changed_after_approval_refuses(root: Path) -> None:
    items = _items(absent=("browser",))
    registry = _registry(items)

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            await _submit_to_review(supervisor, "5" * 64, DependencySetupRequest())
            items["browser"].size = _BROWSER_BYTES + 1
            terminal = await _answer(supervisor, "5" * 64, apply=True)
            result = await _result(host, terminal)
        assert result.outcome is DependencySetupOutcome.PLAN_CHANGED
        assert terminal.effect is OperationEffect.NONE
        assert items["browser"].provisions == 0

    asyncio.run(scenario())


def test_an_install_the_full_check_rejects_is_a_failure_and_status_shows_it(root: Path) -> None:
    items = _items(absent=("browser",), broken=("browser",))
    registry = _registry(items)

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            await _submit_to_review(supervisor, "6" * 64, DependencySetupRequest())
            terminal = await _answer(supervisor, "6" * 64, apply=True)
            result = await _result(host, terminal)
            await supervisor.submit(
                _request(DependencyStatusRequest(), DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID), operation_id="7" * 64
            )
            await supervisor.start("7" * 64)
            status_terminal = await supervisor.await_terminal("7" * 64)
            assert (
                status_terminal.terminal_receipt is not None and status_terminal.terminal_receipt.result_ref is not None
            )
            status = await host.operands.resolve(status_terminal.terminal_receipt.result_ref, DependencyStatusResultV1)
        assert terminal.effect is OperationEffect.PARTIAL
        assert result.items[0].failure_category is DependencyFailureCategory.DAMAGED_DOWNLOAD
        assert items["browser"].finished == 0
        browser = next(row for row in status.rows if row.item_id == "browser")
        assert browser.state is DependencyState.FAILED
        assert browser.failure_category is DependencyFailureCategory.DAMAGED_DOWNLOAD
        assert status.complete is False

    asyncio.run(scenario())


def test_an_unreachable_host_fails_only_its_item_before_any_download(root: Path) -> None:
    items = _items(absent=("browser", "local_ai"))

    seen: list[int] = []

    async def first_blocked(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
        del hosts
        seen.append(1)
        return DependencyFailureCategory.BLOCKED_BY_NETWORK if len(seen) == 1 else None

    registry = _registry(items, reachability=first_blocked)

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            await _submit_to_review(supervisor, "8" * 64, DependencySetupRequest())
            terminal = await _answer(supervisor, "8" * 64, apply=True)
            result = await _result(host, terminal)
        assert [(item.item_id, item.failure_category) for item in result.items] == [
            ("browser", DependencyFailureCategory.BLOCKED_BY_NETWORK),
            ("local_ai", None),
        ]
        assert items["browser"].provisions == 0
        assert terminal.effect is OperationEffect.UPDATED

    asyncio.run(scenario())


def test_an_approved_setup_resumed_after_owner_loss_ends_interrupted_without_downloading(root: Path) -> None:
    items = _items(absent=("browser",))
    registry = _registry(items)

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            await _submit_to_review(supervisor, "9" * 64, DependencySetupRequest())
            DependencyActivityStore(dependency_receipts_root()).mark_run("9" * 64)
            terminal = await _answer(supervisor, "9" * 64, apply=True)
            result = await _result(host, terminal)
        assert result.outcome is DependencySetupOutcome.INTERRUPTED
        assert terminal.effect is OperationEffect.UNKNOWN
        assert items["browser"].provisions == 0
        browser = next(row for row in result.rows if row.item_id == "browser")
        assert browser.failure_category is DependencyFailureCategory.INTERRUPTED

    asyncio.run(scenario())


def test_nothing_to_set_up_settles_without_a_review(root: Path) -> None:
    registry = _registry(_items())

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            snapshot = await _submit_to_review(supervisor, "b" * 64, DependencySetupRequest())
            terminal = await supervisor.await_terminal("b" * 64)
            result = await _result(host, terminal)
        assert snapshot.pending_interaction is None
        assert result.outcome is DependencySetupOutcome.NOTHING_TO_DO
        assert result.complete is True

    asyncio.run(scenario())


def test_results_and_the_review_carry_their_words_in_the_requested_language(root: Path) -> None:
    items = _items(absent=("browser",))
    registry = _registry(items)
    declarations = dependency_item_declarations()
    (setup_registration,) = (
        registration
        for registration in build_dependency_operation_registrations(build_dependency_operation_definitions(_unused))
        if registration.contract.definition_id == DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID
    )

    async def scenario() -> None:
        async with _running(root, registry) as host:
            supervisor = host.supervisor
            waiting = await _submit_to_review(supervisor, "c" * 64, DependencySetupRequest(locale=OutputLanguage.ES))
            pending = waiting.pending_interaction
            assert pending is not None and setup_registration.review_projector is not None
            proposal = await host.operands.resolve(pending.reviewed_proposal_digest, DependencySetupProposal)
            review = setup_registration.review_projector(proposal, pending.request)
            terminal = await _answer(supervisor, "c" * 64, apply=True)
            result = await _result(host, terminal)
            await supervisor.submit(
                _request(
                    DependencyStatusRequest(locale=OutputLanguage.CA), DEPENDENCIES_STATUS_OPERATION_DEFINITION_ID
                ),
                operation_id="d" * 64,
            )
            await supervisor.start("d" * 64)
            status_terminal = await supervisor.await_terminal("d" * 64)
            assert (
                status_terminal.terminal_receipt is not None and status_terminal.terminal_receipt.result_ref is not None
            )
            status = await host.operands.resolve(status_terminal.terminal_receipt.result_ref, DependencyStatusResultV1)

        assert isinstance(review, DependencySetupReviewV2) and review.wording is not None
        browser = next(declaration for declaration in declarations if declaration.item_id == "browser")
        spanish_name = tr(dependency_name_key(browser), locale="es")
        assert {name.item_id: name.name for name in review.wording.names}["browser"] == spanish_name
        assert f"operation: {'c' * 64}" in review.wording.details
        assert "hosts: example.org" in review.wording.details
        assert result.wording is not None
        assert [row.item_id for row in result.wording.rows] == [row.item_id for row in result.rows]
        assert {failure.category for failure in result.wording.failures} == set(DependencyFailureCategory)
        assert "{attempt}" in result.wording.retry and "{seconds}" in result.wording.retry
        assert "dependencies.setup.browser.download" in result.wording.details
        assert status.wording is not None
        catalan = {row.item_id: row for row in status.wording.rows}
        ready = next(row for row in status.rows if row.item_id == "browser")
        assert catalan["browser"].sentence == tr(dependency_sentence_key(ready), locale="ca")
        assert catalan["browser"].name == tr(dependency_name_key(browser), locale="ca") != spanish_name

    asyncio.run(scenario())


def _unused(identity: OperationIdentity, loop: asyncio.AbstractEventLoop) -> DependencyRegistry:
    raise AssertionError("the review projector builds no registry")
