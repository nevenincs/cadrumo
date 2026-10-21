"""``config provision`` sets things up only through the runtime's registered setup operation.

The setup operation runs here through the real supervisor, journal and
encrypted operand store, with recording stand-ins for the browser, model and
Google items, whose own suites own their adapters. The command line's real
handler submits to it, prints and answers the real REVIEW projection, and
renders the settled result; only the native transport between the two is
replaced, by a bridge that hands each request to the supervisor.

Without a runtime connection the command reports a typed refusal and never
acts in the runtime's place: nothing is downloaded or installed.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import typer
import typer.main
from pydantic import BaseModel

from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.dependency_contracts import (
    DependencyCheckMode,
    DependencyItemDeclaration,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencyProvisionResult,
    DependencySetupEvents,
    DependencySetupStep,
)
from ....application.dependency_registry import DependencyRegistry, dependency_item_declarations
from ....application.dependency_setup_operation import (
    DependencySetupProposal,
    DependencySetupResultV1,
    build_dependency_operation_definitions,
    build_dependency_operation_registrations,
)
from ....application.operations.interactions import OperationApplyResponse, OperationRejectResponse
from ....application.operations.models import OperationIdentity, OperationRequest
from ....application.operations.registry import OperationRegistry
from ....application.operations.supervisor import OperationSupervisor
from ....application.operations.tests.authority_test_support import unread_authority_operation
from ....core.config import override_settings
from ....core.operations import OperationLifecycle
from ..config import provision_cli
from .cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TOKEN = "a" * 64
_OPERATION_ID = "5" * 64


class _Item:
    """A recording setup item: absent until provisioned, then present unless it breaks on its check."""

    def __init__(self, declaration: DependencyItemDeclaration, *, present: bool, breaks: bool = False) -> None:
        self.declaration = declaration
        self.present = present
        self.breaks = breaks
        self.provisions = 0
        self.transferred = 0

    async def check(self, mode: DependencyCheckMode) -> DependencyProbeReading:
        outcome = DependencyProbeOutcome.PRESENT if self.present else DependencyProbeOutcome.ABSENT
        return DependencyProbeReading(item_id=self.declaration.item_id, mode=mode, outcome=outcome)

    async def plan(self, *, model_name: str | None) -> DependencyPlanEntry:
        del model_name
        return DependencyPlanEntry(
            item_id=self.declaration.item_id,
            download_bytes=2048,
            source_hosts=("downloads.example.org",),
            destination=self.declaration.storage_category,
            installs_outside_program=self.declaration.installs_outside_program,
            target_version="1",
        )

    async def provision(self, entry: DependencyPlanEntry, events: DependencySetupEvents) -> DependencyProvisionResult:
        self.provisions += 1
        await events.step(DependencySetupStep.DOWNLOAD)
        await events.transferred(completed=2048, total=2048)
        self.transferred += 2048
        self.present = not self.breaks
        return DependencyProvisionResult(item_id=entry.item_id, changed=True, transferred_bytes=2048)


def _items(*, absent: tuple[str, ...], broken: tuple[str, ...] = ()) -> dict[str, _Item]:
    items: dict[str, _Item] = {}
    for declaration in dependency_item_declarations():
        items[declaration.item_id] = _Item(
            declaration, present=declaration.item_id not in absent, breaks=declaration.item_id in broken
        )
    return items


async def _reachable(hosts: tuple[str, ...]) -> DependencyFailureCategory | None:
    del hosts
    return None


def _registry(items: dict[str, _Item]) -> OperationRegistry:
    def factory(identity: OperationIdentity, loop: asyncio.AbstractEventLoop) -> DependencyRegistry:
        del identity, loop
        return DependencyRegistry(items.values(), reachability=_reachable, hosts_for=lambda group: (f"{group}.org",))

    definitions = build_dependency_operation_definitions(factory)
    return OperationRegistry(
        definitions=definitions, public_registrations=build_dependency_operation_registrations(definitions)
    )


class _RuntimeBridge:
    """Hands the command's setup request to the real supervisor and its review to the command's handler."""

    def __init__(self, root: Path, registry: OperationRegistry) -> None:
        self.root = root
        self.registry = registry

    def __call__(self, client: object, payload: BaseModel, **options: Any) -> RegisteredOperationCompletion[Any]:
        del client
        assert options["definition_id"] == DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID
        return asyncio.run(self._run(payload, options))

    async def _run(self, payload: BaseModel, options: dict[str, Any]) -> RegisteredOperationCompletion[Any]:
        journal = OperationJournalRepository(storage_root=self.root)
        operands = operation_secure_reference_repository()
        supervisor = OperationSupervisor(
            authority_operation=unread_authority_operation(),
            registry=self.registry,
            journal=journal,
            event_stream=journal,
            leases=OperationLeaseFilesystemRepository(storage_root=self.root),
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
            request = OperationRequest(
                definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
                subject_ref=options["subject_ref"],
                payload=payload,
            )
            await supervisor.submit(request, operation_id=_OPERATION_ID)
            await supervisor.start(_OPERATION_ID)
            snapshot = await self._settle(supervisor)
            pending = snapshot.pending_interaction
            if pending is not None:
                proposal = await operands.resolve(pending.reviewed_proposal_digest, DependencySetupProposal)
                registration = next(
                    item
                    for item in self.registry.public_registrations
                    if item.contract.definition_id == DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID
                )
                assert registration.review_projector is not None
                review = registration.review_projector(proposal, pending.request)
                decision = options["review"].decide(review)
                await self._answer(supervisor, pending, apply=decision == "apply")
            terminal = await supervisor.await_terminal(_OPERATION_ID)
            assert terminal.terminal_receipt is not None and terminal.terminal_receipt.result_ref is not None
            result = await operands.resolve(terminal.terminal_receipt.result_ref, DependencySetupResultV1)
            assert terminal.terminal_condition is not None
            return RegisteredOperationCompletion(
                operation_id=_OPERATION_ID,
                projection=result,
                effect=terminal.effect,
                terminal_condition=terminal.terminal_condition,
            )
        finally:
            await supervisor.shutdown()

    @staticmethod
    async def _settle(supervisor: OperationSupervisor) -> Any:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 10
        while loop.time() < deadline:
            snapshot = await supervisor.inspect(_OPERATION_ID)
            if snapshot.lifecycle in {OperationLifecycle.WAITING_FOR_INTERACTION, OperationLifecycle.TERMINAL}:
                return snapshot
            await asyncio.sleep(0.01)
        raise AssertionError("setup did not reach its review")

    @staticmethod
    async def _answer(supervisor: OperationSupervisor, pending: Any, *, apply: bool) -> None:
        responded_at = datetime.now(UTC)
        request = pending.request
        if apply:
            await supervisor.respond(
                OperationApplyResponse(
                    interaction_id=request.interaction_id,
                    operation_id=_OPERATION_ID,
                    revision=request.revision,
                    response_token=_TOKEN,
                    continuation_digest=request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:cli-test",
                    responded_at=responded_at,
                    baseline_digest=pending.baseline_digest,
                    proposed_effect_digest=pending.proposed_effect_digest,
                )
            )
        else:
            await supervisor.respond(
                OperationRejectResponse(
                    interaction_id=request.interaction_id,
                    operation_id=_OPERATION_ID,
                    revision=request.revision,
                    response_token=_TOKEN,
                    continuation_digest=request.continuation_digest,
                    reviewed_proposal_digest=pending.reviewed_proposal_digest,
                    actor_ref="operator:cli-test",
                    responded_at=responded_at,
                )
            )


@pytest.fixture
def root(tmp_path: Path) -> Generator[Path]:
    with (
        isolated_runtime_profile(tmp_path=tmp_path) as profile,
        override_settings(cadrumo_local_storage_root=tmp_path / "storage", cadrumo_output_language="en"),
    ):
        yield profile.storage_root


def _context(output_format: str) -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": output_format})


def _bridge(monkeypatch: pytest.MonkeyPatch, root: Path, items: dict[str, _Item]) -> None:
    monkeypatch.setattr(provision_cli, "run_registered_operation", _RuntimeBridge(root, _registry(items)))
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda ctx: object())


def test_setup_reports_the_item_that_failed_its_check_and_exits_2(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    items = _items(absent=("browser",), broken=("browser",))
    _bridge(monkeypatch, root, items)

    with pytest.raises(typer.Exit) as stopped:
        provision_cli.provision_setup(_context("text"), yes=True)
    captured = capsys.readouterr()

    assert stopped.value.exit_code == 2
    assert items["browser"].provisions == 1
    lines = captured.out.splitlines()
    browser_line = next(line for line in lines if line.startswith("Browser for the tax agency website\t"))
    assert not browser_line.endswith("	Ready."), browser_line
    assert "To fix it, run: aeat config provision browser" in captured.out
    assert "Cadrumo will set up:" in captured.err


def test_setup_json_names_the_failed_item_and_its_category(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    items = _items(absent=("browser",), broken=("browser",))
    _bridge(monkeypatch, root, items)

    with pytest.raises(typer.Exit) as stopped:
        provision_cli.provision_setup(_context("json"), yes=True)
    result = json.loads(capsys.readouterr().out)["result"]

    assert stopped.value.exit_code == 2
    assert result["outcome"] == "completed"
    assert result["approved"] is True
    (failed,) = [item for item in result["results"] if item["failure_category"] is not None]
    assert failed["item_id"] == "browser"
    browser = next(row for row in result["items"] if row["item_id"] == "browser")
    assert browser["state"] == "failed"
    assert browser["command"] == "aeat config provision browser"


def test_the_local_ai_without_yes_and_without_a_terminal_downloads_and_installs_nothing(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    items = _items(absent=("local_ai",))
    _bridge(monkeypatch, root, items)

    with pytest.raises(typer.Exit) as stopped:
        provision_cli.provision_pull(_context("text"))
    captured = capsys.readouterr()

    assert stopped.value.exit_code == 2
    assert "This needs your approval. Run the command again with --yes" in captured.out
    assert "This installs a program on this computer." in captured.err
    assert all(item.provisions == 0 and item.transferred == 0 for item in items.values())


def test_without_a_runtime_connection_the_command_refuses_and_acts_in_its_place_never(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    with override_settings(cadrumo_local_storage_root=storage, cadrumo_output_language="en"):
        result = invoke_cached_cli(["--format", "json", "config", "provision", "setup", "--yes"])

    assert result.exit_code == 2
    assert '"status":"error"' in (result.stdout + (result.stderr or "")).replace(" ", "")
    for downloaded in ("components/playwright", "components/ollama/home", "models/ollama"):
        target = storage / downloaded
        assert not target.exists() or not any(target.iterdir()), downloaded
