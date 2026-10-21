"""The local model items through the real setup operation: licence notices and selection refusals.

The setup operation, its supervisor, journal, encrypted operand store and
review projection run for real, and so do the local model program and local
model items. The model program is a real loopback endpoint speaking the
``/api/version``, ``/api/tags``, ``/api/ps`` and ``/api/pull`` wire shapes. The
browser and the Google account are recording stand-ins that are already set up,
because their own adapters have their own tests. Nothing here downloads, loads
or runs a model.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Generator, Mapping
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ...application.dependency_contracts import (
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyProvisionResult,
    DependencyRecoveryAction,
    DependencySetupEvents,
    DependencyState,
    dependency_plan_digest,
)
from ...application.dependency_registry import (
    BROWSER_DECLARATION,
    DependencyRegistry,
    build_setup_plan,
)
from ...application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DependencySetupOutcome,
    DependencySetupProposal,
    DependencySetupRequest,
    DependencySetupResultV1,
    DependencySetupReviewV2,
    build_dependency_operation_definitions,
    build_dependency_operation_registrations,
)
from ...application.local_reader_setup_items import LocalAiModelPart, LocalAiProgramPart, LocalAiSetupItem
from ...application.operations.interactions import OperationApplyResponse
from ...application.operations.models import OperationIdentity, OperationRequest
from ...application.operations.persistence.journal import OperationPersistedSnapshot, OperationSecureReferenceStore
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.operations.tests.authority_test_support import unread_authority_operation
from ...application.provisioning_host import RuntimeInstaller
from ...core.config import override_settings
from ...core.model_catalogue import ModelRole, ModelSelectionAdvisory, default_model_runtime_id, model_candidate
from ...core.operations import OperationLifecycle
from ...core.storage_taxonomy import StorageCategory
from ...tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TOKEN = "b" * 64
_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_RESEARCH_VISION = "qwen2.5vl:3b"
_LOCAL_AI = "local_ai"


def _pin(model: str) -> str:
    candidate = model_candidate(model)
    assert candidate is not None and candidate.weights_pin is not None
    return candidate.weights_pin.digest


class _Program(SilentLoopbackHandler):
    """The model program: a store of name -> digest that a completed pull adds to."""

    store: ClassVar[dict[str, str]] = {}
    pulls: ClassVar[list[str]] = []

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.13.0"}, status=HTTPStatus.OK)
        elif self.path == "/api/tags":
            rows = [{"name": name, "size": 1, "digest": digest} for name, digest in self.store.items()]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
        elif self.path == "/api/ps":
            write_json_response(self, {"models": []}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        body = read_json_body(self)
        if self.path != "/api/pull":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        name = str(body.get("model"))
        type(self).pulls.append(name)
        type(self).store = {**self.store, name: _pin(name)}
        lines = [{"status": "pulling", "digest": "sha256:aa", "total": 10, "completed": 10}, {"status": "success"}]
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/x-ndjson")
        self.end_headers()
        self.wfile.write("".join(json.dumps(line) + "\n" for line in lines).encode("utf-8"))


@dataclass
class _Ready:
    """An item outside this lane that is already set up."""

    declaration: DependencyItemDeclaration

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        return DependencyProbeReading(
            item_id=self.declaration.item_id, mode=mode, outcome=DependencyProbeOutcome.PRESENT
        )


@dataclass
class _ReadyBrowser(_Ready):
    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        raise AssertionError(f"a ready browser is never planned ({model_name})")

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        raise AssertionError(f"a ready browser is never provisioned ({entry}, {events})")


def _never_install(installer: RuntimeInstaller, executable: Path, timeout_s: float) -> int:
    raise AssertionError(f"the answering program is never installed ({installer}, {executable}, {timeout_s})")


def _never_spawn(executable: Path, environment: Mapping[str, str]) -> int:
    raise AssertionError(f"the answering program is never started ({executable}, {environment})")


def _no_retry(attempt: int, elapsed_s: float) -> float | None:
    del attempt, elapsed_s
    return None


async def _reachable(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
    del hosts
    return None


def _registry() -> OperationRegistry:
    def factory(identity: OperationIdentity, loop: asyncio.AbstractEventLoop) -> DependencyRegistry:
        del identity, loop
        items = (
            _ReadyBrowser(BROWSER_DECLARATION),
            LocalAiSetupItem(
                LocalAiProgramPart(
                    source_hosts=("ollama.com",), run_installer=_never_install, spawn=_never_spawn, which=lambda _: None
                ),
                [
                    LocalAiModelPart(role, source_hosts=("registry.ollama.ai",), retry_delay=_no_retry)
                    for role in ModelRole
                ],
            ),
        )
        return DependencyRegistry(items, reachability=_reachable, hosts_for=lambda group: (f"{group}.example",))

    definitions = build_dependency_operation_definitions(factory)
    return OperationRegistry(
        definitions=definitions, public_registrations=build_dependency_operation_registrations(definitions)
    )


@contextmanager
def _program(root: Path, **settings: object) -> Generator[None]:
    _Program.store = {_TEXT: _pin(_TEXT)}
    _Program.pulls = []
    with (
        serving_loopback(_Program, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_text_model=_TEXT,
            cadrumo_llm_ollama_mapping_model=default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING),
            cadrumo_llm_model_runtime_memory_floor_bytes=1,
            # Admission refuses every load, so a full check never loads a model.
            cadrumo_llm_contention_safety_margin_bytes=1 << 60,
            **{"cadrumo_llm_ollama_vision_model": _RESEARCH_VISION, **settings},
        ),
    ):
        del root
        yield


@asynccontextmanager
async def _supervisor(
    root: Path, registry: OperationRegistry
) -> AsyncGenerator[tuple[OperationSupervisor, OperationSecureReferenceStore]]:
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
    try:
        yield supervisor, operands
    finally:
        await supervisor.shutdown()


async def _to_review(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    request = OperationRequest(
        definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
        subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        payload=DependencySetupRequest(),
    )
    await supervisor.submit(request, operation_id=operation_id)
    await supervisor.start(operation_id)
    deadline = asyncio.get_running_loop().time() + 30
    while asyncio.get_running_loop().time() < deadline:
        snapshot = await supervisor.inspect(operation_id)
        if snapshot.lifecycle in {OperationLifecycle.WAITING_FOR_INTERACTION, OperationLifecycle.TERMINAL}:
            return snapshot
        await asyncio.sleep(0.02)
    raise AssertionError("setup did not reach its review")


async def _apply(supervisor: OperationSupervisor, operation_id: str) -> OperationPersistedSnapshot:
    snapshot = await supervisor.inspect(operation_id)
    pending = snapshot.pending_interaction
    assert pending is not None
    assert pending.baseline_digest is not None and pending.proposed_effect_digest is not None
    await supervisor.respond(
        OperationApplyResponse(
            interaction_id=pending.request.interaction_id,
            operation_id=operation_id,
            revision=pending.request.revision,
            response_token=_TOKEN,
            continuation_digest=pending.request.continuation_digest,
            reviewed_proposal_digest=pending.reviewed_proposal_digest,
            actor_ref="operator:local-model-setup-test",
            responded_at=datetime.now(UTC),
            baseline_digest=pending.baseline_digest,
            proposed_effect_digest=pending.proposed_effect_digest,
        )
    )
    return await supervisor.await_terminal(operation_id)


async def _review(
    registry: OperationRegistry, operands: OperationSecureReferenceStore, snapshot: OperationPersistedSnapshot
) -> tuple[DependencySetupProposal, DependencySetupReviewV2]:
    pending = snapshot.pending_interaction
    assert pending is not None
    proposal = await operands.resolve(pending.reviewed_proposal_digest, DependencySetupProposal)
    projector = registry.lookup_public_registration(DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID).review_projector
    assert projector is not None
    review = projector(proposal, pending.request)
    assert isinstance(review, DependencySetupReviewV2)
    return proposal, review


async def _settled(
    operands: OperationSecureReferenceStore, terminal: OperationPersistedSnapshot
) -> DependencySetupResultV1:
    assert terminal.terminal_receipt is not None and terminal.terminal_receipt.result_ref is not None
    return await operands.resolve(terminal.terminal_receipt.result_ref, DependencySetupResultV1)


@pytest.fixture
def root(tmp_path: Path) -> Generator[Path]:
    with (
        isolated_runtime_profile(tmp_path=tmp_path) as profile,
        override_settings(cadrumo_local_storage_root=tmp_path / "storage"),
    ):
        yield profile.storage_root


def test_a_research_licensed_model_is_reviewed_with_its_notice_and_approving_downloads_exactly_it(root: Path) -> None:
    registry = _registry()

    async def scenario() -> None:
        async with _supervisor(root, registry) as (supervisor, operands):
            waiting = await _to_review(supervisor, "7" * 64)
            proposal, review = await _review(registry, operands, waiting)
            terminal = await _apply(supervisor, "7" * 64)
            result = await _settled(operands, terminal)

        # The ready browser is not planned: the plan is the local AI alone.
        (local_ai,) = review.entries
        assert local_ai.entry.item_id == _LOCAL_AI
        vision = next(part for part in local_ai.entry.parts if part.part_id == ModelRole.VISION_TRANSCRIPTION.value)
        assert vision.target_version == f"{_RESEARCH_VISION}@{_pin(_RESEARCH_VISION)}"
        assert vision.advisories == (ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED,)
        assert ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED in local_ai.entry.advisories
        assert [part.part_id for part in local_ai.parts] == [part.part_id for part in local_ai.entry.parts]
        candidate = model_candidate(_RESEARCH_VISION)
        assert candidate is not None
        assert local_ai.licence_notice is not None
        assert _RESEARCH_VISION in local_ai.licence_notice and candidate.licence.name in local_ai.licence_notice
        # The approval binds the plan that carries the notice, and exactly that plan is carried out.
        assert review.plan_digest == dependency_plan_digest(proposal.plan) == result.plan_digest
        assert result.outcome is DependencySetupOutcome.COMPLETED
        assert {item.item_id: item.failure_category for item in result.items} == {_LOCAL_AI: None}
        assert _Program.pulls == [_RESEARCH_VISION]

    with _program(root):
        asyncio.run(scenario())


def test_switching_away_from_the_noticed_model_after_review_changes_the_plan_and_downloads_nothing(root: Path) -> None:
    registry = _registry()

    async def scenario() -> DependencySetupResultV1:
        async with _supervisor(root, registry) as (supervisor, operands):
            await _to_review(supervisor, "8" * 64)
            with override_settings(cadrumo_llm_ollama_vision_model=_VISION):
                terminal = await _apply(supervisor, "8" * 64)
            return await _settled(operands, terminal)

    with _program(root):
        result = asyncio.run(scenario())
    assert result.outcome is DependencySetupOutcome.PLAN_CHANGED
    assert _Program.pulls == []


def test_a_licence_notice_and_a_model_each_change_the_plan_digest() -> None:
    def entry(target: str, advisories: tuple[ModelSelectionAdvisory, ...]) -> DependencyPlanEntry:
        return DependencyPlanEntry(
            item_id=_LOCAL_AI,
            download_bytes=1,
            source_hosts=("registry.ollama.ai",),
            destination=StorageCategory.OLLAMA_MODELS,
            target_version=target,
            advisories=advisories,
        )

    noticed = build_setup_plan([entry("a@1", (ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED,))], free_bytes=1)
    unnoticed = build_setup_plan([entry("a@1", ())], free_bytes=1)
    other_model = build_setup_plan(
        [entry("b@1", (ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED,))], free_bytes=1
    )

    assert dependency_plan_digest(noticed) != dependency_plan_digest(unnoticed)
    assert dependency_plan_digest(noticed) != dependency_plan_digest(other_model)
    assert dependency_plan_digest(noticed) == dependency_plan_digest(
        build_setup_plan([entry("a@1", (ModelSelectionAdvisory.LICENCE_COMMERCIAL_USE_BARRED,))], free_bytes=9)
    )


def test_an_unsatisfiable_model_selection_is_refused_by_setup_and_names_its_recovery(root: Path) -> None:
    registry = _registry()

    async def scenario() -> DependencySetupResultV1:
        async with _supervisor(root, registry) as (supervisor, operands):
            waiting = await _to_review(supervisor, "9" * 64)
            assert waiting.pending_interaction is not None
            terminal = await _apply(supervisor, "9" * 64)
            return await _settled(operands, terminal)

    # No catalogued model can hold this request window, so every role's selection refuses.
    with _program(root, cadrumo_llm_ollama_num_ctx=1_000_000, cadrumo_llm_ollama_vision_model=_VISION):
        result = asyncio.run(scenario())

    # The local AI stops at its first role whose model cannot be named.
    refused = {item.item_id: item.failure_category for item in result.items}
    assert refused == {_LOCAL_AI: DependencyFailureCategory.UNEXPECTED}
    row = {row.item_id: row for row in result.rows}[_LOCAL_AI]
    assert row.state is DependencyState.FAILED
    assert row.recovery is DependencyRecoveryAction.TRY_AGAIN
    assert row.recovery_action_id == "operator.provision.local_ai"
    assert _Program.pulls == []
