"""CLI component commands submit registered operations and render their public results."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
import typer
import typer.main

from cadrumo.tests.english_locale_fixture import english_locale_fixture
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.commands.registered_operation_deadlines import RegisteredOperationSettlement
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ....adapters.outbound.components.tests.recorded_rows import recorded_absent_row, set_up_row
from ....application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_REMOVE_OPERATION_ID,
    COMPONENTS_SETUP_OPERATION_ID,
    COMPONENTS_STATUS_OPERATION_ID,
    COMPONENTS_VERIFY_OPERATION_ID,
    ProvisionMutationRequest,
    ProvisionOutcome,
    ProvisionPlan,
    ProvisionPlanEntry,
    ProvisionPlanSpace,
    ProvisionReadRequest,
    ProvisionResult,
    ProvisionReviewProjection,
)
from ....application.dependency_contracts import DependencyItemKind
from ....application.dependency_registry import dependency_item_declarations
from ....core.operations import OperationEffect
from ..config import provision_cli

__all__ = ["english_locale_fixture"]
pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context(output_format: str = "json") -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": output_format})


def _plan() -> ProvisionPlan:
    return ProvisionPlan(
        contract_version=3,
        entries=(
            ProvisionPlanEntry(
                item_id="browser",
                download_bytes=100,
                source_hosts=("example.com",),
                destination="playwright-browsers",
                installs_outside_program=False,
                target_version=None,
                parts=(),
            ),
        ),
        known_download_bytes=100,
        has_unknown_size=False,
        installs_outside_program=False,
        space=ProvisionPlanSpace(free_bytes=1000, required_bytes=100, sufficient=True),
    )


@pytest.fixture
def submitted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, dict[str, Any]]]:
    calls: list[tuple[object, dict[str, Any]]] = []
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda _ctx: object())

    def run(_client: object, payload: object, **options: Any) -> RegisteredOperationCompletion[ProvisionResult]:
        calls.append((payload, options))
        definition = options["definition_id"]
        rows = (recorded_absent_row("browser"), recorded_absent_row("local_ai"))
        if definition == COMPONENTS_SETUP_OPERATION_ID:
            review = ProvisionReviewProjection(reviewed_proposal_digest="b" * 64, plan=_plan(), plan_digest="c" * 64)
            handler = options["review"]
            decision = handler.decide(review)
            result = ProvisionResult(
                outcome=ProvisionOutcome.COMPLETED if decision == "apply" else ProvisionOutcome.REJECTED,
                rows=(set_up_row("browser"),) if decision == "apply" else (),
                plan_digest=review.plan_digest,
            )
        elif definition == COMPONENTS_REMOVE_OPERATION_ID:
            result = ProvisionResult(outcome=ProvisionOutcome.REMOVED, rows=rows, items=("browser",))
        else:
            result = ProvisionResult(outcome=ProvisionOutcome.OK, rows=rows, setup_complete=False)
        return RegisteredOperationCompletion(operation_id="a" * 64, projection=result, effect=OperationEffect.NONE)

    monkeypatch.setattr(provision_cli, "run_registered_operation", run)
    return calls


@pytest.mark.parametrize(
    ("name", "definition"),
    [
        ("status", COMPONENTS_STATUS_OPERATION_ID),
        ("probe", COMPONENTS_VERIFY_OPERATION_ID),
        ("verify", COMPONENTS_VERIFY_OPERATION_ID),
    ],
)
def test_status_probe_and_verify_route_and_keep_distinct_exit_rules(
    submitted: list[tuple[object, dict[str, Any]]], capsys: pytest.CaptureFixture[str], name: str, definition: str
) -> None:
    command: Callable[..., None] = getattr(provision_cli, f"provision_{name}")
    if name == "verify":
        with pytest.raises(typer.Exit) as exited:
            command(_context())
        assert exited.value.exit_code == 2
    else:
        command(_context())
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["mode"] == ("quick" if name == "status" else "full")
    assert [row["item_id"] for row in result["items"]] == ["browser", "local_ai"]
    assert result["items"][1]["command"] is None
    payload, options = submitted[0]
    assert payload == ProvisionReadRequest()
    assert options["definition_id"] == definition and options["subject_ref"] == COMPONENTS_OPERATION_SUBJECT
    assert callable(options["on_events"]) is (name != "status")


def test_selected_verify_and_refused_check_preserve_public_failure(
    monkeypatch: pytest.MonkeyPatch, submitted: list[tuple[object, dict[str, Any]]], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit):
        provision_cli.provision_verify(_context(), item="browser")
    assert submitted[0][0] == ProvisionReadRequest(items=(DependencyItemKind.BROWSER,))
    capsys.readouterr()
    monkeypatch.setattr(
        provision_cli,
        "_read",
        lambda *_args, **_kwargs: ProvisionResult(
            outcome=ProvisionOutcome.REFUSED, failure_category=DependencyFailureCategory.BLOCKED_BY_NETWORK
        ),
    )
    with pytest.raises(typer.Exit) as exited:
        provision_cli.provision_probe(_context())
    assert exited.value.exit_code == 2
    assert json.loads(capsys.readouterr().out)["result"]["failure_category"] == "blocked_by_network"


@pytest.mark.parametrize(("yes", "expected"), [(True, "completed"), (False, "rejected")])
def test_setup_uses_browser_only_and_prompts_or_rejects(
    submitted: list[tuple[object, dict[str, Any]]], capsys: pytest.CaptureFixture[str], yes: bool, expected: str
) -> None:
    if yes:
        provision_cli.provision_setup(_context(), yes=True)
    else:
        with pytest.raises(typer.Exit):
            provision_cli.provision_setup(_context(), yes=False)
    output = capsys.readouterr()
    document = json.loads(output.out)["result"]
    assert document["outcome"] == expected and document["approved"] is yes
    payload, options = submitted[0]
    assert payload == ProvisionMutationRequest() and options["definition_id"] == COMPONENTS_SETUP_OPERATION_ID
    assert options["settlement_timeout"] is RegisteredOperationSettlement.UNBOUNDED
    assert options["review"].claim is provision_cli._claim_review
    assert options["review"].present_document is not None


def test_remove_only_submits_after_confirmation(submitted: list[tuple[object, dict[str, Any]]]) -> None:
    with pytest.raises(typer.Exit):
        provision_cli.provision_remove(_context(), "browser")
    assert submitted == []
    provision_cli.provision_remove(_context(), "browser", yes=True)
    assert submitted[0][0] == ProvisionMutationRequest()
    assert submitted[0][1]["definition_id"] == COMPONENTS_REMOVE_OPERATION_ID
    with pytest.raises(typer.BadParameter):
        provision_cli.remove_item("local_ai")


def test_recovery_actions_keep_their_real_command() -> None:
    commands = {
        row.item_id: provision_cli.recovery_command(row.recovery_action_id) for row in dependency_item_declarations()
    }
    assert commands == {"browser": "aeat config provision browser", "local_ai": "aeat config provision status"}


def test_unclassified_read_refusal_is_not_rendered_as_empty_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provision_cli, "bound_profile_client", lambda _ctx: object())
    monkeypatch.setattr(
        provision_cli,
        "run_registered_operation",
        lambda *_args, **_kwargs: RegisteredOperationCompletion(
            operation_id="a" * 64,
            projection=ProvisionResult(outcome=ProvisionOutcome.FAILED),
            effect=OperationEffect.NONE,
        ),
    )
    with pytest.raises(RefusalError) as refused:
        provision_cli.provision_status(_context())
    assert refused.value.reason is RefusalCode.INVALID_FRAME
