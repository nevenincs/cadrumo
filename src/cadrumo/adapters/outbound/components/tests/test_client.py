"""The components role client relays the role's lines, answers its review and refuses a broken exchange.

The role's side is a recorded conversation of the real role, replayed on a real
pipe (:mod:`cadrumo.tests.components_role_replay`), so these cases isolate the client's own logic:
what it writes back, what it relays, and when it refuses. The real role is
driven by ``test_client_drives_the_real_role``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemKind,
    DependencyState,
)
from .....core.package_interpreter import ROLE_IMAGE_OPTION
from .....core.storage_environment import StorageMode, StorageModeEvidence
from .....tests.components_role_replay import ReplayLauncher, transcript_lines
from .. import role_image as role_image_module
from ..client import (
    ComponentsCancellation,
    ComponentsLaunch,
    ComponentsRequest,
    not_in_this_build_result,
    run_components_role,
)
from ..protocol import (
    CANCEL_LINE,
    ComponentsApprove,
    ComponentsCommand,
    ComponentsDecline,
    ComponentsEvent,
    ComponentsNoticeCode,
    ComponentsNoticeLine,
    ComponentsOutcome,
    ComponentsProgressLine,
    ComponentsReviewLine,
)
from ..role_image import DEVELOPMENT_ROLE_IMAGE_VARIABLE, components_role_image

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture
def image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A file standing for the built binary; the replay launcher never runs it."""
    path = tmp_path / "cadrumo.exe"
    path.write_bytes(b"")
    monkeypatch.setenv("CADRUMO_LOCAL_STORAGE_ROOT", str(tmp_path / "root"))
    return path


def _refusal(code: RefusalCode, call: Callable[[], object]) -> None:
    with pytest.raises(RefusalError) as raised:
        call()
    assert raised.value.reason is code


def test_a_review_is_answered_with_exactly_the_reviewed_digest_and_events_are_relayed(image: Path) -> None:
    launcher = ReplayLauncher("setup_browser_completed")
    events: list[ComponentsEvent] = []
    reviews: list[ComponentsReviewLine] = []

    def approve(review: ComponentsReviewLine) -> ComponentsApprove:
        reviews.append(review)
        return ComponentsApprove(plan_digest=review.plan_digest)

    result = run_components_role(
        ComponentsRequest(ComponentsCommand.SETUP, items=(DependencyItemKind.BROWSER,)),
        on_event=events.append,
        review=approve,
        image=image,
        launcher=launcher,
    )

    (review,) = reviews
    assert launcher.launch.written == b'{"type":"approve","plan_digest":"' + review.plan_digest.encode() + b'"}\n'
    assert launcher.launch.arguments == ("--role", "components", "setup", "--item", "browser")
    assert launcher.launch.input_closed and launcher.launch.ended
    assert result.outcome is ComponentsOutcome.COMPLETED
    recorded = [json.loads(line) for line in transcript_lines("setup_browser_completed")]
    relayed = [line for line in recorded if line["type"] in {"phase", "progress", "notice"}]
    assert [event.model_dump(mode="json", exclude_unset=True) for event in events] == relayed
    assert any(isinstance(event, ComponentsProgressLine) for event in events)


def test_without_a_reviewer_the_review_is_declined(image: Path) -> None:
    launcher = ReplayLauncher("setup_declined")

    result = run_components_role(ComponentsRequest(ComponentsCommand.SETUP), image=image, launcher=launcher)

    assert launcher.launch.written == b'{"type":"decline"}\n'
    assert result.outcome is ComponentsOutcome.NEEDS_APPROVAL


def test_the_role_gets_the_storage_root_and_the_proxy_and_nothing_else_of_this_command_line(
    image: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CADRUMO_PROXY_URL", "http://127.0.0.1:3128")
    monkeypatch.setenv("CADRUMO_OUTPUT_LANGUAGE", "hu")
    launcher = ReplayLauncher("status_quick")

    run_components_role(ComponentsRequest(ComponentsCommand.STATUS), image=image, launcher=launcher)

    environment = {name.upper(): value for name, value in launcher.launch.environment.items()}
    assert Path(environment["CADRUMO_LOCAL_STORAGE_ROOT"]) == tmp_path / "root"
    assert environment["CADRUMO_PROXY_URL"] == "http://127.0.0.1:3128"
    assert "CADRUMO_OUTPUT_LANGUAGE" not in environment
    assert DEVELOPMENT_ROLE_IMAGE_VARIABLE not in environment


def test_a_cancellation_sends_the_cancel_line_whenever_it_is_asked(image: Path) -> None:
    early = ComponentsCancellation()
    early.cancel()
    launcher = ReplayLauncher("verify_cancelled_by_input")

    result = run_components_role(
        ComponentsRequest(ComponentsCommand.VERIFY, items=(DependencyItemKind.BROWSER,)),
        cancellation=early,
        image=image,
        launcher=launcher,
    )

    assert launcher.launch.written == CANCEL_LINE
    assert early.requested
    assert result.outcome is ComponentsOutcome.OK


def test_a_setup_that_follows_another_relays_its_events_and_is_never_reviewed(image: Path) -> None:
    launcher = ReplayLauncher("setup_followed_completed")
    events: list[ComponentsEvent] = []
    reviews: list[ComponentsReviewLine] = []

    def decline(review: ComponentsReviewLine) -> ComponentsDecline:
        reviews.append(review)
        return ComponentsDecline()

    result = run_components_role(
        ComponentsRequest(ComponentsCommand.SETUP, items=(DependencyItemKind.BROWSER,)),
        on_event=events.append,
        review=decline,
        image=image,
        launcher=launcher,
    )

    assert reviews == []
    assert launcher.launch.written == b""
    recorded = [json.loads(line) for line in transcript_lines("setup_followed_completed")]
    relayed = [line for line in recorded if line["type"] in {"phase", "progress", "notice"}]
    assert [event.model_dump(mode="json", exclude_unset=True) for event in events] == relayed
    first = events[0]
    assert isinstance(first, ComponentsNoticeLine)
    assert first.notice_code is ComponentsNoticeCode.FOLLOWING
    assert result.outcome is ComponentsOutcome.COMPLETED


def test_a_cancellation_of_a_following_setup_stops_only_the_following(image: Path) -> None:
    cancellation = ComponentsCancellation()
    cancellation.cancel()
    launcher = ReplayLauncher("setup_follow_stopped")

    result = run_components_role(
        ComponentsRequest(ComponentsCommand.SETUP, items=(DependencyItemKind.BROWSER,)),
        cancellation=cancellation,
        image=image,
        launcher=launcher,
    )

    assert launcher.launch.written == CANCEL_LINE
    assert (result.outcome, result.item_id) == (ComponentsOutcome.BUSY, "browser")


def test_a_reviewer_that_fails_leaves_the_role_without_input_and_ended(image: Path) -> None:
    launcher = ReplayLauncher("setup_declined")

    def interrupted(review: ComponentsReviewLine) -> ComponentsDecline:
        del review
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_components_role(
            ComponentsRequest(ComponentsCommand.SETUP), review=interrupted, image=image, launcher=launcher
        )
    assert launcher.launch.input_closed
    assert launcher.launch.ended


@pytest.mark.parametrize(
    ("name", "status"),
    [("setup_declined", 0), ("status_quick", 1), ("invalid_request", 1)],
)
def test_an_exit_status_that_contradicts_the_outcome_is_a_broken_exchange(image: Path, name: str, status: int) -> None:
    command = ComponentsCommand.SETUP if name == "setup_declined" else ComponentsCommand.STATUS
    launcher = ReplayLauncher(name, status=status)

    _refusal(
        RefusalCode.INVALID_FRAME,
        lambda: run_components_role(ComponentsRequest(command), image=image, launcher=launcher),
    )
    assert launcher.launch.ended


def test_output_that_ends_without_a_result_means_the_role_is_unavailable(image: Path) -> None:
    launcher = ReplayLauncher("status_quick", only=1)

    _refusal(
        RefusalCode.UNAVAILABLE,
        lambda: run_components_role(ComponentsRequest(ComponentsCommand.STATUS), image=image, launcher=launcher),
    )
    assert launcher.launch.ended


def test_a_role_that_does_not_answer_in_time_is_ended(image: Path) -> None:
    launcher = ReplayLauncher("status_quick", stall_after=1)

    _refusal(
        RefusalCode.DEADLINE_EXCEEDED,
        lambda: run_components_role(
            ComponentsRequest(ComponentsCommand.STATUS), timeout=0.5, image=image, launcher=launcher
        ),
    )
    assert launcher.launch.input_closed and launcher.launch.ended


@pytest.mark.parametrize(
    ("name", "command", "extra"),
    [
        ("status_quick", ComponentsCommand.PLAN, ()),
        ("status_quick", ComponentsCommand.STATUS, (b'{"command":"status","protocol":1,"type":"started"}\n',)),
        ("setup_declined", ComponentsCommand.STATUS, ()),
    ],
)
def test_a_line_out_of_protocol_order_is_a_broken_exchange(
    image: Path, name: str, command: ComponentsCommand, extra: tuple[bytes, ...]
) -> None:
    launcher = ReplayLauncher(name, extra=extra)

    _refusal(
        RefusalCode.INVALID_FRAME,
        lambda: run_components_role(ComponentsRequest(command), image=image, launcher=launcher),
    )
    assert launcher.launch.ended


def test_a_role_that_cannot_start_is_unavailable(image: Path) -> None:
    def refuse(
        image: Path, arguments: Sequence[str], environment: Mapping[str, str], directory: Path
    ) -> ComponentsLaunch:
        del image, arguments, environment, directory
        raise FileNotFoundError("gone")

    _refusal(
        RefusalCode.UNAVAILABLE,
        lambda: run_components_role(ComponentsRequest(ComponentsCommand.STATUS), image=image, launcher=refuse),
    )


def test_a_build_without_the_role_reads_every_item_as_not_in_this_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DEVELOPMENT_ROLE_IMAGE_VARIABLE, raising=False)
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)

    status = run_components_role(ComponentsRequest(ComponentsCommand.STATUS))
    full = run_components_role(ComponentsRequest(ComponentsCommand.STATUS, full=True))
    checked = run_components_role(ComponentsRequest(ComponentsCommand.VERIFY, items=(DependencyItemKind.LOCAL_AI,)))
    setup = run_components_role(ComponentsRequest(ComponentsCommand.SETUP))
    browser = run_components_role(ComponentsRequest(ComponentsCommand.SETUP, items=(DependencyItemKind.BROWSER,)))
    cancel = run_components_role(ComponentsRequest(ComponentsCommand.CANCEL))
    removal = run_components_role(ComponentsRequest(ComponentsCommand.REMOVE, items=(DependencyItemKind.BROWSER,)))

    rows = status.status_rows()
    assert [row.kind for row in rows] == list(DependencyItemKind)
    assert {(row.state, row.blocked_reason, row.recovery) for row in rows} == {
        (DependencyState.BLOCKED, DependencyBlockedReason.NOT_IN_THIS_BUILD, None)
    }
    assert status.outcome is ComponentsOutcome.OK and status.setup_complete is False
    assert {row.mode for row in full.rows} == {DependencyCheckMode.FULL}
    assert [row.item_id for row in checked.rows] == ["local_ai"]
    assert setup.outcome is ComponentsOutcome.NOTHING_TO_DO
    assert (browser.outcome, browser.item_id, browser.failure_category) == (
        ComponentsOutcome.REFUSED,
        "browser",
        DependencyFailureCategory.NOT_IN_THIS_BUILD,
    )
    assert (cancel.outcome, cancel.items) == (ComponentsOutcome.NOTHING_RUNNING, ())
    assert (removal.outcome, removal.failure_category) == (
        ComponentsOutcome.REFUSED,
        DependencyFailureCategory.NOT_IN_THIS_BUILD,
    )
    assert not_in_this_build_result(ComponentsRequest(ComponentsCommand.PLAN)).plan is None


def test_a_request_spells_the_roles_command_line_and_refuses_one_it_lacks() -> None:
    assert ComponentsRequest(ComponentsCommand.STATUS, full=True).arguments() == ("status", "--full")
    assert ComponentsRequest(
        ComponentsCommand.SETUP, items=(DependencyItemKind.LOCAL_AI,), approve="ab" * 32
    ).arguments() == ("setup", "--item", "local_ai", "--approve", "ab" * 32)
    for invalid in (
        lambda: ComponentsRequest(ComponentsCommand.VERIFY, full=True),
        lambda: ComponentsRequest(ComponentsCommand.STATUS, approve="ab" * 32),
        lambda: ComponentsRequest(ComponentsCommand.CANCEL, items=(DependencyItemKind.BROWSER,)),
        lambda: ComponentsRequest(ComponentsCommand.REMOVE),
        lambda: ComponentsRequest(
            ComponentsCommand.STATUS, items=(DependencyItemKind.BROWSER, DependencyItemKind.BROWSER)
        ),
    ):
        with pytest.raises(ValueError):
            invalid()


def test_a_checkout_runs_the_binary_its_developer_names_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = tmp_path / "cadrumo.exe"
    built.write_bytes(b"")
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)

    assert components_role_image(environ={DEVELOPMENT_ROLE_IMAGE_VARIABLE: str(built)}) == built
    assert components_role_image(environ={DEVELOPMENT_ROLE_IMAGE_VARIABLE: "cadrumo.exe"}) is None
    assert components_role_image(environ={DEVELOPMENT_ROLE_IMAGE_VARIABLE: str(tmp_path / "missing")}) is None
    assert components_role_image(environ={}) is None


def test_a_hosted_interpreter_runs_the_binary_that_hosts_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hosting = tmp_path / "cadrumo.exe"
    hosting.write_bytes(b"")
    monkeypatch.setattr(sys, "_xoptions", {ROLE_IMAGE_OPTION: str(hosting)}, raising=False)

    assert components_role_image(environ={}) == hosting


def _package(root: Path, *, desktop: bool = True) -> Path:
    (root / "data").mkdir(parents=True)
    interpreter = root / "python.exe"
    interpreter.write_bytes(b"")
    (root / "cadrumo.exe").write_bytes(b"")
    layout = {
        "paths": {"executable": "python.exe"},
        "entrypoint_suffix": ".exe",
        "application_images": [
            {"name": "cadrumo", "placement": ".", "desktop": desktop},
            {"name": "cadrumo-manager", "placement": ".", "desktop": False},
        ],
    }
    (root / "data" / "package-manifest.json").write_text(json.dumps({"layout": layout}), encoding="utf-8")
    return interpreter


def test_an_installed_package_runs_the_desktop_image_its_manifest_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    interpreter = _package(tmp_path / "package")
    bare = _package(tmp_path / "no-desktop", desktop=False)
    monkeypatch.setattr(sys, "_xoptions", {}, raising=False)
    monkeypatch.setattr(role_image_module, "storage_mode", lambda: StorageModeEvidence(StorageMode.INSTALLED, None))

    monkeypatch.setattr(sys, "executable", str(interpreter))
    assert components_role_image(environ={DEVELOPMENT_ROLE_IMAGE_VARIABLE: str(interpreter)}) == (
        (tmp_path / "package" / "cadrumo.exe").resolve()
    )
    monkeypatch.setattr(sys, "executable", str(bare))
    assert components_role_image(environ={}) is None
    monkeypatch.setattr(sys, "executable", str(tmp_path / "elsewhere" / "python.exe"))
    assert components_role_image(environ={}) is None


def test_a_role_of_another_plan_contract_reads_as_not_in_this_build_and_is_never_answered(image: Path) -> None:
    lines = transcript_lines("setup_declined")
    review = json.loads(lines[3])
    review["plan"]["contract_version"] = 1
    launcher = ReplayLauncher("setup_declined", only=3, extra=(json.dumps(review).encode("utf-8") + b"\n",))
    reviews: list[ComponentsReviewLine] = []

    def approve(line: ComponentsReviewLine) -> ComponentsApprove:
        reviews.append(line)
        return ComponentsApprove(plan_digest=line.plan_digest)

    result = run_components_role(
        ComponentsRequest(ComponentsCommand.SETUP, items=(DependencyItemKind.BROWSER,)),
        review=approve,
        image=image,
        launcher=launcher,
    )

    assert reviews == []
    assert launcher.launch.written == b""
    assert (result.outcome, result.failure_category) == (
        ComponentsOutcome.REFUSED,
        DependencyFailureCategory.NOT_IN_THIS_BUILD,
    )
    assert launcher.launch.input_closed and launcher.launch.ended
