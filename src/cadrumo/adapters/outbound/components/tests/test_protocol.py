"""The components role's recorded output decodes into typed lines; anything the protocol does not declare is refused.

The transcripts in ``cadrumo/tests/fixtures/components_role`` are the raw standard output of the real role,
the Cadrumo binary's ``--role components``, run against a staged package and a
throwaway storage root. ``transcripts.json`` records each one's command line,
the input lines the recorder answered with, and the exit status.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from .....application.dependency_contracts import (
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencySetupStep,
    DependencyState,
    DependencyStatusRow,
)
from .....tests.components_role_replay import TRANSCRIPTS, transcript_lines
from ..protocol import (
    CANCEL_LINE,
    COMPONENTS_PLAN_CONTRACT_VERSION,
    MAX_LINE_BYTES,
    ComponentsApprove,
    ComponentsCommand,
    ComponentsContractMismatchError,
    ComponentsDecline,
    ComponentsLine,
    ComponentsNoticeCode,
    ComponentsNoticeLine,
    ComponentsOutcome,
    ComponentsPhaseLine,
    ComponentsProgressLine,
    ComponentsResultLine,
    ComponentsReviewLine,
    ComponentsStartedLine,
    answer_line,
    decode_components_line,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TRANSCRIPTS = TRANSCRIPTS


def _raw(name: str) -> list[bytes]:
    return transcript_lines(name)


def _decoded(name: str) -> list[ComponentsLine]:
    return [decode_components_line(line) for line in _raw(name)]


def _result(name: str) -> ComponentsResultLine:
    last = _decoded(name)[-1]
    assert isinstance(last, ComponentsResultLine)
    return last


def _refused(line: bytes) -> None:
    with pytest.raises(RefusalError) as raised:
        decode_components_line(line)
    assert raised.value.reason is RefusalCode.INVALID_FRAME


def _mutated(name: str, index: int, change: dict[str, Any], *, drop: tuple[str, ...] = ()) -> bytes:
    value = json.loads(_raw(name)[index])
    value.update(change)
    for key in drop:
        del value[key]
    return json.dumps(value).encode("utf-8") + b"\n"


def test_the_recorded_corpus_covers_every_line_kind() -> None:
    kinds = {type(line) for name in _TRANSCRIPTS for line in _decoded(name)}
    assert kinds == {
        ComponentsStartedLine,
        ComponentsPhaseLine,
        ComponentsProgressLine,
        ComponentsNoticeLine,
        ComponentsReviewLine,
        ComponentsResultLine,
    }


@pytest.mark.parametrize("name", sorted(_TRANSCRIPTS))
def test_every_recorded_line_decodes_in_protocol_order_and_respells_exactly(name: str) -> None:
    raw = _raw(name)
    lines = _decoded(name)
    *body, last = lines
    assert isinstance(last, ComponentsResultLine)
    status = _TRANSCRIPTS[name]["exit"]
    if last.outcome is ComponentsOutcome.INVALID_REQUEST:
        assert body == []
        assert status == 64
    else:
        assert isinstance(body[0], ComponentsStartedLine)
        assert body[0].command is last.command
        assert status == (0 if last.outcome.succeeded else 1)
        assert not any(isinstance(line, ComponentsStartedLine | ComponentsResultLine) for line in body[1:])
    for spelled, line in zip(raw, lines, strict=True):
        assert line.model_dump(mode="json", exclude_unset=True) == json.loads(spelled)


def test_a_quick_status_reports_each_item_as_the_surfaces_render_it() -> None:
    result = _result("status_quick")

    assert result.command is ComponentsCommand.STATUS
    assert result.setup_complete is False
    rows = result.status_rows()
    assert all(isinstance(row, DependencyStatusRow) for row in rows)
    assert [(row.kind, row.state, row.recovery) for row in rows] == [
        (DependencyItemKind.BROWSER, DependencyState.ABSENT, DependencyRecoveryAction.SET_UP),
        (DependencyItemKind.LOCAL_AI, DependencyState.ABSENT, DependencyRecoveryAction.SET_UP),
    ]
    assert [row.recovery_action_id for row in rows] == ["operator.provision.browser", "operator.provision.local_ai"]
    assert [row.item_id for row in _result("status_quick_browser").rows] == ["browser"]


def test_a_declined_review_reports_the_plan_it_declined() -> None:
    lines = _decoded("setup_declined")
    (review,) = [line for line in lines if isinstance(line, ComponentsReviewLine)]
    result = _result("setup_declined")

    assert _TRANSCRIPTS["setup_declined"]["answers"] == ['{"type": "decline"}']
    assert result.outcome is ComponentsOutcome.NEEDS_APPROVAL
    assert result.plan_digest == review.plan_digest
    assert result.plan == review.plan
    (entry,) = review.plan.entries
    assert entry.item_id == "browser"
    assert entry.download_bytes == review.plan.known_download_bytes
    assert review.plan.space.required_bytes > review.plan.known_download_bytes
    steps = [line.step for line in lines if isinstance(line, ComponentsPhaseLine)]
    assert steps == [DependencySetupStep.PLAN, DependencySetupStep.PREFLIGHT]


def test_an_approval_of_another_digest_reports_the_current_plan_for_a_new_approval() -> None:
    lines = _decoded("setup_plan_changed")
    (review,) = [line for line in lines if isinstance(line, ComponentsReviewLine)]
    result = _result("setup_plan_changed")

    assert result.outcome is ComponentsOutcome.PLAN_CHANGED
    assert result.plan_digest == review.plan_digest


def test_a_network_that_refuses_the_tunnel_refuses_the_setup_before_any_review() -> None:
    lines = _decoded("setup_refused_blocked_by_network")
    result = _result("setup_refused_blocked_by_network")

    assert not any(isinstance(line, ComponentsReviewLine) for line in lines)
    assert result.outcome is ComponentsOutcome.REFUSED
    assert result.item_id == "browser"
    assert result.failure_category is DependencyFailureCategory.BLOCKED_BY_NETWORK
    assert result.plan is not None


def test_an_unreadable_input_line_is_acknowledged_and_the_review_still_waits() -> None:
    notices = [line for line in _decoded("setup_input_refused") if isinstance(line, ComponentsNoticeLine)]

    assert [notice.notice_code for notice in notices] == [ComponentsNoticeCode.INPUT_REFUSED]
    assert _result("setup_input_refused").outcome is ComponentsOutcome.NEEDS_APPROVAL


def test_a_cancel_line_is_acknowledged_before_the_check_stops() -> None:
    lines = _decoded("verify_cancelled_by_input")

    assert _TRANSCRIPTS["verify_cancelled_by_input"]["answers"] == [CANCEL_LINE.decode().strip()]
    assert any(
        isinstance(line, ComponentsNoticeLine) and line.notice_code is ComponentsNoticeCode.CANCEL_REQUESTED
        for line in lines
    )
    assert _result("verify_cancelled_by_input").outcome is ComponentsOutcome.OK


def test_a_full_check_through_a_refusing_network_reads_failed_with_its_category() -> None:
    (row,) = _result("verify_browser_blocked_by_network").status_rows()

    assert row.state is DependencyState.FAILED
    assert row.failure_category is DependencyFailureCategory.BLOCKED_BY_NETWORK
    assert row.recovery is DependencyRecoveryAction.TRY_AGAIN


def test_an_approved_browser_setup_moves_through_its_steps_with_byte_progress() -> None:
    lines = _decoded("setup_browser_completed")
    (review,) = [line for line in lines if isinstance(line, ComponentsReviewLine)]
    result = _result("setup_browser_completed")

    answers = _TRANSCRIPTS["setup_browser_completed"]["answers"]
    assert [json.loads(answer) for answer in answers] == [{"type": "approve", "plan_digest": review.plan_digest}]
    steps = list(dict.fromkeys(line.step for line in lines if isinstance(line, ComponentsPhaseLine)))
    assert steps[:3] == [DependencySetupStep.PLAN, DependencySetupStep.PREFLIGHT, DependencySetupStep.DOWNLOAD]
    assert DependencySetupStep.VERIFY in steps
    progress = [line for line in lines if isinstance(line, ComponentsProgressLine)]
    assert progress
    assert [line.completed for line in progress] == sorted(line.completed for line in progress)
    assert {line.total for line in progress} == {review.plan.known_download_bytes}
    assert result.outcome is ComponentsOutcome.COMPLETED
    assert result.plan_digest == review.plan_digest
    browser = next(row for row in result.status_rows() if row.item_id == "browser")
    assert browser.state is DependencyState.READY
    assert browser.recovery is None


def test_cancel_and_removal_name_the_items_they_touched() -> None:
    cancel = _result("cancel_nothing_running")
    removal = _result("remove_absent_browser")

    assert (cancel.outcome, cancel.items) == (ComponentsOutcome.NOTHING_RUNNING, ())
    assert (removal.outcome, removal.items) == (ComponentsOutcome.REMOVED, ("browser",))


def test_an_unreadable_command_line_is_one_result_with_no_command() -> None:
    result = _result("invalid_request")

    assert result.command is None
    assert result.rows == ()
    assert result.mode is None


def test_answers_are_the_input_lines_the_role_reads() -> None:
    digest = "ab" * 32

    assert json.loads(answer_line(ComponentsApprove(plan_digest=digest))) == {"type": "approve", "plan_digest": digest}
    assert json.loads(answer_line(ComponentsDecline())) == {"type": "decline"}
    assert answer_line(ComponentsDecline()).endswith(b"\n")
    with pytest.raises(ValueError):
        ComponentsApprove(plan_digest="AB" * 32)


def test_a_line_over_the_bound_or_without_its_newline_is_refused() -> None:
    line = _raw("status_quick")[-1]
    padded = line[:-2] + b" " * (MAX_LINE_BYTES - len(line) + 1) + b"}\n"

    _refused(padded)
    _refused(line[:-1])
    decode_components_line(line[:-2] + b" " * (MAX_LINE_BYTES - len(line)) + b"}\n")


@pytest.mark.parametrize(
    ("name", "index", "change", "drop"),
    [
        ("status_quick", 0, {"type": "hello"}, ()),
        ("status_quick", 0, {"command": "install"}, ()),
        ("status_quick", 1, {"outcome": "maybe"}, ()),
        ("status_quick", 1, {"surprise": True}, ()),
        ("status_quick", 1, {"command": None}, ()),
        ("setup_declined", 1, {"phase_code": "dependencies.setup.local_ai.plan"}, ()),
        ("setup_declined", 3, {"plan_digest": "not-a-digest"}, ()),
        ("setup_declined", 4, {}, ("plan_digest",)),
        ("setup_input_refused", 4, {"notice_code": "retrying"}, ()),
        ("setup_refused_blocked_by_network", 3, {"outcome": "completed"}, ()),
        ("remove_absent_browser", 2, {"items": ["browser", "printer"]}, ()),
    ],
)
def test_a_line_the_protocol_does_not_declare_is_refused(
    name: str, index: int, change: dict[str, Any], drop: tuple[str, ...]
) -> None:
    decode_components_line(_raw(name)[index])
    _refused(_mutated(name, index, change, drop=drop))


def test_a_row_naming_another_items_action_or_a_reason_its_state_lacks_is_refused() -> None:
    result = json.loads(_raw("status_quick")[-1])
    browser = result["rows"][0]

    _refused(_mutated("status_quick", 1, {"rows": [{**browser, "recovery_action_id": "operator.provision.local_ai"}]}))
    _refused(_mutated("status_quick", 1, {"rows": [browser, browser]}))
    contradicting = decode_components_line(
        _mutated("status_quick", 1, {"rows": [{**browser, "failure_category": "offline"}]})
    )
    assert isinstance(contradicting, ComponentsResultLine)
    with pytest.raises(ValueError):
        contradicting.status_rows()


def test_progress_beyond_its_total_is_refused() -> None:
    progress_index = next(
        index
        for index, line in enumerate(_decoded("setup_browser_completed"))
        if isinstance(line, ComponentsProgressLine)
    )
    value = json.loads(_raw("setup_browser_completed")[progress_index])

    _refused(_mutated("setup_browser_completed", progress_index, {"completed": value["total"] + 1}))
    _refused(_mutated("setup_browser_completed", progress_index, {"unit_code": "items"}))


def test_each_model_part_names_its_licence_and_the_program_none() -> None:
    plan = _result("setup_local_ai_refused_host_unreachable").plan

    assert plan is not None
    assert plan.contract_version == COMPONENTS_PLAN_CONTRACT_VERSION
    (entry,) = plan.entries
    program, *models = entry.parts
    assert (program.part_id, program.licence) == ("program", None)
    assert models
    for part in models:
        assert part.licence is not None
        assert part.licence.name
        assert part.licence.name != part.licence.spdx_id


def _line(value: dict[str, Any]) -> bytes:
    return json.dumps(value).encode("utf-8") + b"\n"


def test_a_part_whose_licence_contradicts_its_kind_is_refused() -> None:
    review = json.loads(_raw("setup_local_ai_refused_host_unreachable")[-1])
    entry = review["plan"]["entries"][0]
    program, model, *rest = entry["parts"]
    missing = {key: value for key, value in model.items() if key != "licence"}

    for parts in (
        [{**program, "licence": model["licence"]}, model, *rest],
        [program, {**model, "licence": None}, *rest],
        [program, missing, *rest],
    ):
        _refused(_line({**review, "plan": {**review["plan"], "entries": [{**entry, "parts": parts}]}}))


@pytest.mark.parametrize(("name", "index"), [("setup_declined", 3), ("setup_declined", 4)])
def test_a_plan_of_another_contract_version_belongs_to_another_build(name: str, index: int) -> None:
    value = json.loads(_raw(name)[index])
    value["plan"]["contract_version"] = 1

    with pytest.raises(ComponentsContractMismatchError):
        decode_components_line(_line(value))


def test_a_role_of_another_protocol_version_belongs_to_another_build() -> None:
    value = json.loads(_raw("status_quick")[0])
    value["protocol"] = 2

    with pytest.raises(ComponentsContractMismatchError):
        decode_components_line(_line(value))
