"""Each ``config provision`` leaf submits the registered operation its command row names.

No leaf provisions in the command-line process any more: each one hands a
typed request to the runtime and renders the public result that operation
settles with, so the terminal interface and MCP, which submit the same
operations, get the same decision. These tests run every leaf through its real
handler with the runtime exchange replaced by a recorder that answers with a
result built from real registry rows, and check the operation, the request,
the rendered envelope and the exit code. The operations themselves are proved
against the real supervisor by their owners' suites.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
import typer
import typer.main
from pydantic import BaseModel

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory
from cadrumo_client.contracts.operation_ids import DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID

from ....application.dependency_contracts import (
    DependencyCheckMode,
    DependencyItemKind,
    DependencyPlanEntry,
    DependencyProbeOutcome,
    DependencyProbeReading,
    DependencySetupStep,
    DependencyStatusRow,
    dependency_phase_code,
    dependency_retry_notice_code,
)
from ....application.dependency_registry import (
    build_setup_plan,
    dependency_item_declarations,
    derive_dependency_row,
)
from ....application.dependency_setup_operation import (
    DEPENDENCIES_OPERATION_SUBJECT,
    DependencyPlanEntryViewV1,
    DependencySetupItemResultV1,
    DependencySetupOutcome,
    DependencySetupRequest,
    DependencySetupResultV1,
    DependencySetupReviewV2,
    DependencyStatusRequest,
    DependencyStatusResultV1,
    DependencyVerifyRequest,
    build_dependency_operation_definitions,
    build_dependency_operation_registrations,
)
from ....application.dependency_wording import dependency_row_wording
from ....application.local_reader_contracts import LocalReaderProvisionAction, LocalReaderProvisionRequest
from ....application.local_reader_report import LocalReaderReportRequest
from ....application.operations.frontend_requests import (
    OperationPublicEventPageV1,
    OperationPublicNoticeEventV1,
    OperationPublicPhaseEventV1,
    OperationPublicProgressEventV1,
)
from ....application.operations.models import OperationIdentity
from ....application.operations.persistence.replay import OperationReplayStatus
from ....application.operations.registry import OperationPublicDefinitionContractV1, OperationRegistry
from ....core.config import override_settings
from ....core.model_catalogue import ModelRole
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.storage_taxonomy import StorageCategory
from ..command_operation_table import COMMAND_OPERATION_ROWS
from ..command_specs import COMMAND_GRAPH
from ..config import provision_cli
from .provision_rendering_support import RenderedLeaf, render_leaf

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64
_NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
_INTERNAL_TERMS = ("runtime", "provision", "playwright", "headless", "digest", "ollama")


def _registered_setup_contract() -> OperationPublicDefinitionContractV1:
    def unbuilt(*_arguments: object) -> Any:
        raise AssertionError("the command line never runs an operation itself")

    definitions = build_dependency_operation_definitions(unbuilt)
    registry = OperationRegistry(
        definitions=definitions, public_registrations=build_dependency_operation_registrations(definitions)
    )
    return registry.lookup_public_contract(DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID)


_SETUP_CONTRACT = _registered_setup_contract()


def _rows(outcome: DependencyProbeOutcome, **reading: Any) -> tuple[DependencyStatusRow, ...]:
    """Derive every registry item's row from one shared probe outcome."""
    return tuple(
        derive_dependency_row(
            declaration,
            DependencyProbeReading(
                item_id=declaration.item_id, mode=DependencyCheckMode.QUICK, outcome=outcome, **reading
            ),
        )
        for declaration in dependency_item_declarations()
    )


def _status(rows: tuple[DependencyStatusRow, ...], *, complete: bool) -> DependencyStatusResultV1:
    return DependencyStatusResultV1(
        mode=DependencyCheckMode.QUICK, rows=rows, complete=complete, hardware_limited=False
    )


def _plan() -> tuple[DependencySetupReviewV2, str]:
    entry = DependencyPlanEntry(
        item_id=DependencyItemKind.BROWSER.value,
        download_bytes=300 * 1024 * 1024,
        source_hosts=("cdn.example.org",),
        destination=StorageCategory.PLAYWRIGHT_BROWSERS,
    )
    plan = build_setup_plan([entry], free_bytes=50 * 1024**3)
    from ....application.dependency_contracts import dependency_plan_digest

    digest = dependency_plan_digest(plan)
    review = DependencySetupReviewV2(
        identity=OperationIdentity(
            operation_id=_OPERATION_ID,
            definition_id=DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID,
            subject_ref=DEPENDENCIES_OPERATION_SUBJECT,
        ),
        revision=1,
        plan_digest=digest,
        entries=(DependencyPlanEntryViewV1(entry=entry, destination_path="/storage/components/playwright"),),
        known_download_bytes=plan.known_download_bytes,
        has_unknown_size=plan.has_unknown_size,
        installs_outside_program=plan.installs_outside_program,
        space=plan.space,
        space_sufficient=plan.space.sufficient,
        reviewed_proposal_digest="b" * 64,
    )
    return review, digest


@dataclass
class _Runtime:
    """Records each submission and answers it the way the runtime would, reviewing a setup plan first."""

    status: DependencyStatusResultV1
    setup_outcome: DependencySetupOutcome = DependencySetupOutcome.COMPLETED
    failed_item: str | None = None
    submissions: list[tuple[str, BaseModel, dict[str, Any]]] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)

    def __call__(self, client: object, payload: BaseModel, **options: Any) -> Any:
        from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
        from cadrumo_client.commands.registered_operation_deadlines import operation_settlement_deadline

        del client
        # The client admits only a settlement wait at least the call timeout; check every leaf's pair as it would.
        operation_settlement_deadline(options["timeout"], options.get("settlement_timeout"))
        definition_id = options["definition_id"]
        self.submissions.append((definition_id, payload, options))
        projection: BaseModel
        if definition_id == DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID:
            # The client refuses a review or answer whose schema differs from the registered contract's.
            assert options["review"].review_schema == _SETUP_CONTRACT.review_projection_schema
            assert options["review"].response_schema == _SETUP_CONTRACT.interaction_response_schema
            review, digest = _plan()
            decision = options["review"].decide(review)
            self.decisions.append(decision)
            approved = decision == "apply"
            outcome = self.setup_outcome if approved else DependencySetupOutcome.REJECTED
            items = (
                ()
                if not approved
                else (
                    DependencySetupItemResultV1(
                        item_id=self.failed_item or DependencyItemKind.BROWSER.value,
                        changed=True,
                        failure_category=None
                        if self.failed_item is None
                        else DependencyFailureCategory.DAMAGED_DOWNLOAD,
                    ),
                )
            )
            projection = DependencySetupResultV1(
                outcome=outcome,
                plan_digest=digest,
                items=items,
                space=review.space,
                rows=self.status.rows,
                complete=self.status.complete,
            )
        elif options["result_type"] is DependencyStatusResultV1:
            projection = self.status
        else:
            raise AssertionError(f"unexpected operation {definition_id}")
        return RegisteredOperationCompletion(
            operation_id=_OPERATION_ID,
            projection=projection,
            effect=OperationEffect.NONE,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
        )


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., _Runtime]]:
    def install(**kwargs: Any) -> _Runtime:
        recorder = _Runtime(**kwargs)
        monkeypatch.setattr(provision_cli, "run_registered_operation", recorder)
        monkeypatch.setattr(provision_cli, "bound_profile_client", lambda ctx: object())
        return recorder

    with override_settings(cadrumo_output_language="en"):
        yield install


def _row_operations() -> dict[str, str | None]:
    return {path[2]: operation for path, operation in COMMAND_OPERATION_ROWS if path[:2] == ("config", "provision")}


def _leaf(name: str, capsys: pytest.CaptureFixture[str], output_format: str = "json", **arguments: Any) -> RenderedLeaf:
    handler = getattr(provision_cli, f"provision_{name}")
    return render_leaf(lambda ctx: handler(ctx, **arguments), output_format=output_format, capsys=capsys)


def test_every_provisioning_leaf_submits_an_operation() -> None:
    leaves = {node.path[-1] for node in COMMAND_GRAPH.nodes() if node.path[1:3] == ("config", "provision")}
    rows = _row_operations()

    assert set(rows) == leaves - {"provision"}
    assert all(operation is not None for operation in rows.values()), rows


_STATUS_LEAVES = {
    "status": (DependencyStatusRequest(mode=DependencyCheckMode.QUICK), "ProvisionStatusResult"),
    "probe": (DependencyStatusRequest(mode=DependencyCheckMode.FULL), "ProvisionProbeResult"),
    "verify": (DependencyVerifyRequest(), "ProvisionVerifyResult"),
}


@pytest.mark.parametrize("leaf", sorted(_STATUS_LEAVES))
def test_a_status_leaf_submits_its_row_operation_and_renders_every_registry_row(
    leaf: str, runtime: Callable[..., _Runtime], capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = runtime(status=_status(_rows(DependencyProbeOutcome.PRESENT), complete=True))

    rendered = _leaf(leaf, capsys)

    ((definition_id, payload, options),) = recorder.submissions
    assert definition_id == _row_operations()[leaf]
    assert options["subject_ref"] == DEPENDENCIES_OPERATION_SUBJECT
    assert payload == _STATUS_LEAVES[leaf][0]
    assert rendered.exit_code == 0
    assert rendered.envelope["command"] == f"config.provision.{leaf}"
    items = rendered.result["items"]
    assert isinstance(items, list)
    assert [item["item_id"] for item in items] == [d.item_id for d in dependency_item_declarations()]
    assert all(item["state"] == "ready" and item["command"] is None for item in items)


def test_verify_exits_2_and_names_the_exact_recovery_command_when_an_item_is_absent(
    runtime: Callable[..., _Runtime], capsys: pytest.CaptureFixture[str]
) -> None:
    rows = _rows(DependencyProbeOutcome.ABSENT)
    runtime(status=_status(rows, complete=False))

    rendered = _leaf("verify", capsys, output_format="text")

    assert rendered.exit_code == 2
    for row in rows:
        declaration = next(d for d in dependency_item_declarations() if d.item_id == row.item_id)
        assert dependency_row_wording(row, declaration).sentence in rendered.output
    assert "To fix it, run: aeat config provision browser" in rendered.output
    assert "To fix it, run: aeat config provision pull" in rendered.output
    # The profile's Google sign-in is not setup: no row offers it.
    assert "google" not in rendered.output.lower()
    # The exact commands are the CLI's own spelling; every other word is plain wording.
    lowered = rendered.output.lower().replace("aeat config provision", "").replace("cadrumo-runtime", "")
    assert not [term for term in _INTERNAL_TERMS if term in lowered]


def test_verify_narrows_to_one_item_and_refuses_an_unknown_or_retired_one() -> None:
    assert provision_cli.verify_item_ids("browser") == ("browser",)
    assert provision_cli.verify_item_ids("local_ai") == ("local_ai",)
    assert provision_cli.verify_item_ids(None) is None
    for unknown in ("printer", "model_runtime", "local_model.text_extraction", "google"):
        with pytest.raises(typer.BadParameter):
            provision_cli.verify_item_ids(unknown)


_SETUP_LEAVES: dict[str, tuple[dict[str, Any], DependencySetupRequest]] = {
    "setup": ({}, DependencySetupRequest()),
    "browser": ({}, DependencySetupRequest(item_ids=("browser",))),
    "pull": ({}, DependencySetupRequest(item_ids=("local_ai",))),
    "pull-model": (
        {"model": "example-model:7b"},
        DependencySetupRequest(item_ids=("local_ai",), model_name="example-model:7b"),
    ),
}


@pytest.mark.parametrize("case", sorted(_SETUP_LEAVES))
def test_a_setup_leaf_with_yes_approves_the_printed_plan_and_reports_completion(
    case: str, runtime: Callable[..., _Runtime], capsys: pytest.CaptureFixture[str]
) -> None:
    leaf = case.split("-")[0]
    arguments, expected = _SETUP_LEAVES[case]
    recorder = runtime(status=_status(_rows(DependencyProbeOutcome.PRESENT), complete=True))

    handler = getattr(provision_cli, f"provision_{leaf}")
    capsys.readouterr()
    rendered = render_leaf(lambda ctx: handler(ctx, yes=True, **arguments), output_format="json", capsys=capsys)

    ((definition_id, payload, _options),) = recorder.submissions
    assert definition_id == _row_operations()[leaf] == DEPENDENCIES_SETUP_OPERATION_DEFINITION_ID
    assert payload == expected
    assert recorder.decisions == ["apply"]
    assert rendered.exit_code == 0
    assert rendered.result["outcome"] == "completed"
    assert rendered.result["approved"] is True


def test_setup_without_yes_and_without_a_terminal_rejects_the_plan_and_asks_for_approval(
    runtime: Callable[..., _Runtime], capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = runtime(status=_status(_rows(DependencyProbeOutcome.ABSENT), complete=False))

    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    context = typer.Context(typer.main.get_command(app), obj={"format": "text"})
    capsys.readouterr()
    with pytest.raises(typer.Exit) as stopped:
        provision_cli.provision_setup(context)
    captured = capsys.readouterr()
    output, errors = captured.out, captured.err

    assert recorder.decisions == ["reject"]
    assert stopped.value.exit_code == 2
    assert "This needs your approval. Run the command again with --yes" in output
    assert "Cadrumo will set up:" in errors
    assert "Browser for the tax agency website: 300 MB from cdn.example.org" in errors


def test_setup_exits_2_when_an_item_failed_its_independent_check(
    runtime: Callable[..., _Runtime], capsys: pytest.CaptureFixture[str]
) -> None:
    runtime(status=_status(_rows(DependencyProbeOutcome.PRESENT), complete=True), failed_item="browser")

    rendered = _leaf("browser", capsys, yes=True)

    assert rendered.exit_code == 2
    assert rendered.result["results"] == [
        {"item_id": "browser", "changed": True, "failure_category": "damaged_download", "transferred_bytes": 0}
    ]


def test_the_local_reader_leaves_submit_only_actions_that_download_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted: list[tuple[str, BaseModel]] = []

    def record(client: object, payload: BaseModel, **options: Any) -> Any:
        submitted.append((options["definition_id"], payload))
        raise _StopError

    monkeypatch.setattr(provision_cli, "run_registered_operation", record)
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda ctx: object())
    for leaf, arguments in (
        ("start", {}),
        ("load", {}),
        ("remove", {"role": ModelRole.TEXT_EXTRACTION}),
        ("report", {}),
    ):
        with pytest.raises(_StopError):
            getattr(provision_cli, f"provision_{leaf}")(object(), **arguments)

    rows = _row_operations()
    assert [definition for definition, _ in submitted] == [rows["start"], rows["load"], rows["remove"], rows["report"]]
    actions = [payload.action for _, payload in submitted if isinstance(payload, LocalReaderProvisionRequest)]
    assert actions == [
        LocalReaderProvisionAction.START,
        LocalReaderProvisionAction.LOAD,
        LocalReaderProvisionAction.REMOVE,
    ]
    assert isinstance(submitted[-1][1], LocalReaderReportRequest)


class _StopError(Exception):
    """Ends a recorded submission before any result is rendered."""


def test_every_registry_recovery_action_resolves_to_a_live_command() -> None:
    commands = {
        declaration.item_id: provision_cli.recovery_command(declaration.recovery_action_id)
        for declaration in dependency_item_declarations()
    }

    assert commands == {"browser": "aeat config provision browser", "local_ai": "aeat config provision pull"}


def _page(*events: Any) -> OperationPublicEventPageV1:
    return OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=len(events),
        requested_cursor=0,
        status=OperationReplayStatus.PAGE,
        events=events,
        next_cursor=len(events),
        restart_cursor=None,
    )


def _setup_events() -> OperationPublicEventPageV1:
    phase = dependency_phase_code("browser", DependencySetupStep.DOWNLOAD)
    retry = dependency_retry_notice_code("browser", attempt=2, delay_s=4.0)
    return _page(
        OperationPublicPhaseEventV1(revision=1, sequence=1, timestamp=_NOW, code=phase, phase_code=phase),
        OperationPublicProgressEventV1(
            revision=1,
            sequence=2,
            timestamp=_NOW,
            code="dependencies.setup.progress",
            completed=50 * 1024 * 1024,
            total=100 * 1024 * 1024,
            unit_code="bytes",
            subject_code="browser",
        ),
        OperationPublicNoticeEventV1(revision=1, sequence=3, timestamp=_NOW, code=retry, notice_code=retry),
    )


def test_the_progress_line_names_the_item_step_and_retry_in_plain_words(capsys: pytest.CaptureFixture[str]) -> None:
    with override_settings(cadrumo_output_language="en"):
        line = provision_cli.SetupProgressLine(json_mode=False, interactive=False)
        line.observe(_setup_events())
        line.finish()
    errors = capsys.readouterr().err.splitlines()

    assert errors == [
        "Browser for the tax agency website: downloading",
        "Browser for the tax agency website: Connection problem. Trying again in 4 seconds (attempt 2).",
    ]


def test_json_mode_relays_each_setup_event_as_one_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    line = provision_cli.SetupProgressLine(json_mode=True, interactive=False)
    line.observe(_setup_events())
    documents = [json.loads(text) for text in capsys.readouterr().err.splitlines()]

    assert documents == [
        {"event": "step", "item_id": "browser", "step": "download"},
        {"event": "progress", "item_id": "browser", "completed": 52428800, "total": 104857600},
        {"event": "retry", "item_id": "browser", "attempt": 2, "delay_s": 4},
    ]


def _review_with_licence(notice: str) -> DependencySetupReviewV2:
    review, _digest = _plan()
    (view,) = review.entries
    return review.model_copy(update={"entries": (view.model_copy(update={"licence_notice": notice}),)})


@pytest.mark.parametrize("json_mode", [False, True])
def test_a_licence_notice_is_shown_with_the_plan_before_yes_approves_it(
    json_mode: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    notice = "This model's licence does not permit commercial use."
    review = _review_with_licence(notice)
    with override_settings(cadrumo_output_language="en"):
        handler = provision_cli.setup_review_handler(yes=True, ask=False, json_mode=json_mode)
        decision = handler.decide(review)
    errors = capsys.readouterr().err

    assert decision == "apply"
    if json_mode:
        (line,) = errors.splitlines()
        plan = json.loads(line)
        assert plan["event"] == "plan"
        assert plan["plan_digest"] == review.plan_digest
        assert [entry["licence_notice"] for entry in plan["entries"]] == [notice]
    else:
        lines = errors.splitlines()
        assert lines.index(f"  {notice}") > lines.index("Cadrumo will set up:")


def test_without_yes_the_plan_and_its_licence_notice_are_shown_and_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    notice = "This model's licence does not permit commercial use."
    with override_settings(cadrumo_output_language="en"):
        handler = provision_cli.setup_review_handler(yes=False, ask=False)
        decision = handler.decide(_review_with_licence(notice))

    assert decision == "reject"
    assert f"  {notice}" in capsys.readouterr().err.splitlines()
